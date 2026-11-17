# PROJECT_STATE.md

## Done
- Fixed metadata JSON filename mismatch in `auto_pilot.py` (now checks both `.json` and `_metadata.json` so Gemini titles/descriptions are no longer discarded).
- Replaced copy-pasted Finance fallback script in `main.py` with genuine Cosmic space/astrophysics fallback and added clean title normalization (`<=55` chars + `#shorts`).
- Added `get_next_cosmic_publish_time` in `uploader.py` (`20:30` & `00:30 UTC` US prime slots with collision avoidance) to eliminate `07:36 TRT` dead-hour drift.

## Current State
- Cosmic Secrets bot updated with working metadata resolution, space-themed fallback, and US prime-time scheduling.

## Next Step
- Push changes to `origin/main` and monitor upcoming Cosmic Shorts views and metadata.
