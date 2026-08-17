import os
import re
import math
import asyncio
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
if not hasattr(Image, "LANCZOS"):
    Image.LANCZOS = Image.Resampling.LANCZOS

from moviepy.editor import (
    AudioFileClip,
    VideoFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ImageClip,
    ColorClip,
    concatenate_videoclips,
)
from moviepy.audio.fx.all import audio_loop, volumex, audio_fadein, audio_fadeout
from moviepy.video.fx.all import fadein, fadeout, loop

import edge_tts
from license_registry import init_manifest, add_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("video_maker")

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
TTS_DIR = CACHE_DIR / "tts"
BG_DIR = CACHE_DIR / "backgrounds"
TEMP_DIR = CACHE_DIR / "temp"
ASSETS_DIR = BASE_DIR / "assets"
for d in [CACHE_DIR, TTS_DIR, BG_DIR, TEMP_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

WIDTH = 1080
HEIGHT = 1920
FPS = 24

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
VOICE_NAME = os.getenv("SHORTS_VOICE_NAME", "ko-KR-SunHiNeural").strip()
VOICE_RATE = os.getenv("SHORTS_VOICE_RATE", "+6%").strip()
BRAND_NAME = os.getenv("SHORTS_BRAND_NAME", "AI 이슈 브리핑").strip()
BGM_PATH = Path(os.getenv("SHORTS_BGM_PATH", str(ASSETS_DIR / "bgm_news.mp3")))

CATEGORY_THEMES = {
    "politics": {"primary": (59, 130, 246), "secondary": (16, 78, 139), "accent": (147, 197, 253), "label": "정치"},
    "society": {"primary": (14, 165, 233), "secondary": (12, 74, 110), "accent": (103, 232, 249), "label": "사회"},
    "economy": {"primary": (16, 185, 129), "secondary": (6, 78, 59), "accent": (110, 231, 183), "label": "경제"},
    "entertainment": {"primary": (217, 70, 239), "secondary": (126, 34, 206), "accent": (233, 213, 255), "label": "연예"},
    "general": {"primary": (249, 115, 22), "secondary": (154, 52, 18), "accent": (254, 215, 170), "label": "종합"},
}
FALLBACK_VISUAL_QUERIES = {
    "politics": ["government building", "city parliament", "news background"],
    "society": ["city people", "hospital city", "urban lifestyle"],
    "economy": ["business district", "stock market", "financial building"],
    "entertainment": ["concert lights", "stage lights", "night city"],
    "general": ["digital background", "city skyline", "news background"],
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
]


def find_font_path():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


FONT_PATH = find_font_path()


def get_font(size: int):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size=size)
    return ImageFont.load_default()


def safe_name(text: str):
    text = re.sub(r"[^\w가-힣\s-]", "", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text[:60] or "item"


def md5hex(text: str):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def pil_to_imageclip(img: Image.Image, duration: float, pos=("center", "center")):
    return ImageClip(np.array(img)).set_duration(duration).set_position(pos)


def fit_vertical(clip):
    scale = max(WIDTH / clip.w, HEIGHT / clip.h)
    clip = clip.resize(scale)
    return clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=WIDTH, height=HEIGHT)


async def _tts_async(text: str, output_path: str):
    communicate = edge_tts.Communicate(text=text, voice=VOICE_NAME, rate=VOICE_RATE)
    await communicate.save(output_path)


def synthesize_tts(text: str, output_path: str):
    try:
        asyncio.run(_tts_async(text, output_path))
    except RuntimeError:
        loop_obj = asyncio.new_event_loop()
        asyncio.set_event_loop(loop_obj)
        loop_obj.run_until_complete(_tts_async(text, output_path))
        loop_obj.close()


