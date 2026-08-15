import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# YouTube 업로드를 위한 권한 범위
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    """
    YouTube API 인증을 수행합니다. 
    처음 실행 시 브라우저가 열리며 Google 계정 로그인을 요구합니다.
    (client_secrets.json 파일이 필요합니다.)
    """
    creds = None
    # token.pickle 파일은 사용자의 액세스 토큰과 리프레시 토큰을 저장합니다.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # 유효한 자격증명이 없는 경우 새로 로그인
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secrets.json'):
                print("[에러] client_secrets.json 파일이 없습니다.")
                print("구글 클라우드 콘솔에서 OAuth 클라이언트 ID를 생성하고 다운로드 받아주세요.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # 인증 성공 시 토큰 저장
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('youtube', 'v3', credentials=creds)

def upload_video(youtube, video_file, title, description, tags):
    """지정된 정보를 바탕으로 YouTube에 영상을 업로드합니다."""
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '22' # 22번: People & Blogs
        },
        'status': {
            'privacyStatus': 'private', # 테스트를 위해 '비공개'로 설정 ('public'으로 변경 가능)
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    
    print(f"[{title}] 유튜브 업로드 중...")
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = request.execute()
    print(f"업로드 성공! 영상 ID: {response['id']}")
    return response['id']

if __name__ == "__main__":
    print("유튜브 자동 업로드 모듈입니다.")
    print("실제 업로드를 위해선 구글 클라우드 세팅이 필요합니다.")
