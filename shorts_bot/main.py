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

def get_available_model():
    """사용 가능한 Gemini 모델 목록을 확인하고 첫 번째 텍스트 모델을 반환합니다."""
    url = f"{GEMINI_BASE_URL}/models?key={GEMINI_API_KEY}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    models = response.json().get("models", [])
    print("[진단] 사용 가능한 모델 목록:")
    for m in models:
        name = m.get("name", "")
        # generateContent를 지원하는 텍스트 모델만 필터링
        supported = m.get("supportedGenerationMethods", [])
        if "generateContent" in supported:
            print(f"  ✅ {name}")
    # generateContent 지원 모델 중 첫 번째 flash 모델 반환
    for m in models:
        name = m.get("name", "")
        supported = m.get("supportedGenerationMethods", [])
        if "generateContent" in supported and "flash" in name:
            return name.replace("models/", "")
    # flash가 없으면 첫 번째 generateContent 지원 모델 반환
    for m in models:
        name = m.get("name", "")
        supported = m.get("supportedGenerationMethods", [])
        if "generateContent" in supported:
            return name.replace("models/", "")
    return None

def call_gemini(prompt, model_name):
    """Gemini REST API를 직접 호출하여 텍스트를 생성합니다."""
    url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    response = requests.post(url, json=body, headers=headers, timeout=60)
    response.raise_for_status()
    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

def generate_shorts_script(topic, model_name):
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
    
    raw_text = call_gemini(prompt, model_name)
    
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

    # 0. 사용 가능한 Gemini 모델 자동 탐색
    print("\n[0/4] 사용 가능한 Gemini 모델 탐색 중...")
    active_model = get_available_model()
    if not active_model:
        print("[치명적 오류] 사용 가능한 Gemini 모델이 없습니다. API 키를 확인해주세요.")
        exit(1)
    print(f"-> 선택된 모델: {active_model}")

    # 1. 트렌드 분석
    print("\n[1/4] 실시간 트렌드 분석 중...")
    trends = get_daily_trends()
    target_topic = trends[0]
    print(f"-> 선정된 주제: {target_topic}")
    
    # 2. 대본 기획
    print("\n[2/4] AI 쇼츠 대본 기획 중...")
    script = generate_shorts_script(target_topic, active_model)
    if not script:
        exit(1)
        
    print(f"-> 제목: {script['title']}")
    
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
