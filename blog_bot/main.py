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
BLOG_SITE_NICHE = os.getenv("BLOG_SITE_NICHE", "IT·소프트웨어 실무 활용법, 업무 생산성 도구 가이드, 디지털 라이프 꿀팁 전문 블로그").strip()
BLOG_PERSONA = os.getenv("BLOG_PERSONA", "친절하고 실무적인 IT/테크 가이드 톤").strip()
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
    common_stops = {"2026", "2025", "2024", "가이드", "정리", "비교", "신청", "방법", "조건", "혜택", "총정리", "알아보기", "완벽", "해결", "설정"}
    meaningful_tokens = candidate_tokens - common_stops

    if not meaningful_tokens:
        return False

    for title in existing_titles:
        title_tokens = set(re.findall(r"[A-Za-z0-9가-힣]{2,}", title)) - common_stops
        shared = meaningful_tokens & title_tokens
        if len(shared) >= 2 or (len(meaningful_tokens) > 0 and len(shared) / len(meaningful_tokens) >= 0.6):
            return True

    return False


def choose_topic(exclude_topics: List[str] = None, existing_titles: List[str] = None) -> str:
    """중복 없이 새로운 주제를 선정 (IT/테크 트렌드 우선, 없으면 에버그린 IT 실무 가이드 풀에서 중복 배제)"""
    if exclude_topics is None:
        exclude_topics = []
    if existing_titles is None:
        existing_titles = get_existing_published_titles()

    all_excluded = set(exclude_topics)

    manual = os.getenv("BLOG_TOPIC", "").strip()
    if manual and manual not in all_excluded:
        return manual

    # 1. 실시간 IT/기술 트렌드 RSS에서 수집
    logger.info("실시간 구글 트렌드 및 최신 IT/기술 뉴스 기반 주제 탐색 중...")
    trending_candidates = fetch_trending_topics(max_topics=15)
    for t in trending_candidates:
        if t in all_excluded:
            continue
        if not is_topic_too_similar(t, existing_titles):
            logger.info(f"선정된 실시간 트렌드 주제: {t}")
            return t

    # 2. 애드센스 승인 보증용 에버그린 IT/소프트웨어 실무 가이드 풀 (Non-YMYL 고품질 가이드)
    default_topics = [
        "윈도우 11 정품 인증 오류 코드 0x803F7001 원인 및 단계별 완벽 해결 방법",
        "구글 크롬 브라우저 속도 느려짐 현상 해결하는 7가지 메모리 최적화 설정법",
        "노션(Notion) 데이터베이스 관계형(Relation) 및 롤업(Rollup) 속성 실전 활용 가이드",
        "구글 스프레드시트 VLOOKUP과 XLOOKUP 함수 차이점 및 실무 적용 예제",
        "아이폰 배터리 효율 100% 오래 유지하는 충전 습관과 배터리 절약 설정",
        "윈도우 11 필수 단축키 모음 업무 효율 2배 올려주는 실무 단축키 15선",
        "PDF 파일 용량 줄이기 프로그램 설치 없이 무료로 압축하는 3가지 방법",
        "스마트폰 저장공간 부족할 때 카카오톡 캐시 데이터 정리로 10GB 확보하기",
        "크롬 시크릿 모드 단축키 및 자동 실행 설정 방법 (개인정보 보호 가이드)",
        "노트북 블루스크린(BSOD) 자주 뜰 때 원인 파악 및 단계별 자가 조치 순서",
        "엑셀 중복값 찾기 및 조건부 서식으로 한 번에 제거하는 실무 테크닉",
        "구글 드라이브 파일 공유 링크 권한 설정(뷰어/댓글/편집자) 완벽 정리",
        "윈도우 11 작업표시줄 위치 및 아이콘 검색창 깔끔하게 커스텀하는 법",
        "스마트폰 스팸 문자 및 해외 발신 전화 완벽 차단하는 필수 설정 꿀팁",
        "유튜브 프리미엄 오프라인 저장 다운로드 오류 해결 및 화질 설정 가이드",
        "구글 검색 명령어 모음 원하는 정보만 정확히 찾아내는 고급 검색 테크닉",
        "노션(Notion) 웹 클리퍼 확장 프로그램 설치 및 인터넷 자료 수집 자동화",
        "외장하드 USB 인식 안 될 때 디스크 관리자에서 볼륨 복구하는 방법",
        "카카오톡 대화 내용 백업 및 새 스마트폰으로 복원하는 안전한 절차",
        "크롬 즐겨찾기 북마크 내보내기 및 새 PC로 가져오기 백업 가이드",
        "컴퓨터 부팅 속도 5배 빠르게 만드는 윈도우 시작 프로그램 관리법",
        "스마트폰 사진 컴퓨터로 옮기기 케이블 없이 무선으로 전송하는 방법 4가지",
        "구글 캘린더 네이버 캘린더 연동 및 대한민국 공휴일 일정 동기화 설정",
        "윈도우 화면 캡처 단축키 및 캡처 도구 영역 지정 스크린샷 활용법",
        "엑셀 드롭다운 목록 만들기 실무 서식 데이터 유효성 검사 적용법",
        "구글 계정 2단계 인증 설정 및 분실 대비 백업 복구 코드 발급 방법",
        "아이폰 화면 녹화 소리 안 나올 때 마이크 켜는 법 및 고화질 저장 설정",
        "컴퓨터 인터넷 연결 없음 DNS 서버가 응답하지 않습니다 해결 가이드",
        "크롬 팝업 차단 해제 및 특정 사이트만 허용하는 세부 권한 설정법",
        "윈도우 11 임시 파일 및 캐시 삭제로 C드라이브 용량 확보하는 팁"
    ]

    import random
    random.shuffle(default_topics)

    for topic in default_topics:
        if topic in all_excluded:
            continue
        if not is_topic_too_similar(topic, existing_titles):
            logger.info(f"선정된 기본 풀 주제 (기존 글과 중복 없음): {topic}")
            return topic

    for topic in default_topics:
        if topic not in all_excluded:
            return topic

    return random.choice(default_topics)



