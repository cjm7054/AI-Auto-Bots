# -*- coding: utf-8 -*-
"""
human_touch_v2.py — 워드프레스 + 블로거 통합 사람 손길 게이트

[배경]
AdSense "낮은 가치의 콘텐츠" / Scaled content abuse 정책 통과를 위해
발행 직전 4-Gate 검증을 강제합니다:
  G1) 1인칭 경험 단락 — 패턴 2개 이상, 120자 이상
  G2) 직접 캡처 이미지 — capture_origin ∈ {self, modified, annotated}
  G3) 독자 행동 유도 — "댓글로/여러분의/해보세요" 등 1개 이상
  G4) AI 어투 밀도 — 1개 이하
  G5) (v2 신규) 워드프레스↔블로거 슬러그 일치 — 카테고리 슬로건 동일 여부
  G6) (v2 신규) SEO 표기 — 작성자, 작성일, 최종수정일이 post 본문/메타에 존재
  G7) (v2 신규) 내부 링크 — 동일 카테고리 글 1개 이상 추천 박스

하나라도 실패 시 HumanTouchMissing 예외로 발행을 차단합니다.
검증 통과해야만 WordPress 또는 Blogger API로 실제 발행이 진행됩니다.
"""
from __future__ import annotations
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
NOW = lambda: datetime.now(KST).isoformat()


# ──────────────────────────────────────────────────────────────────
# 슬롯 정의 (사람 손길이 반드시 들어가야 하는 영역)
# ──────────────────────────────────────────────────────────────────
PERSONA_SLOT = {
    "marker_open":  "<!--HUMAN_EDIT_START-->",
    "marker_close": "<!--HUMAN_EDIT_END-->",
    "min_chars": 120,
    "min_patterns": 2,
    "patterns": [
        r"저는\b", r"제가\b", r"필자가\b",
        r"직접\s?(해|사용|써|찍어|만들어)",
        r"경험(으로|상|을|담)", r"\d+년\s?(차|동안|근무)",
        r"솔직히", r"근데", r"사실\s",
    ],
    "label": "1인칭 경험 단락",
}

CAPTURE_META = {
    "required_keys": ["capture_origin", "capture_source"],
    "allowed_origins": {"self", "modified", "annotated"},
    "blocked_sources": {"stock", "ai-generated-only", "scraped"},
    "label": "직접 캡처 이미지",
}

NUDGE_SLOT = {
    "min_patterns": 1,
    "patterns": [
        r"댓글로\s?(나누|공유|알려|남겨)",
        r"여러분의?\s?(경험|사례|의견|생각|반응)",
        r"질문(해|을|이)\s?(주세요|있으신|드려)",
        r"어떠셨나요|어땠나요|해보세요",
        r"피드백\s?(주세요|부탁|남겨)",
        r"공유\s?해\s?주세요|알려\s?주세요",
    ],
    "label": "독자 행동 유도",
}

INTERNAL_LINK_PATTERN = re.compile(
    r"\[.+?\]\((?P<url>https?://[^\s)]+)\)|<a\s+href=[\"'](?P<url2>[^\"']+)[\"']",
    re.IGNORECASE,
)

AI_PHRASE_BLOCKLIST = [
    "결론적으로 말씀드리자면",
    "이 글에서는 ~ 살펴보겠습니다",
    "정리하자면",
    "요약하면",
    "위에서 살펴본",
    "총정리해보면",
    "오늘은 ~ 알아봤",
    "이렇게 해서 마무리",
    "체계적으로 정리합니다",
    "체계적으로 정리해 봅니다",
    "현실적인 활용 방안",
    "심층 분석해 보겠습니다",
    "총정리해 봅니다",
]
AI_PHRASE_MAX = 1

INFLATION_TERMS = [
    "놀라운 변화", "획기적인 도약", "미래를 바꾸",
    "혁신적인 전환", "최고의 선택", "완벽한 해결",
    "월 백만 원", "월 수백만 원",
]
INFLATION_MAX = 0

