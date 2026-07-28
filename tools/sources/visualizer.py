"""
Sumber data: Audio Spectrum Equalizer Visualizer.

Animasi 20-Bar Graphical Equalizer Spectrum (VU Meter style dengan Floating Peak Hold) yang menari-nari sesuai lagu Spotify.
Halaman 1: Graphical Spectrum Equalizer (20 Bands + Peak Hold) & Marquee Judul Lagu
Halaman 2: Detail Track, Progress, & Status Playback
"""

import math
import subprocess
import time
from sources.base import TokenSource

NAME = "visualizer"
DISPLAY_NAME = "Audio Spectrum"


def get_media_info():
    script = """
    if application "Spotify" is running then
        tell application "Spotify"
            if player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                set trackPos to player position
                set trackDur to duration of current track
                return trackName & "||" & artistName & "||" & trackPos & "||" & trackDur
            end if
        end tell
    end if
    return "No Track||Spotify Idle||0||100"
    """
    try:
        out = (
            subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
        parts = out.split("||")
        if len(parts) == 4:
            return {
                "title": parts[0] or "No Track",
                "artist": parts[1] or "Spotify Idle",
                "pos": float(parts[2].replace(",", ".")) if parts[2] else 0.0,
                "dur": float(parts[3].replace(",", ".")) if parts[3] else 100.0,
                "playing": parts[0] != "No Track",
            }
    except Exception:
        pass
    return {"title": "No Track", "artist": "Spotify Idle", "pos": 0.0, "dur": 100.0, "playing": False}


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.frame = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def generate_20_eq_bands(self, is_playing):
        self.frame += 1
        bands = []
        num_bands = 20

        for i in range(num_bands):
            if is_playing:
                # Frequency spectrum simulation across 20 audio bands (Sub-bass, Bass, Mids, Highs)
                freq_offset = i * 0.45
                w1 = math.sin(self.frame * 0.5 + freq_offset) * 4.0
                w2 = math.cos(self.frame * 0.8 - freq_offset * 0.5) * 3.0
                w3 = math.sin(self.frame * 1.2 + freq_offset * 1.5) * 2.0
                jitter = (hash(f"{self.frame}_{i}") % 3)

                raw_val = w1 + w2 + w3 + 4.5 + jitter
                val = max(1, min(10, int(raw_val)))
            else:
                # Baseline idle pulse
                val = 1 if (i % 5 == 0 and (self.frame // 2) % 2 == 0) else 0

            bands.append(str(val))

        return ",".join(bands)

    def snapshot(self):
        m = get_media_info()
        eq_string = self.generate_20_eq_bands(m["playing"])

        pos_m, pos_s = divmod(int(m["pos"]), 60)
        dur_m, dur_s = divmod(int(m["dur"] if m["dur"] < 10000 else m["dur"] / 1000), 60)
        time_fmt = f"{pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}"

        track_title = m["title"]
        artist_name = m["artist"]

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Graphical Spectrum Equalizer (20 Bands + Peak Hold)
                "hdr": f"SPECTRUM | {'PLAYING' if m['playing'] else 'PAUSED'}",
                "eq": eq_string,
                "l2": track_title,
                "l3": artist_name,
                # Halaman 2: Details & Track Info
                "p2_hdr": f"AUDIO DET : {time_fmt}",
                "p2_l1": f"Lagu : {track_title[:16]}",
                "p2_l2": f"Artis: {artist_name[:16]}",
                "p2_l3": f"Time : {time_fmt}",
                "p2_l4": f"State: {'PLAYING' if m['playing'] else 'PAUSED'}",
            },
            "plan": "Visualizer",
            "model": track_title[:16],
            "effort": artist_name[:16],
            "context_used": int(m["pos"]),
            "context_max": max(int(m["dur"]), 1),
            "context_pct": int(m["pos"] / max(m["dur"], 1) * 100) if m["dur"] > 0 else 0,
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(m["pos"]),
            "input": self.frame,
            "output": 20,
            "requests": 1,
            "project": f"EQ:{track_title[:10]}",
            "credit": float(self.frame),
            "models": [],
        }
