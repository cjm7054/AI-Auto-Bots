# -*- coding: utf-8 -*-
"""
main_v2.py — 워드프레스 + 블로거 통합 발행 진입점

[흐름]
1) 초안 → drafts/pending_human_touch/<slug>.md
2) 사람이 직접 손길 7-Gate 채우기 (1인칭/캡처이미지/행동유도/AI어투/슬러그/작성자/내부링크)
3) drafts/human_edited/<slug>.md + <slug>.meta.json
4) 본 스크립트가 7-Gate 모두 통과해야만 실제 발행

사용법:
  python main_v2.py --platform blogger --file drafts/human_edited/x.md --meta ... --action publish
  python main_v2.py --platform wordpress --file ... --meta ... --action publish
  python main_v2.py --platform both --file ... --meta ... --action publish
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from blog_bot.human_touch_v2 import safe_publish, HumanTouchMissing, CATEGORY_SLOGAN


class WordPressPublisher:
    """워드프레스 REST API v2 발행 어댑터 (앱 비밀번호 인증)

    - site_url : https://insightlab365.com
    - username : 워드프레스 관리자 ID
    - password : 앱 비밀번호 (16자리 보통 — 계정 본 비밀번호 X)
    """

    def __init__(self, site_url: str, username: str, app_password: str):
        self.site_url = site_url.rstrip("/")
        self.auth = (username, app_password)

    def publish(self, post_md_path: str, meta_path: str | None) -> dict:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "requests 패키지 필요: pip install requests"
            ) from exc

        text = Path(post_md_path).read_text(encoding="utf-8")
        meta: dict = {}
        if meta_path and Path(meta_path).exists():
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))

        body = {
            "title": meta.get("title") or Path(post_md_path).stem,
            "content": text,
            "status": "publish",
            "categories": [CATEGORY_SLOGAN],
            "meta": {
                "author": meta.get("author", ""),
                "publish_date": meta.get("publish_date", ""),
                "modify_date": meta.get("modify_date", ""),
            },
        }
        r = requests.post(
            f"{self.site_url}/wp-json/wp/v2/posts",
            auth=self.auth,
            json=body,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return {"url": data.get("link"), "id": data.get("id"),
                "status": data.get("status")}


def _build_publishers(platform: str):
    """플랫폼별 발행기 인스턴스 생성
    환경변수:
      WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD (워드프레스)
      BLOGGER_BLOG_ID, BLOGGER_TOKEN_PATH  (블로거)
    """
    wp = bp = None
    if platform in {"wordpress", "both"}:
        wp = WordPressPublisher(
            os.environ["WP_SITE_URL"],
            os.environ["WP_USERNAME"],
            os.environ["WP_APP_PASSWORD"],
        )
    if platform in {"blogger", "both"}:
        from publishers.blogger_publisher_v2 import BloggerPublisher
        bp = BloggerPublisher(
            os.environ["BLOGGER_BLOG_ID"],
            os.environ.get("BLOGGER_TOKEN_PATH", "secrets/google_token.json"),
        )

    if platform == "wordpress":
        return wp, "wordpress"
    if platform == "blogger":
        return bp, "blogger"
    return (wp, bp), "both"


def _publish(publisher_pair, md: str, meta: str, platform: str, category: str):
    if platform == "both":
        wp, bp = publisher_pair
        return {
            "wordpress": safe_publish(md, meta, wp, "wordpress", category),
            "blogger":   safe_publish(md, meta, bp, "blogger",   category),
        }
    return safe_publish(md, meta, publisher_pair, platform, category)


def main(args):
    pair, label = _build_publishers(args.platform)
    try:
        result = _publish(pair, args.file, args.meta, args.platform, args.category)
    except HumanTouchMissing as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n✅ [{label}] 발행 완료 — 사람 손길 7-Gate 통과")


def parse_args():
    p = argparse.ArgumentParser(description="통합 발행 진입점")
    p.add_argument("--platform", choices=["wordpress", "blogger", "both"], required=True)
    p.add_argument("--file", required=True, help="게시할 .md 파일 경로")
    p.add_argument("--meta", help="meta.json 파일 경로")
    p.add_argument("--category", default="ai_side_hustle")
    p.add_argument("--action", choices=["publish", "draft"], default="publish")
    return p.parse_args()


if __name__ == "__main__":
    main(parse_args())
