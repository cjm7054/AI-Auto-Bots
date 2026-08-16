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
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

import re
from wordpress_uploader import upload_to_wordpress
from blogger_uploader import upload_to_blogger

def extract_title_and_content(markdown_text):
    lines = markdown_text.strip().split('\n')
    title = "블로그 자동 생성 포스팅"
    if lines:
        title = re.sub(r'^#+\s*', '', lines[0]).strip()
        content = '\n'.join(lines[1:]).strip()
    return title, content

if __name__ == "__main__":
    test_topic = "초보자를 위한 AI 부업 시작하기"
    test_persona = "친근하고 유머러스한 동네 형 느낌, 짧고 간결한 문장 사용"
    print(f"[{test_topic}] 블로그 포스팅 작성 중...\n")
    post = generate_blog_post(test_topic, test_persona)
    
    print("--- 생성된 글 ---")
    print(post)
    print("-----------------")
    
    title, content = extract_title_and_content(post)
    
    print("\n[업로드 시작]")
    upload_to_wordpress(title, content)
    upload_to_blogger(title, content)
    print("\n[모든 작업 완료]")
