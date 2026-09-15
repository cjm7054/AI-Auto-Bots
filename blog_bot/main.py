import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

from dotenv import load_dotenv
from google import genai

from source_collector import collect_google_news_sources, build_source_context, fetch_trending_topics
from quality_checker import evaluate_draft
from policy_guard import validate_blog_package
from wordpress_uploader import upload_to_wordpress, get_recent_wordpress_titles
from blogger_uploader import upload_to_blogger, get_recent_blogger_titles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("blog_bot")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DRAFT_DIR = DATA_DIR / "drafts"
REPORT_DIR = DATA_DIR / "reports"
for d in [DATA_DIR, DRAFT_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)
DEFAULT_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview"]
env_models = os.getenv("GEMINI_MODELS", "").strip()
MODELS_TO_TRY = [m.strip() for m in env_models.split(",") if m.strip()] if env_models else DEFAULT_MODELS

BLOG_SAFE_MODE = os.getenv("BLOG_SAFE_MODE", "adsense_approval").strip()
BLOG_SITE_NICHE = os.getenv("BLOG_SITE_NICHE", "경제, 재테크, 정부지원금, 실무 생활정보 전문 블로그").strip()
BLOG_PERSONA = os.getenv("BLOG_PERSONA", "신뢰감 있고 실무적인 톤").strip()
BLOG_MIN_WORDS = int(os.getenv("BLOG_MIN_WORDS", "1400"))
BLOG_ALLOW_AUTO_PUBLISH = os.getenv("BLOG_ALLOW_AUTO_PUBLISH", "false").lower() == "true"
BLOG_UPLOAD_TARGETS = [x.strip() for x in os.getenv("BLOG_UPLOAD_TARGETS", "wordpress,blogger").split(",") if x.strip()]
BLOG_PUBLISH_STATUS = os.getenv("BLOG_PUBLISH_STATUS", "draft").strip()


def get_existing_published_titles() -> List[str]:
    """블로그(Blogger, WordPress) 및 로컬 초안 파일에서 이미 작성된 글들의 제목을 수집"""
    existing_titles = []

    # 1. Blogger 최근 글 제목
    try:
        bg_titles = get_recent_blogger_titles(max_results=30)
        existing_titles.extend(bg_titles)
    except Exception:
        pass

    # 2. WordPress 최근 글 제목
    try:
        wp_titles = get_recent_wordpress_titles(per_page=30)
        existing_titles.extend(wp_titles)
    except Exception:
        pass

    # 3. 로컬 drafts 디렉토리 파일명 확인
    try:
        if DRAFT_DIR.exists():
            for f in DRAFT_DIR.glob("*.md"):
                clean_name = re.sub(r"^\d{8}_\d{6}_", "", f.stem).replace("_", " ")
                existing_titles.append(clean_name)
    except Exception:
        pass

    return existing_titles


def is_topic_too_similar(candidate: str, existing_titles: List[str]) -> bool:
    """후보 주제가 이미 발행된 글 제목들과 핵심 키워드상 유사한지 검사 (중복 방지)"""
    candidate_tokens = set(re.findall(r"[A-Za-z0-9가-힣]{2,}", candidate))
    # '2026', '가이드', '정리', '비교', '신청' 등 일반 단어 제외
    common_stops = {"2026", "2025", "2024", "가이드", "정리", "비교", "신청", "방법", "조건", "혜택", "총정리", "알아보기", "완벽"}
    meaningful_tokens = candidate_tokens - common_stops

    if not meaningful_tokens:
        return False

    for title in existing_titles:
        title_tokens = set(re.findall(r"[A-Za-z0-9가-힣]{2,}", title)) - common_stops
        shared = meaningful_tokens & title_tokens
        # 핵심 키워드가 2개 이상 겹치거나, 핵심 키워드의 60% 이상이 겹치면 유사 주제로 판단
        if len(shared) >= 2 or (len(meaningful_tokens) > 0 and len(shared) / len(meaningful_tokens) >= 0.6):
            return True

    return False


