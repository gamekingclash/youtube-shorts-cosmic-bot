import asyncio
import base64
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import edge_tts
import imageio_ffmpeg
import numpy as np
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_long"
TEMP_DIR = BASE_DIR / "temp_long"
LONG_HISTORY_FILE = BASE_DIR / "long_history.json"
USED_CLIPS_FILE = BASE_DIR / "used_clips.json"

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

FORBIDDEN_TAGS = {
    "dog", "cat", "pet", "puppy", "kitten", "animal", "insect", "bee",
    "stickman", "cartoon", "baby", "kid", "child", "massage", "spa", "flower",
    "yoga", "fitness", "horror", "creepy", "blood", "zombie", "cute", "funny",
    "green screen", "greenscreen", "chroma", "chromakey", "template",
    "subscribe", "button", "animation", "3d", "vfx", "isolated", "emoji"
}

COSMIC_VIDEO_QUERIES = [
    "deep space galaxy stars nebulae",
    "black hole space accretion disk",
    "planet earth orbiting space cinematic",
    "milky way stars night sky dark",
    "supernova cosmic explosion stars",
    "alien planet surface exoplanet horizon",
    "solar flare sun surface cosmic",
    "telescope observatory night sky stars",
]

COSMIC_PHOTO_QUERIES = [
    "james webb deep field galaxy space",
    "pillars of creation eagle nebula",
    "spiral galaxy deep space telescope",
    "black hole event horizon space",
    "saturn rings planet astronomy",
    "northern lights aurora starry sky",
    "nebula cosmic dust stars space",
]

CURATED_LONG_TOPICS = [
    "What Lies Beyond the Edge of the Observable Universe?",
    "The Terrifying Reality of Supermassive Black Holes",
    "Rogue Planets: The Ghost Worlds Wandering in Cold Darkness",
    "The Great Attractor: The Mysterious Force Pulling Our Entire Galaxy",
    "What Will Actually Happen at the Heat Death of the Universe?",
    "James Webb's Mind-Bending Discoveries That Shook Modern Physics",
    "The Silent Cosmos: The Dark Reality of the Fermi Paradox",
    "Neutron Stars: Objects So Dense That Physics Completely Breaks Down",
    "The Multiverse Theory: Are Infinite Realities Actually Real?",
]


def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def load_json_list(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_json_list(path: Path, data: list):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_used_clips() -> set:
    return set(str(x) for x in load_json_list(USED_CLIPS_FILE))


def mark_clip_used(clip_id: str):
    used = get_used_clips()
    used.add(str(clip_id))
    save_json_list(USED_CLIPS_FILE, sorted(list(used)))


def call_gemini_text(prompt: str, timeout: int = 45, json_mode: bool = True) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return ""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    models = [
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3-flash-preview",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
    ]
    for model in models:
        for attempt in range(2):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=timeout,
                )
                if r.status_code == 200:
                    data = r.json()
                    cands = data.get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
            except Exception:
                pass
            time.sleep(1.0)
    return ""


