import os
import re
import json
import time
import random
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from trend_analyzer import get_daily_trends
from video_maker import create_video
from youtube_uploader import get_authenticated_service, upload_video
from policy_guard import validate_shorts_package
from license_registry import load_manifest

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("shorts_main")

KST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(os.getenv("SHORTS_OUTPUT_DIR", str(BASE_DIR / "outputs")))
DATA_DIR = Path(os.getenv("SHORTS_DATA_DIR", str(BASE_DIR / "data")))
SCRIPTS_DIR = DATA_DIR / "scripts"
REPORTS_DIR = DATA_DIR / "reports"
STATE_PATH = DATA_DIR / "run_state.json"
for d in [OUTPUT_DIR, DATA_DIR, SCRIPTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY 가 필요합니다.")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_TO_TRY = [m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-pro-preview").split(",") if m.strip()]
DEFAULT_PRIVACY_STATUS = os.getenv("SHORTS_DEFAULT_PRIVACY_STATUS", "private").strip()
REQUIRE_HUMAN_REVIEW = os.getenv("SHORTS_REQUIRE_HUMAN_REVIEW", "true").lower() == "true"
BRAND_NAME = os.getenv("SHORTS_BRAND_NAME", "AI 이슈 브리핑")
RUN_SLOT = os.getenv("RUN_SLOT", "auto").strip()

SLOT_STRATEGY = {
    "07": ["economy", "politics", "society"],
    "09": ["politics", "economy", "society"],
    "12": ["society", "economy", "politics"],
    "15": ["economy", "entertainment", "society"],
    "17": ["society", "politics", "entertainment"],
    "19": ["entertainment", "society", "economy"],
    "21": ["entertainment", "politics", "economy"],
}
CATEGORY_LABELS = {
    "politics": "정치",
    "society": "사회",
    "economy": "경제",
    "entertainment": "연예",
    "general": "종합",
}
YOUTUBE_CATEGORY_MAP = {
    "politics": "25",
    "society": "25",
    "economy": "25",
    "entertainment": "24",
    "general": "25",
}
DEFAULT_TAGS = ["뉴스브리핑", "시사이슈", "AI브리핑", "shorts", "유튜브쇼츠"]


def now_kst():
    return datetime.now(KST)


def resolve_run_slot() -> str:
    if RUN_SLOT != "auto":
        return RUN_SLOT.zfill(2)
    hour = now_kst().hour
    slots = sorted(int(k) for k in SLOT_STRATEGY.keys())
    chosen = slots[0]
    for slot in slots:
        if hour >= slot:
            chosen = slot
    return str(chosen).zfill(2)


def load_state() -> Dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": [], "last_run": None}


