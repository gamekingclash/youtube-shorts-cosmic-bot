import asyncio
import json
import math
import os
import re
import sys
import textwrap
import wave
from pathlib import Path
from urllib.parse import quote

import edge_tts
import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30


def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def generate_script_and_metadata(topic: str) -> dict:
    """
    Generates an engaging, high-retention English YouTube Shorts script, title, description,
    and visual stock search queries about Finance, Wealth Mindset, and Investing.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        prompt = f"""
You are an elite YouTube Shorts scriptwriter specializing in Space, Astrophysics, Black Holes, James Webb Discoveries, and Cosmic Mysteries.
Create a fast-paced, hook-driven 30-45 second YouTube Short about: "{topic}"

Target Audience: US & global viewers fascinated by space exploration, cosmic anomalies, astronomy, and astrophysics.
Tone: Cinematic, mysterious, awe-inspiring, gripping, scientific.

Return ONLY valid JSON with this exact structure:
{{
  "title": "Viral Cosmic title under 60 chars #shorts",
  "description": "Engaging description with 5 relevant astronomy and space hashtags",
  "scenes": [
    {{
      "narration": "1-2 punchy spoken sentences for this scene (plain text, no emojis or stage directions).",
      "search_query": "2-3 simple English keywords for stock video (e.g. 'galaxy spinning space', 'black hole event horizon', 'nebula stars deep space', 'earth from orbit', 'telescope night sky')",
      "image_prompt": "Cinematic visual description"
    }}
  ]
}}
Rules:
- Create 4 to 5 scenes total.
- Scene 1 narration MUST start with a complete, mind-blowing cosmic hook sentence under 8 words (e.g. 'Something is moving through our galaxy.') that stops scrolling in the first 1.5 seconds.
- Final scene MUST end with a chilling cosmic question or awe-inspiring revelation.
"""
        for model_name in ["gemini-flash-lite-latest", "gemini-flash-latest"]:
            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=20,
                )
                if resp.status_code == 200:
                    data_json = resp.json()
                    raw = data_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        if "scenes" in parsed and len(parsed["scenes"]) > 0:
                            print(f"[OK] Script generated via Google Gemini API ({model_name}).")
                            return parsed
                else:
                    print(f"[WARN] Gemini model {model_name} returned status {resp.status_code}")
            except Exception as exc:
                print(f"[WARN] Gemini API call ({model_name}) failed: {exc}")

    # Fallback script generator
    clean_topic = topic.strip().rstrip("?.!")
    print(f"[INFO] Generating Cosmic Secrets Shorts script for topic: '{clean_topic}'")
    return {
        "title": f"The Brutal Truth About {clean_topic.title()} #shorts",
        "description": (
            f"Here is what 99% of people never understand about {clean_topic}. "
            f"Watch until the end to change your perspective on wealth! #shorts #space #astronomy #universe #cosmic #science"
        ),
        "scenes": [
            {
                "narration": f"Here is the brutal truth about {clean_topic} that the top 1% understands, but most people never will.",
                "search_query": "luxury watch cash",
                "image_prompt": "Ultra luxury watch and counting cash in dark cinematic lighting",
            },
            {
                "narration": "Most people stay broke not because of how much they earn, but because of the hidden psychological money traps they fall for daily.",
                "search_query": "wall street stock market",
                "image_prompt": "Wall Street stock exchange floor fast motion",
            },
            {
                "narration": "True wealth is not about showing off expensive depreciating toys. It is about buying your time and financial sovereignty.",
                "search_query": "penthouse city skyline",
                "image_prompt": "Modern luxury high-rise penthouse overlooking nocturnal city skyline",
            },
            {
                "narration": "The moment you start acquiring income-producing assets instead of liabilities, you stop working for money, and money starts working for you.",
                "search_query": "supercar night drive",
                "image_prompt": "Cinematic night drive in modern luxury sports car",
            },
        ],
    }


def generate_tts_with_word_timings(text: str, audio_path: Path) -> list[dict]:
    """
    Synthesizes speech using edge-tts with precise word boundaries for dynamic captions.
    Voice: en-US-ChristopherNeural with 1.1x speed (rate=+10%).
    """
    voice = os.getenv("TTS_VOICE", "en-US-ChristopherNeural").strip()
    word_timings = []

    clean_text = re.sub(r"[\*\_#`]+", "", text)
    clean_text = re.sub(r"^\d+[\.\)]\s*", "", clean_text).strip()

    async def _run():
        communicate = edge_tts.Communicate(clean_text, voice, rate="+10%", boundary="WordBoundary")
        with open(audio_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # Offset and duration are in 100-nanosecond ticks
                    start_sec = chunk["offset"] / 10_000_000.0
                    dur_sec = chunk["duration"] / 10_000_000.0
                    word = chunk["text"].strip()
                    if word:
                        word_timings.append(
                            {
                                "text": word,
                                "start": start_sec,
                                "end": start_sec + dur_sec,
                            }
                        )

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[WARN] edge-tts stream failed: {e}. Retrying without word boundaries...")
        communicate = edge_tts.Communicate(clean_text, voice, rate="+10%")
        asyncio.run(communicate.save(str(audio_path)))
        try:
            import wave
            with wave.open(str(audio_path), "rb") as wf:
                dur = wf.getnframes() / float(wf.getframerate())
        except Exception:
            dur = max(2.5, len(clean_text.split()) * 0.35)
        words = clean_text.split()
        if words:
            step = dur / len(words)
            for i, w in enumerate(words):
                word_timings.append(
                    {"text": w, "start": i * step, "end": (i + 1) * step}
                )
    # Re-attach punctuation (.,?!:;'-") stripped by edge-tts WordBoundary events
    orig_tokens = clean_text.split()
    ptr = 0
    for wt in word_timings:
        w_clean = re.sub(r"[^a-zA-Z0-9]", "", wt["text"]).lower()
        if not w_clean:
            continue
        for k in range(ptr, min(ptr + 3, len(orig_tokens))):
            tok_clean = re.sub(r"[^a-zA-Z0-9]", "", orig_tokens[k]).lower()
            if tok_clean == w_clean or (len(w_clean) >= 2 and tok_clean.startswith(w_clean)):
                wt["text"] = orig_tokens[k]
                ptr = k + 1
                break
    return word_timings


def group_words_into_captions(
    word_timings: list[dict],
    fallback_text: str,
    total_duration: float,
    is_hook_scene: bool = False,
    words_per_group: int = 3,
) -> list[dict]:
    """
    Groups word timings into punchy 2-3 word viral Shorts captions with microsecond sync.
    If is_hook_scene=True, keeps the opening hook (first 1.5 - 2.0s) as an intact,
    punchy phrase so that awkward split fragments never appear in the first frame.
    """
    if not word_timings:
        words = fallback_text.split()
        if not words:
            return []
        chunks = [
            " ".join(words[i : i + words_per_group])
            for i in range(0, len(words), words_per_group)
        ]
        step = total_duration / len(chunks)
        return [
            {"text": c.upper(), "start": idx * step, "end": (idx + 1) * step}
            for idx, c in enumerate(chunks)
        ]

    captions = []
    start_idx = 0

    # Ensure Scene 1 opening hook (first 1.5 - 2.2s) is intact and complete
    if is_hook_scene and len(word_timings) >= 2:
        if len(word_timings) <= 8:
            hook_words = word_timings
        else:
            hook_words = []
            for w in word_timings[:7]:
                hook_words.append(w)
                if len(hook_words) >= 4 and w["end"] >= 1.6:
                    break
            # If remaining words are 2 or fewer, absorb into hook to avoid awkward leftovers
            if len(word_timings) - len(hook_words) <= 2:
                hook_words = word_timings

        if hook_words:
            hook_text = " ".join(w["text"] for w in hook_words).upper()
            captions.append({
                "text": hook_text,
                "start": hook_words[0]["start"],
                "end": max(hook_words[-1]["end"], 1.6),
            })
            start_idx = len(hook_words)

    # Group remaining words into natural chunks (2-3 words, NO single orphan words)
    i = start_idx
    while i < len(word_timings):
        remaining = len(word_timings) - i
        if remaining == 4:
            take = 2
        elif remaining == 5:
            take = 3  # leaves 2 for the final group
        elif remaining <= 3:
            take = remaining
        else:
            take = words_per_group

        group = word_timings[i : i + take]
        text = " ".join(w["text"] for w in group).upper()
        captions.append({
            "text": text,
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })
        i += take

    # Smooth contiguous timings only across brief micro-pauses (< 0.20s)
    for k in range(len(captions) - 1):
        gap = captions[k + 1]["start"] - captions[k]["end"]
        if 0 < gap < 0.20:
            captions[k]["end"] = captions[k + 1]["start"]

    return captions


def validate_video_file(file_path: Path, min_size_bytes: int = 120_000) -> bool:
    """
    Validates that a video file exists, has a valid file size (>120KB),
    can be decoded without corruption, and does NOT contain green-screen / chroma-key frames.
    """
    if not file_path.exists():
        return False
    try:
        if file_path.stat().st_size < min_size_bytes:
            print(f"[WARN] Video file {file_path.name} too small ({file_path.stat().st_size} bytes). Discarding.")
            file_path.unlink(missing_ok=True)
            return False
        from moviepy import VideoFileClip
        with VideoFileClip(str(file_path)) as probe:
            if probe.duration is None or probe.duration < 0.5:
                print(f"[WARN] Video {file_path.name} has invalid duration. Discarding.")
                return False
            # Sample 3 frames across the video to detect green-screen / chroma key or blank frames
            sample_times = [0.1, probe.duration * 0.5, max(0.1, probe.duration - 0.2)]
            for t_check in sample_times:
                frame = probe.get_frame(min(t_check, probe.duration - 0.05))
                if frame is None or frame.size == 0:
                    return False
                r_ch = frame[:, :, 0].astype(np.float32)
                g_ch = frame[:, :, 1].astype(np.float32)
                b_ch = frame[:, :, 2].astype(np.float32)
                # Chroma green detection: bright green dominant over red and blue
                green_mask = (g_ch > 150) & (g_ch > r_ch * 1.45) & (g_ch > b_ch * 1.45)
                green_ratio = float(np.mean(green_mask))
                if green_ratio > 0.08:
                    print(f"[WARN] Green-screen / chroma-key detected ({green_ratio:.1%} green) in {file_path.name}. Discarding!")
                    file_path.unlink(missing_ok=True)
                    return False
        return True
    except Exception as exc:
        print(f"[WARN] Video file {file_path.name} corrupted or unreadable: {exc}. Discarding.")
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def create_vignette_overlay(width: int, height: int) -> np.ndarray:
    """
    Generates a radial vignette overlay array (RGBA) that darkens edges and
    modifies digital frame hash across all frames to prevent 'reused content' flags.
    """
    y, x = np.ogrid[:height, :width]
    cx, cy = width / 2.0, height / 2.0
    max_dist = math.sqrt(cx**2 + cy**2)
    dist = np.sqrt((x - cx)**2 + (y - cy)**2) / max_dist
    vignette = np.clip((dist - 0.38) / 0.62, 0, 1) ** 1.8
    alpha = (vignette * 95).astype(np.uint8)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 3] = alpha
    return rgba


def create_ambient_drone(duration: float, out_path: Path, is_dark: bool = False) -> Path:
    """
    Synthesizes a royalty-free modern low-pass ambient bed track scaled to -24 dB
    using standard Python wave and numpy.
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    if is_dark:
        drone = (
            0.50 * np.sin(2 * np.pi * 55.0 * t) +
            0.30 * np.sin(2 * np.pi * 110.0 * t + 0.5) +
            0.20 * np.sin(2 * np.pi * 82.4 * t + 1.2)
        )
        lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 0.18 * t)
    else:
        # Wealth / Finance: 65.4Hz (C2), 130.8Hz (C3), 98Hz (G2) warm low pad
        drone = (
            0.45 * np.sin(2 * np.pi * 65.4 * t) +
            0.35 * np.sin(2 * np.pi * 130.8 * t + 0.8) +
            0.20 * np.sin(2 * np.pi * 98.0 * t + 0.4)
        )
        lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.25 * t)

    drone = drone * lfo
    # -24 dB relative to full scale: 10^(-24/20) = 0.0631
    ambient = np.clip(drone * 0.0631, -1.0, 1.0)
    int16_ambient = (ambient * 32767).astype(np.int16)

    with wave.open(str(out_path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(int16_ambient.tobytes())

    return out_path


FORBIDDEN_TAGS = {
    "dog", "cat", "pet", "puppy", "kitten", "animal", "insect", "bee",
    "stickman", "cartoon", "baby", "kid", "child", "massage", "spa", "flower",
    "yoga", "fitness", "horror", "creepy", "blood", "zombie", "cute", "funny", "bird", "birds", "avian", "wildlife", "nature", "tree", "plant", "forest", "wood",
    "green screen", "greenscreen", "chroma", "chromakey", "chroma key",
    "template", "subscribe", "button", "animation", "3d", "vfx", "loop", "isolated"
}

CURATED_COSMIC_QUERIES = [
    "deep space stars galaxy nebula",
    "supermassive black hole event horizon",
    "milky way night sky stars timelapse",
    "james webb space telescope deep field",
    "cosmic dust interstellar nebula 4k",
    "planet earth from space orbit atmosphere",
    "solar flare sun surface cosmic",
    "alien exoplanet deep universe astronomy",
    "aurora borealis northern lights night sky",
    "meteor shower shooting stars cosmos",
]

REQUIRED_COSMIC_CONCEPTS = {
    "space", "galaxy", "universe", "stars", "star", "nebula", "planet",
    "astronomy", "cosmos", "cosmic", "black hole", "telescope", "sky",
    "night", "earth", "moon", "solar", "deep space", "milky way",
    "supernova", "alien", "interstellar", "aurora", "meteor", "orbit"
}

USED_CLIPS_FILE = BASE_DIR / "used_clips.json"
SESSION_USED_VIDEO_IDS = set()


def load_persistent_used_clips() -> set:
    global SESSION_USED_VIDEO_IDS
    if USED_CLIPS_FILE.exists():
        try:
            data = json.loads(USED_CLIPS_FILE.read_text(encoding="utf-8"))
            SESSION_USED_VIDEO_IDS.update(str(x) for x in data)
        except Exception:
            pass
    return SESSION_USED_VIDEO_IDS


def save_persistent_used_clip(clip_id: str):
    SESSION_USED_VIDEO_IDS.add(str(clip_id))
    try:
        USED_CLIPS_FILE.write_text(
            json.dumps(sorted(list(SESSION_USED_VIDEO_IDS)), indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def fetch_pixabay_video(query: str, dest_path: Path, retry_with_curated: bool = True) -> bool:
    """
    Downloads space, astronomy, and cosmic film stock video from Pixabay API (video_type=film)
    with strict anti-green-screen filtering and persistent deduplication across runs.
    """
    import random
    load_persistent_used_clips()
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        return False

    clean_query = re.sub(r"[^a-zA-Z0-9 ]+", " ", query).strip()
    clean_query = " ".join(clean_query.split()[:3])
    # video_type=film strictly excludes cartoons, green screen templates, and VFX overlays!
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={quote(clean_query)}&video_type=film&per_page=30"

    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            valid_hits = []
            for hit in hits:
                raw_tags = hit.get("tags", "").lower()
                tags = set(t.strip().lower() for t in raw_tags.split(","))
                if tags.intersection(FORBIDDEN_TAGS) or "green" in raw_tags or "chroma" in raw_tags:
                    continue
                if not any(req in raw_tags for req in REQUIRED_COSMIC_CONCEPTS):
                    continue
                clip_key = f"px_{hit.get('id')}"
                if clip_key in SESSION_USED_VIDEO_IDS or hit.get("id") in SESSION_USED_VIDEO_IDS:
                    continue
                valid_hits.append(hit)

            random.shuffle(valid_hits)
            for chosen_hit in valid_hits[:6]:
                clip_key = f"px_{chosen_hit.get('id')}"
                videos = chosen_hit.get("videos", {})
                chosen = (
                    videos.get("medium")
                    or videos.get("large")
                    or videos.get("small")
                )
                if chosen and chosen.get("url"):
                    vid_resp = requests.get(chosen["url"], stream=True, timeout=25)
                    if vid_resp.status_code == 200:
                        with open(dest_path, "wb") as f:
                            for chunk in vid_resp.iter_content(chunk_size=65536):
                                f.write(chunk)
                        if validate_video_file(dest_path):
                            save_persistent_used_clip(clip_key)
                            print(f"[OK] Downloaded unique cosmic stock video ({clip_key}) for '{clean_query}'.")
                            return True
    except Exception as exc:
        print(f"[WARN] Pixabay fetch failed for '{clean_query}': {exc}")

    if retry_with_curated:
        fallback_q = random.choice(CURATED_COSMIC_QUERIES)
        print(f"[INFO] Falling back to randomized cosmic query: '{fallback_q}'")
        return fetch_pixabay_video(fallback_q, dest_path, retry_with_curated=False)

    return False


def fetch_fallback_stock_video(dest_path: Path, scene_idx: int) -> bool:
    """
    Fallback using randomized curated finance queries so clips never repeat.
    """
    import random
    q = CURATED_COSMIC_QUERIES[scene_idx % len(CURATED_COSMIC_QUERIES)]
    return fetch_pixabay_video(q, dest_path, retry_with_curated=False)


def create_gradient_backdrop(title_text: str, dest_path: Path, scene_idx: int) -> Path:
    """
    Creates an ultra-luxury obsidian & gold/emerald gradient backdrop.
    """
    palettes = [
        ((10, 15, 20), (5, 25, 20)),      # Obsidian to Deep Emerald
        ((15, 12, 5), (35, 25, 10)),      # Obsidian to Dark Bronze Gold
        ((8, 12, 18), (18, 22, 32)),      # Midnight Navy to Obsidian
        ((20, 15, 5), (10, 10, 10)),      # Deep Amber Gold to Charcoal
    ]
    top_rgb, bot_rgb = palettes[scene_idx % len(palettes)]
    y = np.linspace(0, 1, VIDEO_HEIGHT)[:, None]
    x = np.linspace(-1, 1, VIDEO_WIDTH)[None, :]
    glow = np.exp(-(x**2 + (y - 0.42) ** 2) * 2.8)[..., None]

    grad = (1 - y)[..., None] * np.array(top_rgb) + y[..., None] * np.array(bot_rgb)
    arr = np.clip(grad + glow * 65, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    draw = ImageDraw.Draw(img)
    header_font = get_bold_font(44)
    wrapped_header = textwrap.fill(title_text.upper(), width=26)
    bbox = draw.multiline_textbbox((0, 0), wrapped_header, font=header_font, align="center")
    hw = bbox[2] - bbox[0]
    draw.multiline_text(
        ((VIDEO_WIDTH - hw) // 2, 180),
        wrapped_header,
        font=header_font,
        fill=(255, 215, 0),  # Gold header
        align="center",
        stroke_width=4,
        stroke_fill=(0, 0, 0),
    )
    img.save(dest_path)
    return dest_path


def get_bold_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        # Windows fonts
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        # Linux (Ubuntu / GitHub Actions) fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def render_caption_overlay(text: str) -> np.ndarray:
    """
    Renders bold, centered text with gold highlight and thick black outline.
    """
    canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = get_bold_font(78)

    wrapped = textwrap.fill(text, width=16)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=12)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = (VIDEO_WIDTH - text_w) // 2
    y = int(VIDEO_HEIGHT * 0.62) - (text_h // 2)

    pad_x, pad_y = 36, 22
    draw.rounded_rectangle(
        [x - pad_x, y - pad_y, x + text_w + pad_x, y + text_h + pad_y],
        radius=28,
        fill=(0, 0, 0, 160),
    )

    # Gold / Yellow text with thick black stroke
    draw.multiline_text(
        (x, y),
        wrapped,
        font=font,
        fill=(255, 215, 0, 255),  # Electric Gold
        align="center",
        spacing=12,
        stroke_width=8,
        stroke_fill=(0, 0, 0, 255),
    )
    return np.array(canvas)


def build_shorts_video(topic: str) -> Path:
    ensure_dirs()

    # 1. Script & metadata
    meta = generate_script_and_metadata(topic)
    scenes = meta["scenes"]

    from moviepy import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        ImageClip,
        VideoFileClip,
        concatenate_audioclips,
        concatenate_videoclips,
        vfx,
    )

    scene_video_clips = []
    scene_audio_clips = []
    all_captions = []
    cumulative_time = 0.0

    print(f"\n[STEP 1/4] Processing {len(scenes)} scenes for topic: '{topic}'...")

    for idx, scene in enumerate(scenes):
        narration = scene["narration"]
        query = scene.get("search_query", "luxury money")
        audio_path = TEMP_DIR / f"scene_{idx}.mp3"
        video_raw_path = TEMP_DIR / f"raw_{idx}.mp4"

        # A. TTS Voice & Word Boundaries with 1.1x speed
        word_timings = generate_tts_with_word_timings(narration, audio_path)
        audio_clip = AudioFileClip(str(audio_path))
        scene_dur = audio_clip.duration  # Exactly match audio duration for 100% sync

        # Group words into captions (intact hook in Scene 1)
        captions = group_words_into_captions(
            word_timings, narration, scene_dur, is_hook_scene=(idx == 0), words_per_group=3
        )
        for cap in captions:
            all_captions.append({
                "text": cap["text"],
                "start": cumulative_time + cap["start"],
                "end": cumulative_time + cap["end"],
            })
        cumulative_time += scene_dur

        # B. Video Footage Fetching (Pixabay -> Fallback Stock -> Luxury Gradient) with asset validation
        ok = fetch_pixabay_video(query, video_raw_path) and validate_video_file(video_raw_path)
        if not ok:
            ok = fetch_fallback_stock_video(video_raw_path, idx) and validate_video_file(video_raw_path)

        if ok:
            try:
                raw_clip = VideoFileClip(str(video_raw_path)).without_audio()
                # Dynamic speed modification
                try:
                    raw_clip = raw_clip.with_effects([vfx.MultiplySpeed(1.02)])
                except Exception:
                    pass

                if raw_clip.duration < scene_dur:
                    n_loops = math.ceil(scene_dur / raw_clip.duration)
                    raw_clip = concatenate_videoclips([raw_clip] * n_loops)
                sub_clip = raw_clip.subclipped(0, scene_dur)

                # Vertical 9:16 crop & scale with 1.04x zoom for digital hash change
                rw, rh = sub_clip.size
                scale_factor = max(VIDEO_WIDTH / rw, VIDEO_HEIGHT / rh) * 1.04
                sw, sh = int(rw * scale_factor), int(rh * scale_factor)
                scaled_clip = sub_clip.resized((sw, sh))
                x1 = (sw - VIDEO_WIDTH) // 2
                y1 = (sh - VIDEO_HEIGHT) // 2
                vclip = scaled_clip.cropped(x1=x1, y1=y1, width=VIDEO_WIDTH, height=VIDEO_HEIGHT)

                # Overlay subtle vignette filter
                vignette_arr = create_vignette_overlay(VIDEO_WIDTH, VIDEO_HEIGHT)
                vig_clip = ImageClip(vignette_arr).with_duration(scene_dur)
                scene_vclip = CompositeVideoClip([vclip, vig_clip], size=(VIDEO_WIDTH, VIDEO_HEIGHT))
                scene_video_clips.append(scene_vclip)
            except Exception as e:
                print(f"[WARN] Failed to process video for scene {idx}: {e}. Using backdrop.")
                ok = False

        if not ok:
            print(f"[FALLBACK] Stock video invalid/missing for scene {idx}. Rendering luxury gradient.")
            backdrop_path = TEMP_DIR / f"backdrop_{idx}.png"
            create_gradient_backdrop(meta.get("title", topic), backdrop_path, idx)
            vclip = ImageClip(str(backdrop_path)).with_duration(scene_dur)
            scene_video_clips.append(vclip)

        scene_audio_clips.append(audio_clip)

    print("\n[STEP 2/4] Concatenating scenes and applying audio with ambient drone...")
    final_video_base = concatenate_videoclips(scene_video_clips, method="compose")
    speech_audio = concatenate_audioclips(scene_audio_clips)

    # Add -24 dB modern ambient audio bed
    try:
        ambient_path = TEMP_DIR / "ambient_drone.wav"
        create_ambient_drone(speech_audio.duration, ambient_path, is_dark=False)
        ambient_audio = AudioFileClip(str(ambient_path)).with_duration(speech_audio.duration)
        final_audio = CompositeAudioClip([speech_audio, ambient_audio])
        print(f"[AUDIO] Mixed -24 dB modern luxury ambient bed.")
    except Exception as exc:
        print(f"[WARN] Ambient audio mix fallback: {exc}")
        final_audio = speech_audio

    final_video = final_video_base.with_audio(final_audio)

    print("\n[STEP 3/4] Generating synchronized viral caption overlays...")
    caption_clips = []
    for cap in all_captions:
        dur = max(0.2, cap["end"] - cap["start"])
        overlay_arr = render_caption_overlay(cap["text"])
        c_clip = (
            ImageClip(overlay_arr)
            .with_start(cap["start"])
            .with_duration(dur)
        )
        caption_clips.append(c_clip)

    composite = CompositeVideoClip([final_video] + caption_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    composite = composite.with_duration(final_audio.duration)

    safe_title = re.sub(r"[^a-zA-Z0-9]+", "_", meta.get("title", topic))[:35]
    output_path = OUTPUT_DIR / f"Cosmic_{safe_title}.mp4"

    print(f"\n[STEP 4/4] Rendering vertical 1080x1920 MP4 to {output_path.name}...")
    composite.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        ffmpeg_params=["-crf", "22", "-pix_fmt", "yuv420p"],
        threads=4,
    )

    # Save metadata JSON for uploader
    meta_path = output_path.with_suffix(".json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Cosmic Secrets Short generated successfully: {output_path}")
    return output_path


if __name__ == "__main__":
    test_topic = sys.argv[1] if len(sys.argv) > 1 else "The brutal truth about money and freedom"
    build_shorts_video(test_topic)
