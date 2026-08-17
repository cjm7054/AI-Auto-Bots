import re
from typing import Dict, List


def count_words_ko_en(text: str) -> int:
    if not text:
        return 0
    tokens = re.findall(r"[A-Za-z0-9가-힣]+", text)
    return len(tokens)


def heading_count(markdown_text: str) -> int:
    return len(re.findall(r"^\s{0,3}#{1,6}\s+", markdown_text, flags=re.MULTILINE))


def has_faq_section(markdown_text: str) -> bool:
    patterns = [r"FAQ", r"자주 묻는 질문", r"질문과 답변"]
    return any(re.search(p, markdown_text, flags=re.IGNORECASE) for p in patterns)


def has_reference_section(markdown_text: str) -> bool:
    patterns = [r"참고 자료", r"출처", r"References"]
    return any(re.search(p, markdown_text, flags=re.IGNORECASE) for p in patterns)


def evaluate_draft(title: str, content: str, sources: List[Dict], min_words: int = 1200) -> Dict:
    words = count_words_ko_en(content)
    headings = heading_count(content)
    faq = has_faq_section(content)
    refs = has_reference_section(content)

    suggestions = []
    if words < min_words:
        suggestions.append(f"본문 분량을 더 늘리세요. 현재 약 {words}단어 수준입니다.")
    if headings < 4:
        suggestions.append("소제목 구조를 더 명확하게 늘리세요.")
    if not faq:
        suggestions.append("FAQ 섹션을 추가하세요.")
    if not refs:
        suggestions.append("참고 자료 또는 출처 섹션을 추가하세요.")
    if len(sources) < 3:
        suggestions.append("최소 3개 이상의 외부 참고 자료를 확보하세요.")
    if len(title.strip()) < 12:
        suggestions.append("제목이 지나치게 짧습니다. 검색 의도를 반영해 구체화하세요.")

    return {
        "word_count": words,
        "heading_count": headings,
        "has_faq_section": faq,
        "has_reference_section": refs,
        "source_count": len(sources),
        "suggestions": suggestions,
        "passes_minimum_quality": (
            words >= min_words and headings >= 4 and faq and refs and len(sources) >= 3
        )
    }
