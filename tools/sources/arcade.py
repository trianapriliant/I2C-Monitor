"""
Sumber data: Retro OLED Mini Games (Modul #20 - arcade).

Game konsol mini retro (Flappy Bird, Snake, Pong) di layar SSD1306 128x64.
"""

import time
from sources.base import TokenSource

NAME = "arcade"
DISPLAY_NAME = "Arcade Games"

GAMES = [
    ("FLAPPY BIRD", "Flappy Bird OLED"),
    ("RETRO SNAKE", "Classic Snake Game"),
    ("PONG RETRO", "Classic Ping Pong"),
]


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.game_index = 0
        self.last_game_switch = time.time()

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if now - self.last_game_switch > 15:
            self.game_index = (self.game_index + 1) % len(GAMES)
            self.last_game_switch = now

        game_name, game_desc = GAMES[self.game_index]
        frame_num = int((now * 25) % 10000)
        anim_data = f"{self.game_index}||{frame_num}||{game_name}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"ARCADE | {game_name}",
                "eq": f"{self.game_index},{frame_num}",
                "l1": f"GAME: {game_name}",
                "l2": anim_data,
                "l3": game_desc,
                "l4": f"FPS: 25 | Frame: {frame_num}",
            },
            "plan": "Arcade",
            "model": game_name,
            "effort": game_desc[:16],
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
            "requests": self.game_index + 1,
            "project": "25 FPS",
            "credit": 0.0,
            "models": [],
        }
