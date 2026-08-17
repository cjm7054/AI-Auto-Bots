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
DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
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
    return "항만 유지관리 체크리스트"


def generate_blog_post(topic: str, persona_keywords: str, sources: List[Dict]) -> str:
    source_context = build_source_context(sources)
    prompt = f"""
당신은 검색 유입을 노리는 저가치 양산형 작가가 아니라,
사용자에게 실제 도움이 되는 장문 정보성 블로그를 쓰는 전문 편집자입니다.

[블로그 목표]
- Google AdSense 승인 우선
- 사람에게 도움이 되는 글
- 과장/자극/어그로 금지
- 출처 없는 단정 금지
- 자동생성 티 나는 문장 금지
- 의료/법률/투자 조언처럼 보이지 않도록 일반 정보 제공 중심 유지

[사이트 니치]
{BLOG_SITE_NICHE}

[주제]
{topic}

[작성자 톤]
{persona_keywords}

[참고 자료]
{source_context}

[반드시 지킬 작성 규칙]
1. 최종 결과는 순수 Markdown만 출력
2. 문서 첫 줄은 반드시 '# 제목'
3. 분량은 최소 {BLOG_MIN_WORDS}단어 이상
4. 구조는 다음을 포함
   - 서론
   - 핵심 소주제 최소 3개
   - 실무/체크리스트/주의사항
   - FAQ 섹션
   - 참고 자료 섹션
5. 출처가 있는 내용은 참고 자료 섹션에서 링크를 다시 정리
6. '무조건', '반드시 된다', '확실한 수익' 같은 표현 금지
7. 경험한 적 없는 내용을 직접 경험처럼 꾸며 쓰지 말 것
8. AI가 썼다는 메타 문장 금지
9. 한국어로 자연스럽게 작성
10. 승인용 사이트에 어울리게 광고 유도, 과도한 CTA, 낚시성 문구 금지
11. 민감 주제일 경우 아래 문구를 자연스럽게 포함:
   '이 글은 일반적인 정보 제공을 위한 내용이며, 개별 상황에 따라 전문가 확인이 필요합니다.'
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

    logger.info("블로그 자동화 완료")


if __name__ == "__main__":
    main()
