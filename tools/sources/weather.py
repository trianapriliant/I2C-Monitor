"""
Sumber data: Jam Digital & Cuaca Lokal.

Membaca waktu PC lokal dan data cuaca dari wttr.in.
"""

import json
import re
import time
import urllib.request
from datetime import datetime
from sources.base import TokenSource

NAME = "weather"
DISPLAY_NAME = "Clock & Weather"


def fetch_weather(city="Jakarta"):
    url = f"https://wttr.in/{city}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                current = data["current_condition"][0]
                temp_c = current.get("temp_C", "30")
                desc = current.get("weatherDesc", [{}])[0].get("value", "Cerah")
                humidity = current.get("humidity", "75")
                return {"temp": f"{temp_c}C", "desc": desc[:15], "humidity": f"{humidity}%"}
    except Exception:
        pass
    return {"temp": "30C", "desc": "Cerah Berawan", "humidity": "75%"}


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_weather = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%d %b %Y")
        day_str = now.strftime("%A")

        t_now = time.time()
        if not self.cached_weather or (t_now - self.last_fetch) > 300:
            self.cached_weather = fetch_weather("Jakarta")
            self.last_fetch = t_now

        w = self.cached_weather
        temp = w["temp"]
        desc = w["desc"]
        hum = w["humidity"]

        # Calculate progress of the current hour (0-100%)
        minute_pct = int((now.minute / 60.0) * 100)

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"JAM & CUACA | {day_str}",
                "big": time_str,
                "l2": date_str,
                "l3": f"Jakarta: {temp} ({desc})",
            },
            "plan": "Clock",
            "model": time_str,
            "effort": day_str,
            "context_used": now.minute,
            "context_max": 60,
            "context_pct": minute_pct,
            "limit_5h_pct": minute_pct,
            "limit_5h_mins": 300,
            "limit_week_pct": int((now.hour / 24.0) * 100),
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": now.day,
            "output": now.month,
            "requests": int(re.sub(r"[^\d]", "", temp) or 30),
            "project": f"{temp} {desc}",
            "credit": 0.0,
            "models": [
                {"model": f"Jam: {time_str}", "cost": 0.0, "pct": minute_pct},
                {"model": f"Suhu: {temp}", "cost": 0.0, "pct": int(hum.replace("%", ""))},
                {"model": f"Lembap: {hum}", "cost": 0.0, "pct": int(hum.replace("%", ""))},
            ]
        }
