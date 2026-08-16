import asyncio
import edge_tts
import os
import random
import io
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

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

def download_pixabay_video(keyword, output_filename="bg_video.mp4"):
    """Pixabay API를 통해 키워드에 맞는 세로형 스톡 비디오를 다운로드합니다."""
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    if not pixabay_key:
        print("  [경고] PIXABAY_API_KEY가 없습니다. 픽사베이 영상을 사용할 수 없습니다.")
        return False
        
    print(f"  [{keyword}] 픽사베이 비디오 검색 중...")
    url = f"https://pixabay.com/api/videos/?key={pixabay_key}&q={keyword}&video_type=film&orientation=vertical&safesearch=true"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("totalHits", 0) > 0:
            # 첫 번째 비디오의 medium 사이즈 URL 가져오기
            video_url = data["hits"][0]["videos"]["medium"]["url"]
            print(f"  비디오 다운로드 중: {video_url}")
            video_resp = requests.get(video_url, stream=True, timeout=30)
            with open(output_filename, 'wb') as f:
                for chunk in video_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("  비디오 다운로드 완료!")
            return True
        else:
            print(f"  [경고] '{keyword}'에 대한 비디오 검색 결과가 없습니다.")
            return False
    except Exception as e:
        print(f"  [오류] 픽사베이 비디오 다운로드 실패: {e}")
        return False

def make_text_frame(text, base_img=None, width=1080, height=1920):
    """
    미리 준비된 배경 이미지(base_img) 위에 흰색 한글 자막을 생성합니다.
    base_img가 없으면 투명 배경(알파 채널)으로 생성합니다.
    """
    if base_img:
        img = base_img.copy()
    else:
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
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
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    return np.array(img)

def create_video(script_data, output_video="output.mp4"):
    """
    JSON 대본을 받아서 각 문장별로 TTS를 생성하고,
    스톡 동영상 배경(또는 그라데이션) 위에 자막 클립을 올려 영상으로 합성합니다.
    """
    print("비디오 합성 시작...")
    
    keyword = script_data.get("keyword", "business")
    width, height = 1080, 1920
    
    bg_video_clip = None
    bg_image_clip = None
    bg_video_path = "temp_bg.mp4"
    
    # 1. Pixabay 비디오 다운로드 시도
    if download_pixabay_video(keyword, bg_video_path):
        try:
            # 어둡게 처리 (가독성 확보, colorx 사용)
            bg_video_clip = VideoFileClip(bg_video_path).resize((width, height)).fx(vfx.colorx, 0.4)
        except Exception as e:
            print(f"  [경고] 비디오 클립 로드 실패: {e}")
            bg_video_clip = None

    # 비디오 다운로드 실패 시 대체 이미지 생성
    if bg_video_clip is None:
        print("  동영상 대신 프리미엄 다크 그라데이션 배경을 사용합니다.")
        base_img = create_dynamic_bg(width, height)
        bg_image_clip = ImageClip(np.array(base_img))

    clips = []
    total_duration = 0
    
    for idx, caption in enumerate(script_data['captions']):
        audio_file = f"temp_voice_{idx}.mp3"
        
        # 1. TTS 오디오 생성
        asyncio.run(generate_tts(caption, audio_file))
        
        # 2. 오디오 길이 측정
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration + 0.5
        
        # 3. 투명 배경의 자막 이미지 프레임 생성
        frame = make_text_frame(caption, base_img=None, width=width, height=height)
        
        # 4. ImageClip + 오디오 합성
        text_clip = ImageClip(frame).set_duration(duration).set_audio(audio_clip)
        
        # 5. 배경 위에 자막 얹기
        if bg_video_clip:
            # 현재 시점부터 duration만큼 배경 비디오의 부분을 추출하여 루프(반복)
            # 만약 배경 비디오가 짧으면 loop로 길이를 늘림
            local_bg = bg_video_clip.fx(vfx.loop, duration=duration).subclip(0, duration)
            from moviepy.editor import CompositeVideoClip
            img_clip = CompositeVideoClip([local_bg, text_clip]).set_duration(duration)
        else:
            # 그라데이션 이미지 배경 사용
            local_bg = bg_image_clip.set_duration(duration)
            from moviepy.editor import CompositeVideoClip
            img_clip = CompositeVideoClip([local_bg, text_clip]).set_duration(duration)
            
        clips.append(img_clip)
        total_duration += duration
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
    
    # 리소스 정리
    if bg_video_clip:
        bg_video_clip.close()
    try:
        os.remove(bg_video_path)
    except:
        pass

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
