import os
import json
import time
import random
import logging
from typing import List, Optional, Dict

import httplib2
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("youtube_uploader")


def _load_token_from_env_or_file() -> Credentials:
    token_env = os.getenv("YOUTUBE_TOKEN", "").strip()
    if token_env:
        try:
            token_info = json.loads(token_env)
            return Credentials.from_authorized_user_info(token_info, SCOPES)
        except json.JSONDecodeError:
            if os.path.exists(token_env):
                with open(token_env, "r", encoding="utf-8") as f:
                    token_info = json.load(f)
                return Credentials.from_authorized_user_info(token_info, SCOPES)
            raise RuntimeError("YOUTUBE_TOKEN 환경변수가 JSON도 아니고 유효한 파일 경로도 아닙니다.")
    if os.path.exists("youtube_token.json"):
        with open("youtube_token.json", "r", encoding="utf-8") as f:
            token_info = json.load(f)
        return Credentials.from_authorized_user_info(token_info, SCOPES)
    raise RuntimeError("YouTube 인증 토큰이 없습니다. YOUTUBE_TOKEN 또는 youtube_token.json 필요")


def get_authenticated_service():
    creds = _load_token_from_env_or_file()
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            logger.info("YouTube 토큰 refresh 시도")
            creds.refresh(Request())
        else:
            raise RuntimeError("YouTube 토큰이 유효하지 않습니다. get_youtube_token.py로 재발급하세요.")
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path: str, title: str, description: str, tags: Optional[List[str]] = None, category_id: str = "25", privacy_status: str = "private", publish_at: Optional[str] = None, made_for_kids: bool = False) -> Dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"업로드할 파일이 없습니다: {file_path}")
    tags = tags or []
    safe_description = description.strip()
    if "자료화면" not in safe_description:
        safe_description += "\n\n※ 본 영상에는 자료화면(representative footage)과 AI 보조 제작 요소(TTS/요약)가 포함될 수 있습니다."

    body = {
        "snippet": {
            "title": title[:100],
            "description": safe_description[:5000],
            "tags": tags[:15],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
            "madeForKids": made_for_kids,
        }
    }
    if publish_at:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(file_path, chunksize=256 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    error = None
    retry = 0
    max_retries = 10
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                logger.info(f"업로드 진행률: {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                error = f"재시도 가능한 업로드 오류: {e}"
            else:
                raise
        except (httplib2.HttpLib2Error, OSError) as e:
            error = f"재시도 가능한 전송 오류: {e}"

        if error:
            retry += 1
            if retry > max_retries:
                raise RuntimeError(f"업로드 재시도 한도 초과: {error}")
            sleep_seconds = min(60, (2 ** retry) + random.random())
            logger.warning(f"{error} | {sleep_seconds:.1f}초 후 재시도")
            time.sleep(sleep_seconds)
            error = None

    return {
        "video_id": response.get("id"),
        "title": title,
        "privacy_status": body["status"]["privacyStatus"],
        "publish_at": body["status"].get("publishAt"),
        "youtube_url": f"https://www.youtube.com/watch?v={response.get('id')}" if response.get("id") else None,
        "raw_response": response,
        "note": "실존 인물/현장을 사실처럼 보이게 하는 합성 연출이 있으면 YouTube Studio에서 altered/synthetic content disclosure를 추가 검토하세요."
    }
