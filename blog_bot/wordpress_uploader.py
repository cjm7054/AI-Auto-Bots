import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import markdown

load_dotenv()


def upload_to_wordpress(title, markdown_content, status="draft", categories=None, tags=None):
    wp_url = os.getenv("WP_URL")
    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")

    if not wp_url or not wp_username or not wp_app_password:
        print("[WordPress] 인증 정보(.env)가 부족합니다. 업로드를 건너뜁니다.")
        return False

    api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    html_content = markdown.markdown(markdown_content, extensions=["extra", "sane_lists"])

    post_data = {"title": title, "content": html_content, "status": status or "draft"}
    if categories:
        post_data["categories"] = categories
    if tags:
        post_data["tags"] = tags

    try:
        response = requests.post(
            api_url,
            auth=HTTPBasicAuth(wp_username, wp_app_password),
            json=post_data,
            timeout=30
        )
        if response.status_code in (200, 201):
            body = response.json()
            print(f"[WordPress] 업로드 성공! status={body.get('status')} URL={body.get('link')}")
            return body
        else:
            print(f"[WordPress] 업로드 실패: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[WordPress] 업로드 중 에러 발생: {e}")
        return False