def generate_long_script(topic: str, target_minutes: int = 11) -> dict:
    """
    Generates a coherent 5-chapter Cosmic documentary script (~1,500-1,800 words for ~10-13 min)
    with explicit visual_type ('video' or 'photo') and cohesive atmospheric search queries.
    """
    outline_prompt = f"""
You are an elite scientific documentary writer and astrophysicist for a premier space channel ("Cosmic Secrets"), whose audience watches AND listens with headphones while working, studying, or winding down at night.

Topic: "{topic}"

Create a 5-Chapter outline for an awe-inspiring, scientifically accurate, and deeply atmospheric {target_minutes}-minute space documentary (~1,500 to 1,800 words total).
Return ONLY valid JSON:
{{
  "title": "Compelling, high-CTR Cosmic documentary title under 75 chars (DO NOT include #shorts)",
  "thumbnail_text": "3-4 BOLD WORDS for thumbnail",
  "description_summary": "2-sentence compelling hook summarizing the cosmic mysteries explored.",
  "chapters": [
    {{
      "chapter_num": 1,
      "chapter_title": "Introduction: The Edge of the Unknown",
      "theme_mood": "deep space galaxy, dark void, nebulae",
      "key_points": "Hook the listener immediately with mind-bending scale, cosmic silence, and the core scientific mystery."
    }}
  ]
}}
"""
    raw_outline = call_gemini_text(outline_prompt, timeout=35)
    m = re.search(r"\{.*\}", raw_outline, re.DOTALL)
    if not m:
        raise RuntimeError("Failed to generate cosmic documentary outline from Gemini.")
    outline = json.loads(m.group(0))

    full_chapters = []
    for ch in outline["chapters"]:
        c_num = ch["chapter_num"]
        c_title = ch["chapter_title"]
        c_mood = ch.get("theme_mood", "deep space stars galaxy nebula")
        c_points = ch.get("key_points", "")

        ch_prompt = f"""
Write Chapter {c_num} ("{c_title}") of our cinematic cosmic documentary on: "{topic}".
Mood/Visual theme for this chapter: {c_mood}
Core scientific concepts to explore: {c_points}

CRITICAL VOICE & LISTENER RULES:
1. Write 320 to 380 spoken words divided into 10 cohesive micro-scenes (30-40 words per scene, ~10-12 seconds each so visuals stay fresh and dynamic).
2. Because listeners also consume this audio-only, use DELIBERATE punctuation for a hypnotic, cinematic delivery:
   - Commas (,) for breathing pauses and pacing.
   - Em-dashes (—) for conceptual shifts and dramatic scale.
   - Ellipses (...) for contemplative awe.
   - Rhetorical questions (?) that invite the listener to look up at the night sky.
3. No stage directions, no markdown asterisks, no emojis, no spoken chapter header.
4. For each scene, choose either "video" (70% of scenes) or "photo" (30% of scenes — ideal for James Webb deep field, Pillars of Creation, planetary surfaces), and give a simple 2-3 word English stock search query matching the chapter's cosmic theme.
5. Weave in authentic astrophysics concepts (light-years, cosmic web, event horizon, singularity, general relativity, quantum fluctuations, dark energy) and historical scientific titans (Einstein, Hawking, Sagan, Hubble).

Return ONLY valid JSON:
{{
  "scenes": [
    {{
      "narration": "Spoken sentences for this scene with rich punctuation...",
      "visual_type": "video",
      "search_query": "deep space galaxy"
    }}
  ]
}}
"""
        raw_ch = call_gemini_text(ch_prompt, timeout=45)
        cm = re.search(r"\{.*\}", raw_ch, re.DOTALL)
        if not cm:
            raise RuntimeError(f"Failed to generate script for Chapter {c_num}")
        ch_data = json.loads(cm.group(0))
        full_chapters.append({
            "chapter_num": c_num,
            "chapter_title": c_title,
            "scenes": ch_data["scenes"],
        })
        print(f"[SCRIPT] Generated Chapter {c_num}: {c_title} ({len(ch_data['scenes'])} scenes)")
        time.sleep(1.5)

    return {
        "title": outline["title"].replace("#shorts", "").replace("#Shorts", "").strip(),
        "thumbnail_text": outline.get("thumbnail_text", "BEYOND THE UNIVERSE"),
        "description_summary": outline.get("description_summary", topic),
        "chapters": full_chapters,
    }


