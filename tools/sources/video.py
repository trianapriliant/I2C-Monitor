import os
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

        # Cek ketersediaan file data/video.bin (hasil konversi video_converter.py)
        self.bin_path = "data/video.bin"
        self.bin_frames = 0
        self.bin_size = 0
        self._check_binary_video()

    def _check_binary_video(self):
        if os.path.exists(self.bin_path):
            try:
                self.bin_size = os.path.getsize(self.bin_path)
                self.bin_frames = self.bin_size // 1024
            except Exception:
                self.bin_frames = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        self._check_binary_video()

        has_binary_file = self.bin_frames > 0

        # Jika ada file data/video.bin, utamakan pemutaran file biner video
        if has_binary_file:
            frame_num = int((now * 30) % self.bin_frames)
            preset_name = f"VIDEO BIN ({self.bin_frames}f)"
            preset_desc = f"Playing video.bin frame {frame_num+1}/{self.bin_frames}"
            anim_data = f"99||{frame_num}||{self.bin_frames}"
        else:
            # Otomatis ganti preset animasi setiap 12 detik
            if now - self.last_preset_switch > 12:
                self.preset_index = (self.preset_index + 1) % len(PRESETS)
                self.last_preset_switch = now

            preset_name, preset_desc = PRESETS[self.preset_index]
            frame_num = int((now * 25) % 10000)
            anim_data = f"{self.preset_index}||{frame_num}||{preset_name}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"VIDEO | {preset_name}",
                "eq": f"{self.preset_index if not has_binary_file else 99},{frame_num}",
                "l1": f"VIDEO: {preset_name}",
                "l2": anim_data,
                "l3": preset_desc,
                "l4": f"FPS: 30 | Frame: {frame_num}",
            },
            "plan": "Video",
            "model": preset_name,
            "effort": preset_desc[:16],
            "context_used": frame_num,
            "context_max": max(self.bin_frames, 10000),
            "context_pct": ((frame_num % 100) if not has_binary_file else int(frame_num / max(self.bin_frames, 1) * 100)),
            "limit_5h_pct": (frame_num % 100),
            "limit_5h_mins": 300,
            "limit_week_pct": (frame_num % 100),
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": frame_num,
            "output": max(self.bin_frames, 10000),
            "requests": self.preset_index + 1,
            "project": "30 FPS",
            "credit": 0.0,
            "models": [],
        }
