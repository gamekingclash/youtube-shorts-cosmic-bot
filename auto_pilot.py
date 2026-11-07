import json
import os
import random
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


def save_to_history(topic: str, title: str, url: str):
    history = load_history()
    history.append({
        "topic": topic,
        "title": title,
        "url": url,
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })
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

    "3 brutal money truths 99% of people realize too late in life",
    "How the top 1% use debt to become richer while the poor stay broke",
    "Warren Buffett's 5/25 rule for extreme wealth and focus",
    "The silent psychological money trap keeping most people poor",
    "3 dark tricks luxury brands use to make you feel broke",
    "Why saving money in a bank account is a guaranteed loss",
    "The 24-hour rule millionaires use before spending any money",
    "How self-made billionaires think about risk and asymmetric bets",
    "3 daily financial habits that separate the rich from the middle class",
    "The psychology of compounding interest: How small habits build empires",
    "Why a monthly salary is the drug employers give you to forget your ambition",
    "The unspoken rules of wealth they intentionally never taught in school",
    "How to negotiate business deals and salary like a high-stakes closer",
    "Why truly wealthy people practice stealth wealth and never brag",
    "The asset vs liability mindset explained in under 30 seconds",
    "The psychological difference between being rich and being truly wealthy",
    "How money amplifies who you truly are inside",
    "The 3 financial leaks draining your net worth without you knowing",
]


def pick_viral_topic() -> str:
    """
    Picks a fresh viral English topic using Gemini or the curated list,
    strictly avoiding any previously covered topics.
    """
    history = load_history()
    past_topics = [item.get("topic", "").lower() for item in history]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            import requests

            past_list_str = "\n- ".join(past_topics[-15:]) if past_topics else "None"
            prompt = f"""
We have ALREADY published YouTube Shorts about these wealth & finance topics:
- {past_list_str}

CRITICAL RULE: Suggest ONE brand new, fresh, high-status YouTube Shorts topic in English about wealth mindset, millionaire psychology, money traps, or asymmetric investing.
Do NOT duplicate or repeat the ideas above.
Return ONLY the topic sentence, under 10 words, no quotes.
"""
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=12,
            )
            if r.status_code == 200:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if txt and len(txt) > 5 and txt.lower() not in past_topics:
                    return txt.strip('"')
        except Exception:
            pass

    # Fallback to curated list
    available = [p for p in VIRAL_COSMIC_PROMPTS if p.lower() not in past_topics]
    if not available:
        available = VIRAL_COSMIC_PROMPTS
    return random.choice(available)


def run_autopilot(privacy_status: str = "scheduled"):
    print("=" * 60)
    print("      24/7 AUTONOMOUS WEALTH & FINANCE SHORTS ENGINE      ")
    print("=" * 60)

    # 1. Pick unique topic
    topic = pick_viral_topic()
    print(f"\n[AUTOPILOT] Selected Topic: '{topic}'")

    # 2. Build video
    video_path = build_shorts_video(topic)

    # 3. Load generated metadata
    meta_path = video_path.with_suffix(".json")
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        title = meta.get("title", f"{topic.title()} #shorts")
        description = meta.get("description", f"{topic} #shorts #money #wealth #mindset")
    else:
        title = f"{topic.title()} #shorts"
        description = f"The hidden truth about {topic}. Subscribe for daily wealth insights! #shorts #money #wealth"

    tags = ["shorts", "space", "astronomy", "universe", "blackhole", "science", "astrophysics", "cosmos"]

    # 4. Upload to YouTube
    print(f"\n[AUTOPILOT] Uploading to YouTube ({privacy_status})...")
    url = upload_shorts_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
    )

    # 4b. Cross-post to Facebook Reels & TikTok if credentials are configured
    upload_to_facebook_reels(video_path=video_path, description=f"{title}\n\n{description}")
    upload_to_tiktok(video_path=video_path, title=title)

    # 5. Log to history
    save_to_history(topic=topic, title=title, url=url)
    print("\n" + "=" * 60)
    print(f"[SUCCESS] Cosmic Short Live on YouTube: {url}")
    print("=" * 60)
    return url


if __name__ == "__main__":
    is_public = "--public" in sys.argv
    is_private = "--private" in sys.argv
    if is_public:
        privacy = "public"
    elif is_private:
        privacy = "private"
    else:
        # Default to unlisted for spam flag & algorithmic indexing protection
        privacy = "scheduled"
    run_autopilot(privacy_status=privacy)
