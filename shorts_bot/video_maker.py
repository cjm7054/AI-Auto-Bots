import asyncio
import edge_tts
import os
import random
import io
import requests
import urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 몽키패치: Pillow v10 이상에서 Image.ANTIALIAS가 삭제되어 moviepy resize()가 에러를 뿜는 현상 방지
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from moviepy.editor import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips
import moviepy.video.fx.all as vfx

FONT_PATH = "NanumGothicBold.ttf"
# 폰트가 없으면 안정적인 렌더링을 위해 즉시 다운로드 (GitHub Actions 및 Windows 동일 호환)
if not os.path.exists(FONT_PATH):
    print("  [초기화] 텍스트 잘림 방지용 고해상도 나눔고딕 폰트 다운로드 중...")
    urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", FONT_PATH)


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
    
    # 검색을 여러 번 시도하기 위한 키워드 목록 (원본 키워드 -> 범용 키워드 순)
    keywords_to_try = [keyword, "abstract", "background", "nature"]
    
    for kw in keywords_to_try:
        url = f"https://pixabay.com/api/videos/?key={pixabay_key}&q={kw}&video_type=film&orientation=vertical&safesearch=true"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if data.get("totalHits", 0) > 0:
                video_url = data["hits"][0]["videos"]["medium"]["url"]
                print(f"  [{kw}] 비디오 다운로드 중: {video_url}")
                video_resp = requests.get(video_url, stream=True, timeout=30)
                with open(output_filename, 'wb') as f:
                    for chunk in video_resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                print("  비디오 다운로드 완료!")
                return True
            else:
                print(f"  [경고] '{kw}'에 대한 비디오 검색 결과가 없습니다. 다음 키워드 시도...")
        except Exception as e:
            print(f"  [오류] 픽사베이 API 오류 ({kw}): {e}")
            
    print("  [실패] 모든 키워드에 대한 비디오를 찾지 못했습니다.")
    return False

def make_text_frame(text, base_img=None, width=1080, height=1920):
    """
    미리 준비된 배경 이미지(base_img) 위에 흰색 한글 자막을 생성합니다.
    base_img가 없으면 투명 배경(알파 채널)으로 생성합니다.
    """
    if base_img:
        img = base_img.copy().resize((width, height))
    else:
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    draw = ImageDraw.Draw(img)
    
    # 확실히 다운로드된 폰트 사용, 사이즈를 약간 줄여 오버플로우 원천 차단 (65 -> 55)
    font = ImageFont.truetype(FONT_PATH, 55)

    # 자막 줄바꿈 처리 (최대 너비 보수적 설정: 880 -> 800)
    max_width = 800
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
    각 문장에 맞는 스톡 동영상을 다운로드하여 매 문장마다 배경이 바뀌게 합성합니다.
    """
    print("비디오 합성 시작...")
    
    # 구형 데이터를 위한 fallback
    keywords = script_data.get("keywords", [script_data.get("keyword", "business")] * len(script_data['captions']))
    # captions 길이에 맞게 키워드 배열 채우기
    while len(keywords) < len(script_data['captions']):
        keywords.append("abstract")
        
    width, height = 1080, 1920
    clips = []
    total_duration = 0
    
    for idx, caption in enumerate(script_data['captions']):
        kw = keywords[idx]
        bg_video_path = f"temp_bg_{idx}.mp4"
        audio_file = f"temp_voice_{idx}.mp3"
        
        # 1. TTS 오디오 생성
        asyncio.run(generate_tts(caption, audio_file))
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration + 0.5
        
        # 2. 이번 자막에 쓸 비디오 다운로드
        bg_video_clip = None
        if download_pixabay_video(kw, bg_video_path):
            try:
                # 3. 비디오 강제 세로비율(9:16) 맞춤 (가로 영상이 들어와도 찌그러지지 않게 센터 크롭)
                # 먼저 높이를 1920으로 맞춤 (비율 유지)
                raw_clip = VideoFileClip(bg_video_path).resize(height=height)
                # 만약 폭이 1080보다 좁다면 폭을 1080으로 맞춤 (비율 유지)
                if raw_clip.w < width:
                    raw_clip = raw_clip.resize(width=width)
                # 최종적으로 1080x1920 중앙 부분을 잘라냄 (crop)
                bg_video_clip = vfx.crop(raw_clip, x_center=raw_clip.w/2, y_center=raw_clip.h/2, width=width, height=height)
                # 가독성을 위해 살짝 어둡게 (밝기 40%)
                bg_video_clip = bg_video_clip.fx(vfx.colorx, 0.4)
            except Exception as e:
                print(f"  [경고] 비디오 클립 로드 실패: {e}")
                bg_video_clip = None

        # 비디오 다운로드 실패 시 자체 생성 다크 그라데이션 이미지 
        if bg_video_clip is None:
            print("  대체 그라데이션 배경을 사용합니다.")
            base_img = create_dynamic_bg(width, height)
            local_bg = ImageClip(np.array(base_img)).set_duration(duration)
        else:
            # 비디오를 duration만큼 잘라내거나 루프시킴
            local_bg = bg_video_clip.fx(vfx.loop, duration=duration).subclip(0, duration)
            
        # 4. 투명 배경의 자막 프레임 생성
        frame = make_text_frame(caption, base_img=None, width=width, height=height)
        text_clip = ImageClip(frame).set_duration(duration).set_audio(audio_clip)
        
        # 5. 배경 + 자막 합성
        from moviepy.editor import CompositeVideoClip
        img_clip = CompositeVideoClip([local_bg, text_clip]).set_duration(duration)
        
        clips.append(img_clip)
        total_duration += duration
        print(f"  [{idx+1}/{len(script_data['captions'])}] 클립 생성 완료: {caption[:20]}...")

    print("전체 클립 이어 붙이기...")
    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
    
    # 임시 오디오 파일 삭제
    # 임시 파일 정리
    for idx in range(len(script_data['captions'])):
        try:
            os.remove(f"temp_voice_{idx}.mp3")
        except:
            pass
        try:
            os.remove(f"temp_bg_{idx}.mp4")
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
