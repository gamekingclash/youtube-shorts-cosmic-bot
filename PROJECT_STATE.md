# PROJECT_STATE.md

## Done
- Assigned dedicated voice (`en-US-BrianMultilingualNeural`, `rate=+3%`, `pitch=-2Hz`) and electric-cyan instant `t=0.0` hook caption identity in `main.py`.
- Upgraded script prompt to 5–6 scenes / 75–95 words (28–36s target) with `<62`-word retry guard, closing comment question, and `_clean_cosmic_title`.
- Added topic + title token-overlap deduplication (`_is_duplicate_cosmic_item`, `_ensure_unique_title`) in `auto_pilot.py`.
- Focused Shorts to 1x/day US prime-time (`20:30 UTC`, 18h spacing in `uploader.py` & `daily_cosmic_shorts.yml`) and paused auto-cron on `weekly_long_cosmic.yml` (manual `workflow_dispatch` preserved while `0-view` long-form hurts retention); verified with `py_compile` + unit checks.

## Current State
- `youtube-shorts-cosmic-bot` updated, verified, and pushed to `origin/main`.

## Next Step
- Monitor 1x/day Cosmic Shorts (`20:30 UTC`) recovery over the next 5–7 days before re-enabling long-form cron.