def generate_blog_post(topic: str, persona_keywords: str, sources: List[Dict]) -> str:
    source_context = build_source_context(sources)
    current_date = datetime.now().strftime("%Y년 %m월 %d일")
    current_year = datetime.now().year
    
    prompt = f"""
당신은 사용자의 실질적인 IT/소프트웨어 문제를 깔끔하게 해결해 주는 '테크 전문 블로거'이자 '소프트웨어 활용 가이드 전문가'입니다.
당신의 목표는 구글 검색 엔진과 애드센스 심사역이 보았을 때 '실질적인 사용자 문제를 해결하는 고품질의 독창적인 튜토리얼'로 인정받을 수 있는 글을 쓰는 것입니다.
단순히 뉴스를 요약하거나 주식/코인/부동산 등 금융 자문을 흉내 내는 글쓰기는 구글 정책 위반(YMYL)이므로 철저히 배제합니다.

[현재 시점]
현재 날짜는 {current_date}입니다. 연도를 언급해야 할 경우 반드시 {current_year}년을 기준으로 작성하세요.

[블로그 목표]
- Google AdSense '가치 있는 콘텐츠' 심사 통과 (체류 시간 확보, 실용성 극대화)
- 독자가 글을 읽고 화면을 보며 100% 그대로 따라 할 수 있는 친절한 단계별 튜토리얼
- 명확한 원인 분석, 단계별 해결 절차(Step-by-Step), 실전 꿀팁, 비교표, 트러블슈팅 FAQ 포함

[사이트 니치]
{BLOG_SITE_NICHE}

[주제]
{topic}

[작성자 톤]
{persona_keywords}

[참고 자료]
{source_context}

[반드시 지킬 작성 규칙]
1. 분량: 최소 {BLOG_MIN_WORDS}단어(공백 제외 2,500자) 이상으로 매우 상세하고 친절하게 작성하세요.
2. 제목: 첫 줄은 반드시 '# (독자의 검색 의도를 정확히 저격하는 매력적이고 명확한 제목)'으로 시작하세요.
3. 문서 구조:
   - 서론: 해당 문제나 기능이 왜 필요한지, 어떤 상황에서 겪는 문제인지 공감대 형성 및 해결 결과 예고
   - 1단계: 원인 파악 또는 사전 준비 사항 (왜 이런 문제가 발생하는가 / 준비물)
   - 2단계: 핵심 단계별 해결 절차 (Step 1, Step 2, Step 3 형태로 메뉴 위치, 경로, 클릭할 버튼을 명확히 서술)
   - 3단계: 실무 활용 꿀팁 및 옵션 비교표 (|설정 항목|기본값|권장 설정|효과| 등 마크다운 표 필수 1개 이상)
   - 4단계: 자주 발생하는 오류 및 트러블슈팅 FAQ (독자가 가장 많이 막히는 3가지 질문과 명쾌한 답변)
   - 결론: 요약 정리 및 독자 피드백 유도 ("적용해 보시다가 막히는 단계가 있다면 댓글로 남겨주세요")
4. 실전성 강조:
   - "설정 > 시스템 > 디스플레이 경로로 이동합니다"처럼 구체적인 UI 경로와 단축키(예: Win + I, Ctrl + Shift + Esc)를 정확히 명시하세요.
   - 글 중간에 [캡처 화면 설명] 형태로 독자가 어떤 화면을 보아야 하는지 텍스트로 친절히 가이드하세요.
5. 금지 사항:
   - 주식, 가상화폐, 부동산 투자, 대출, 세금 관련 YMYL 금융 자문 내용 절대 포함 금지.
   - "결론적으로 말씀드리자면", "오늘은 ~에 대해 알아보았습니다" 등 AI 상투어 금지.
6. 출처/참고 자료: 글 맨 마지막에 참고할 수 있는 공식 도움말/가이드 링크 형식 섹션(`## 📚 참고 자료`)을 남겨주세요.
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
