"""
Sumber data: Audio Spectrum Equalizer Visualizer.

Animasi 20-Bar Graphical Equalizer dirender secara LOKAL di firmware ESP32 pada kecepatan penuh (~25fps).
Python hanya mengirim status PLAYING/PAUSED dan info lagu — ESP32 menangani semua animasi grafis secara mandiri.

Halaman 1: Graphical Spectrum Equalizer (20 Bands + Floating Peak Hold) & Marquee Judul Lagu
Halaman 2: Detail Track, Progress, & Status Playback
"""

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

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        m = get_media_info()

        pos_m, pos_s = divmod(int(m["pos"]), 60)
        dur_m, dur_s = divmod(int(m["dur"] if m["dur"] < 10000 else m["dur"] / 1000), 60)
        time_fmt = f"{pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}"

        track_title = m["title"]
        artist_name = m["artist"]

        # Send "1" for playing, "0" for paused — ESP32 generates animation locally
        eq_state = "1" if m["playing"] else "0"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: ESP32-animated Graphical Spectrum Equalizer
                "hdr": f"SPECTRUM | {'PLAYING' if m['playing'] else 'PAUSED'}",
                "eq": eq_state,
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
            "input": 1 if m["playing"] else 0,
            "output": 20,
            "requests": 1,
            "project": f"EQ:{track_title[:10]}",
            "credit": float(m["pos"]),
            "models": [],
        }
