"""
Sumber data: World Clock Multi-Timezone.

Menampilkan jam digital multi-zona waktu dunia (WIB/Jakarta, JST/Tokyo, GMT/London, PST/San Francisco, EST/New York, AEST/Sydney).
Halaman 1: Jakarta (WIB), Tokyo (JST), London (GMT)
Halaman 2: San Francisco (PST), New York (EST), Sydney (AEST)
"""

import datetime
import time
from sources.base import TokenSource

NAME = "worldclock"
DISPLAY_NAME = "World Clock"


def format_timezone_time(utc_now, offset_hours, tz_name):
    tz_time = utc_now + datetime.timedelta(hours=offset_hours)
    time_str = tz_time.strftime("%H:%M:%S")
    date_str = tz_time.strftime("%d/%m")
    return f"{tz_name:<8}: {time_str} ({date_str})"


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
        utc_now = datetime.datetime.utcnow()

        wib_str = format_timezone_time(utc_now, 7, "WIB/JKT")
        jst_str = format_timezone_time(utc_now, 9, "JST/TYO")
        gmt_str = format_timezone_time(utc_now, 0, "GMT/LON")

        pst_str = format_timezone_time(utc_now, -8, "PST/SFO")
        est_str = format_timezone_time(utc_now, -5, "EST/NYC")
        aest_str = format_timezone_time(utc_now, 10, "AEST/SYD")

        local_time_short = (utc_now + datetime.timedelta(hours=7)).strftime("%H:%M:%S")

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Asia & Europe (WIB, JST, GMT)
                "hdr": f"WORLD CLOCK (1/2) | {local_time_short}",
                "l1": wib_str,
                "l2": jst_str,
                "l3": gmt_str,
                "l4": f"UTC Time : {utc_now.strftime('%H:%M:%S UTC')}",
                # Halaman 2: US & Australia (PST, EST, AEST)
                "p2_hdr": f"WORLD CLOCK (2/2) | GLOBAL",
                "p2_l1": pst_str,
                "p2_l2": est_str,
                "p2_l3": aest_str,
                "p2_l4": f"Local JKT: {local_time_short}",
            },
            "plan": "WorldClock",
            "model": local_time_short,
            "effort": "UTC+7 WIB",
            "context_used": utc_now.hour,
            "context_max": 24,
            "context_pct": int(utc_now.hour / 24 * 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(utc_now.hour),
            "input": utc_now.hour,
            "output": utc_now.minute,
            "requests": 24,
            "project": f"WIB:{local_time_short}",
            "credit": float(utc_now.minute),
            "models": [],
        }
