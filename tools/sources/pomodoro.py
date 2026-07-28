"""
Sumber data: Pomodoro & Focus Timer Interaktif.

Navigasi Tombol Hardware:
- Single Click : Start / Pause Toggle
- Double Click : Reset Sesi Timer
- Hold (Tahan) : Ganti Preset Profile (25/5/30 -> 50/10/60 -> 90/10/60)
"""

import json
import os
import time
from sources.base import TokenSource

NAME = "pomodoro"
DISPLAY_NAME = "Pomodoro Timer"

STATE_FILE = "/tmp/pomodoro_state.json"

PRESETS = [
    {"name": "25/5/30", "focus": 25 * 60, "break": 5 * 60, "long_break": 30 * 60},
    {"name": "50/10/60", "focus": 50 * 60, "break": 10 * 60, "long_break": 60 * 60},
    {"name": "90/10/60", "focus": 90 * 60, "break": 10 * 60, "long_break": 60 * 60},
]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "preset_idx": 0,
        "mode": "focus",
        "is_running": False,
        "start_time": time.time(),
        "paused_remaining": PRESETS[0]["focus"],
        "completed": 0,
    }


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)

    def available(self):
        return True

    def totals(self):
        return {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "cost": 0.0,
            "requests": 0,
        }

    def handle_event(self, event_type):
        state = load_state()
        preset = PRESETS[state.get("preset_idx", 0)]

        if event_type in ("BTN_SHORT", "short_click", "toggle_start"):
            # Single Click: Start / Pause Toggle
            if state["is_running"]:
                elapsed = time.time() - state["start_time"]
                state["paused_remaining"] = max(
                    0, int(state["paused_remaining"] - elapsed)
                )
                state["is_running"] = False
            else:
                state["start_time"] = time.time()
                state["is_running"] = True
            save_state(state)

        elif event_type in ("BTN_DOUBLE", "double_click", "reset"):
            # Double Click: Reset Sesi Timer
            state["is_running"] = False
            if state["mode"] == "focus":
                state["paused_remaining"] = preset["focus"]
            elif state["mode"] == "break":
                state["paused_remaining"] = preset["break"]
            else:
                state["paused_remaining"] = preset["long_break"]
            state["start_time"] = time.time()
            save_state(state)

        elif event_type in ("BTN_HOLD", "hold_click", "next_preset"):
            # Hold Button: Ganti Preset (25/5/30 -> 50/10/60 -> 90/10/60)
            new_idx = (state.get("preset_idx", 0) + 1) % len(PRESETS)
            new_preset = PRESETS[new_idx]
            state["preset_idx"] = new_idx
            state["mode"] = "focus"
            state["is_running"] = False
            state["paused_remaining"] = new_preset["focus"]
            state["start_time"] = time.time()
            save_state(state)

    def snapshot(self):
        state = load_state()
        preset = PRESETS[state.get("preset_idx", 0)]
        now = time.time()

        if state["is_running"]:
            elapsed = int(now - state["start_time"])
            rem = max(0, state["paused_remaining"] - elapsed)
            if rem <= 0:
                state["is_running"] = False
                if state["mode"] == "focus":
                    state["completed"] += 1
                    if state["completed"] % 4 == 0:
                        state["mode"] = "long_break"
                        state["paused_remaining"] = preset["long_break"]
                    else:
                        state["mode"] = "break"
                        state["paused_remaining"] = preset["break"]
                else:
                    state["mode"] = "focus"
                    state["paused_remaining"] = preset["focus"]
                state["start_time"] = now
                save_state(state)
                rem = state["paused_remaining"]
        else:
            rem = state["paused_remaining"]

        if state["mode"] == "focus":
            total_dur = preset["focus"]
            mode_name = "FOKUS"
        elif state["mode"] == "break":
            total_dur = preset["break"]
            mode_name = "REHAT"
        else:
            total_dur = preset["long_break"]
            mode_name = "REHAT PANJANG"

        mins, secs = divmod(rem, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        pct = (
            int(((total_dur - rem) / total_dur) * 100)
            if total_dur > 0
            else 0
        )

        # Tampilan simpel & tidak penuh
        if not state["is_running"]:
            line2_str = "Klik to Start"
        else:
            line2_str = f"{mode_name} [RUNNING]"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"POMODORO | {preset['name']}",
                "big": time_str,
                "l2": line2_str,
                "l3": "",
                "bar2": pct if state["is_running"] else 0,
            },
            "plan": "Focus",
            "model": time_str,
            "effort": line2_str,
            "context_used": total_dur - rem,
            "context_max": total_dur,
            "context_pct": pct,
            "limit_5h_pct": pct,
            "limit_5h_mins": rem // 60,
            "limit_week_pct": state["completed"] * 10,
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": rem,
            "output": total_dur,
            "requests": state["completed"],
            "project": f"{preset['name']} {line2_str}",
            "credit": 0.0,
            "models": [
                {"model": f"Timer {time_str}", "cost": 0.0, "pct": pct},
            ],
        }
