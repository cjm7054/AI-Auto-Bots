import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Claude 클라이언트 초기화 (Gemini 전환 시 genai 사용)
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_commerce_copy(product_name, competitor_flaws):
    prompt = f"""
    당신은 월매출 1억을 내는 스마트스토어 카피라이터입니다.
    현재 소싱한 제품: {product_name}
    경쟁사 상위 제품들의 주요 단점(리뷰 분석 결과): {competitor_flaws}
    
    [세인투 사입 만능 프롬프트 지시사항]
    1. 경쟁사의 단점을 바탕으로 고객이 느끼는 '진짜 결핍(Pain Point)'이 무엇인지 1문장으로 정의하세요.
    2. 그 결핍을 완벽하게 해결해 줄 수 있는 우리 제품만의 '셀링 포인트(UVP)' 3가지를 도출하세요.
    3. 도출된 셀링 포인트를 활용하여 상세페이지 도입부에 들어갈 '전환율을 높이는 카피(약 3문단)'를 작성하세요.
    
    결과물을 순서대로 출력해 주세요.
    """
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return message.content[0].text

if __name__ == "__main__":
    product = "무선 차량용 청소기"
    flaws = "1. 흡입력이 약하다. 2. 배터리가 10분만에 닳는다. 3. 소음이 너무 크다."
    print(f"[{product}] 상세페이지 카피 작성 중...\n")
    copy = generate_commerce_copy(product, flaws)
    print(copy)
