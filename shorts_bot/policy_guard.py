import re
from typing import Dict, List

BANNED_PATTERNS = [
    r"확실히\s*범인", r"무조건\s*사실", r"100%\s*사실", r"주가\s*무조건", r"대박\s*보장",
    r"충격\s*실화", r"폭로", r"루머", r"음모론", r"자살", r"잔혹", r"참수", r"성인", r"혐오",
]
CLICKBAIT_TITLE_PATTERNS = [r"충격", r"안\s*보면\s*손해", r"무조건", r"역대급", r"소름"]


def _contains_any(text: str, patterns: List[str]) -> List[str]:
    hits = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            hits.append(p)
    return hits


def validate_shorts_package(script: Dict, topic_item: Dict, manifest: Dict) -> Dict:
    errors, warnings, notes = [], [], []
    title = script.get("title", "")
    captions = script.get("captions", [])
    source_links = topic_item.get("links", []) if topic_item else []

    all_text = title + "\n" + "\n".join(c["text"] if isinstance(c, dict) else str(c) for c in captions)
    banned = _contains_any(all_text, BANNED_PATTERNS)
    if banned:
        errors.append(f"정책 위험 표현이 감지되었습니다: {banned}")

    clickbait = _contains_any(title, CLICKBAIT_TITLE_PATTERNS)
    if clickbait:
        warnings.append(f"제목에 과한 클릭 유도 표현 가능성이 있습니다: {clickbait}")

    if len(captions) < 5:
        warnings.append("자막 수가 너무 적어 저품질·반복 템플릿처럼 보일 수 있습니다.")
    if len(source_links) < 2:
        warnings.append("참고 링크가 2개 미만입니다. 뉴스형 콘텐츠는 근거 링크를 더 확보하세요.")

    assets = manifest.get("assets", [])
    if not assets:
        warnings.append("라이선스 매니페스트에 기록된 시각 자산이 없습니다.")

    synthetic_realism = bool(script.get("synthetic_realism", False))
    if synthetic_realism:
        notes.append("실존 인물/현장을 사실처럼 보이게 하는 합성 요소가 있다면 YouTube disclosure 검토가 필요합니다.")

    if "자료화면" not in script.get("description", "") and "representative footage" not in script.get("description", ""):
        warnings.append("설명문에 자료화면 안내가 없습니다.")

    return {
        "approved_for_render": len(errors) == 0,
        "approved_for_upload": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }
