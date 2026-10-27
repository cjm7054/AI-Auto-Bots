import os
import sys
import json
import logging
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
import markdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("clean_and_publish")

WP_URL = (os.getenv("WP_SITE_URL") or os.getenv("WP_URL") or "https://insightlab365.com").rstrip("/")
WP_USER = os.getenv("WP_USERNAME")
WP_PWD = os.getenv("WP_APP_PASSWORD")

if not WP_USER or not WP_PWD:
    logger.error("WP_USERNAME 또는 WP_APP_PASSWORD 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

auth = HTTPBasicAuth(WP_USER, WP_PWD)


def convert_all_published_posts_to_draft():
    """워드프레스의 모든 공개(publish) 상태 글을 임시글(draft)로 일괄 변경"""
    logger.info("=== [1단계] 기존 공개 글 조회 및 임시글(draft) 전환 시작 ===")
    page = 1
    total_converted = 0

    while True:
        url = f"{WP_URL}/wp-json/wp/v2/posts"
        params = {"status": "publish", "per_page": 50, "page": page, "_fields": "id,title"}
        res = requests.get(url, auth=auth, params=params, timeout=20)
        
        if res.status_code == 400 or not res.json():
            # 페이지 끝
            break
        if res.status_code != 200:
            logger.error(f"글 목록 조회 실패: {res.status_code} - {res.text}")
            break

        posts = res.json()
        if not posts:
            break

        logger.info(f"페이지 {page}: {len(posts)}개 공개 글 발견. 임시글 전환 진행 중...")
        for p in posts:
            post_id = p.get("id")
            title = p.get("title", {}).get("rendered", "")
            update_url = f"{WP_URL}/wp-json/wp/v2/posts/{post_id}"
            up_res = requests.post(update_url, auth=auth, json={"status": "draft"}, timeout=15)
            if up_res.status_code == 200:
                logger.info(f"  [성공] ID {post_id} ('{title[:25]}...') -> 임시글(draft) 전환 완료")
                total_converted += 1
            else:
                logger.warning(f"  [실패] ID {post_id} 전환 실패: {up_res.status_code}")

        page += 1

    logger.info(f"=== [1단계 완료] 총 {total_converted}개의 글이 안전하게 '임시글(draft)'로 변경되었습니다! ===")


def upload_new_safe_guides():
    """미리 작성된 A급 에버그린 IT 실무 가이드 3편을 워드프레스에 정식 발행(publish)"""
    logger.info("=== [2단계] 애드센스 승인 보증용 고품질 IT 가이드 3편 신규 발행 시작 ===")
    drafts_dir = Path(__file__).resolve().parent / "data" / "drafts"
    
    files = [
        "20261027_windows11_activation_error_0x803f7001_guide.md",
        "20261027_chrome_browser_memory_optimization_guide.md",
        "20261027_notion_database_relation_rollup_guide.md",
    ]

    for fname in files:
        fpath = drafts_dir / fname
        if not fpath.exists():
            logger.warning(f"파일을 찾을 수 없음: {fpath}")
            continue

        raw_md = fpath.read_text(encoding="utf-8")
        lines = raw_md.strip().split("\n")
        title = lines[0].replace("#", "").strip() if lines else "IT 실무 가이드"
        body_md = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw_md

        html_content = markdown.markdown(body_md, extensions=["extra", "sane_lists"])

        post_data = {
            "title": title,
            "content": html_content,
            "status": "publish",
        }

        url = f"{WP_URL}/wp-json/wp/v2/posts"
        res = requests.post(url, auth=auth, json=post_data, timeout=30)
        if res.status_code in (200, 201):
            created = res.json()
            logger.info(f"  ✅ [신규 발행 성공] ID {created.get('id')}: {title} -> {created.get('link')}")
        else:
            logger.error(f"  ❌ [신규 발행 실패] {title}: {res.status_code} - {res.text}")

    logger.info("=== [2단계 완료] 모든 승인용 신규 글 발행 완료! ===")


def main():
    convert_all_published_posts_to_draft()
    upload_new_safe_guides()


if __name__ == "__main__":
    main()