CATEGORY_SLOGAN = "AI·업무 자동화"
CATEGORY_SLOGAN_LEGACY = [
    "AI/IT/경영정보/재테크/쇼핑/디지털기술",
    "AI, IT, 생활정보, 재테크, 쇼핑, 디지털 기술",
]

REQUIRED_SEO_FIELDS = ["author", "publish_date", "modify_date"]


@dataclass
class CheckResult:
    label: str
    ok: bool
    detail: str = ""
    fix_hint: str = ""


@dataclass
class ValidationReport:
    ok: bool
    post_path: str
    platform: str
    category: str
    checks: list[CheckResult] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    evaluated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_persona(text: str) -> str:
    if PERSONA_SLOT["marker_open"] not in text or PERSONA_SLOT["marker_close"] not in text:
        return ""
    s = text.index(PERSONA_SLOT["marker_open"]) + len(PERSONA_SLOT["marker_open"])
    e = text.index(PERSONA_SLOT["marker_close"])
    return text[s:e].strip()


def _pattern_hits(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text))


def _ai_phrase_hits(text: str) -> list[str]:
    compact = text.replace(" ", "")
    return [p for p in AI_PHRASE_BLOCKLIST if p.replace(" ", "") in compact]


def _inflation_hits(text: str) -> list[str]:
    return [t for t in INFLATION_TERMS if t in text]


def _has_internal_link(text: str) -> int:
    matches = INTERNAL_LINK_PATTERN.findall(text)
    urls = [m[0] or m[1] for m in matches]
    return len([u for u in urls if u])


