import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from dotenv import load_dotenv
import markdown

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/blogger']

def get_blogger_service():
    """BLOGGER_TOKEN 환경변수로 Blogger API 인증을 수행합니다."""
    token_json = os.getenv("BLOGGER_TOKEN")
    
    if not token_json and os.path.exists("blogger_token.json"):
        with open("blogger_token.json", "r", encoding="utf-8") as f:
            token_json = f.read()
            
    if not token_json:
        print("  [경고] BLOGGER_TOKEN이 없습니다.")
        return None
        
    try:
        token_data = json.loads(token_json)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", SCOPES)
        )
        
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            
        service = build('blogger', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"  [오류] Blogger 인증 실패: {e}")
        return None

def upload_to_blogger(title, content, labels=None):
    """Blogger API를 사용하여 글을 발행합니다."""
    service = get_blogger_service()
    if not service:
        return False
        
    try:
        # 사용자의 블로그 목록 조회
        blogs = service.blogs().listByUser(userId='self').execute()
        if not blogs.get('items'):
            print("  [오류] 연결된 구글 블로그가 없습니다.")
            return False
            
        # 첫 번째 블로그 선택
        blog_id = blogs['items'][0]['id']
        
        # 마크다운을 HTML로 변환
        html_content = markdown.markdown(content)
        
        body = {
            "kind": "blogger#post",
            "blog": {"id": blog_id},
            "title": title,
            "content": html_content
        }
        
        if labels:
            body["labels"] = labels
            
        # 글 발행
        post = service.posts().insert(blogId=blog_id, body=body, isDraft=False).execute()
        print(f"  [성공] 블로거 발행 완료: {post.get('url')}")
        return True
        
    except Exception as e:
        print(f"  [오류] 블로거 글 발행 실패: {e}")
        return False
