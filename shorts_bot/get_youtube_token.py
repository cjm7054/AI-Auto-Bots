"""
[1회만 실행] YouTube OAuth 토큰 생성 - URL 복사 방식
브라우저가 자동으로 안 열릴 때 사용합니다.

사용법:
  1. 이 스크립트 실행
  2. 출력되는 URL을 복사해서 브라우저에 붙여넣기
  3. 구글 로그인 + 권한 허용
  4. 리디렉트된 페이지에서 보이는 '코드'를 복사해서 터미널에 붙여넣기
  5. youtube_token.json 파일 생성 완료!
"""
import json
import os
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 이 스크립트 파일이 있는 폴더(shorts_bot/)를 기준으로 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_PATH = os.path.join(SCRIPT_DIR, 'client_secrets.json')
TOKEN_OUTPUT_PATH = os.path.join(SCRIPT_DIR, 'youtube_token.json')

# redirect_uri를 oob(out-of-band)로 설정 - 브라우저 자동 실행 없이 코드 표시
if not os.path.exists(CLIENT_SECRETS_PATH):
    print(f"[오류] client_secrets.json 파일이 없습니다!")
    print(f"[경로] {CLIENT_SECRETS_PATH}")
    print()
    print("[해결 방법]")
    print("1. Google Cloud Console → API 및 서비스 → 사용자 인증 정보")
    print("2. 'OAuth 2.0 클라이언트 ID' 생성 (유형: 데스크톱 앱)")
    print("3. JSON 다운로드 후 다음 위치에 저장:")
    print(f"   {CLIENT_SECRETS_PATH}")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(
    CLIENT_SECRETS_PATH,
    scopes=SCOPES,
    redirect_uri="urn:ietf:wg:oauth:2.0:oob"
)

auth_url, _ = flow.authorization_url(
    access_type='offline',
    prompt='consent'
)

print("=" * 70)
print("[ YouTube 인증 URL ]")
print("=" * 70)
print(f"\n{auth_url}\n")
print("=" * 70)
print("위 URL을 복사해서 브라우저(크롬 등)에 붙여넣으세요!")
print("구글 계정 로그인 → '계속' → 권한 허용 → 화면에 코드가 표시됩니다.")
print("=" * 70)

code = input("\n화면에 표시된 인증 코드를 여기에 붙여넣고 Enter: ").strip()

# 코드로 토큰 교환
flow.fetch_token(code=code)
creds = flow.credentials

token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": list(creds.scopes)
}

with open(TOKEN_OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(token_data, f, ensure_ascii=False, indent=2)

print(f"\n저장 위치: {TOKEN_OUTPUT_PATH}")

print("\n" + "=" * 70)
print("[성공] youtube_token.json 파일 생성 완료!")
print("\n[다음 단계]")
print("1. youtube_token.json 파일을 메모장으로 열기")
print("2. 내용 전체 복사 (Ctrl+A → Ctrl+C)")
print("3. GitHub → Settings → Secrets → New repository secret")
print("   Name: YOUTUBE_TOKEN")
print("   Value: 복사한 내용 붙여넣기")
print("=" * 70)
