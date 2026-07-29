"""
Sumber data: Stage Karaoke & Advanced Beat Visualizer (Modul #18).

Menggabungkan Real-Time Audio Spectrum Equalizer (FFT via BlackHole) + Synced Spotify Lyrics
dengan Word-by-Word Karaoke Engine, Beat Shaking, dan Dancing Line Animations.
"""

import math
import re
import subprocess
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from sources.base import TokenSource

NAME = "stage"
DISPLAY_NAME = "Stage Karaoke"

# Coba import audio libraries
try:
    import numpy as np
    import sounddevice as sd
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# ==============================================================================
# Transliterasi Unicode → ASCII
# ==============================================================================
_CYRILLIC_MAP = {
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'І': 'I', 'і': 'i', 'Ї': 'Yi', 'ї': 'yi', 'Є': 'Ye', 'є': 'ye',
    'Ґ': 'G', 'ґ': 'g',
}


def transliterate_to_ascii(text):
    if not text:
        return text
    res = []
    for ch in text:
        if ord(ch) < 128:
            res.append(ch)
            continue
        if ch in _CYRILLIC_MAP:
            res.append(_CYRILLIC_MAP[ch])
            continue
        decomposed = unicodedata.normalize('NFKD', ch)
        ascii_chars = ''.join(c for c in decomposed if ord(c) < 128)
        if ascii_chars:
            res.append(ascii_chars)
            continue
        res.append('')
    return ''.join(res)


# ==============================================================================
# Audio Capture FFT Thread (Low Latency)
# ==============================================================================
def find_blackhole_device():
    if not HAS_AUDIO:
        return None
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = d["name"].lower()
            if "blackhole" in name and d["max_input_channels"] >= 2:
                return i
        return None
    except Exception:
        return None


class AudioCaptureThread(threading.Thread):
    def __init__(self, device_id):
        super().__init__(daemon=True)
        self.device_id = device_id
        self.sample_rate = 44100
        self.block_size = 1024
        self.num_bands = 20
        self.bands = [0] * self.num_bands
        self.lock = threading.Lock()
        self.running = True
        self.smooth = 0.6
        self.smoothed = [0.0] * self.num_bands
        self.freq_edges = np.logspace(
            np.log10(60), np.log10(16000), self.num_bands + 1
        )

    def run(self):
        try:
            with sd.InputStream(
                device=self.device_id,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback,
                latency='low',
            ):
                while self.running:
                    time.sleep(0.05)
        except Exception:
            self.running = False

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            signal = indata[:, 0]
            windowed = signal * np.hanning(len(signal))
            fft_data = np.abs(np.fft.rfft(windowed))
            freqs = np.fft.rfftfreq(len(windowed), 1.0 / self.sample_rate)

            new_bands = []
            for i in range(self.num_bands):
                lo = self.freq_edges[i]
                hi = self.freq_edges[i + 1]
                mask = (freqs >= lo) & (freqs < hi)
                magnitude = np.mean(fft_data[mask]) if np.any(mask) else 0.0

                if magnitude > 1e-8:
                    db = 20 * np.log10(magnitude + 1e-10)
                    raw = (db + 10) / 3.5
                    raw = max(0.0, min(10.0, raw))
                else:
                    raw = 0.0

                self.smoothed[i] = self.smoothed[i] * (1 - self.smooth) + raw * self.smooth
                val = int(round(self.smoothed[i]))
                new_bands.append(max(0, min(10, val)))

            with self.lock:
                self.bands = new_bands
        except Exception:
            pass

    def get_bands(self):
        with self.lock:
            return list(self.bands)


# ==============================================================================
# Spotify AppleScript & Synced Lyrics Engine
# ==============================================================================
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

LYRICS_CACHE = {}
LYRICS_OFFSET = 0.7


def clean_song_title(title):
    t = re.sub(
        r"\s*-\s*(Remastered|Live|Deluxe|Single Version|Radio Edit|Bonus Track).*",
        "",
        title,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\s*\[(Official Audio|Official Video|Audio|Video)\].*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\(feat\..*?\)", "", t, flags=re.IGNORECASE)
    return t.strip()


def parse_lrc(lrc_text):
    lines = []
    for line in lrc_text.splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\](.*)", line)
        if m:
            mins = float(m.group(1))
            secs = float(m.group(2))
            text = m.group(3).strip()
            total_sec = mins * 60.0 + secs
            if text:
                lines.append((total_sec, text))
    lines.sort(key=lambda x: x[0])
    return lines


def fetch_synced_lyrics(title, artist, album="", duration=0):
    if not title or title in ("No Media", "Paused", "Tidak Ada Media"):
        return []

    c_title = clean_song_title(title)
    key = f"{c_title.lower()}||{artist.lower()}"
    now = time.time()

    if key in LYRICS_CACHE:
        cached_time, cached_data = LYRICS_CACHE[key]
        if cached_data or (now - cached_time) < 60:
            return cached_data

    try:
        query = urllib.parse.urlencode({"track_name": c_title, "artist_name": artist})
        url = f"https://lrclib.net/api/get?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "I2C-OLED-Stage/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("syncedLyrics"):
                parsed = parse_lrc(data["syncedLyrics"])
                if parsed:
                    LYRICS_CACHE[key] = (now, parsed)
                    return parsed
    except Exception:
        pass

    try:
        query = urllib.parse.urlencode({"q": f"{c_title} {artist}"})
        url = f"https://lrclib.net/api/search?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "I2C-OLED-Stage/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                for item in data:
                    if item.get("syncedLyrics"):
                        parsed = parse_lrc(item["syncedLyrics"])
                        if parsed:
                            LYRICS_CACHE[key] = (now, parsed)
                            return parsed
    except Exception:
        pass

    LYRICS_CACHE[key] = (now, [])
    return []


