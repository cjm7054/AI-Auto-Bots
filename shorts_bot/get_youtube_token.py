import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_PATH = os.path.join(SCRIPT_DIR, "client_secrets.json")
TOKEN_OUTPUT_PATH = os.path.join(SCRIPT_DIR, "youtube_token.json")


def main():
    if not os.path.exists(CLIENT_SECRETS_PATH):
        raise FileNotFoundError(f"client_secrets.json 파일이 없습니다: {CLIENT_SECRETS_PATH}")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, scopes=SCOPES)
    creds = flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message="브라우저에서 YouTube 권한을 승인해 주세요.",
        success_message="YouTube 인증이 완료되었습니다. 이 창을 닫아도 됩니다.",
        open_browser=True
    )
    token_data = json.loads(creds.to_json())
    with open(TOKEN_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    print(f"[성공] youtube_token.json 저장 완료: {TOKEN_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
