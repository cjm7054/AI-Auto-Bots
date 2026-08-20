import re
from typing import Dict, List

RISKY_PATTERNS = [
    r"100%\s*보장",
    r"무조건\s*승인",
    r"확실한\s*수익",
    r"원금\s*보장",
    r"반드시\s*오릅니다",
    r"치료됩니다",
    r"완치",
    r"불법",
    r"우회\s*방법",
    r"심사\s*속이는",
]

YMYL_PATTERNS = [
    r"투자", r"주식", r"코인", r"부동산", r"세금", r"절세", r"의료", r"치료", r"약", r"법률", r"소송",
]

CLICKBAIT_TITLE_PATTERNS = [r"충격", r"역대급", r"무조건", r"안\s*보면\s*손해", r"비밀", r"폭로"]
REQUIRED_DISCLAIMER_PATTERNS = [r"이 글은 일반적인 정보 제공을 위한 내용", r"개별 상황에 따라 전문가 확인이 필요"]


def _contains_any(text: str, patterns: List[str]) -> List[str]:
    hits = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            hits.append(p)
    return hits


def validate_blog_package(title: str, content: str, sources: List[Dict], safe_mode: str = "adsense_approval") -> Dict:
    errors, warnings, notes = [], [], []

    risky = _contains_any(title + "\n" + content, RISKY_PATTERNS)
    if risky:
        errors.append(f"과도한 확정·과장·위험 표현이 감지되었습니다: {risky}")

    clickbait = _contains_any(title, CLICKBAIT_TITLE_PATTERNS)
    if clickbait:
        warnings.append(f"제목에 과한 클릭유도 표현 가능성이 있습니다: {clickbait}")

    ymyl_hits = _contains_any(title + "\n" + content, YMYL_PATTERNS)
    if ymyl_hits:
        notes.append(f"민감 주제(YMYL) 가능성이 있습니다: {ymyl_hits}")
        has_disclaimer = any(re.search(p, content, flags=re.IGNORECASE) for p in REQUIRED_DISCLAIMER_PATTERNS)
        if not has_disclaimer:
            warnings.append("YMYL 성격의 주제인데 일반 정보 제공 및 전문가 확인 유도 문구가 부족합니다.")

    if len(sources) < 3:
        errors.append("승인 우선 모드에서는 최소 3개 이상의 참고 자료가 필요합니다.")

    if "출처" not in content and "참고 자료" not in content and "References" not in content:
        warnings.append("출처/참고자료 섹션이 없습니다.")

    auto_publish_allowed = (len(errors) == 0)

    return {
        "approved_for_draft": len(errors) == 0,
        "approved_for_auto_publish": auto_publish_allowed,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }
