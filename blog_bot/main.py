import os
import re
from google import genai
from dotenv import load_dotenv

from wordpress_uploader import upload_to_wordpress
from blogger_uploader import upload_to_blogger

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

# 쉼표로 여러 모델을 넣을 수 있음.
# 예:
# GEMINI_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite,gemini-2.5-pro
DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]

env_models = os.getenv("GEMINI_MODELS", "").strip()
MODELS_TO_TRY = [m.strip() for m in env_models.split(",") if m.strip()] if env_models else DEFAULT_MODELS


def generate_blog_post(topic, persona_keywords):
    prompt = f"""
당신은 10년 차 전문 블로거입니다.
작성 주제: {topic}
작성자 페르소나(문체): {persona_keywords}

[세이프 블로그 자동화 프롬프트 지시사항]
다음 3단계(CoT)를 거쳐 블로그 포스팅을 완성하세요.

1단계 [기획]:
주제에 대해 타깃 독자가 궁금해할 만한 소주제 3가지를 도출하세요.

2단계 [구조화]:
서론(공감) - 본론(소주제 3가지) - 결론(요약 및 행동 유도) 형태의 개요를 작성하세요.

3단계 [작성]:
개요를 바탕으로 주어진 '페르소나(문체)'를 완벽히 반영하여 실제 네이버/티스토리 블로그에 바로 올릴 수 있는 완성형 글을 작성하세요.

중요:
- 최종 결과물은 3단계 [작성] 결과만 출력하세요.
- 1단계, 2단계 사고 과정은 절대 노출하지 마세요.
- 제목은 문서 첫 줄의 Markdown 제목(# 제목) 형태로 작성하세요.
- 본문은 자연스럽고 읽기 쉽게 작성하세요.
- 과도한 이모지, 과도한 특수기호는 사용하지 마세요.
- 문체는 사람이 직접 쓴 것처럼 자연스럽게 유지하세요.
"""

    last_error = None

    for model in MODELS_TO_TRY:
        try:
            print(f"[시도] Gemini 모델: {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            text = getattr(response, "text", None)
            if text and text.strip():
                print(f"[성공] 모델 사용 완료: {model}")
                return text.strip()

            raise ValueError(f"{model} 응답에서 text를 추출하지 못했습니다.")

        except Exception as e:
            print(f"[실패] 모델 {model}: {e}")
            last_error = e

    raise RuntimeError(f"모든 Gemini 모델 호출 실패. 마지막 오류: {last_error}")


def extract_title_and_content(markdown_text):
    lines = markdown_text.strip().split("\n")
    title = "블로그 자동 생성 포스팅"
    content = markdown_text.strip()

    if lines:
        first_line = lines[0].strip()

        # 첫 줄이 '# 제목' 형식이면 제목으로 사용
        if first_line.startswith("#"):
            title = re.sub(r"^#+\s*", "", first_line).strip()
            content = "\n".join(lines[1:]).strip()
        else:
            # 첫 줄을 제목처럼 간주할 수 있으면 사용
            if len(first_line) <= 80:
                title = first_line
                content = "\n".join(lines[1:]).strip() if len(lines) > 1 else markdown_text.strip()

    return title, content


if __name__ == "__main__":
    test_topic = "초보자를 위한 AI 부업 시작하기"
    test_persona = "친근하고 유머러스한 동네 형 느낌, 짧고 간결한 문장 사용"

    print(f"[test_topic] 블로그 포스팅 작성 중...\n")
    post = generate_blog_post(test_topic, test_persona)

    print("=== 생성된 글 ===")
    print(post)
    print("=================")

    title, content = extract_title_and_content(post)

    print("\n[업로드 시작]")
    upload_to_wordpress(title, content)
    upload_to_blogger(title, content)
    print("\n[모든 작업 완료]")
