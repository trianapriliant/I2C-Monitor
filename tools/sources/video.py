"""
Sumber data: Video Animation & 3D Visualizer Streamer (Modul #19).

Terinspirasi dari ESP32_Video_Display (younes-makhchan/ESP32_Video_Display).
Menyediakan animasi 3D Starfield Warp, 3D Rotating Wireframe Cube, Cyberpunk Grid,
dan Bad Apple / Sprite Dance Player secara real-time pada 25-30 FPS.
"""

import math
import time
from sources.base import TokenSource

NAME = "video"
DISPLAY_NAME = "Video & 3D FX"

PRESETS = [
    ("STARFIELD 3D", "Warp Speed 3D Starfield"),
    ("CUBE 3D", "Rotating 3D Wireframe Cube"),
    ("CYBER GRID", "Retro Synthwave 3D Grid"),
    ("BAD APPLE", "Monochrome Vector Dance"),
]


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.preset_index = 0
        self.last_preset_switch = time.time()

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        # Otomatis ganti preset animasi setiap 12 detik
        if now - self.last_preset_switch > 12:
            self.preset_index = (self.preset_index + 1) % len(PRESETS)
            self.last_preset_switch = now

        preset_name, preset_desc = PRESETS[self.preset_index]
        frame_num = int((now * 25) % 10000)

        # Parameter kontrol animasi real-time yang dikirim ke ESP32
        anim_data = f"{self.preset_index}||{frame_num}||{preset_name}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"VIDEO | {preset_name}",
                "eq": f"{self.preset_index},{frame_num}",
                "l1": f"VIDEO: {preset_name}",
                "l2": anim_data,
                "l3": preset_desc,
                "l4": f"FPS: 30 | Frame: {frame_num}",
            },
            "plan": "Video",
            "model": preset_name,
            "effort": preset_desc[:16],
            "context_used": frame_num,
            "context_max": 10000,
            "context_pct": (frame_num % 100),
            "limit_5h_pct": (frame_num % 100),
            "limit_5h_mins": 300,
            "limit_week_pct": (frame_num % 100),
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": frame_num,
            "output": 10000,
            "requests": self.preset_index + 1,
            "project": "25 FPS",
            "credit": 0.0,
            "models": [],
        }
