import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import markdown

load_dotenv()


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _get_wp_config():
    wp_url = (os.getenv("WP_SITE_URL") or os.getenv("WP_URL") or "https://insightlab365.com").strip().rstrip("/")
    if wp_url.startswith("http://"):
        wp_url = "https://" + wp_url[len("http://"):]
    wp_username = (os.getenv("WP_USERNAME") or "cjm7054").strip()
    wp_app_password = (os.getenv("WP_APP_PASSWORD") or "").strip()
    return wp_url, wp_username, wp_app_password


def upload_to_wordpress(title, markdown_content, status="draft", categories=None, tags=None):
    wp_url, wp_username, wp_app_password = _get_wp_config()

    if not wp_url or not wp_username or not wp_app_password:
        print("[WordPress] 인증 정보(.env)가 부족합니다. 업로드를 건너뜁니다.", flush=True)
        return False

    lines = markdown_content.strip().split("\n")
    if lines and lines[0].strip().startswith("#"):
        markdown_body = "\n".join(lines[1:]).strip()
    else:
        markdown_body = markdown_content.strip()

    html_content = markdown.markdown(markdown_body, extensions=["extra", "sane_lists"])

    # 기본 카테고리: IT 실무 팁 (ID: 119)
    if categories is None:
        categories = [119]

    post_data = {
        "title": title,
        "content": html_content,
        "status": status or "draft",
        "categories": categories,
    }
    if tags:
        post_data["tags"] = tags

    endpoints = [
        f"{wp_url}/wp-json/wp/v2/posts",
        f"{wp_url}/?rest_route=/wp/v2/posts",
    ]
    headers = {**DEFAULT_HEADERS, "Referer": f"{wp_url}/wp-admin/"}

    for api_url in endpoints:
        try:
            response = requests.post(
                api_url,
                auth=HTTPBasicAuth(wp_username, wp_app_password),
                headers=headers,
                json=post_data,
                timeout=30,
            )
            if response.status_code in (200, 201) and response.text.strip():
                body = response.json()
                print(f"[WordPress] 업로드 성공! status={body.get('status')} URL={body.get('link')}", flush=True)
                return body
            else:
                snippet = response.text[:160].replace("\n", " ").replace("\r", " ")
                print(
                    f"::error title=WP_DIAG::url={api_url} status={response.status_code} "
                    f"len={len(response.text)} server={response.headers.get('Server')} body={snippet!r}",
                    flush=True,
                )
        except Exception as e:
            print(f"::error title=WP_EXC::url={api_url} err={e}", flush=True)

    return False


def get_recent_wordpress_titles(per_page=30):
    wp_url, wp_username, wp_app_password = _get_wp_config()

    if not wp_url:
        return []

    endpoints = [
        f"{wp_url}/wp-json/wp/v2/posts",
        f"{wp_url}/?rest_route=/wp/v2/posts",
    ]
    headers = {**DEFAULT_HEADERS, "Referer": f"{wp_url}/"}
    auth = HTTPBasicAuth(wp_username, wp_app_password) if (wp_username and wp_app_password) else None

    for api_url in endpoints:
        try:
            # 공개 글 목록 조회는 인증 없이도 가능하므로 먼저 시도 후 필요 시 인증 사용
            response = requests.get(
                api_url,
                headers=headers,
                params={"per_page": per_page, "_fields": "title"},
                timeout=15,
            )
            if response.status_code != 200 or not response.text.strip():
                if auth:
                    response = requests.get(
                        api_url,
                        auth=auth,
                        headers=headers,
                        params={"per_page": per_page, "_fields": "title"},
                        timeout=15,
                    )
            if response.status_code == 200 and response.text.strip():
                posts = response.json()
                return [p.get("title", {}).get("rendered", "").strip() for p in posts if p.get("title")]
            else:
                print(
                    f"[WordPress] 최근 글 목록 조회 비정상 ({api_url}): status={response.status_code}, "
                    f"len={len(response.text)}",
                    flush=True,
                )
        except Exception as e:
            print(f"[WordPress] 최근 글 목록 조회 실패 ({api_url}): {e}", flush=True)

    return []

