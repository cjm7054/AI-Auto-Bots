import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import markdown

load_dotenv()


def upload_to_blogger(title, markdown_content, is_draft=True):
    token_file = os.path.join(os.path.dirname(__file__), "blogger_token.json")
    blog_id_env = os.getenv("BLOGGER_BLOG_ID", "").strip()

    if not os.path.exists(token_file):
        print("[Blogger] blogger_token.json 파일이 없습니다. 업로드를 건너뜁니다.")
        return False

    try:
        creds = Credentials.from_authorized_user_file(token_file)
        service = build("blogger", "v3", credentials=creds)

        if blog_id_env:
            blog_id = blog_id_env
        else:
            blogs = service.blogs().listByUser(userId="self").execute()
            if not blogs.get("items"):
                print("[Blogger] 사용자의 블로그를 찾을 수 없습니다.")
                return False
            blog_id = blogs["items"][0]["id"]

        html_content = markdown.markdown(markdown_content, extensions=["extra", "sane_lists"])
        body = {"kind": "blogger#post", "title": title, "content": html_content}

        result = service.posts().insert(blogId=blog_id, body=body, isDraft=bool(is_draft)).execute()
        print(f"[Blogger] 업로드 성공! draft={is_draft} URL={result.get('url')}")
        return result

    except Exception as e:
        print(f"[Blogger] 업로드 중 에러 발생: {e}")
        return False


def get_recent_blogger_titles(max_results=30):
    token_file = os.path.join(os.path.dirname(__file__), "blogger_token.json")
    blog_id_env = os.getenv("BLOGGER_BLOG_ID", "").strip()

    if not os.path.exists(token_file):
        return []

    try:
        creds = Credentials.from_authorized_user_file(token_file)
        service = build("blogger", "v3", credentials=creds)

        if blog_id_env:
            blog_id = blog_id_env
        else:
            blogs = service.blogs().listByUser(userId="self").execute()
            if not blogs.get("items"):
                return []
            blog_id = blogs["items"][0]["id"]

        posts = service.posts().list(blogId=blog_id, maxResults=max_results, fetchBodies=False).execute()
        items = posts.get("items", [])
        return [item.get("title", "").strip() for item in items if item.get("title")]
    except Exception as e:
        print(f"[Blogger] 최근 글 목록 조회 실패: {e}")
        return []

