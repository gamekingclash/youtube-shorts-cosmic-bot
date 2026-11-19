# PROJECT_STATE.md

## Done
- Removed `"3d"`, `"animation"`, `"vfx"`, `"loop"` over-filtering from `FORBIDDEN_TAGS` in `main.py` and `long_form_cosmic.py`, and added `video_type=all` fallback after `video_type=film` so space/black-hole/exoplanet simulations are available while pixel-level green-screen rejection remains active.
- Expanded `CURATED_COSMIC_QUERIES` (10 -> 18) and `REQUIRED_COSMIC_CONCEPTS` to eliminate exhausted Pixabay queries.
- Hardened `main.py` Gemini call (`responseMimeType: "application/json"` + retry) and updated `auto_pilot.py` to deduplicate against `past_topics[-80:]` with curiosity-question hooks.

## Current State
- `youtube-shorts-cosmic-bot` updated and verified (`py_compile` + Gemini smoke test + Pixabay pool check).

## Next Step
- Monitor upcoming Cosmic Shorts (`20:30` / `00:30 UTC`) for Shorts feed distribution recovery.