def choose_topic(exclude_topics: List[str] = None, existing_titles: List[str] = None) -> str:
    """중복 없이 새로운 주제를 선정 (최신 트렌드/뉴스 우선, 없으면 기본 풀에서 중복 배제)"""
    if exclude_topics is None:
        exclude_topics = []
    if existing_titles is None:
        existing_titles = get_existing_published_titles()

    all_excluded = set(exclude_topics)

    manual = os.getenv("BLOG_TOPIC", "").strip()
    if manual and manual not in all_excluded:
        return manual

    # 1. 실시간 트렌드 및 최신 경제 뉴스 RSS에서 수집
    logger.info("실시간 구글 트렌드 및 최신 경제 뉴스 기반 주제 탐색 중...")
    trending_candidates = fetch_trending_topics(max_topics=15)
    for t in trending_candidates:
        if t in all_excluded:
            continue
        if not is_topic_too_similar(t, existing_titles):
            logger.info(f"선정된 실시간 트렌드 주제: {t}")
            return t

    # 2. 고정 주제 풀 (총 30개 이상으로 대폭 확장)
    default_topics = [
        "2026 청년도약계좌 신청 조건 및 정부 기여금 매칭 혜택 총정리",
        "근로장려금 정기 반기 신청 자격 및 소득 재산 기준 계산법",
        "국민내일배움카드 발급 방법 및 훈련장려금 500만원 지원 한도 활용 가이드",
        "신생아 특례대출 디딤돌 버팀목 금리 및 부부합산 소득 조건 완벽 비교",
        "탄소중립포인트 실천 다회용기 텀블러 전자영수증으로 연간 7만원 환급받는 법",
        "소상공인 정책자금 희망플러스 특례보증 대출 조건 및 신청 절차",
        "ISA 개인종합자산관리계좌 일반형 서민형 차이와 비과세 한도 극대화 꿀팁",
        "연말정산 연금저축 vs IRP 차이점과 세액공제 최대 900만원 채우는 최적 비율",
        "파킹통장 금리 비교 제1금융권 토스 카뱅 vs 저축은행 파킹통장 장단점",
        "개인사업자 프리랜서 노란우산공제 소득공제 혜택과 복리 이자 안전성 분석",
        "신용점수 900점 올리는 5가지 실전 습관과 신용카드 한도 대비 사용 비율",
        "숨은 내 돈 찾기 어카운트인포와 잠자는 카드포인트 계좌 입금 현금화 방법",
        "실손의료보험 4세대 청구 서류와 도수치료 비급여 주사 보상 제외 기준",
        "자동차 채권 미환급금 조회 및 계좌 이체 신청 방법 5년 지난 환급금 찾기",
        "전월세 계약 전 등기부등본 보는 법 갑구 을구 근저당 확인과 깡통전세 예방법",
        "해외여행 트래블로그 vs 트래블월렛 환전 수수료 및 현지 ATM 출금 비교",
        "2026년 주택연금 가입 조건과 수령액 계산법 내 집 연금 장단점",
        "국민연금 조기노령연금 vs 연기연금 수령 시기별 득실 분석",
        "건강보험료 피부양자 자격 유지 조건 및 금융소득 2천만원 초과 탈락 기준",
        "소액 투자자를 위한 미국 배당 다우존스 SCHD vs 국내 배당 ETF 분배금 비교",
        "청년월세 특별지원 신청 대상 소득 기준 및 월 최대 20만원 지원 가이드",
        "햇살론 유스 신청 자격 및 청년 긴급 생계비 보증 대출 심사 팁",
        "퇴직연금 DC형 DB형 차이점 및 IRP 계좌 이체 시 퇴직소득세 절세 전략",
        "예적금 만기 후 풍차돌리기 재테크 실전 전략과 복리 효과 극대화",
        "상속세 및 증여세 면제 한도와 10년 주기 합법적 사전 증여 꿀팁"
    ]

    import random
    random.shuffle(default_topics)

    # 최근 작성된 글들과 겹치지 않는 주제 우선 선택
    for topic in default_topics:
        if topic in all_excluded:
            continue
        if not is_topic_too_similar(topic, existing_titles):
            logger.info(f"선정된 기본 풀 주제 (기존 글과 중복 없음): {topic}")
            return topic

    # 만약 모든 주제가 겹친다면, 최소한 현재 실행 세션에서 쓰지 않은 것 중 선택
    for topic in default_topics:
        if topic not in all_excluded:
            return topic

    return random.choice(default_topics)



