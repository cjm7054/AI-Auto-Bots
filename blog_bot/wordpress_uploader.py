import os
import requests
import json
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import markdown

load_dotenv()

def upload_to_wordpress(title, content, status="publish"):
    """
    워드프레스 REST API를 사용하여 글을 발행합니다.
    - WP_URL: 워드프레스 주소 (예: https://insightlab365.com)
    - WP_USERNAME: 워드프레스 로그인 아이디
    - WP_APP_PASSWORD: 응용 프로그램 비밀번호 (일반 비밀번호 아님)
    """
    wp_url = os.getenv("WP_URL")
    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")

    if not all([wp_url, wp_username, wp_app_password]):
        print("  [경고] 워드프레스 환경 변수(WP_URL, WP_USERNAME, WP_APP_PASSWORD)가 설정되지 않았습니다.")
        return False

    api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    
    # 마크다운을 HTML로 변환
    html_content = markdown.markdown(content)

    post_data = {
        "title": title,
        "content": html_content,
        "status": status  # "publish", "draft", "private"
    }

    try:
        response = requests.post(
            api_url,
            json=post_data,
            auth=HTTPBasicAuth(wp_username, wp_app_password)
        )
        
        if response.status_code in [200, 201]:
            post_url = response.json().get("link")
            print(f"  [성공] 워드프레스 발행 완료: {post_url}")
            return True
        else:
            print(f"  [실패] 워드프레스 발행 실패: HTTP {response.status_code}")
            print(f"  응답 내용: {response.text}")
            return False
            
    except Exception as e:
        print(f"  [오류] 워드프레스 API 호출 중 오류 발생: {e}")
        return False
