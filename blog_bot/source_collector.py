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
            
        def is_valid_url(u):
            # http로 시작하고 구글 뉴스 관련 주소가 아니어야 함
            return u and u.startswith("http") and "news.google.com" not in u and "google.com/url" not in u

        # 1. requests가 최종 도착한 URL이 정상 언론사 사이트인 경우
        if is_valid_url(r.url):
            return r.url
            
        import re
        # 2. 구글 뉴스 중간 페이지의 data-n-au 속성에서 진짜 URL 추출
        match = re.search(r'data-n-au="([^"]+)"', r.text)
        if match and is_valid_url(match.group(1)):
            return match.group(1)
            
        # 3. 리디렉션 a 태그에서 진짜 URL 추출
        match = re.search(r'<a[^>]*href="([^"]+)"', r.text)
        if match and is_valid_url(match.group(1)):
            return match.group(1)
            
        # 진짜 언론사 주소를 못 찾더라도 구글 뉴스 원본 링크를 반환하여 누락 방지
        return url
    except Exception:
        return url

def collect_google_news_sources(query: str, max_items: int = 6) -> List[Dict]:
    # 최신 뉴스 위주로 수집하기 위해 30일에서 2일로 기간 축소
    encoded = quote_plus(f"{query} when:2d")
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
