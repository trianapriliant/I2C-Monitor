"""
Sumber data: Pixel Art Desk Companion & Mascot.

Maskot piksel reaktif yang menyesuaikan status PC & Musik:
- HOT     : Jika CPU > 75% (kepanasan)
- DANCING : Jika Spotify/Musik menyala (berjoget)
- SLEEPING: Jika malam hari / PC idle (tidur zZ)
- WORKING : Jika sedang mengetik / coding aktif (fokus)
"""

import os
import subprocess
import time
from sources.base import TokenSource

NAME = "companion"
DISPLAY_NAME = "Desk Mascot"


def get_cpu_load():
    try:
        out = (
            subprocess.check_output(["top", "-l", "1", "-n", "0"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .splitlines()
        )
        for line in out:
            if "CPU usage:" in line:
                # CPU usage: 5.2% user, 3.1% sys, 91.7% idle
                parts = line.split(",")
                user_pct = float(parts[0].split(":")[1].replace("%", "").strip().split()[0])
                sys_pct = float(parts[1].replace("%", "").strip().split()[0])
                return user_pct + sys_pct
    except Exception:
        pass
    return 10.0


def is_spotify_playing():
    try:
        out = (
            subprocess.check_output(
                ["osascript", "-e", 'tell application "Spotify" to get player state as string'],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
        return out == "playing"
    except Exception:
        return False


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

    def snapshot(self):
        self.frame = (self.frame + 1) % 4
        cpu = get_cpu_load()
        music = is_spotify_playing()
        hour = time.localtime().tm_hour

        if cpu > 75.0:
            state = "HOT"
            face = "( > _ < ) !!" if self.frame % 2 == 0 else "( > o < ) !!"
            sub = f"CPU {cpu:.0f}% Hot!"
        elif music:
            state = "DANCING"
            face = "( ^ o ^ ) ♪" if self.frame % 2 == 0 else "( ^ w ^ ) ♫"
            sub = "Spotify Playing"
        elif hour >= 23 or hour < 6:
            state = "SLEEPING"
            face = "( - _ - ) zZ" if self.frame % 2 == 0 else "( - . - ) zZ"
            sub = "Night Rest Mode"
        else:
            state = "WORKING"
            face = "( ^ _ ^ ) v" if self.frame % 2 == 0 else "( o _ o ) ."
            sub = f"CPU {cpu:.0f}% Active"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Mascot Screen
                "hdr": f"MASCOT | {state}",
                "big": face,
                "l2": sub,
                "l3": f"State: {state} [{self.frame+1}/4]",
                # Halaman 2: Stats Details
                "p2_hdr": f"COMPANION | DETAILS",
                "p2_l1": f"Status: {state}",
                "p2_l2": f"CPU   : {cpu:.1f}%",
                "p2_l3": f"Music : {'PLAYING' if music else 'OFF'}",
                "p2_l4": f"Frame : #{self.frame+1}",
            },
            "plan": "Companion",
            "model": state,
            "effort": face,
            "context_used": int(cpu),
            "context_max": 100,
            "context_pct": min(int(cpu), 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(cpu),
            "input": int(cpu),
            "output": self.frame,
            "requests": 1,
            "project": f"Mascot:{state}",
            "credit": float(cpu),
            "models": [],
        }
