import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_blog_post(topic, persona_keywords):
    prompt = f"""
    당신은 10년 차 전문 블로거입니다. 
    작성 주제: {topic}
    작성자 페르소나(문체): {persona_keywords}
    
    [세인투 블로그 자동화 프롬프트 지시사항]
    다음 3단계(CoT)를 거쳐 블로그 포스팅을 완성하세요.
    
    1단계 [기획]: 주제에 대해 타겟 독자가 궁금해할 만한 소주제 3가지를 도출하세요.
    2단계 [구조화]: 서론(공감) - 본론(소주제 3가지) - 결론(요약 및 행동 유도) 형태의 개요를 작성하세요.
    3단계 [작성]: 개요를 바탕으로 주어진 '페르소나(문체)'를 완벽히 반영하여 실제 네이버/티스토리 블로그에 바로 올릴 수 있는 분량(공백 포함 1500자 내외)의 마크다운 포스팅을 작성하세요.
    
    최종 결과물은 [3단계 작성] 결과물만 출력해 주십시오. (1, 2단계는 내부 사고 과정으로만 사용하고 감추세요.)
    """
    
    response = client.models.generate_content(
        model='gemini-3.7-flash',
        contents=prompt,
    )
    return response.text

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shorts_bot.trend_analyzer import get_daily_trends
except ImportError:
    get_daily_trends = None

from wordpress_uploader import upload_to_wordpress
from blogger_uploader import upload_to_blogger

if __name__ == "__main__":
    print("=== [100% 무인 블로그 자동화 파이프라인 시작] ===")
    
    # 1. 트렌드 분석
    if get_daily_trends:
        print("\n[1/3] 실시간 트렌드 분석 중...")
        trends = get_daily_trends()
        test_topic = trends[0]
    else:
        test_topic = "초보자를 위한 AI 부업 시작하기"
        
    test_persona = "전문적이고 신뢰감을 주는 IT 에디터, 가독성 높은 문장 사용"
    print(f"-> 선정된 주제: {test_topic}")
    
    # 2. 포스팅 작성
    print("\n[2/3] AI 블로그 포스팅 작성 중...")
    post = generate_blog_post(test_topic, test_persona)
    
    # 제목과 본문 분리 (마크다운의 첫 번째 # 제목 줄을 찾음)
    lines = post.split('\n')
    title = test_topic
    content = post
    for i, line in enumerate(lines):
        if line.strip().startswith('# '):
            title = line.strip().replace('# ', '', 1)
            content = '\n'.join(lines[i+1:]).strip()
            break
            
    print(f"-> 추출된 제목: {title}")
    
    # 3. 자동 업로드
    print("\n[3/3] 블로그 자동 업로드 시작...")
    
    # 워드프레스 업로드
    wp_success = upload_to_wordpress(title, content)
    if wp_success:
        print("-> 워드프레스 업로드 완료!")
        
    # 블로거 업로드
    blogger_success = upload_to_blogger(title, content, labels=["AI부업", "트렌드"])
    if blogger_success:
        print("-> 구글 블로거 업로드 완료!")
        
    print("\n=== [모든 파이프라인 종료] ===")
