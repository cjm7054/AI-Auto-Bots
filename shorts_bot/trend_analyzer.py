import re
import math
import logging
from typing import Dict, List
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

try:
    from pytrends.request import TrendReq
except Exception:
    TrendReq = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("shorts_trend_analyzer")

REQUEST_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

CATEGORY_SEARCH_QUERIES = {
    "politics": ["정치", "대통령", "국회"],
    "society": ["사회", "의료", "교육"],
    "economy": ["경제", "증시", "부동산"],
    "entertainment": ["연예", "드라마", "아이돌"],
}
CATEGORY_HINTS = {
    "politics": ["대통령", "국회", "장관", "정당", "선거", "외교", "안보", "법안"],
    "society": ["사건", "사고", "재난", "폭우", "태풍", "의료", "교육", "경찰", "법원"],
    "economy": ["증시", "코스피", "환율", "금리", "부동산", "반도체", "물가", "고용"],
    "entertainment": ["아이돌", "배우", "가수", "드라마", "영화", "예능", "컴백", "앨범"],
}
SENSITIVE_FILTER = [r"살인", r"자살", r"시신", r"성범죄", r"잔혹", r"혐오", r"루머", r"폭로"]
FALLBACK_TOPICS = [
    {"keyword": "코스피 장중 변동성 확대", "category": "economy", "source": "fallback"},
    {"keyword": "국회 주요 법안 논의", "category": "politics", "source": "fallback"},
    {"keyword": "폭염·집중호우 대응 이슈", "category": "society", "source": "fallback"},
    {"keyword": "드라마·예능 화제 장면", "category": "entertainment", "source": "fallback"},
    {"keyword": "반도체 업황 전망", "category": "economy", "source": "fallback"},
]


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def shorten_topic(text: str, max_length: int = 34) -> str:
    text = re.sub(r"\s+-\s+.*$", "", text).strip()
    text = re.sub(r"\s+\|.*$", "", text).strip()
    text = re.sub(r"\[[^\]]+\]", "", text).strip()
    text = re.sub(r"\([^)]*\)", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length].rstrip() if len(text) > max_length else text


def classify_topic(text: str) -> str:
    normalized = normalize_text(text)
    scores = {}
    for category, hints in CATEGORY_HINTS.items():
        scores[category] = sum(1 for h in hints if h.lower() in normalized)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def is_sensitive_topic(text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in SENSITIVE_FILTER)


def fetch_google_trends(limit: int = 12) -> List[Dict]:
    if TrendReq is None:
        logger.warning("pytrends import 실패")
        return []
    try:
        pytrends = TrendReq(hl="ko-KR", tz=540)
        df = pytrends.trending_searches(pn="south_korea")
        keywords = df[0].dropna().astype(str).tolist()
        results = []
        for rank, keyword in enumerate(keywords[:limit], start=1):
            if is_sensitive_topic(keyword):
                continue
            results.append({
                "keyword": keyword.strip(),
                "category": classify_topic(keyword),
                "source": "google_trends",
                "trend_rank": rank,
                "article_count": 0,
                "related_headlines": [],
                "links": [],
                "score": max(0, 80 - (rank - 1) * 4),
            })
        return results
    except Exception as e:
        logger.warning(f"Google Trends 수집 실패: {e}")
        return []


def fetch_google_news_rss(query: str, category: str, max_items: int = 5) -> List[Dict]:
    encoded_query = quote_plus(f"{query} when:1d")
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        results = []
        for item in items[:max_items]:
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            if not title or is_sensitive_topic(title):
                continue
            topic = shorten_topic(title)
            results.append({
                "keyword": topic,
                "category": category if category else classify_topic(topic),
                "source": "google_news",
                "trend_rank": None,
                "article_count": 1,
                "related_headlines": [title],
                "links": [link] if link else [],
                "score": 14,
            })
        return results
    except Exception as e:
        logger.warning(f"Google News RSS 수집 실패 | query={query} | error={e}")
        return []