def validate_post(post_md_path: str,
                  meta_path: str | None,
                  platform: str = "wordpress",
                  category: str = "ai_side_hustle") -> ValidationReport:
    post = Path(post_md_path).read_text(encoding="utf-8")
    meta: dict = {}
    if meta_path and Path(meta_path).exists():
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))

    persona_text = _extract_persona(post)
    persona_chars = len(persona_text)
    persona_hits = _pattern_hits(persona_text, PERSONA_SLOT["patterns"])

    origin = meta.get("capture_origin")
    source = meta.get("capture_source")
    capture_ok = (origin in CAPTURE_META["allowed_origins"]
                  and source not in CAPTURE_META["blocked_sources"])

    nudge_hits = _pattern_hits(post, NUDGE_SLOT["patterns"])
    ai_hits = _ai_phrase_hits(post)
    infl_hits = _inflation_hits(post)
    internal_links = _has_internal_link(post)

    seo_missing = [f for f in REQUIRED_SEO_FIELDS if not meta.get(f)]

    slogan_in_meta = meta.get("site_slogan", "") or ""
    slogan_unified_ok = (
        CATEGORY_SLOGAN in slogan_in_meta
        or CATEGORY_SLOGAN in post
        or any(legacy.replace(" ", "") in slog.replace(" ", "")
               for legacy in CATEGORY_SLOGAN_LEGACY
               for slog in [slogan_in_meta, post] if slog)
    ) or meta.get("slogan_unified", False)

    report = ValidationReport(
        ok=False, post_path=post_md_path, platform=platform, category=category,
        evaluated_at=NOW(),
    )

    ok = persona_chars >= PERSONA_SLOT["min_chars"] and persona_hits >= PERSONA_SLOT["min_patterns"]
    report.checks.append(CheckResult(
        label=PERSONA_SLOT["label"], ok=ok,
        detail=f"{persona_chars}자 / 패턴 {persona_hits}개",
        fix_hint="<!--HUMAN_EDIT_START--> ... <!--HUMAN_EDIT_END--> 사이 최소 120자, "
                 "'저는 / 제가 / 직접 / 경험 / 솔직히 / N년차' 패턴 2개 이상 직접 채우기",
    ))
    if not ok: report.blocked_reasons.append(report.checks[-1].label + " 미충족")

    report.checks.append(CheckResult(
        label=CAPTURE_META["label"], ok=capture_ok,
        detail=f"origin={origin}, source={source}",
        fix_hint="meta.json에 capture_origin=self|modified|annotated, "
                 "capture_source에 본인 캡처/수정/주석 값 입력",
    ))
    if not capture_ok: report.blocked_reasons.append(report.checks[-1].label + " 미충족")

    report.checks.append(CheckResult(
        label=NUDGE_SLOT["label"],
        ok=nudge_hits >= NUDGE_SLOT["min_patterns"],
        detail=f"패턴 {nudge_hits}개",
        fix_hint="본문 끝에 '댓글로 사례 알려주세요', '여러분의 경험은?', "
                 "'해보세요' 같은 행동 유도 1개+ 직접 작성",
    ))
    if nudge_hits < NUDGE_SLOT["min_patterns"]: report.blocked_reasons.append("독자 행동 유도 부족")

    ok4 = len(ai_hits) <= AI_PHRASE_MAX and len(infl_hits) <= INFLATION_MAX
    report.checks.append(CheckResult(
        label="AI 어투 / 과장 표현 밀도", ok=ok4,
        detail=f"AI 어투 {len(ai_hits)}개 / 과장 {len(infl_hits)}개",
        fix_hint=f"AI 어투 1개 초과 시 차단. 발견 어투: {ai_hits[:3] if ai_hits else '없음'}",
    ))
    if not ok4: report.blocked_reasons.append("AI 어투/과장 밀도 초과")

    report.checks.append(CheckResult(
        label="카테고리 슬러그 통일", ok=slogan_unified_ok,
        detail=f"site_slogan={slogan_in_meta!r}",
        fix_hint=f"meta.json 또는 본문 헤더에 site_slogan='{CATEGORY_SLOGAN}' 입력",
    ))
    if not slogan_unified_ok: report.blocked_reasons.append("슬러그 불일치")

    report.checks.append(CheckResult(
        label="SEO 작성자/작성일", ok=len(seo_missing) == 0,
        detail=f"누락: {seo_missing or '없음'}",
        fix_hint="meta.json에 author(이메일+실명), publish_date, modify_date 모두 입력",
    ))
    if seo_missing: report.blocked_reasons.append("SEO 누락: " + ", ".join(seo_missing))

    report.checks.append(CheckResult(
        label="내부 링크", ok=internal_links >= 1,
        detail=f"링크 {internal_links}개",
        fix_hint="마지막 '관련 글' 박스에 동일 카테고리 글 2~3개 [텍스트](URL)",
    ))
    if internal_links < 1: report.blocked_reasons.append("내부 링크 부족")

    report.ok = all(c.ok for c in report.checks)
    return report


class HumanTouchMissing(Exception):
    pass


def enforce(report: ValidationReport) -> None:
    if not report.ok:
        raise HumanTouchMissing(
            "🚫 발행 차단 — 사람 손길 게이트 미충족\n"
            + "\n".join(f"  • {r}" for r in report.blocked_reasons)
            + "\n\n→ 위 이슈 해결 후 drafts/human_edited/ 로 옮겨 재실행해 주세요."
        )


def safe_publish(post_md_path: str, meta_path: str | None,
                 publisher: object, platform: str, category: str) -> dict:
    report = validate_post(post_md_path, meta_path, platform, category)
    enforce(report)
    return publisher.publish(post_md_path, meta_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python human_touch_v2.py <post.md> [meta.json] [platform] [category]")
        sys.exit(1)
    md = sys.argv[1]
    meta = sys.argv[2] if len(sys.argv) > 2 else None
    platform = sys.argv[3] if len(sys.argv) > 3 else "wordpress"
    category = sys.argv[4] if len(sys.argv) > 4 else "ai_side_hustle"

    r = validate_post(md, meta, platform, category)
    print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    if not r.ok:
        print("\n🚫 발행 차단됨 — 위 사유 해결 후 재실행", file=sys.stderr)
        sys.exit(2)
    print("\n✅ 7-Gate 검증 통과 — 발행 가능")
