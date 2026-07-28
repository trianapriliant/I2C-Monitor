"""
Sumber data: macOS Calendar & Meeting Alert.

Membaca jadwal rapat & agenda hari ini dari macOS Calendar.
Halaman 1: Event/Meeting Terdekat + Hitung Mundur Waktu
Halaman 2: Daftar Agenda Hari Ini
"""

import datetime
import json
import re
import subprocess
import time
from sources.base import TokenSource

NAME = "calendar"
DISPLAY_NAME = "Calendar Events"


def get_calendar_events():
    script = """
    set now to current date
    set startOfDay to now - (time of now)
    set endOfDay to startOfDay + (24 * 60 * 60)
    
    set eventList to {}
    try
        tell application "Calendar"
            repeat with cal in calendars
                set evs to (every event of cal whose start date >= startOfDay and start date <= endOfDay)
                repeat with ev in evs
                    set end strSummary to summary of ev
                    set end strStart to (start date of ev) as string
                    set end eventList to strSummary & "||" & strStart
                end repeat
            end repeat
        end tell
    end try
    return eventList
    """
    try:
        out = (
            subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, timeout=4)
            .decode("utf-8")
            .strip()
        )
        if out:
            lines = [l.strip() for l in out.split(",") if "||" in l]
            events = []
            now_dt = datetime.datetime.now()
            for l in lines:
                parts = l.split("||")
                if len(parts) >= 2:
                    title = parts[0].strip()
                    time_str = parts[1].strip()
                    events.append({"title": title, "time": time_str})
            return events
    except Exception:
        pass

    # Fallback sample events if macOS Calendar permissions or idle
    now_hour = datetime.datetime.now().hour
    return [
        {"title": "Daily Standup Meeting", "hour": (now_hour + 1) % 24, "min": 0},
        {"title": "Code Review & PRs", "hour": (now_hour + 3) % 24, "min": 30},
        {"title": "Project Sync", "hour": (now_hour + 5) % 24, "min": 0},
    ]


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_events = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if not self.cached_events or (now - self.last_fetch) > 60:
            self.cached_events = get_calendar_events()
            self.last_fetch = now

        events = self.cached_events
        now_dt = datetime.datetime.now()

        next_event = "No More Meetings"
        countdown_str = "Clear"
        event_lines = []

        if events:
            ev0 = events[0]
            if isinstance(ev0, dict) and "hour" in ev0:
                h = ev0["hour"]
                m = ev0["min"]
                ev_time = now_dt.replace(hour=h, minute=m, second=0, microsecond=0)
                if ev_time < now_dt:
                    ev_time += datetime.timedelta(days=1)
                diff_mins = int((ev_time - now_dt).total_seconds() / 60)
                next_event = ev0["title"]
                countdown_str = f"In {diff_mins} mins ({h:02d}:{m:02d})"
            else:
                next_event = ev0.get("title", "Meeting")
                countdown_str = ev0.get("time", "Today")

            for idx, ev in enumerate(events[:4]):
                t = ev.get("title", f"Event {idx+1}")[:16]
                event_lines.append(f"{idx+1}. {t}")

        while len(event_lines) < 4:
            event_lines.append("")

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Next Meeting Countdown
                "hdr": f"CALENDAR | TODAY",
                "l1": f"Next : {next_event[:16]}",
                "l2": f"Waktu: {countdown_str[:16]}",
                "l3": f"Total: {len(events)} agenda hari ini",
                "l4": f"Status: Active",
                # Halaman 2: Agenda List
                "p2_hdr": f"AGENDA ({len(events)}) | 2/2",
                "p2_l1": event_lines[0],
                "p2_l2": event_lines[1],
                "p2_l3": event_lines[2],
                "p2_l4": event_lines[3],
            },
            "plan": "Calendar",
            "model": next_event[:16],
            "effort": countdown_str,
            "context_used": len(events),
            "context_max": 10,
            "context_pct": min(len(events) * 10, 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(len(events)),
            "input": len(events),
            "output": 1,
            "requests": len(events),
            "project": f"Cal:{len(events)}ev",
            "credit": float(len(events)),
            "models": [],
        }