def make_dynamic_background(duration: float, theme: Dict, seed_text: str):
    seed = int(md5hex(seed_text)[:8], 16) % 10000
    c1 = np.array(theme["primary"], dtype=np.float32)
    c2 = np.array(theme["secondary"], dtype=np.float32)
    c3 = np.array(theme["accent"], dtype=np.float32)

    xs = np.linspace(0, 1, WIDTH, dtype=np.float32)
    ys = np.linspace(0, 1, HEIGHT, dtype=np.float32)
    X, Y = np.meshgrid(xs, ys)

    def make_frame(t):
        shift = 0.07 * math.sin((t * 0.3) + seed * 0.001)
        mix = np.clip((X * 0.62 + Y * 0.38 + shift), 0, 1)[..., None]
        base = c1 * (1 - mix) + c2 * mix

        cx = 0.58 + 0.1 * math.sin(t * 0.45 + seed * 0.003)
        cy = 0.38 + 0.08 * math.cos(t * 0.3 + seed * 0.004)
        radial = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        glow = np.clip(1 - radial * 1.7, 0, 1)[..., None]

        frame = base * (1 - 0.18 * glow) + c3 * (0.22 * glow)
        return np.clip(frame, 0, 255).astype(np.uint8)

    from moviepy.video.VideoClip import VideoClip
    return VideoClip(make_frame, duration=duration).set_fps(FPS)


