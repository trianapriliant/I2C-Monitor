"""
Sumber data: Cute Expressive Robo Eyes (Modul #23 - eyes).

Animasi Mata Lucu Interaktif di layar OLED SSD1306 (Kedip, Lirik Kiri-Kanan, Happy, Sleepy, Squint, Winking).
"""

import time
from sources.base import TokenSource

NAME = "eyes"
DISPLAY_NAME = "Cute Robo Eyes"

MOODS = [
    ("NORMAL", "Happy Robot Eyes"),
    ("HAPPY", "Joyful Sparkle Eyes"),
    ("LOOK_LEFT", "Glance Left"),
    ("LOOK_RIGHT", "Glance Right"),
    ("SLEEPY", "Drowsy Cute Eyes"),
    ("WINK", "Playful Winking Eye"),
]


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.mood_index = 0
        self.last_mood_switch = time.time()

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()

        # Otomatis ganti ekspresi mata setiap 6 detik
        if now - self.last_mood_switch > 6:
            self.mood_index = (self.mood_index + 1) % len(MOODS)
            self.last_mood_switch = now

        mood_name, mood_desc = MOODS[self.mood_index]
        frame_num = int((now * 25) % 10000)

        # Flag kedipan mata periodik (blink) setiap ~3.5 detik
        is_blinking = int(now * 10) % 35 == 0

        anim_data = f"{self.mood_index}||{'1' if is_blinking else '0'}||{mood_name}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"EYES | {mood_name}",
                "eq": f"{self.mood_index},{'1' if is_blinking else '0'}",
                "l1": f"MOOD: {mood_name}",
                "l2": anim_data,
                "l3": mood_desc,
                "l4": f"State: {mood_name}",
            },
            "plan": "Eyes",
            "model": mood_name,
            "effort": mood_desc[:16],
            "context_used": self.mood_index + 1,
            "context_max": len(MOODS),
            "context_pct": int((self.mood_index + 1) / len(MOODS) * 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": self.mood_index + 1,
            "output": len(MOODS),
            "requests": 1,
            "project": "Cute Eyes",
            "credit": 0.0,
            "models": [],
        }