# ==============================================================================
# Word-by-Word Karaoke Engine
# ==============================================================================
def calculate_word_karaoke(lyrics, current_pos):
    """Hitung lirik aktif, kata aktif, dan progress kata (0..N-1)."""
    if not lyrics:
        return "", "No Synced Lyric", 0, 1

    effective_pos = current_pos + LYRICS_OFFSET

    # Intro check
    if len(lyrics) > 0 and (lyrics[0][0] - effective_pos > 2.5):
        return "~~~ ~~ ~", "~~~ ~~ ~", 0, 1

    active_idx = -1
    for i, (ts, text) in enumerate(lyrics):
        if effective_pos >= ts:
            active_idx = i
        else:
            break

    if active_idx == -1:
        return "", lyrics[0][1], 0, 1

    line_ts, line_text = lyrics[active_idx]

    # End timestamp is next line's timestamp or line_ts + 4s
    if active_idx + 1 < len(lyrics):
        next_ts = lyrics[active_idx + 1][0]
    else:
        next_ts = line_ts + 4.0

    line_dur = max(0.5, next_ts - line_ts)
    elapsed_in_line = max(0.0, min(line_dur, effective_pos - line_ts))

    words = line_text.split()
    if not words:
        return line_text, line_text, 0, 1

    # Weighted duration per word based on word character lengths
    total_chars = sum(max(1, len(w)) for w in words)
    word_starts = []
    accum_time = 0.0
    for w in words:
        w_dur = (max(1, len(w)) / total_chars) * line_dur
        word_starts.append(accum_time)
        accum_time += w_dur

    # Find active word index
    active_word_idx = 0
    for idx, w_start in enumerate(word_starts):
        if elapsed_in_line >= w_start:
            active_word_idx = idx

    active_word = words[active_word_idx]
    return line_text, active_word, active_word_idx, len(words)


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
                "pos": pos,
                "dur": dur,
                "pct": min(pct, 100),
                "playing": full_title not in ("No Media", "Paused", "Tidak Ada Media"),
            }
    except Exception:
        pass
    return {
        "title": "No Media",
        "artist": "Spotify/Music",
        "album": "",
        "pos": 0.0,
        "dur": 100.0,
        "pct": 0,
        "playing": False,
    }


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.audio_thread = None
        self.has_real_audio = False

        if HAS_AUDIO:
            device_id = find_blackhole_device()
            if device_id is not None:
                try:
                    self.audio_thread = AudioCaptureThread(device_id)
                    self.audio_thread.start()
                    self.has_real_audio = True
                    print(f"[INFO] Stage Audio FFT via BlackHole (device #{device_id})")
                except Exception as e:
                    print(f"[WARN] Gagal start stage audio FFT: {e}")

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        m = get_media_info()
        pos_m, pos_s = divmod(int(m["pos"]), 60)
        dur_m, dur_s = divmod(int(m["dur"]), 60)
        time_fmt = f"{pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}"

        # Synced Lyrics + Word Karaoke
        lyrics = fetch_synced_lyrics(m["title"], m["artist"], m["album"], m["dur"])
        full_line, active_word, word_idx, total_words = calculate_word_karaoke(lyrics, m["pos"])

        # Transliterasi to ASCII
        safe_title = transliterate_to_ascii(m["title"])
        safe_artist = transliterate_to_ascii(m["artist"])
        safe_line = transliterate_to_ascii(full_line)
        safe_word = transliterate_to_ascii(active_word)

        # Determine EQ String
        if self.has_real_audio and self.audio_thread and self.audio_thread.running:
            bands = self.audio_thread.get_bands()
            eq_string = ",".join(str(v) for v in bands)
        else:
            eq_string = "1" if m["playing"] else "0"

        # Format karaoke highlight tag for ESP32: line||active_word_idx
        stage_karaoke_data = f"{safe_line}||{word_idx}||{safe_word}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Page 1: Stage Karaoke + Spectrum Visualizer
                "hdr": f"STAGE | {'PLAYING' if m['playing'] else 'PAUSED'}",
                "eq": eq_string,
                "l1": f"{safe_title} - {safe_artist}",
                "l2": stage_karaoke_data,
                "l3": f"W:{word_idx+1}/{total_words} [{safe_word}]",
                "l4": time_fmt,

                # Page 2: Details & Track Info
                "p2_hdr": f"STAGE DET | {time_fmt}",
                "p2_l1": f"Lagu : {safe_title[:16]}",
                "p2_l2": f"Artis: {safe_artist[:16]}",
                "p2_l3": f"Word : {safe_word[:16]}",
                "p2_l4": f"Audio: {'REALTIME' if self.has_real_audio else 'PROCEDURAL'}",
            },
            "plan": "Stage",
            "model": safe_title[:16],
            "effort": safe_artist[:16],
            "context_used": int(m["pos"]),
            "context_max": max(int(m["dur"]), 1),
            "context_pct": m["pct"],
            "limit_5h_pct": m["pct"],
            "limit_5h_mins": 300,
            "limit_week_pct": m["pct"],
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": int(m["pos"]),
            "output": int(m["dur"]),
            "requests": m["pct"],
            "project": time_fmt,
            "credit": 0.0,
            "models": [],
        }
