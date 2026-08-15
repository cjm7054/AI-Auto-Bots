"""
진단 스크립트: 이 API 키로 사용 가능한 Gemini 모델 전체 목록을 출력합니다.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("[오류] GEMINI_API_KEY 환경변수가 비어있습니다!")
    exit(1)

print(f"API 키 앞 10자리: {API_KEY[:10]}...")
print("=" * 60)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
try:
    response = requests.get(url, timeout=30)
    print(f"HTTP 응답 코드: {response.status_code}")
    
    if response.status_code != 200:
        print(f"응답 내용: {response.text}")
        exit(1)
        
    data = response.json()
    models = data.get("models", [])
    print(f"\n총 모델 수: {len(models)}개\n")
    
    for m in models:
        name = m.get("name", "")
        display = m.get("displayName", "")
        methods = m.get("supportedGenerationMethods", [])
        can_generate = "✅ generateContent 가능" if "generateContent" in methods else "❌ generateContent 불가"
        print(f"  {name} ({display})")
        print(f"    -> {can_generate} | 지원 메서드: {methods}")
        
except Exception as e:
    print(f"[오류] API 호출 실패: {e}")
