"""
Sumber data: Spotify / Apple Music Media Player (macOS) + Synced Lyrics.

Membaca metadata lagu yang sedang diputar di macOS via AppleScript,
mengambil lirik tersinkronisasi dari LRCLIB API, serta mendukung marquee scrolling text.
"""

import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from sources.base import TokenSource

NAME = "spotify"
DISPLAY_NAME = "Media Player"

APPLESCRIPT_SPOTIFY = """
if application "Spotify" is running then
    tell application "Spotify"
        if player state is playing then
            set trackName to name of current track
            set artistName to artist of current track
            set albumName to album of current track
            set trackDur to duration of current track
            set trackPos to player position
            return trackName & "||" & artistName & "||" & albumName & "||" & trackPos & "||" & trackDur
        else
            return "Paused||Spotify||Spotify||0||100"
        end if
    end tell
else if application "Music" is running then
    tell application "Music"
        if player state is playing then
            set trackName to name of current track
            set artistName to artist of current track
            set albumName to album of current track
            set trackDur to duration of current track
            set trackPos to player position
            return trackName & "||" & artistName & "||" & albumName & "||" & trackPos & "||" & trackDur
        else
            return "Paused||Music||Music||0||100"
        end if
    end tell
else
    return "No Media||Stopped||Stopped||0||100"
end if
"""

# In-memory lyrics cache: key -> list of (timestamp_seconds, text)
LYRICS_CACHE = {}


def parse_lrc(lrc_text):
    lines = []
    for line in lrc_text.splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
        if m:
            mins = float(m.group(1))
            secs = float(m.group(2))
            text = m.group(3).strip()
            if text:
                lines.append((mins * 60.0 + secs, text))
    lines.sort(key=lambda x: x[0])
    return lines


def clean_song_title(title):
    # Remove (...) and [...]
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)
    # Remove "- 2020 Remaster", "- Live", "- Deluxe", "- Single Version", "- Radio Edit", etc.
    t = re.sub(r"\s*-\s*.*?(remaster|live|deluxe|version|edit|edition|mono|stereo).*", "", t, flags=re.IGNORECASE)
    # Remove "feat. ...", "ft. ...", "with ..."
    t = re.sub(r"\s+(feat\.|ft\.|with)\s+.*", "", t, flags=re.IGNORECASE)
    return t.strip()


def fetch_synced_lyrics(title, artist, album="", duration=0):
    if not title or title in ("No Media", "Paused", "Tidak Ada Media"):
        return []

    c_title = clean_song_title(title)
    c_artist = artist.strip()
    primary_artist = re.split(r"[,&/]", c_artist)[0].strip()

    key = f"{c_title.lower()}|{c_artist.lower()}"
    now = time.time()

    if key in LYRICS_CACHE:
        ts, data = LYRICS_CACHE[key]
        if data or (now - ts) < 60:
            return data

    # Strategy 1: Direct GET API with clean_title and artist
    for a_name in (c_artist, primary_artist):
        params = {"track_name": c_title, "artist_name": a_name}
        if duration > 0:
            params["duration"] = str(duration)
        url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SpotifyBar/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    d = json.loads(resp.read().decode("utf-8"))
                    lrc = d.get("syncedLyrics") or d.get("plainLyrics")
                    if lrc:
                        parsed = parse_lrc(lrc)
                        if parsed:
                            LYRICS_CACHE[key] = (now, parsed)
                            return parsed
        except Exception:
            pass

    # Strategy 2: SEARCH API with clean_title and primary_artist
    query_str = f"{c_title} {primary_artist}"
    url = "https://lrclib.net/api/search?q=" + urllib.parse.quote(query_str)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpotifyBar/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                items = json.loads(resp.read().decode("utf-8"))
                if isinstance(items, list):
                    for item in items:
                        lrc = item.get("syncedLyrics") or item.get("plainLyrics")
                        if lrc:
                            parsed = parse_lrc(lrc)
                            if parsed:
                                LYRICS_CACHE[key] = (now, parsed)
                                return parsed
    except Exception:
        pass

    LYRICS_CACHE[key] = (now, [])
    return []


# ==============================================================================
# ⚠️ GUARDRAIL & CONFIGURATION WARNING (STABLE VERIFIED VERSION)
# DILARANG MENGUBAH PARAMETER SINKRONISASI SPOTIFY DENGAN SEMBARANGAN!
# 1. LYRICS_OFFSET diset presisi ke 0.7s (Sweet Spot delay AppleScript + UART).
# 2. Pembersihan judul (clean_song_title) melindungi remaster/deluxe/live/feat.
# 3. LRCLIB fetch menggunakan direct GET + search fallback + 60s cooldown cache.
# 4. Instrumental break ~~~ ~~ ~ HANYA aktif untuk jeda > 10.0s & elapsed >= 6.5s
#    agar lirik lagu lambat TIDAK TERPOTONG di tengah kalimat!
# ==============================================================================

LYRICS_OFFSET = 0.7


