# -*- coding: utf-8 -*-
import os
import requests
import logging

logger = logging.getLogger("blog_bot.notifier")

class KakaoNotifier:
    def __init__(self):
        self.rest_api_key = os.getenv("KAKAO_REST_API_KEY", "").strip()
        self.refresh_token = os.getenv("KAKAO_REFRESH_TOKEN", "").strip()
        self.access_token = None

    def _refresh_access_token(self) -> bool:
        if not self.rest_api_key or not self.refresh_token:
            logger.warning("카카오톡 연동 환경변수(KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN)가 누락되었습니다.")
            return False

        url = "https://kauth.kakao.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.rest_api_key,
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            self.access_token = result.get("access_token")
            
            # 리프레시 토큰이 갱신된 경우 (유효기간 1개월 미만일 때 발급됨)
            if "refresh_token" in result:
                new_refresh_token = result["refresh_token"]
                logger.info(f"⚠️ [필독] 카카오 리프레시 토큰이 갱신되었습니다. Github Secrets의 KAKAO_REFRESH_TOKEN을 다음 값으로 변경해주세요: {new_refresh_token}")
            
            return True
        except Exception as e:
            logger.error(f"카카오톡 액세스 토큰 갱신 실패: {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                logger.error(response.text)
            return False

    def send_message(self, text: str) -> bool:
        if not self._refresh_access_token():
            return False

        url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        template_object = {
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": "https://github.com",
                "mobile_web_url": "https://github.com"
            },
            "button_title": "확인하기"
        }
        
        import json
        data = {"template_object": json.dumps(template_object)}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            logger.info("카카오톡 알림 전송 완료!")
            return True
        except Exception as e:
            logger.error(f"카카오톡 알림 전송 실패: {e}")
            if 'response' in locals() and hasattr(response, 'text'):
                logger.error(response.text)
            return False

def send_draft_notification(title: str, draft_path: str):
    notifier = KakaoNotifier()
    msg = f"📝 [블로그 봇] 새로운 임시글이 저장되었습니다.\n\n제목: {title}\n파일경로: {draft_path}\n\n1인칭 경험담과 이미지를 추가하고 최종 발행을 진행해 주세요!"
    notifier.send_message(msg)

if __name__ == "__main__":
    # Test execution
    send_draft_notification("테스트 제목", "drafts/test.md")
