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


def _verify_and_resolve_link(url: str) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10, allow_redirects=True)
            
        # 리다이렉트되어 실제 언론사 사이트로 넘어간 경우 (가장 확실함)
        if not r.url.startswith("https://news.google.com/"):
            return r.url
            
        import re
        # Google News 중간 페이지에서 실제 URL 추출 시도
        match = re.search(r'data-n-au="([^"]+)"', r.text)
        if match:
            return match.group(1)
            
        match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>여기를 클릭', r.text)
        if match:
            return match.group(1)
            
        # 구글 뉴스 링크 그대로 남아있거나 400 에러 페이지면 무조건 폐기(None)
        return None
    except Exception:
        return None

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

        for item in items: # Look through more items in case many fail verification
            title = _clean_title(item.findtext("title", default=""))
            link = item.findtext("link", default="").strip()
            pub_date = item.findtext("pubDate", default="").strip()

            if not title or not link:
                continue

            # Verify and resolve the actual URL
            resolved_link = _verify_and_resolve_link(link)
            if not resolved_link:
                continue
                
            key = (title, resolved_link)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": title,
                "url": resolved_link,
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
