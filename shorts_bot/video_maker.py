import asyncio
import edge_tts
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

async def generate_tts(text, output_file="voice.mp3"):
    """edge-tts를 사용하여 한국어 여성 음성(SunHi)으로 텍스트를 음성 파일로 변환"""
    voice = "ko-KR-SunHiNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output_file)

def make_text_frame(text, width=1080, height=1920):
    """
    PIL(Pillow)로 검은 배경 + 흰색 한글 자막 이미지를 생성합니다.
    ImageMagick 불필요, 어디서나 작동합니다.
    """
    img = Image.new('RGB', (width, height), color=(10, 10, 10))
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
    PIL로 자막 이미지를 만들어 영상으로 합성합니다. (ImageMagick 불필요)
    """
    print("비디오 합성 시작 (PIL 방식)...")
    clips = []
    
    for idx, caption in enumerate(script_data['captions']):
        audio_file = f"temp_voice_{idx}.mp3"
        
        # 1. TTS 오디오 생성
        asyncio.run(generate_tts(caption, audio_file))
        
        # 2. 오디오 길이 측정
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration + 0.5
        
        # 3. PIL로 자막 이미지 프레임 생성
        frame = make_text_frame(caption)
        
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
