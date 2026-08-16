import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    """
    GitHub Secrets의 YOUTUBE_TOKEN 환경변수로 YouTube API 인증을 수행합니다.
    로컬에서는 youtube_token.json 파일을 사용합니다.
    """
    token_json = os.getenv("YOUTUBE_TOKEN")
    
    # 환경변수 없으면 로컬 파일에서 시도
    if not token_json and os.path.exists("youtube_token.json"):
        with open("youtube_token.json", "r", encoding="utf-8") as f:
            token_json = f.read()
        print("-> 로컬 youtube_token.json 파일로 인증합니다.")
    
    if not token_json:
        print("-> [경고] YOUTUBE_TOKEN이 없어 업로드를 건너뜁니다.")
        print("   설정 방법: shorts_bot/get_youtube_token.py 를 실행하세요.")
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
        
        # 토큰 만료 시 자동 갱신 (refresh_token이 있으면 무기한 사용 가능)
        if creds.expired and creds.refresh_token:
            print("-> 토큰 만료됨, 자동 갱신 중...")
            creds.refresh(Request())
        
        service = build('youtube', 'v3', credentials=creds)
        print("-> YouTube API 인증 성공!")
        return service
        
    except Exception as e:
        print(f"-> [오류] YouTube 인증 실패: {e}")
        return None

def upload_video(youtube, video_file, title, description, tags):
    """지정된 정보를 바탕으로 YouTube에 영상을 업로드합니다."""
    print(f"-> 업로드 시작: {title}")
    
    body = {
        'snippet': {
            'title': title,
            'description': description + "\n\n#AI부업 #유튜브쇼츠 #자동화",
            'tags': tags,
            'categoryId': '22'  # 22번: People & Blogs
        },
        'status': {
            'privacyStatus': 'private',  # 처음엔 비공개로 업로드
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype='video/mp4')
    
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    # 진행률 표시와 함께 업로드
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"   업로드 진행: {pct}%")
    
    video_id = response['id']
    print(f"-> 업로드 완료! 영상 ID: {video_id}")
    print(f"   비공개 링크: https://www.youtube.com/watch?v={video_id}")
    print(f"   (YouTube Studio에서 공개로 변경 가능)")
    return video_id

if __name__ == "__main__":
    print("유튜브 자동 업로드 모듈입니다.")
    print("토큰 생성: python get_youtube_token.py 를 먼저 실행하세요.")
