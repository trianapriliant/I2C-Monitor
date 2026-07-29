"""
Sumber data: Solar System & Moon Phase Orbit Simulator (Modul #24 - orbit).

Simulasi Orbit Planet Tata Surya & Fase Bulan Real-Time di layar OLED SSD1306.
"""

import math
import time
from sources.base import TokenSource

NAME = "orbit"
DISPLAY_NAME = "Solar Orbit 3D"

MOON_PHASES = [
    "NEW MOON",
    "WAXING CRESCENT",
    "FIRST QUARTER",
    "WAXING GIBBOUS",
    "FULL MOON",
    "WANING GIBBOUS",
    "THIRD QUARTER",
    "WANING CRESCENT",
]


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
        # Hitung fase bulan (periode ~29.53 hari)
        synodic_month = 29.53058867 * 86400
        phase_ratio = (now % synodic_month) / synodic_month
        phase_idx = int(phase_ratio * 8) % 8
        phase_name = MOON_PHASES[phase_idx]

        frame_num = int((now * 25) % 10000)
        anim_data = f"{phase_idx}||{int(phase_ratio * 100)}||{phase_name}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"ORBIT | {phase_name}",
                "eq": f"{phase_idx},{int(phase_ratio * 100)}",
                "l1": f"MOON: {phase_name}",
                "l2": anim_data,
                "l3": f"Lunar Phase {int(phase_ratio * 100)}%",
                "l4": f"FPS: 25 | {phase_name}",
            },
            "plan": "Orbit",
            "model": phase_name,
            "effort": f"Phase {int(phase_ratio * 100)}%",
            "context_used": int(phase_ratio * 100),
            "context_max": 100,
            "context_pct": int(phase_ratio * 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": phase_idx + 1,
            "output": 8,
            "requests": 1,
            "project": "3D Solar Orbit",
            "credit": 0.0,
            "models": [],
        }