def synthesize_gemini_tts(text: str, out_wav: Path, voice_name: str = "Charon") -> bool:
    """
    Synthesizes studio-grade cinematic narration using Gemini native TTS endpoint.
    Voice options: Charon (deep resonant documentary), Puck (contemplative), Orpheus (smooth).
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return False

    clean_text = re.sub(r"[\*#_~`]", "", text).strip()
    payload = {
        "contents": [{"parts": [{"text": clean_text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent?key={api_key}"
    try:
        r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            cands = data.get("candidates", [])
            if cands:
                parts = cands[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline = part.get("inlineData", {})
                    if inline.get("mimeType", "").startswith("audio/"):
                        audio_bytes = base64.b64decode(inline.get("data", ""))
                        if inline.get("mimeType") == "audio/wav" or audio_bytes[:4] == b"RIFF":
                            out_wav.write_bytes(audio_bytes)
                        else:
                            # Assume raw 24kHz 16-bit PCM mono
                            with wave.open(str(out_wav), "wb") as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(24000)
                                wf.writeframes(audio_bytes)
                        return True
        else:
            print(f"[TTS WARN] Gemini TTS status {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[TTS WARN] Gemini TTS error: {e}")
    return False


def synthesize_edge_fallback(text: str, out_wav: Path, voice: str = "en-US-BrianNeural") -> bool:
    """Fallback high-quality neural TTS using Edge-TTS."""
    clean_text = re.sub(r"[\*#_~`]", "", text).strip()
    mp3_tmp = out_wav.with_suffix(".mp3")
    try:
        async def _speak():
            comm = edge_tts.Communicate(clean_text, voice=voice, rate="+0%")
            await comm.save(str(mp3_tmp))
        asyncio.run(_speak())

        # Convert to 24kHz WAV
        cmd = [FFMPEG_EXE, "-y", "-i", str(mp3_tmp), "-ar", "24000", "-ac", "1", str(out_wav)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if mp3_tmp.exists():
            mp3_tmp.unlink()
        return True
    except Exception as e:
        print(f"[TTS WARN] Edge-TTS fallback error: {e}")
        return False


def get_audio_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def detect_silences(wav_path: Path, noise_db: int = -35, min_dur: float = 0.4) -> list:
    """Uses FFmpeg silencedetect to find natural breath pauses."""
    cmd = [
        FFMPEG_EXE, "-i", str(wav_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d\.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d\.]+)", res.stderr)]
    silences = []
    for s, e in zip(starts, ends):
        if e > s:
            silences.append((s, e))
    return silences


def compute_scene_durations(total_duration: float, num_scenes: int, silences: list) -> list:
    """Distributes scene durations aligning with speech pauses whenever possible."""
    target_durs = [total_duration / num_scenes] * num_scenes
    if not silences or num_scenes <= 1:
        return target_durs

    scene_ends = []
    accum = 0.0
    for i in range(num_scenes - 1):
        target_time = accum + (total_duration - accum) / (num_scenes - i)
        best_pause = None
        min_diff = 999.0
        for s_start, s_end in silences:
            mid = (s_start + s_end) / 2.0
            diff = abs(mid - target_time)
            if diff < min_diff and mid > accum + 5.0 and mid < total_duration - 4.0:
                min_diff = diff
                best_pause = mid
        cut_point = best_pause if (best_pause and min_diff < 4.5) else target_time
        scene_ends.append(cut_point)
        accum = cut_point
    scene_ends.append(total_duration)

    durations = []
    prev = 0.0
    for end_t in scene_ends:
        durations.append(max(4.0, end_t - prev))
        prev = end_t
    return durations


def fetch_landscape_media(query: str, visual_type: str, min_duration: int = 8) -> tuple:
    """Fetches 16:9 widescreen 1080p cosmic space video or high-res photo from Pixabay."""
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        return None, None

    used = get_used_clips()
    q_encoded = quote(query)

    # 1. Video
    if visual_type == "video":
        url = f"https://pixabay.com/api/videos/?key={api_key}&q={q_encoded}&video_type=film&per_page=15"
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                hits = r.json().get("hits", [])
                for hit in hits:
                    hit_id = f"px_v_{hit.get('id')}"
                    if hit_id in used:
                        continue
                    tags = set(t.strip().lower() for t in hit.get("tags", "").split(","))
                    if tags & FORBIDDEN_TAGS:
                        continue
                    if hit.get("duration", 0) < min_duration:
                        continue
                    videos = hit.get("videos", {})
                    for q in ["large", "medium", "small"]:
                        v_info = videos.get(q, {})
                        if v_info and v_info.get("width", 0) >= v_info.get("height", 0):
                            return v_info.get("url"), hit_id
        except Exception:
            pass

    # 2. Photo (fallback or explicit visual_type == 'photo')
    url_img = f"https://pixabay.com/api/?key={api_key}&q={q_encoded}&image_type=photo&orientation=horizontal&per_page=15"
    try:
        r = requests.get(url_img, timeout=12)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            for hit in hits:
                hit_id = f"px_p_{hit.get('id')}"
                if hit_id in used:
                    continue
                tags = set(t.strip().lower() for t in hit.get("tags", "").split(","))
                if tags & FORBIDDEN_TAGS:
                    continue
                img_url = hit.get("largeImageURL")
                if img_url:
                    return img_url, hit_id
    except Exception:
        pass

    # Fallback to curated cosmic query
    fallback_q = quote(random.choice(COSMIC_PHOTO_QUERIES))
    url_fb = f"https://pixabay.com/api/?key={api_key}&q={fallback_q}&image_type=photo&orientation=horizontal&per_page=10"
    try:
        r = requests.get(url_fb, timeout=12)
        if r.status_code == 200:
            hits = r.json().get("hits", [])
            for hit in hits:
                img_url = hit.get("largeImageURL")
                if img_url:
                    return img_url, f"px_p_{hit.get('id')}"
    except Exception:
        pass

    return None, None


def create_chapter_overlay_png(chapter_num: int, chapter_title: str, out_png: Path):
    """Renders a sleek, cinematic space-themed lower-third chapter marker."""
    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_large = None
    font_small = None
    for cand in [
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(cand):
            font_large = ImageFont.truetype(cand, 38)
            font_small = ImageFont.truetype(cand, 24)
            break
    if not font_large:
        font_large = ImageFont.load_default()
        font_small = font_large

    # Translucent card at top-left
    card_w, card_h = 580, 110
    card_x, card_y = 70, 70
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=14,
        fill=(8, 12, 28, 190),
        outline=(0, 210, 255, 160),
        width=2,
    )

    tag = f"CHAPTER {chapter_num}"
    draw.text((card_x + 28, card_y + 16), tag, font=font_small, fill=(0, 220, 255, 230))
    draw.text((card_x + 28, card_y + 48), chapter_title[:32], font=font_large, fill=(255, 255, 255, 255))

    img.save(out_png)


def render_normalized_scene_clip(
    media_path: Path,
    duration: float,
    out_mp4: Path,
    is_photo: bool = False,
    camera_movement_idx: int = 0,
):
    """
    Renders 1080p 16:9 widescreen clip.
    If photo, applies continuous normalized dynamic Ken Burns pan/zoom across 4 alternating styles.
    """
    if is_photo:
        frames = int(duration * FPS)
        styles = [
            f"scale=8000:-1,zoompan=z='1.0+0.15*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS}",
            f"scale=8000:-1,zoompan=z='1.15-0.15*(on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS}",
            f"scale=8000:-1,zoompan=z='1.0+0.12*(on/{frames})':x='iw*0.4*(on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS}",
            f"scale=8000:-1,zoompan=z='1.12':x='(iw-iw/zoom)*(1.0-on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps={FPS}",
        ]
        chosen_vf = styles[camera_movement_idx % len(styles)]
        cmd = [
            FFMPEG_EXE, "-y",
            "-loop", "1",
            "-i", str(media_path),
            "-vf", f"{chosen_vf},format=yuv420p",
            "-t", f"{duration:.3f}",
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            str(out_mp4),
        ]
    else:
        cmd = [
            FFMPEG_EXE, "-y",
            "-stream_loop", "-1",
            "-i", str(media_path),
            "-t", f"{duration:.3f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,format=yuv420p",
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-an",
            str(out_mp4),
        ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def create_cosmic_ambient_pad(duration: float, out_wav: Path):
    """
    Creates a deep interstellar cosmic rumble and harmonic drone (55Hz / A1 fundamental + 82.4Hz + 110Hz).
    Captures the hypnotic, infinite expanse of deep space (-28 dB).
    """
    sr = 24000
    chunk_sec = 30.0
    t_chunk = np.linspace(0, chunk_sec, int(sr * chunk_sec), endpoint=False)
    pad = (
        0.55 * np.sin(2 * np.pi * 55.00 * t_chunk) +
        0.28 * np.sin(2 * np.pi * 82.41 * t_chunk + 0.7) +
        0.17 * np.sin(2 * np.pi * 110.00 * t_chunk + 1.4)
    )
    # Slow undulating cosmic drift modulation (20-second period)
    lfo = 0.80 + 0.20 * np.sin(2 * np.pi * (1.0 / 20.0) * t_chunk)
    pad = np.clip(pad * lfo * 0.040, -1.0, 1.0)  # ~ -28 dB
    pcm = (pad * 32767).astype(np.int16).tobytes()

    total_chunks = int(math.ceil(duration / chunk_sec))
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for _ in range(total_chunks):
            wf.writeframes(pcm)


def create_thumbnail(bg_img: Path, hook_text: str, out_thumb: Path):
    """Generates a high-CTR 1280x720 YouTube thumbnail with deep space aesthetic."""
    img = Image.open(bg_img).convert("RGB")
    img = img.resize((1280, 720), Image.Resampling.LANCZOS)
    
    # Cinematic vignette overlay
    overlay = Image.new("RGBA", (1280, 720), (5, 8, 20, 130))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_path = None
    for cand in [
        "C:\\Windows\\Fonts\\impact.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(cand):
            font_path = cand
            break
    font = ImageFont.truetype(font_path, 88) if font_path else ImageFont.load_default()

    words = hook_text.upper().split()
    lines = [" ".join(words[i:i+2]) for i in range(0, len(words), 2)]
    y = 220
    for idx, line in enumerate(lines[:3]):
        color = (0, 230, 255) if idx == 0 else (255, 255, 255)
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (1280 - tw) // 2
        # Heavy drop shadow
        draw.text((x + 5, y + 5), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=color)
        y += 105

    img.save(out_thumb, quality=94)


def upload_long_youtube(
    video_path: Path,
    thumb_path: Path,
    title: str,
    description: str,
    privacy_status: str = "public",
) -> str:
    from uploader import get_authenticated_service

    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [
                "astronomy", "space documentary", "universe", "black hole",
                "james webb", "astrophysics", "science", "cosmos", "deep space", "fermi paradox"
            ],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": "private" if privacy_status == "scheduled" else privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    if privacy_status == "scheduled":
        pub = datetime.now(timezone.utc) + timedelta(hours=2)
        body["status"]["publishAt"] = pub.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    print(f"[YOUTUBE] Uploading long-form space documentary '{title}'...")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"[YOUTUBE] Progress: {int(status.progress() * 100)}%")

    vid_id = resp["id"]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    print(f"[SUCCESS] Long-form video live at: {url}")

    if thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=vid_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg"),
            ).execute()
            print("[SUCCESS] Custom cosmic thumbnail uploaded!")
        except Exception as e:
            print(f"[WARN] Thumbnail upload skipped (requires intermediate YouTube channel verification): {e}")

    return url


def run_long_form_pipeline(topic: str = None, privacy_status: str = "public") -> dict:
    ensure_dirs()

    # 1. Topic Selection
    history = load_json_list(LONG_HISTORY_FILE)
    used_topics = set(x.get("topic", "").lower() for x in history)

    if not topic:
        avail = [t for t in CURATED_LONG_TOPICS if t.lower() not in used_topics]
        topic = random.choice(avail if avail else CURATED_LONG_TOPICS)

    print(f"============================================================")
    print(f"🚀 INITIATING COSMIC SECRETS DOCUMENTARY: '{topic}'")
    print(f"============================================================")

    # 2. Script Generation (5 Chapters, ~12-15 min)
    script_data = generate_long_script(topic, target_minutes=11)
    title = script_data["title"]
    chapters = script_data["chapters"]

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # 3. Audio & Scene Synthesis
    chapter_rendered_videos = []
    chapter_timestamps = []
    current_time_sec = 0.0
    best_thumb_bg = None
    camera_movement_counter = 0

    for ch in chapters:
        c_num = ch["chapter_num"]
        c_title = ch["chapter_title"]
        scenes = ch["scenes"]

        print(f"\n--- [PRODUCING CHAPTER {c_num}: {c_title}] ---")
        ch_audio_wav = session_dir / f"ch_{c_num}_audio.wav"

        # Combine narration for natural flow
        full_narration = " ".join(s["narration"] for s in scenes)
        tts_ok = synthesize_gemini_tts(full_narration, ch_audio_wav, voice_name="Charon")
        if not tts_ok:
            print("[TTS] Falling back to Edge-TTS...")
            synthesize_edge_fallback(full_narration, ch_audio_wav)

        ch_dur = get_audio_duration(ch_audio_wav)
        silences = detect_silences(ch_audio_wav)
        scene_durs = compute_scene_durations(ch_dur, len(scenes), silences)

        print(f"[AUDIO] Chapter {c_num} Duration: {ch_dur:.2f}s across {len(scenes)} scenes.")

        # Timestamp for YouTube Description
        mins = int(current_time_sec // 60)
        secs = int(current_time_sec % 60)
        chapter_timestamps.append(f"{mins:02d}:{secs:02d} - {c_title}")

        # Render Scene Clips
        scene_clip_paths = []
        for s_idx, (scene, s_dur) in enumerate(zip(scenes, scene_durs)):
            v_type = scene.get("visual_type", "video")
            q = scene.get("search_query", "deep space galaxy")

            media_url, clip_id = fetch_landscape_media(q, v_type)
            if not media_url:
                media_url, clip_id = fetch_landscape_media("deep space galaxy nebulae stars", "video")

            ext = ".jpg" if "px_p_" in str(clip_id) or v_type == "photo" else ".mp4"
            is_photo = ext == ".jpg"
            raw_media = session_dir / f"ch_{c_num}_s_{s_idx}{ext}"

            # Download media
            r = requests.get(media_url, timeout=30)
            raw_media.write_bytes(r.content)
            if clip_id:
                mark_clip_used(clip_id)

            if is_photo and not best_thumb_bg:
                best_thumb_bg = raw_media

            scene_mp4 = session_dir / f"ch_{c_num}_clip_{s_idx}.mp4"
            render_normalized_scene_clip(
                raw_media,
                s_dur,
                scene_mp4,
                is_photo=is_photo,
                camera_movement_idx=camera_movement_counter,
            )
            camera_movement_counter += 1
            scene_clip_paths.append(scene_mp4)

        # Concatenate Scene Clips for Chapter
        concat_list = session_dir / f"ch_{c_num}_concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for sc in scene_clip_paths:
                f.write(f"file '{sc.as_posix()}'\n")

        ch_raw_video = session_dir / f"ch_{c_num}_raw.mp4"
        cmd = [
            FFMPEG_EXE, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(ch_raw_video),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Add Chapter Lower-Third Overlay
        overlay_png = session_dir / f"ch_{c_num}_overlay.png"
        create_chapter_overlay_png(c_num, c_title, overlay_png)

        ch_final_mp4 = session_dir / f"ch_{c_num}_final.mp4"
        cmd_overlay = [
            FFMPEG_EXE, "-y",
            "-i", str(ch_raw_video),
            "-i", str(overlay_png),
            "-filter_complex", "[0:v][1:v]overlay=0:0:enable='between(t,0,7)'[v]",
            "-map", "[v]",
            "-t", f"{ch_dur:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            str(ch_final_mp4),
        ]
        subprocess.run(cmd_overlay, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Combine Video + Narration
        ch_av_mp4 = session_dir / f"ch_{c_num}_av.mp4"
        cmd_av = [
            FFMPEG_EXE, "-y",
            "-i", str(ch_final_mp4),
            "-i", str(ch_audio_wav),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            str(ch_av_mp4),
        ]
        subprocess.run(cmd_av, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        chapter_rendered_videos.append(ch_av_mp4)
        current_time_sec += ch_dur

    # 4. Master Concatenation
    master_concat_txt = session_dir / "master_concat.txt"
    with open(master_concat_txt, "w", encoding="utf-8") as f:
        for cv in chapter_rendered_videos:
            f.write(f"file '{cv.as_posix()}'\n")

    master_dry_video = session_dir / "master_dry.mp4"
    cmd_master = [
        FFMPEG_EXE, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(master_concat_txt),
        "-c", "copy",
        str(master_dry_video),
    ]
    subprocess.run(cmd_master, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 5. Cosmic Ambient Music Generation & Final Sound Mix
    total_doc_dur = current_time_sec
    ambient_wav = session_dir / "cosmic_ambient.wav"
    create_cosmic_ambient_pad(total_doc_dur + 5.0, ambient_wav)

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()[:45]
    final_output_mp4 = OUTPUT_DIR / f"{safe_title}_{session_id}.mp4"

    cmd_mix = [
        FFMPEG_EXE, "-y",
        "-i", str(master_dry_video),
        "-i", str(ambient_wav),
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        str(final_output_mp4),
    ]
    print(f"\n[MIXING] Generating master cosmic audio mix...")
    subprocess.run(cmd_mix, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 6. Thumbnail Creation
    thumb_path = OUTPUT_DIR / f"{safe_title}_{session_id}_thumb.jpg"
    if not best_thumb_bg or not best_thumb_bg.exists():
        # Fallback query for cosmic background
        fb_thumb_url, _ = fetch_landscape_media("deep space galaxy nebulae", "photo")
        if fb_thumb_url:
            r = requests.get(fb_thumb_url, timeout=20)
            best_thumb_bg = session_dir / "thumb_bg.jpg"
            best_thumb_bg.write_bytes(r.content)

    if best_thumb_bg and best_thumb_bg.exists():
        create_thumbnail(best_thumb_bg, script_data["thumbnail_text"], thumb_path)

    # 7. Build Description with Timestamps
    desc_lines = [
        script_data["description_summary"],
        "",
        "🌌 CHAPTERS:",
        "\n".join(chapter_timestamps),
        "",
        "🔭 Explore the deepest mysteries of the universe, astrophysics, and the silent cosmos.",
        "Subscribe to Cosmic Secrets for weekly deep space documentaries.",
        "",
        "#astronomy #space #documentary #universe #blackhole #jameswebb #science",
    ]
    full_description = "\n".join(desc_lines)

    # 8. Upload to YouTube
    print(f"\n[UPLOAD] Uploading 1080p documentary to Cosmic Secrets...")
    yt_url = upload_long_youtube(
        final_output_mp4,
        thumb_path,
        title,
        full_description,
        privacy_status=privacy_status,
    )

    # 9. Update History
    history.append({
        "topic": topic,
        "title": title,
        "url": yt_url,
        "duration_min": round(total_doc_dur / 60.0, 2),
        "timestamp": datetime.now().isoformat()[:19],
    })
    save_json_list(LONG_HISTORY_FILE, history)

    print(f"\n🎉 DOCUMENTARY COMPLETED & PUBLISHED!")
    print(f"🎬 Title: {title}")
    print(f"⏱️ Duration: {total_doc_dur/60.0:.2f} minutes")
    print(f"🔗 URL: {yt_url}")

    return {
        "title": title,
        "url": yt_url,
        "duration_min": round(total_doc_dur / 60.0, 2),
        "output_path": str(final_output_mp4),
    }


if __name__ == "__main__":
    privacy = "scheduled" if "--scheduled" in sys.argv else "public"
    custom_topic = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            custom_topic = arg
            break

    run_long_form_pipeline(topic=custom_topic, privacy_status=privacy)
