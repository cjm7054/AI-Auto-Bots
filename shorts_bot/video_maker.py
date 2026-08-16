import asyncio
import edge_tts
import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

async def generate_tts(text, output_file="voice.mp3"):
    """edge-tts를 사용하여 한국어 여성 음성(SunHi)으로 텍스트를 음성 파일로 변환"""
    voice = "ko-KR-SunHiNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_file)

def create_dynamic_bg(width=1080, height=1920):
    """자체적으로 다크 그라데이션 + 추상적인 도형 배경을 생성하여 API 차단 문제를 해결"""
    palettes = [
        ((43, 88, 118), (78, 67, 118)),   # 오션 퍼플
        ((100, 43, 115), (198, 66, 110)), # 선셋 핑크
        ((20, 30, 48), (36, 59, 85)),     # 딥 블루 (기존보다 밝음)
        ((17, 153, 142), (56, 239, 125)), # 에메랄드 그린
        ((62, 81, 81), (222, 203, 164)),  # 올리브 샌드
    ]
    c1, c2 = random.choice(palettes)
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # 세로 그라데이션 그리기
    for y in range(height):
        r = int(c1[0] + (c2[0] - c1[0]) * y / height)
        g = int(c1[1] + (c2[1] - c1[1]) * y / height)
        b = int(c1[2] + (c2[2] - c1[2]) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # 은은한 빛(원형) 추가
    for _ in range(5):
        rad = random.randint(300, 800)
        x = random.randint(-200, width)
        y = random.randint(-200, height)
        overlay = Image.new('RGBA', (width, height), (0,0,0,0))
        ImageDraw.Draw(overlay).ellipse([x, y, x+rad, y+rad], fill=(255, 255, 255, 25))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        
    return img

def make_text_frame(text, base_img, width=1080, height=1920):
    """
    미리 준비된 배경 이미지(base_img) 위에 흰색 한글 자막을 생성합니다.
    """
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    
    # 한글 폰트 탐색 (없으면 기본 폰트 사용)
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # Ubuntu 나눔폰트
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",   # Noto CJK
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # 기본 폰트
    ]
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, 65)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # 자막 줄바꿈 처리 (최대 너비 880px)
    max_width = 880
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)

    # 텍스트를 화면 정중앙에 배치
    line_height = 90
    total_h = len(lines) * line_height
    y = (height - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) // 2
        # 그림자 효과 (가독성 향상)
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    return np.array(img)

def create_video(script_data, output_video="output.mp4"):
    """
    JSON 대본을 받아서 각 문장별로 TTS를 생성하고,
    자체 생성한 그라데이션 배경화면 위에 자막 이미지를 만들어 영상으로 합성합니다.
    """
    print("비디오 합성 시작 (PIL 방식)...")
    
    # 1. 고품질 다크 그라데이션 배경 자체 생성 (API 차단 방지)
    print("  프리미엄 배경 생성 중...")
    base_img = create_dynamic_bg(1080, 1920)

    clips = []
    
    for idx, caption in enumerate(script_data['captions']):
        audio_file = f"temp_voice_{idx}.mp3"
        
        # 1. TTS 오디오 생성
        asyncio.run(generate_tts(caption, audio_file))
        
        # 2. 오디오 길이 측정
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration + 0.5
        
        # 3. PIL로 자막 이미지 프레임 생성 (배경 이미지 전달)
        frame = make_text_frame(caption, base_img)
        
        # 4. ImageClip + 오디오 합성
        img_clip = ImageClip(frame).set_duration(duration).set_audio(audio_clip)
        clips.append(img_clip)
        print(f"  [{idx+1}/{len(script_data['captions'])}] 클립 생성 완료: {caption[:20]}...")

    print("전체 클립 이어 붙이기...")
    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
    
    # 임시 오디오 파일 삭제
    for idx in range(len(script_data['captions'])):
        try:
            os.remove(f"temp_voice_{idx}.mp3")
        except:
            pass
    
    print(f"영상 합성 완료! 파일명: {output_video}")

if __name__ == "__main__":
    test_script = {
        "captions": [
            "AI로 100% 무인 쇼츠 만드는 방법?",
            "이거 하나면 진짜 끝납니다.",
            "바로 세인투 자동화 파이프라인!",
            "지금 당장 구독하고 시작하세요!"
        ]
    }
    create_video(test_script, "test_output.mp4")
