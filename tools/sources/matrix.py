"""
Sumber data: Matrix Digital Rain ASCII & Cyberpunk HUD (Modul #22 - matrix).

Menyediakan parameter animasi hujan karakter Matrix & Terminal Cyberpunk.
"""

import time
from sources.base import TokenSource

NAME = "matrix"
DISPLAY_NAME = "Matrix Digital Rain"


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
        now = time.time()
        frame_num = int((now * 25) % 10000)
        cyber_hash = f"0x{(int(now * 1000) % 0xFFFFFF):06X}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"MATRIX | {cyber_hash}",
                "eq": f"{frame_num}",
                "l1": "SYSTEM MATRIX CODE",
                "l2": cyber_hash,
                "l3": "CYBERNETIC TERMINAL",
                "l4": f"STREAMING 25 FPS | {frame_num}",
            },
            "plan": "Matrix",
            "model": cyber_hash,
            "effort": "Digital Rain",
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
            "requests": 1,
            "project": "25 FPS",
            "credit": 0.0,
            "models": [],
        }