def merge_candidates(candidates: List[Dict]) -> List[Dict]:
    merged = {}
    def find_existing(keyword: str):
        norm = normalize_text(keyword)
        for k, item in merged.items():
            e = normalize_text(item["keyword"])
            if norm == e or (norm and e and (norm in e or e in norm)):
                return k
        return None

    for item in candidates:
        k = find_existing(item["keyword"])
        if not k:
            merged[item["keyword"]] = {
                "keyword": item["keyword"],
                "category": item.get("category", "general"),
                "sources": {item.get("source", "unknown")},
                "trend_rank": item.get("trend_rank"),
                "article_count": item.get("article_count", 0),
                "related_headlines": list(item.get("related_headlines", [])),
                "links": list(item.get("links", [])),
                "score": float(item.get("score", 0)),
            }
            continue
        base = merged[k]
        base["sources"].add(item.get("source", "unknown"))
        base["article_count"] += item.get("article_count", 0)
        base["related_headlines"].extend(item.get("related_headlines", []))
        base["links"].extend(item.get("links", []))
        base["score"] += float(item.get("score", 0))
        if base.get("category") == "general" and item.get("category") != "general":
            base["category"] = item.get("category")
        if base.get("trend_rank") is None and item.get("trend_rank") is not None:
            base["trend_rank"] = item.get("trend_rank")
        elif item.get("trend_rank") is not None and base.get("trend_rank") is not None:
            base["trend_rank"] = min(base["trend_rank"], item["trend_rank"])

    final = []
    for _, item in merged.items():
        if len(item["sources"]) >= 2:
            item["score"] += 18
        if item["article_count"] > 1:
            item["score"] += min(16, math.log(item["article_count"] + 1) * 5)
        item["related_headlines"] = list(dict.fromkeys(item["related_headlines"]))[:5]
        item["links"] = list(dict.fromkeys(item["links"]))[:5]
        item["sources"] = sorted(item["sources"])
        final.append(item)
    return final


def diversify_top_topics(items: List[Dict], limit: int = 5) -> List[Dict]:
    selected, used_categories = [], set()
    for item in items:
        if item["category"] not in used_categories:
            selected.append(item)
            used_categories.add(item["category"])
        if len(selected) >= limit:
            return selected
    seen = {normalize_text(x["keyword"]) for x in selected}
    for item in items:
        k = normalize_text(item["keyword"])
        if k not in seen:
            selected.append(item)
            seen.add(k)
        if len(selected) >= limit:
            return selected
    return selected[:limit]


def get_daily_trends(limit: int = 5) -> List[Dict]:
    all_candidates = []
    all_candidates.extend(fetch_google_trends(limit=12))
    for category, queries in CATEGORY_SEARCH_QUERIES.items():
        for query in queries:
            all_candidates.extend(fetch_google_news_rss(query, category, max_items=4))

    merged = merge_candidates(all_candidates)
    filtered = []
    for item in merged:
        keyword = item["keyword"].strip()
        if len(keyword) < 2 or is_sensitive_topic(keyword):
            continue
        if item.get("category") == "general":
            item["category"] = classify_topic(keyword)
        filtered.append(item)

    filtered.sort(key=lambda x: (x.get("score", 0), x.get("article_count", 0), -999 if x.get("trend_rank") is None else -x["trend_rank"]), reverse=True)
    final = diversify_top_topics(filtered, limit=limit)
    if not final:
        final = FALLBACK_TOPICS[:limit]

    results = []
    for rank, item in enumerate(final[:limit], start=1):
        results.append({
            "rank": rank,
            "keyword": item["keyword"],
            "category": item.get("category", "general"),
            "sources": item.get("sources", [item.get("source", "fallback")]),
            "trend_rank": item.get("trend_rank"),
            "article_count": item.get("article_count", 0),
            "related_headlines": item.get("related_headlines", []),
            "links": item.get("links", []),
            "score": round(float(item.get("score", 0)), 2),
        })
    return results


if __name__ == "__main__":
    print(get_daily_trends())
