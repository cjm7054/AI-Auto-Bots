import os
import json
import time
import requests
from dotenv import load_dotenv

# 내부 모듈 임포트
from trend_analyzer import get_daily_trends
from video_maker import create_video
from youtube_uploader import get_authenticated_service, upload_video

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# 진단으로 확인된 안정적인 모델 alias (50개 모델 중 검증 완료)
ACTIVE_MODEL = "gemini-flash-latest"

def call_gemini(prompt, max_retries=5):
    """Gemini REST API를 직접 호출합니다. 503 오류 시 최대 5회 재시도합니다."""
    url = f"{GEMINI_BASE_URL}/models/{ACTIVE_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=body, headers=headers, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 503 and attempt < max_retries:
                wait = 2 ** attempt  # 지수 백오프: 2, 4, 8, 16초
                print(f"[재시도 {attempt}/{max_retries}] 서버 과부하(503), {wait}초 후 재시도...")
                time.sleep(wait)
            else:
                raise
    return None

def generate_shorts_script(topic):
    """
    세인투의 [3초 후킹 - 공감 - 해결 - CTA] 공식에 맞춘 쇼츠 대본 생성.
    영상 합성을 위해 결과물을 JSON 형태로 반환받도록 강제합니다.
    """
    prompt = f"""
    당신은 수백만 조회수를 찍는 유튜브 쇼츠/인스타 릴스 대본 기획자입니다.
    오늘의 핫이슈 주제: {topic}
    
    [작성 공식]
    1. 3초 후킹: 이탈을 막기 위해 무조건 자극적이고 궁금하게 시작 (질문형 등)
    2. 공감: 타겟 시청자의 문제점이나 현실을 짚어줌
    3. 해결: 구체적이고 빠른 해결책 1~2개 제시
    4. CTA(행동유도): "구독하고 더 많은 정보 받기" 형태의 마무리
    
    [출력 형식]
    다음과 같은 JSON 형식으로만 출력하세요. 마크다운 기호(```json 등)는 절대 넣지 마세요.
    {{
        "title": "유튜브에 올라갈 어그로성 제목",
        "tags": ["#쇼츠", "#트렌드", "#키워드"],
        "captions": [
            "후킹 텍스트 1줄",
            "공감 텍스트 1줄",
            "해결 텍스트 1줄",
            "해결 텍스트 2줄",
            "CTA 텍스트 1줄"
        ]
    }}
    """
    
    raw_text = call_gemini(prompt)
    
    # JSON 파싱
    raw_text = raw_text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(raw_text)
    except Exception as e:
        print(f"[오류] 대본 생성 실패: {e}")
        print(f"Raw text: {raw_text}")
        return None

if __name__ == "__main__":
    print("=== [100% 무인 쇼츠 자동화 파이프라인 시작] ===")
    print(f"사용 모델: {ACTIVE_MODEL}")

    # 1. 트렌드 분석
    print("\n[1/4] 실시간 트렌드 분석 중...")
    trends = get_daily_trends()
    target_topic = trends[0]
    print(f"-> 선정된 주제: {target_topic}")
    
    # 2. 대본 기획
    print("\n[2/4] AI 쇼츠 대본 기획 중...")
    script = generate_shorts_script(target_topic)
    if not script:
        exit(1)
        
    print(f"-> 제목: {script['title']}")
    print(f"-> 자막 수: {len(script['captions'])}줄")
    
    # 3. 영상 합성 (TTS + 자막 + 배경)
    print("\n[3/4] 음성(TTS) 및 영상 렌더링 시작...")
    output_filename = f"shorts_{int(time.time())}.mp4"
    create_video(script, output_filename)
    
    # 4. 유튜브 자동 업로드
    print("\n[4/4] YouTube 자동 업로드 시작...")
    youtube = get_authenticated_service()
    if youtube:
        upload_video(youtube, output_filename, script['title'], "AI가 자동으로 생성한 쇼츠 영상입니다.", script['tags'])
    else:
        print("-> 유튜브 API 인증이 완료되지 않아 업로드를 건너뜁니다.")
        
    print("\n=== [모든 파이프라인 종료] ===")
