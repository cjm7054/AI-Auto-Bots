import re
import logging
from typing import List, Dict
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("blog_source_collector")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    return title


def collect_google_news_sources(query: str, max_items: int = 6) -> List[Dict]:
    encoded = quote_plus(f"{query} when:30d")
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")

        results = []
        seen = set()

        for item in items[:max_items * 2]:
            title = _clean_title(item.findtext("title", default=""))
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()

            if not title or not link:
                continue

            key = (title, link)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": title,
                "url": link,
                "publisher": "Google News RSS",
                "published_at": pub_date,
            })

            if len(results) >= max_items:
                break

        return results

    except Exception as e:
        logger.warning(f"Google News RSS 수집 실패 | query={query} | error={e}")
        return []


def build_source_context(sources: List[Dict]) -> str:
    if not sources:
        return "참고 자료 없음"

    lines = []
    for idx, s in enumerate(sources, start=1):
        lines.append(f"{idx}. {s['title']} | {s['url']}")
    return "\n".join(lines)
