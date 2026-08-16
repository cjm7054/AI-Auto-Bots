import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import markdown

def upload_to_blogger(title, content):
    token_file = os.path.join(os.path.dirname(__file__), 'blogger_token.json')
    if not os.path.exists(token_file):
        print("[Blogger] blogger_token.json 파일이 없습니다. 업로드를 건너뜁니다.")
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(token_file)
        service = build('blogger', 'v3', credentials=creds)
        
        # 블로그 목록 가져오기
        blogs = service.blogs().listByUser(userId='self').execute()
        if not blogs.get('items'):
            print("[Blogger] 사용자의 블로그를 찾을 수 없습니다.")
            return False
        
        # 첫 번째 블로그 선택
        blog_id = blogs['items'][0]['id']
        
        # 마크다운을 HTML로 변환
        html_content = markdown.markdown(content)
        
        body = {
            "kind": "blogger#post",
            "title": title,
            "content": html_content
        }
        
        posts = service.posts()
        result = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        
        print(f"[Blogger] 업로드 성공! URL: {result.get('url')}")
        return True
    except Exception as e:
        print(f"[Blogger] 업로드 중 에러 발생: {e}")
        return False

if __name__ == "__main__":
    # 테스트용
    upload_to_blogger("Blogger API 테스트", "자동 생성된 **포스팅**입니다.")