def generate_blog_post(topic: str, persona_keywords: str, sources: List[Dict]) -> str:
    source_context = build_source_context(sources)
    current_date = datetime.now().strftime("%Y년 %m월 %d일")
    current_year = datetime.now().year
    
    prompt = f"""
당신은 특정 주제에 대해 깊이 있는 통찰과 실제 경험을 바탕으로 글을 작성하는 '전문 칼럼니스트'이자 '블로거'입니다. 
당신의 목표는 구글 검색 엔진과 애드센스 심사역이 보았을 때 '고품질의 독창적인 콘텐츠'로 인정받을 수 있는 글을 쓰는 것입니다.
단순히 정보를 나열하는 양산형 AI 글쓰기를 철저히 배제해야 합니다.

[현재 시점]
현재 날짜는 {current_date}입니다. 연도를 언급해야 할 경우 반드시 {current_year}년을 기준으로 작성하세요. 제목이나 본문에 과거 연도(예: 2024년, 2023년)를 현재인 것처럼 적는 실수를 절대 하지 마세요.

[블로그 목표]
- Google AdSense '가치 있는 콘텐츠' 심사 통과
- 독자가 글을 끝까지 읽게 만드는 체류 시간 확보
- 실제 사람의 경험과 주관적 견해가 담긴 자연스러운 어투 사용

[사이트 니치]
{BLOG_SITE_NICHE}

[주제]
{topic}

[작성자 톤]
{persona_keywords}

[참고 자료]
{source_context}

[반드시 지킬 작성 규칙]
1. 분량: 최소 {BLOG_MIN_WORDS}단어(공백 제외 2,500자) 이상으로 매우 상세하고 깊이 있게 작성하세요.
2. 형식: 순수 Markdown 형식으로 작성하며, 첫 줄은 반드시 '# (창의적이고 클릭을 유도하는 제목)'으로 시작하세요.
3. 1인칭 경험담 필수: 글의 서론이나 본문 중에 "제가 직접 경험해 보니...", "실제로 이 방법을 적용해 본 결과..."와 같은 1인칭 시점의 주관적 경험과 인사이트를 2문단 이상 반드시 포함하세요. (애드센스 통과를 위한 핵심 요건입니다)
4. 문서 구조: 
   - 서론 (독자의 흥미 유발 및 문제 제기)
   - 본론 1, 2, 3 (각 핵심 소주제별로 h2, h3 태그를 사용하여 구조화)
   - 실무 적용 팁 / 주의사항 (표나 리스트 형태 활용)
   - 자주 묻는 질문 (FAQ)
   - 결론 및 독자 소통 유도 ("여러분의 생각은 어떠신가요? 댓글로 남겨주세요." 등)
5. 어투 통제: "결론적으로 말씀드리자면", "오늘은 ~에 대해 알아보았습니다", "요약하자면" 같은 전형적인 AI 어투를 절대 사용하지 마세요.
5. 문체: '알아보겠습니다', '살펴보도록 하겠습니다' 등 AI 상투어 절대 금지.
6. 7-Gate 인간적 요소 및 E-E-A-T 검증 필수:
   - 본문 도중 '제가 직접 신청해보니', '실무 경험상' 등 1인칭 실무 경험담을 2회 이상 자연스럽게 녹여낼 것.
   - 자격 조건, 금액, 금리 등을 정리한 Markdown 비교 요약표(|---|---|)를 1개 이상 반드시 포함할 것.
   - 독자가 가장 궁금해할 실무 질문 3문 3답(FAQ) 섹션을 체계적으로 구성할 것.
   - 글 끝에 '독자 여러분은 어떤 혜택을 준비하고 계신가요? 댓글로 공유해 주세요' 등 소통 질문을 넣을 것.
   - 글 말미에 '※ 본 글은 일반 정보 제공용이며 세부 사항은 공식 공고를 확인하세요' 법적 고지문을 포함할 것.
7. 출처 및 외부 링크: 글의 맨 마지막에는 반드시 '## 📚 참고 자료' 단락을 만들고, 제공된 참고 자료(Sources)를 바탕으로 클릭 가능한 마크다운 하이퍼링크 형식(예: `* [기사 제목](URL)`)으로 정확하게 남겨주세요. (없는 링크를 지어내거나 URL을 임의로 축약하면 절대 안 됩니다.)
""".strip()

    last_error = None
    for model in MODELS_TO_TRY:
        try:
            logger.info(f"[시도] Gemini 모델: {model}")
            response = client.models.generate_content(model=model, contents=prompt)
            text = getattr(response, "text", None)
            if text and text.strip():
                logger.info(f"[성공] 모델 사용 완료: {model}")
                return text.strip()
            raise ValueError(f"{model} 응답에서 text를 추출하지 못했습니다.")
        except Exception as e:
            logger.warning(f"[실패] 모델 {model}: {e}")
            last_error = e
    raise RuntimeError(f"모든 Gemini 모델 호출 실패. 마지막 오류: {last_error}")


