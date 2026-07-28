# Repository Behavioral Rules & Guardrails

## 🎵 Spotify Media Player & Synced Lyrics Module
- **CRITICAL STABLE VERIFIED IMPLEMENTATION**:
  1. `LYRICS_OFFSET` in `tools/sources/spotify.py` is strictly fixed to `0.7` seconds (the sweet spot for AppleScript IPC + UART serial transmission latency).
  2. `clean_song_title()` must preserve regex rules stripping `- Remastered`, `- Live`, `- Deluxe`, `- Single Version`, `- Radio Edit`, `(feat. ...)`, `[Official Audio]` to ensure exact matches on LRCLIB API.
  3. `fetch_synced_lyrics()` uses direct `GET /api/get?track_name=...&artist_name=...` as primary high-precision strategy, with search fallback and a 60-second cooldown on failed queries.
  4. Instrumental break wave `~~~ ~~ ~` must ONLY trigger on explicit LRC markers (`♪`, `[instrumental]`, etc.) or true long interludes (`>= 10.0s` gap and `elapsed >= 6.5s`) so slow song lyrics are NEVER cut off prematurely in the middle of a sentence!

## 🖥️ ESP32 Display Firmware (`src/main.cpp`)
- **CRITICAL DOUBLE-BUFFERING RULE**:
  1. `incomingCustomScreen` acts as the shadow double-buffer. All incoming serial fields populate `incomingCustomScreen`.
  2. The atomic frame commit `customScreen = incomingCustomScreen` MUST ONLY occur when the `END` token is received and verified (`fieldsInBlock > 0`). This prevents mid-frame flicker and split-second fallthrough to Page 1.
  3. `pageCustomScreen()` SubPage 1 must explicitly `return;` to prevent fallthrough to Page 1 layout.
