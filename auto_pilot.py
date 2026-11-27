import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
from main import build_shorts_video
from uploader import upload_shorts_video
from multi_platform_uploader import upload_to_facebook_reels, upload_to_tiktok

HISTORY_FILE = BASE_DIR / "history.json"


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_to_history(topic: str, title: str, url: str, publish_at: str = None):
    history = load_history()
    entry = {
        "topic": topic,
        "title": title,
        "url": url,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    }
    if publish_at:
        entry["publish_at"] = publish_at
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


VIRAL_COSMIC_PROMPTS = [
    "What James Webb just discovered at the edge of the universe terrified scientists",
    "What actually happens to your body if you fall into a supermassive black hole",
    "The Great Attractor: The invisible cosmic force pulling our entire galaxy",
    "Why the Fermi Paradox is the scariest question in astrophysics",
    "The terrifying reality of magnetars: Stars that can erase your DNA from light years away",
    "The Boötes Void: Why is there an empty region in space 330 million light-years wide",
    "The Wow! Signal: The 72-second extraterrestrial broadcast science still cannot explain",
    "What if the Big Bang was not the beginning of the universe?",
    "Rogue planets: Giant dark worlds wandering alone in deep interstellar space",
    "The Heat Death: What the final second of our universe will look like",
    "The mysterious radio pulses repeating every 16 days from deep space",
    "Why time slows down near a black hole: Gravitational time dilation explained",
    "The cosmic web: Why the large-scale universe looks identical to human brain neurons",
    "The Pillars of Creation: Giant towers of gas and dust birthing new solar systems",
    "Why moving at the speed of light means you never experience time at all",
    "Dark Energy: The mysterious 68% of the universe that is tearing space apart",
    "Oumuamua: Was the first interstellar object visiting our solar system alien technology?",
    "The Dyson Sphere: How advanced alien civilizations could harvest entire stars",
    "Neutron stars: A single teaspoon weighs more than Mount Everest",
    "The multiverse theory: Are infinite versions of you living in parallel dimensions?",
    "What happens when the Andromeda galaxy collides with our Milky Way?",
    "KIC 8462852: The star whose light fluctuations science still cannot explain",
    "The cosmic horizon: The point in space we will never be able to see",
    "Solar superstorms: The Carrington Event that could fry our entire power grid",
    "The dark matter mystery: Why 85% of cosmic mass is completely invisible"
]


_COSMIC_STOP_WORDS = {
    "that", "this", "with", "from", "your", "about", "what", "when", "where",
    "which", "while", "into", "happens", "space", "cosmic", "universe", "galaxy",
    "star", "planet", "shorts", "earth", "actually", "really", "could", "would",
    "inside", "through", "coming", "deep",
}


def _norm_text(s: str) -> str:
    s = re.sub(r"#shorts", "", s or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s.lower())).strip()


def _meaningful_tokens(s: str) -> set[str]:
    return {w for w in _norm_text(s).split() if len(w) >= 4 and w not in _COSMIC_STOP_WORDS}


def _is_duplicate_cosmic_item(candidate: str, history: list[dict]) -> bool:
    cand_norm = _norm_text(candidate)
    if not cand_norm:
        return True
    cand_tokens = _meaningful_tokens(cand_norm)
    for item in history:
        for field in ("topic", "title"):
            past_norm = _norm_text(item.get(field, ""))
            if past_norm and cand_norm == past_norm:
                return True
    for item in history[-80:]:
        for field in ("topic", "title"):
            past_tokens = _meaningful_tokens(item.get(field, ""))
            if not cand_tokens or not past_tokens:
                continue
            overlap = cand_tokens & past_tokens
            union = cand_tokens | past_tokens
            if len(overlap) >= 2 and (len(overlap) / len(union) >= 0.45 or len(overlap) >= 3):
                return True
    return False


def _ensure_unique_title(title: str, topic: str, history: list[dict]) -> str:
    cand_norm = _norm_text(title)
    past_titles = {_norm_text(item.get("title", "")) for item in history}
    if cand_norm and cand_norm not in past_titles:
        return title
    clean_topic = re.sub(r"#shorts", "", topic or "", flags=re.IGNORECASE).strip().rstrip("?.!:-")
    if len(clean_topic) > 50:
        clean_topic = clean_topic[:50].rsplit(" ", 1)[0].rstrip(".,:-")
    alt = f"{clean_topic} #shorts"
    if _norm_text(alt) not in past_titles:
        print(f"[DEDUP] Replaced duplicate title '{title}' -> '{alt}'")
        return alt
    return title


