import asyncio
import edge_tts
import os
from moviepy.editor import ColorClip, TextClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})
async def generate_tts(text, output_file="voice.mp3"):
    """edge-tts를 사용하여 한국어 여성 음성(SunHi)으로 텍스트를 음성 파일로 변환"""
    voice = "ko-KR-SunHiNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+10%") # 속도 10% 빠르게
    await communicate.save(output_file)

def create_video(script_data, output_video="output.mp4"):
    """
    JSON 대본을 받아서 각 문장별로 TTS를 생성하고,
    검은색 세로 배경(1080x1920)에 중앙 자막을 띄우는 숏폼 영상을 합성합니다.
    """
    print("비디오 합성 시작...")
    clips = []
    
    # 윈도우 환경에서 한글 폰트 지정 (폰트가 없으면 깨질 수 있음)
    font_path = "Malgun-Gothic-Bold" # 맑은 고딕
    
    for idx, caption in enumerate(script_data['captions']):
        audio_file = f"temp_voice_{idx}.mp3"
        # 1. TTS 오디오 생성 (비동기 함수 실행)
        asyncio.run(generate_tts(caption, audio_file))
        
        # 2. 오디오 길이 측정
        audio_clip = AudioFileClip(audio_file)
        duration = audio_clip.duration + 0.5 # 자막이 읽히는 시간 + 0.5초 여유
        
        # 3. 9:16 비율(1080x1920)의 검은 배경화면 클립 생성
        bg_clip = ColorClip(size=(1080, 1920), color=(10, 10, 10)).set_duration(duration)
        
        # 4. 텍스트(자막) 클립 생성
        txt_clip = TextClip(caption, fontsize=70, color='white', font=font_path, size=(900, None), method='caption')
        txt_clip = txt_clip.set_position('center').set_duration(duration)
        
        # 5. 배경 + 자막 + 오디오 합성
        video_clip = CompositeVideoClip([bg_clip, txt_clip]).set_audio(audio_clip)
        clips.append(video_clip)
        
    print("문장별 클립 생성 완료. 전체 클립 이어 붙이기...")
    # 6. 모든 클립을 하나로 이어 붙임
    final_video = concatenate_videoclips(clips, method="compose")
    
    # 7. 렌더링 후 파일 저장
    final_video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
    
    # 8. 임시 오디오 파일 삭제
    for idx in range(len(script_data['captions'])):
        try:
            os.remove(f"temp_voice_{idx}.mp3")
        except:
            pass
            
    print(f"영상 합성 완료! 파일명: {output_video}")

if __name__ == "__main__":
    # 테스트용 대본 데이터
    test_script = {
        "captions": [
            "AI로 100% 무인 쇼츠 만드는 방법?",
            "이거 하나면 진짜 끝납니다.",
            "바로 세인투 자동화 파이프라인을 쓰는 거죠.",
            "지금 당장 시작해보세요!"
        ]
    }
    create_video(test_script, "test_output.mp4")