def search_pixabay_video(query: str, category: str) -> Optional[str]:
    if not PIXABAY_API_KEY:
        return None

    queries = [query] + FALLBACK_VISUAL_QUERIES.get(category, [])
    headers = {"User-Agent": "Mozilla/5.0"}

    for q in queries:
        try:
            resp = requests.get(
                "https://pixabay.com/api/videos/",
                params={
                    "key": PIXABAY_API_KEY,
                    "q": q,
                    "per_page": 8,
                    "safesearch": "true",
                    "order": "popular",
                },
                headers=headers,
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
            best_url = None
            best_score = -1
            for hit in data.get("hits", []):
                videos = hit.get("videos", {})
                for quality_name in ["large", "medium", "small", "tiny"]:
                    info = videos.get(quality_name)
                    if not info:
                        continue
                    video_url = info.get("url")
                    w = info.get("width", 0)
                    h = info.get("height", 0)
                    if not video_url or not w or not h:
                        continue
                    ratio = w / max(h, 1)
                    score = (w * h) - (abs(ratio - (9 / 16)) * 200000)
                    if score > best_score:
                        best_score = score
                        best_url = video_url
            if best_url:
                return best_url
        except Exception as e:
            logger.warning(f"Pixabay 검색 실패 | q={q} | error={e}")
    return None


def download_file(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    return dest


def load_background_clip(keyword: str, category: str, duration: float, theme: Dict, manifest_path: str):
    bg_url = search_pixabay_video(keyword, category)
    if bg_url:
        dest = BG_DIR / f"{md5hex(keyword + category)}.mp4"
        try:
            download_file(bg_url, dest)
            add_asset(manifest_path, {
                "type": "video_background",
                "provider": "Pixabay",
                "query": keyword,
                "source_url": bg_url,
                "saved_path": str(dest),
                "downloaded_at": datetime.utcnow().isoformat() + "Z",
                "usage_note": "자료화면 / representative footage",
                "license_reference": "https://pixabay.com/service/license-summary/"
            })
            clip = VideoFileClip(str(dest)).without_audio()
            clip = fit_vertical(clip)
            if clip.duration < duration:
                clip = clip.fx(loop, duration=duration)
            else:
                clip = clip.subclip(0, duration)
            return clip
        except Exception as e:
            logger.warning(f"배경 영상 로드 실패 | {keyword} | {e}")

    add_asset(manifest_path, {
        "type": "generated_background",
        "provider": "internal_dynamic_background",
        "query": keyword,
        "source_url": None,
        "saved_path": None,
        "downloaded_at": datetime.utcnow().isoformat() + "Z",
        "usage_note": "non-photoreal abstract background"
    })
    return make_dynamic_background(duration, theme, keyword)


def rounded_panel(size, radius, fill, outline=None, outline_width=0):
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((12, 12, w - 4, h - 4), radius=radius, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(shadow)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=fill, outline=outline, width=outline_width)
    return img


def wrap_text(text: str, font, max_width: int):
    dummy = Image.new("RGBA", (max_width, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    words = text.split()
    if len(words) <= 1:
        chunks, cur = [], ""
        for ch in text:
            test = cur + ch
            bbox = draw.textbbox((0, 0), test, font=font, stroke_width=3)
            if (bbox[2] - bbox[0]) <= max_width or not cur:
                cur = test
            else:
                chunks.append(cur)
                cur = ch
        if cur:
            chunks.append(cur)
        return chunks

    lines, cur = [], ""
    for w in words:
        test = w if not cur else cur + " " + w
        bbox = draw.textbbox((0, 0), test, font=font, stroke_width=3)
        if (bbox[2] - bbox[0]) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(text: str, max_width: int, max_lines: int, start_size: int, min_size: int):
    for size in range(start_size, min_size - 1, -2):
        font = get_font(size)
        lines = wrap_text(text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = get_font(min_size)
    lines = wrap_text(text, font, max_width)
    return font, lines[:max_lines]


def make_badge(text: str, theme: Dict, min_width: int = 160):
    font = get_font(40)
    dummy = Image.new("RGBA", (500, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w = max(min_width, tw + 56)
    h = th + 30
    img = rounded_panel((w, h), 24, theme["primary"] + (235,))
    draw = ImageDraw.Draw(img)
    draw.text(((w - tw) // 2, (h - th) // 2 - 2), text, font=font, fill=(255, 255, 255, 255))
    return img


def make_watermark():
    font = get_font(28)
    text = BRAND_NAME
    dummy = Image.new("RGBA", (500, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + 40, th + 24
    img = rounded_panel((w, h), 18, (0, 0, 0, 120))
    draw = ImageDraw.Draw(img)
    draw.text((20, (h - th) // 2 - 1), text, font=font, fill=(255, 255, 255, 230))
    return img


def make_source_label():
    font = get_font(28)
    text = "자료화면 / representative footage"
    dummy = Image.new("RGBA", (700, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w, h = tw + 40, th + 22
    img = rounded_panel((w, h), 18, (0, 0, 0, 130))
    draw = ImageDraw.Draw(img)
    draw.text((20, (h - th) // 2 - 1), text, font=font, fill=(255, 255, 255, 220))
    return img


def make_caption_panel(text: str, theme: Dict):
    panel_width = 930
    font, lines = fit_text(text, 820, 3, 74, 44)
    dummy = Image.new("RGBA", (panel_width, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        heights.append(bbox[3] - bbox[1])
    content_height = sum(heights) + 14 * (len(lines) - 1 if len(lines) > 1 else 0)
    panel_height = content_height + 110
    img = rounded_panel((panel_width, panel_height), 42, (10, 14, 22, 190), outline=theme["accent"] + (130,), outline_width=4)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((24, 22, panel_width - 24, 34), radius=6, fill=theme["accent"] + (235,))
    y = 58
    for line, h in zip(lines, heights):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        w = bbox[2] - bbox[0]
        x = (panel_width - w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 180))
        y += h + 14
    return img


def make_intro_card(title: str, category_label: str, slot: str, theme: Dict):
    card = Image.new("RGBA", (920, 820), (0, 0, 0, 0))
    card.alpha_composite(rounded_panel((920, 820), 50, (8, 12, 20, 178)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((34, 34, 886, 48), radius=6, fill=theme["accent"] + (255,))
    label = make_badge(category_label, theme)
    card.alpha_composite(label, (60, 82))
    small_font = get_font(34)
    mode_text = f"{slot}:00 브리핑"
    bbox = draw.textbbox((0, 0), mode_text, font=small_font)
    draw.text((920 - 60 - (bbox[2] - bbox[0]), 98), mode_text, font=small_font, fill=(255, 255, 255, 220))
    big_font, lines = fit_text(title, 780, 4, 86, 48)
    y = 250
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=big_font, stroke_width=3)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((920 - tw) // 2, y), line, font=big_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 170))
        y += th + 12
    footer = "핵심만 빠르게 정리합니다"
    footer_font = get_font(36)
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    draw.text(((920 - (bbox[2] - bbox[0])) // 2, 690), footer, font=footer_font, fill=theme["accent"] + (235,))
    return card


def make_outro_card(theme: Dict):
    card = Image.new("RGBA", (920, 720), (0, 0, 0, 0))
    card.alpha_composite(rounded_panel((920, 720), 48, (8, 12, 20, 168)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((34, 34, 886, 48), radius=6, fill=theme["accent"] + (255,))
    font1 = get_font(74)
    font2 = get_font(38)
    lines = ["핵심 흐름은 계속 바뀝니다", "다음 브리핑에서 이어집니다"]
    y = 180
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font1, stroke_width=3)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((920 - tw) // 2, y), line, font=font1, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 160))
        y += th + 18
    sub = "자료화면과 해설 중심으로 구성된 브리핑입니다"
    bbox = draw.textbbox((0, 0), sub, font=font2)
    draw.text(((920 - (bbox[2] - bbox[0])) // 2, 520), sub, font=font2, fill=theme["accent"] + (255,))
    return card


def attach_bgm(video):
    if not BGM_PATH.exists():
        return video
    try:
        bgm = AudioFileClip(str(BGM_PATH))
        bgm = bgm.fx(audio_loop, duration=video.duration)
        bgm = bgm.fx(volumex, 0.10)
        bgm = bgm.fx(audio_fadein, 0.25).fx(audio_fadeout, 0.4)
        final_audio = CompositeAudioClip([bgm, video.audio.fx(volumex, 1.15)]) if video.audio is not None else bgm
        return video.set_audio(final_audio)
    except Exception as e:
        logger.warning(f"BGM 적용 실패: {e}")
        return video


def make_scene_clip(caption_item: Dict, idx: int, total: int, theme: Dict, meta: Dict, manifest_path: str):
    text = caption_item.get("text", "").strip()
    duration_hint = float(caption_item.get("duration", 4.2))
    keyword = caption_item.get("background_keyword") or caption_item.get("keyword") or meta.get("category_label", "뉴스")
    category = meta.get("category", "general")

    tts_file = TTS_DIR / f"{md5hex(text)}.mp3"
    if not tts_file.exists() or tts_file.stat().st_size < 5000:
        synthesize_tts(text, str(tts_file))

    add_asset(manifest_path, {
        "type": "tts_audio",
        "provider": "edge_tts",
        "voice": VOICE_NAME,
        "text_excerpt": text[:80],
        "saved_path": str(tts_file),
        "generated_at": datetime.utcnow().isoformat() + "Z"
    })

    narration_audio = AudioFileClip(str(tts_file)).fx(audio_fadein, 0.04).fx(audio_fadeout, 0.1)
    duration = max(duration_hint, narration_audio.duration + 0.5)

    bg = load_background_clip(keyword, category, duration, theme, manifest_path)
    scrim = ColorClip((WIDTH, HEIGHT), color=(0, 0, 0)).set_opacity(0.28).set_duration(duration)
    caption_panel = pil_to_imageclip(make_caption_panel(text, theme), duration=duration, pos=("center", 1010))
    badge = pil_to_imageclip(make_badge(meta.get("category_label", "종합"), theme), duration=duration, pos=(60, 86))
    watermark = pil_to_imageclip(make_watermark(), duration=duration, pos=(WIDTH - 260, 86))
    rep = pil_to_imageclip(make_source_label(), duration=duration, pos=(50, HEIGHT - 210))
    scene_label = pil_to_imageclip(make_badge(f"{idx+1}/{total}", theme, min_width=120), duration=duration, pos=(WIDTH - 180, 174))
    bar_w, bar_h = 760, 10
    x, y = (WIDTH - bar_w) // 2, HEIGHT - 150
    base_bar = ColorClip((bar_w, bar_h), color=(255, 255, 255)).set_opacity(0.18).set_duration(duration).set_position((x, y))
    fill_w = max(18, int(bar_w * ((idx + 1) / max(total, 1))))
    fill_bar = ColorClip((fill_w, bar_h), color=theme["accent"]).set_opacity(0.95).set_duration(duration).set_position((x, y))

    clip = CompositeVideoClip([bg, scrim, caption_panel, badge, watermark, rep, scene_label, base_bar, fill_bar], size=(WIDTH, HEIGHT)).set_duration(duration)
    clip = clip.fx(fadein, 0.12).fx(fadeout, 0.18)
    clip = clip.set_audio(narration_audio.set_start(0.12))
    return clip


def create_video(script: Dict, output_filename: Optional[str] = None) -> str:
    captions = script.get("captions", [])
    if not captions:
        raise ValueError("script['captions'] 가 비어 있습니다.")

    meta = script.get("meta", {}) or {}
    category = meta.get("category", "general")
    theme = CATEGORY_THEMES.get(category, CATEGORY_THEMES["general"])
    title = script.get("title") or script.get("search_keyword") or "오늘의 이슈 브리핑"
    if output_filename is None:
        output_filename = str(BASE_DIR / "outputs" / f"{safe_name(title)}.mp4")

    output_path = Path(output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = str(output_path.with_suffix(".assets.json"))
    init_manifest(manifest_path=manifest_path, video_title=title, topic=script.get("search_keyword", title), category=category)

    clips = []
    intro_bg = make_dynamic_background(1.8, theme, title + "_intro")
    intro_card = pil_to_imageclip(make_intro_card(title, meta.get("category_label", "종합"), meta.get("slot", "00"), theme), duration=1.8, pos=("center", 540))
    intro_scrim = ColorClip((WIDTH, HEIGHT), color=(0, 0, 0)).set_opacity(0.26).set_duration(1.8)
    intro = CompositeVideoClip([intro_bg, intro_scrim, intro_card], size=(WIDTH, HEIGHT)).set_duration(1.8).fx(fadein, 0.08).fx(fadeout, 0.14)
    clips.append(intro)

    total = len(captions)
    for idx, item in enumerate(captions):
        clips.append(make_scene_clip(item, idx, total, theme, meta, manifest_path))

    outro_bg = make_dynamic_background(1.6, theme, title + "_outro")
    outro_card = pil_to_imageclip(make_outro_card(theme), duration=1.6, pos=("center", 620))
    outro_scrim = ColorClip((WIDTH, HEIGHT), color=(0, 0, 0)).set_opacity(0.28).set_duration(1.6)
    outro = CompositeVideoClip([outro_bg, outro_scrim, outro_card], size=(WIDTH, HEIGHT)).set_duration(1.6).fx(fadein, 0.08).fx(fadeout, 0.14)
    clips.append(outro)

    final_video = concatenate_videoclips(clips, method="compose")
    final_video = attach_bgm(final_video)
    final_video.write_videofile(
        str(output_path), fps=FPS, codec="libx264", audio_codec="aac", preset="medium", bitrate="6000k", threads=4,
        temp_audiofile=str(TEMP_DIR / "temp-audio.m4a"), remove_temp=True,
    )

    try:
        final_video.close()
    except Exception:
        pass
    for c in clips:
        try:
            c.close()
        except Exception:
            pass

    logger.info(f"비디오 생성 완료: {output_path}")
    logger.info(f"라이선스 매니페스트 생성: {manifest_path}")
    return str(output_path)
