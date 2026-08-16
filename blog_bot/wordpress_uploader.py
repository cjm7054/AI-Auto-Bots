import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import markdown

load_dotenv()

def upload_to_wordpress(title, content):
    wp_url = os.getenv("WP_URL")
    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")

    if not wp_url or not wp_username or not wp_app_password:
        print("[WordPress] 인증 정보(.env)가 부족합니다. 업로드를 건너뜁니다.")
        return False

    api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    
    # 마크다운을 HTML로 변환
    html_content = markdown.markdown(content)
    
    post_data = {
        'title': title,
        'content': html_content,
        'status': 'publish'
    }

    try:
        response = requests.post(
            api_url,
            auth=HTTPBasicAuth(wp_username, wp_app_password),
            json=post_data
        )
        if response.status_code == 201:
            print(f"[WordPress] 업로드 성공! URL: {response.json().get('link')}")
            return True
        else:
            print(f"[WordPress] 업로드 실패: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[WordPress] 업로드 중 에러 발생: {e}")
        return False

if __name__ == "__main__":
    # 테스트용
    upload_to_wordpress("WordPress API 테스트", "자동 생성된 **포스팅**입니다.")