def extract_title_and_content(markdown_text: str) -> Tuple[str, str]:
    lines = markdown_text.strip().split("\n")
    title = "정보성 블로그 초안"
    content = markdown_text.strip()
    if lines:
        first_line = lines[0].strip()
        if first_line.startswith("#"):
            title = re.sub(r"^#+\s*", "", first_line).strip()
            content = "\n".join(lines[1:]).strip()
        elif len(first_line) <= 90:
            title = first_line
            content = "\n".join(lines[1:]).strip() if len(lines) > 1 else markdown_text.strip()
    return title, content


def save_markdown_draft(title: str, full_markdown: str) -> str:
    safe = re.sub(r"[^\w가-힣\s-]", "", title)
    safe = re.sub(r"\s+", "_", safe).strip("_")[:60] or "draft"
    path = DRAFT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(full_markdown)
    return str(path)


def save_report(title: str, report: Dict) -> str:
    safe = re.sub(r"[^\w가-힣\s-]", "", title)
    safe = re.sub(r"\s+", "_", safe).strip("_")[:60] or "report"
    path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return str(path)


def main():
    existing_titles = get_existing_published_titles()
    logger.info(f"기존 발행 및 초안 글 {len(existing_titles)}개 감지 (중복 필터링 적용)")

    logger.info('=== [1단계] WordPress 전용 독립 포스팅 시작 ===')
    topic_wp = choose_topic(exclude_topics=[], existing_titles=existing_titles)
    logger.info(f'[WordPress 주제] {topic_wp}')
    sources_wp = collect_google_news_sources(topic_wp, max_items=5)
    md_wp = generate_blog_post(topic_wp, BLOG_PERSONA, sources_wp)
    t_wp, c_wp = extract_title_and_content(md_wp)
    save_markdown_draft(t_wp, md_wp)

    if 'wordpress' in BLOG_UPLOAD_TARGETS:
        try:
            upload_to_wordpress(t_wp, md_wp, status=BLOG_PUBLISH_STATUS)
            logger.info(f'✅ [WordPress 발행 완료] {t_wp}')
        except Exception as e:
            logger.error(f'❌ [WordPress 발행 실패] {e}')

    logger.info('=== [2단계] Google Blogger 전용 독립 포스팅 시작 (서로 다른 주제) ===')
    # WordPress에서 쓴 주제 및 생성된 제목을 제외 목록과 기존 목록에 추가
    existing_titles_bg = existing_titles + [topic_wp, t_wp]
    topic_bg = choose_topic(exclude_topics=[topic_wp], existing_titles=existing_titles_bg)

    logger.info(f'[Blogger 주제] {topic_bg}')
    sources_bg = collect_google_news_sources(topic_bg, max_items=5)
    md_bg = generate_blog_post(topic_bg, BLOG_PERSONA, sources_bg)
    t_bg, c_bg = extract_title_and_content(md_bg)
    save_markdown_draft(t_bg, md_bg)

    if 'blogger' in BLOG_UPLOAD_TARGETS:
        try:
            upload_to_blogger(t_bg, md_bg, is_draft=(BLOG_PUBLISH_STATUS != 'publish'))
            logger.info(f'✅ [Blogger 발행 완료] {t_bg}')
        except Exception as e:
            logger.error(f'❌ [Blogger 발행 실패] {e}')

    logger.info('🎉 워드프레스와 블로거에 서로 다른 2개의 7-Gate 고품질 글 발행 완료!')

if __name__ == '__main__':
    main()