def save_state(state: Dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def recent_keywords(state: Dict, days: int = 3) -> List[str]:
    cutoff = now_kst() - timedelta(days=days)
    results = []
    for item in state.get("history", []):
        try:
            ts = datetime.fromisoformat(item["run_at"])
        except Exception:
            continue
        if ts >= cutoff:
            results.append(item.get("keyword", ""))
    return results


def call_gemini_with_model(prompt: str, model_name: str) -> str:
    url = GEMINI_BASE_URL.format(model=model_name)
    resp = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=90,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini 호출 실패({model_name}): {resp.status_code} {resp.text[:400]}")
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini 응답에 candidates 없음: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError(f"Gemini 빈 응답: {data}")
    return text


def call_gemini(prompt: str) -> str:
    last_error = None
    for model in MODELS_TO_TRY:
        for attempt in range(1, 4):
            try:
                return call_gemini_with_model(prompt, model)
            except Exception as e:
                last_error = e
                sleep_sec = min(12, attempt * 2 + random.random())
                logger.warning(f"Gemini 실패 | model={model} | attempt={attempt} | error={e}")
                time.sleep(sleep_sec)
    raise RuntimeError(f"모든 Gemini 모델 호출 실패: {last_error}")


def clean_json_block(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```json", "", text).strip()
    text = re.sub(r"^```", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def choose_topic_for_slot(candidates: List[Dict], slot: str, state: Dict) -> Dict:
    preferred = SLOT_STRATEGY.get(slot, ["economy", "society", "politics"])
    recent = [x.strip().lower() for x in recent_keywords(state)]
    ranked = []
    for item in candidates:
        keyword = item.get("keyword", "")
        category = item.get("category", "general")
        penalty = 0
        if keyword.strip().lower() in recent:
            penalty -= 30
        if category in preferred:
            penalty += (len(preferred) - preferred.index(category)) * 10
        ranked.append((item.get("score", 0) + penalty, item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


def generate_shorts_script(topic_item: Dict, slot: str) -> Dict:
    keyword = topic_item["keyword"]
    category = topic_item.get("category", "general")
    headlines = topic_item.get("related_headlines", [])[:4]
    links = topic_item.get("links", [])[:4]
    category_label = CATEGORY_LABELS.get(category, "종합")

    prompt = f"""
너는 한국어 뉴스 쇼츠 제작 에디터다.
목표: 과장/선동/단정 없이 핵심만 전달하는 YouTube Shorts 스크립트를 JSON으로 생성한다.

규칙:
- 루머, 음모론, 과장, 단정적 표현 금지
- '충격', '소름', '무조건', '100% 사실' 같은 클릭베이트 금지
- 실존 인물을 합성한 듯한 지시 금지
- 35~60초 분량 목표
- 각 자막은 1~2문장, 쉬운 한국어, 사실 요약 중심
- 설명문에는 반드시 '자료화면(representative footage)' 문구 포함
- 출력은 오직 JSON 객체 하나

입력 주제: {keyword}
카테고리: {category_label}
참고 헤드라인:
- """ + "\n- ".join(headlines) + f"""
참고 링크:
- """ + "\n- ".join(links) + """

JSON 스키마:
{{
  "title": "45자 이내의 중립적 제목",
  "description": "영상 설명. 자료화면(representative footage) 포함 문구, 핵심 요약 2~3문장, 참고 링크 2개 이상 포함",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "search_keyword": "핵심 검색어",
  "synthetic_realism": false,
  "captions": [
    {{"text": "첫 자막", "duration": 4.5, "background_keyword": "검색 키워드"}},
    {{"text": "둘째 자막", "duration": 4.5, "background_keyword": "검색 키워드"}},
    {{"text": "셋째 자막", "duration": 4.5, "background_keyword": "검색 키워드"}},
    {{"text": "넷째 자막", "duration": 4.5, "background_keyword": "검색 키워드"}},
    {{"text": "다섯째 자막", "duration": 4.5, "background_keyword": "검색 키워드"}},
    {{"text": "여섯째 자막", "duration": 4.5, "background_keyword": "검색 키워드"}}
  ]
}}
"""
    raw = call_gemini(prompt)
    cleaned = clean_json_block(raw)
    data = json.loads(cleaned)
    data.setdefault("tags", [])
    data["tags"] = list(dict.fromkeys(data.get("tags", []) + DEFAULT_TAGS))[:15]
    data["meta"] = {
        "category": category,
        "category_label": category_label,
        "slot": slot,
        "source_links": links,
        "source_headlines": headlines,
    }
    return data


def save_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_once():
    slot = resolve_run_slot()
    logger.info(f"실행 슬롯: {slot}")
    state = load_state()
    trends = get_daily_trends(limit=5)
    if not trends:
        raise RuntimeError("트렌드 후보를 가져오지 못했습니다.")

    topic_item = choose_topic_for_slot(trends, slot, state)
    logger.info(f"선정 주제: {topic_item['keyword']} | category={topic_item.get('category')}")
    script = generate_shorts_script(topic_item, slot)

    timestamp = now_kst().strftime("%Y%m%d_%H%M%S")
    base_name = f"shorts_{timestamp}_{re.sub(r'[^a-zA-Z0-9가-힣]+', '_', topic_item['keyword'])[:30]}"
    script_path = SCRIPTS_DIR / f"{base_name}.json"
    save_json(script_path, script)

    video_path = OUTPUT_DIR / f"{base_name}.mp4"
    actual_video_path = create_video(script, str(video_path))
    manifest_path = str(Path(actual_video_path).with_suffix(".assets.json"))
    manifest = load_manifest(manifest_path)

    policy_result = validate_shorts_package(script, topic_item, manifest)
    report = {
        "run_at": now_kst().isoformat(),
        "slot": slot,
        "topic_item": topic_item,
        "script_path": str(script_path),
        "video_path": actual_video_path,
        "manifest_path": manifest_path,
        "policy_result": policy_result,
    }
    report_path = REPORTS_DIR / f"{base_name}.report.json"
    save_json(report_path, report)

    if not policy_result["approved_for_upload"]:
        raise RuntimeError(f"정책 검사 미통과: {policy_result}")

    if REQUIRE_HUMAN_REVIEW:
        logger.info("SHORTS_REQUIRE_HUMAN_REVIEW=true 이므로 업로드를 생략합니다.")
        upload_result = {"skipped": True, "reason": "human_review_required", "report_path": str(report_path)}
    else:
        youtube = get_authenticated_service()
        upload_result = upload_video(
            youtube=youtube,
            file_path=actual_video_path,
            title=script["title"],
            description=script["description"],
            tags=script.get("tags", []),
            category_id=YOUTUBE_CATEGORY_MAP.get(topic_item.get("category", "general"), "25"),
            privacy_status=DEFAULT_PRIVACY_STATUS,
        )

    report["upload_result"] = upload_result
    save_json(report_path, report)

    state.setdefault("history", []).append({
        "run_at": now_kst().isoformat(),
        "keyword": topic_item["keyword"],
        "category": topic_item.get("category", "general"),
        "video_path": actual_video_path,
        "report_path": str(report_path),
        "uploaded": not upload_result.get("skipped", False),
    })
    state["history"] = state["history"][-50:]
    state["last_run"] = now_kst().isoformat()
    save_state(state)
    return report


if __name__ == "__main__":
    result = run_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))
