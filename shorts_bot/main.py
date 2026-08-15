import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Gemini 클라이언트 초기화 (Claude 전환 시 anthropic 라이브러리 사용)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_shorts_script(topic):
    prompt = f"""
    당신은 100만 유튜버를 기획하는 숏폼/릴스 전문 대본 기획자입니다.
    주제: {topic}
    
    [CoT 지시사항: 아래 단계에 따라 차근차근 생각하고 결과를 작성하세요]
    1. 이 주제에 대해 사람들이 흔히 겪는 '결핍'이나 '오해' 3가지를 구상하세요.
    2. 그 중 가장 자극적이고 공감되는 포인트를 골라 '초반 3초 후킹 문구'를 작성하세요.
    3. 전체 대본을 [후킹] -> [공감대 형성] -> [명확한 해결책] -> [CTA(행동유도)] 구조로 1분 이내 분량(약 400자)으로 작성하세요.
    
    [출력 형식]
    === 기획 의도 ===
    (1, 2번 과정 요약)
    
    === 완성된 대본 ===
    (3번 결과물)
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

if __name__ == "__main__":
    test_topic = "직장인 부업으로 전자책 쓰는 법"
    print(f"[{test_topic}] 숏폼 대본 생성 중...\n")
    script = generate_shorts_script(test_topic)
    print(script)