def get_current_lyric_lines(lyrics, current_pos):
    """Kembalikan (prev_line, current_active_line, next_line)."""
    if not lyrics:
        return ("", "Lirik tidak ditemukan", "")

    effective_pos = current_pos + LYRICS_OFFSET

    # 1. Intro sebelum lirik pertama dimulai (> 2.5 detik)
    if len(lyrics) > 0 and (lyrics[0][0] - effective_pos > 2.5):
        return ("", "~~~ ~~ ~", lyrics[0][1])

    current_idx = -1
    for idx, (ts, text) in enumerate(lyrics):
        if ts <= effective_pos:
            current_idx = idx
        else:
            break

    if current_idx == -1:
        prev_t = ""
        curr_t = lyrics[0][1] if len(lyrics) > 0 else ""
        next_t = lyrics[1][1] if len(lyrics) > 1 else ""
    else:
        current_ts, current_text = lyrics[current_idx]
        next_ts = lyrics[current_idx + 1][0] if current_idx + 1 < len(lyrics) else None

        # 2. Jeda musik/instrumen antar baris (hanya untuk jeda instrumen panjang > 10 detik)
        elapsed = effective_pos - current_ts
        is_instrumental = False
        if not current_text or current_text.lower() in ("♪", "[instrumental]", "(instrumental)", "[music]", "(music)"):
            is_instrumental = True
        elif next_ts and (next_ts - current_ts >= 10.0):
            # Hanya masuk wave ~~~ ~~ ~ jika jeda > 10s dan sudah tampil minimal 6.5s
            if elapsed >= 6.5:
                is_instrumental = True

        if is_instrumental:
            curr_t = "~~~ ~~ ~"
        else:
            curr_t = current_text

        prev_t = lyrics[current_idx - 1][1] if current_idx > 0 else ""
        next_t = lyrics[current_idx + 1][1] if current_idx + 1 < len(lyrics) else ""

    return (prev_t, curr_t, next_t)


def marquee_text(text, max_len=14):
    text = text.strip()
    if len(text) <= max_len:
        return text
    padded = text + "   *   " + text
    offset = int(time.time() * 2) % (len(text) + 7)
    return padded[offset : offset + max_len]


def get_media_info():
    try:
        out = (
            subprocess.check_output(
                ["osascript", "-e", APPLESCRIPT_SPOTIFY], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
        parts = out.split("||")
        if len(parts) == 5:
            full_title = parts[0]
            full_artist = parts[1]
            full_album = parts[2]
            pos_str = parts[3].replace(",", ".")
            dur_str = parts[4].replace(",", ".")
            pos = float(pos_str) if pos_str else 0.0
            dur = float(dur_str) if dur_str else 100.0
            if dur > 10000:
                dur = dur / 1000.0
            pct = int((pos / dur * 100)) if dur > 0 else 0
            return {
                "title": full_title or "No Media",
                "artist": full_artist or "-",
                "album": full_album or "",
                "pos": int(pos),
                "dur": int(dur),
                "pct": min(pct, 100),
            }
    except Exception:
        pass
    return {
        "title": "Tidak Ada Media",
        "artist": "Spotify/Music",
        "album": "",
        "pos": 0,
        "dur": 100,
        "pct": 0,
    }


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)

    def available(self):
        return True

    def totals(self):
        return {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "cost": 0.0,
            "requests": 0,
        }

    def snapshot(self):
        m = get_media_info()
        pos_m, pos_s = divmod(m["pos"], 60)
        dur_m, dur_s = divmod(m["dur"], 60)
        time_fmt = f"{pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}"

        # Fetch synced lyrics
        lyrics = fetch_synced_lyrics(m["title"], m["artist"], m["album"], m["dur"])
        prev_lyr, curr_lyr, next_lyr = get_current_lyric_lines(lyrics, m["pos"])

        title_mq = marquee_text(m["title"], max_len=14)
        artist_mq = marquee_text(m["artist"], max_len=14)

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Page 1: Player Dashboard
                "hdr": f"NOW PLAYING | 1/2",
                "l1": f"Lagu : {m['title']}",
                "l2": f"Artis: {m['artist']}",
                "l3": f"Waktu: {time_fmt}",
                "bar2": m["pct"],
                # Page 2: Synced Lyrics (Single active lyric focus + Song title marquee)
                "p2_hdr": f"{m['title']} | 2/2",
                "p2_l2": curr_lyr if curr_lyr else "-",
            },
            "plan": "Player",
            "model": m["title"],
            "effort": m["artist"],
            "context_used": m["pos"],
            "context_max": max(m["dur"], 1),
            "context_pct": m["pct"],
            "limit_5h_pct": m["pct"],
            "limit_5h_mins": 300,
            "limit_week_pct": m["pct"],
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": m["pos"],
            "output": m["dur"],
            "requests": m["pct"],
            "project": time_fmt,
            "credit": 0.0,
            "models": [
                {"model": m["title"], "cost": 0.0, "pct": m["pct"]},
                {"model": m["artist"], "cost": 0.0, "pct": m["pct"]},
            ],
        }