def pick_viral_topic() -> str:
    """
    Picks a fresh viral English topic using Gemini or the curated list,
    strictly avoiding any previously covered topics or titles.
    """
    history = load_history()
    past_entries = [
        f"{item.get('topic', '')} | Title: {item.get('title', '')}".strip()
        for item in history[-80:]
    ]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            import requests

            past_list_str = "\n- ".join(past_entries) if past_entries else "None"
            prompt = (
                "We have ALREADY published YouTube Shorts about these cosmic & space topics and titles:\n"
                f"- {past_list_str}\n\n"
                "CRITICAL RULE: Suggest ONE brand new, mind-bending YouTube Shorts topic in English about "
                "space exploration, astrophysics, black holes, cosmic anomalies, or deep universe mysteries.\n"
                "Prefer high-curiosity 'What Happens If/When...' or 'Why...' questions about real astrophysics/space phenomena.\n"
                "Do NOT duplicate or closely paraphrase ANY topic or title above.\n"
                "Return ONLY the topic sentence, under 10 words, no quotes."
            )
            for _attempt in range(3):
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=12,
                )
                if r.status_code == 200:
                    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"\'` ')
                    if txt and len(txt) > 5 and not _is_duplicate_cosmic_item(txt, history):
                        return txt
        except Exception:
            pass

    available = [t for t in VIRAL_COSMIC_PROMPTS if not _is_duplicate_cosmic_item(t, history)]
    if not available:
        available = VIRAL_COSMIC_PROMPTS
    return random.choice(available)


def run_autopilot(privacy_status: str = "scheduled"):
    print("=" * 60)
    print("      24/7 AUTONOMOUS COSMIC SECRETS SHORTS ENGINE      ")
    print("=" * 60)

    # 1. Pick viral topic
    topic = pick_viral_topic()
    print(f"\n[TOPIC SELECTED] {topic}")

    # 2. Build complete Short video
    video_path = build_shorts_video(topic)

    # 3. Load generated metadata (supports both .json and _metadata.json)
    meta_path = video_path.with_suffix(".json")
    if not meta_path.exists():
        meta_path = video_path.with_name(video_path.stem + "_metadata.json")
    clean_topic = topic.strip().rstrip("?.!")
    fallback_title = clean_topic[:55].rsplit(" ", 1)[0].rstrip(".,:-") if len(clean_topic) > 55 else clean_topic
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        title = _ensure_unique_title(meta.get("title", f"{fallback_title} #shorts"), topic, load_history())
        description = meta.get("description", f"Exploring {clean_topic} in deep space. #shorts #space #astronomy #universe #cosmic #science")
    else:
        title = _ensure_unique_title(f"{fallback_title} #shorts", topic, load_history())
        description = f"Exploring {clean_topic} in deep space. Subscribe for daily cosmic insights! #shorts #space #astronomy #universe #cosmic"

    tags = ["shorts", "space", "astronomy", "universe", "cosmic", "science", "blackhole", "deepspace", "astrophysics"]

    # 4. Upload to YouTube
    print(f"\n[AUTOPILOT] Uploading to YouTube ({privacy_status})...")
    url = upload_shorts_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status
    )

    # 5. Dual publishing to Facebook Reels & TikTok
    upload_to_facebook_reels(video_path=video_path, description=f"{title}\n\n{description}")
    upload_to_tiktok(video_path=video_path, title=title)

    # 6. Save to history
    import uploader as _uploader
    save_to_history(topic=topic, title=title, url=url, publish_at=getattr(_uploader, "LAST_SCHEDULED_PUBLISH_AT", None))
    print("\n" + "=" * 60)
    print(f"[SUCCESS] Cosmic Short Live on YouTube: {url}")
    print("=" * 60)
    return url


if __name__ == "__main__":
    privacy = "scheduled"
    if "--public" in sys.argv:
        privacy = "public"
    elif "--unlisted" in sys.argv:
        privacy = "unlisted"
    elif "--private" in sys.argv:
        privacy = "private"
    run_autopilot(privacy_status=privacy)
