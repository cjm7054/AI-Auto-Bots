import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

from dotenv import load_dotenv
from google import genai

from source_collector import collect_google_news_sources, build_source_context
from quality_checker import evaluate_draft
from policy_guard import validate_blog_package
from wordpress_uploader import upload_to_wordpress
from blogger_uploader import upload_to_blogger

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
BLOG_SITE_NICHE = os.getenv("BLOG_SITE_NICHE", "실무형 정보 블로그").strip()
BLOG_PERSONA = os.getenv("BLOG_PERSONA", "신뢰감 있고 실무적인 톤").strip()
BLOG_MIN_WORDS = int(os.getenv("BLOG_MIN_WORDS", "1400"))
BLOG_ALLOW_AUTO_PUBLISH = os.getenv("BLOG_ALLOW_AUTO_PUBLISH", "false").lower() == "true"
BLOG_UPLOAD_TARGETS = [x.strip() for x in os.getenv("BLOG_UPLOAD_TARGETS", "wordpress,blogger").split(",") if x.strip()]
BLOG_PUBLISH_STATUS = os.getenv("BLOG_PUBLISH_STATUS", "draft").strip()


def choose_topic() -> str:
    manual = os.getenv("BLOG_TOPIC", "").strip()
    if manual:
        return manual
    topics = [x.strip() for x in os.getenv("BLOG_TOPICS", "").split(",") if x.strip()]
    if topics:
        idx = datetime.now().day % len(topics)
        return topics[idx]
    return "인공지능 챗봇 최신 동향"


def generate_blog_post(topic: str, persona_keywords: str, sources: List[Dict]) -> str:
    source_context = build_source_context(sources)
    prompt = f"""
당신은 특정 주제에 대해 깊이 있는 통찰과 실제 경험을 바탕으로 글을 작성하는 '전문 칼럼니스트'이자 '블로거'입니다. 
당신의 목표는 구글 검색 엔진과 애드센스 심사역이 보았을 때 '고품질의 독창적인 콘텐츠'로 인정받을 수 있는 글을 쓰는 것입니다.
단순히 정보를 나열하는 양산형 AI 글쓰기를 철저히 배제해야 합니다.

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
6. 출처 및 링크: 제공된 참고 자료를 바탕으로 작성하되, 복사/붙여넣기 하지 말고 본인의 언어로 재해석하세요.
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
    topic = choose_topic()
    logger.info(f"선정 주제: {topic}")
    sources = collect_google_news_sources(topic, max_items=6)
    logger.info(f"수집된 참고 자료 수: {len(sources)}")

    markdown_text = generate_blog_post(topic, BLOG_PERSONA, sources)
    title, content = extract_title_and_content(markdown_text)

    quality = evaluate_draft(title, markdown_text, sources, min_words=BLOG_MIN_WORDS)
    policy = validate_blog_package(title, markdown_text, sources, safe_mode=BLOG_SAFE_MODE)

    draft_path = save_markdown_draft(title, markdown_text)
    report = {
        "topic": topic,
        "title": title,
        "draft_path": draft_path,
        "quality": quality,
        "policy": policy,
        "sources": sources,
        "safe_mode": BLOG_SAFE_MODE,
        "publish_default": "draft",
    }
    report_path = save_report(title, report)

    logger.info(f"초안 저장: {draft_path}")
    logger.info(f"검사 보고서 저장: {report_path}")

    if not policy["approved_for_draft"]:
        logger.error("정책 검사에서 치명적 오류가 발견되어 업로드를 중단합니다.")
        logger.error(policy["errors"])
        return

    final_status = "draft"
    if BLOG_ALLOW_AUTO_PUBLISH and policy["approved_for_auto_publish"] and BLOG_PUBLISH_STATUS == "publish":
        final_status = "publish"

    logger.info(f"최종 업로드 상태: {final_status}")

    if "wordpress" in BLOG_UPLOAD_TARGETS:
        upload_to_wordpress(title, markdown_text, status=final_status)
    if "blogger" in BLOG_UPLOAD_TARGETS:
        upload_to_blogger(title, markdown_text, is_draft=(final_status != "publish"))

    if final_status == "draft":
        from notifier import send_draft_notification
        send_draft_notification(title, draft_path)

    logger.info("블로그 자동화 완료")


if __name__ == "__main__":
    main()
