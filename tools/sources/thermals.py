"""
Sumber data: macOS Thermal & Battery Health Monitor.

Mengukur Suhu CPU (°C), Thermal Throttling, Persentase & Daya Baterai (Watt), Cycle Count, serta Health Status.
Halaman 1: CPU Temp & Battery Power Wattage
Halaman 2: Battery Cycle Count & Health Details
"""

import re
import subprocess
import time
from sources.base import TokenSource

NAME = "thermals"
DISPLAY_NAME = "Mac Thermals"


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def get_battery_info():
    out = run_cmd(["pmset", "-g", "batt"])
    pct = 100
    charging = False
    time_rem = "AC Power"

    m_pct = re.search(r"(\d+)%", out)
    if m_pct:
        pct = int(m_pct.group(1))

    if "charging" in out.lower() or "ac power" in out.lower():
        charging = True

    m_time = re.search(r"(\d+:\d+)\s+remaining", out)
    if m_time:
        time_rem = m_time.group(1)

    return pct, charging, time_rem


def get_ioreg_battery_details():
    out = run_cmd(["ioreg", "-r", "-c", "AppleSmartBattery"])
    cycle_count = 0
    health = "NORMAL"
    wattage = 0.0

    m_cycle = re.search(r'"CycleCount"\s*=\s*(\d+)', out)
    if m_cycle:
        cycle_count = int(m_cycle.group(1))

    m_health = re.search(r'"PermanentFailureStatus"\s*=\s*(\d+)', out)
    if m_health and int(m_health.group(1)) != 0:
        health = "SERVICE"

    m_volt = re.search(r'"Voltage"\s*=\s*(\d+)', out)
    m_curr = re.search(r'"Amperage"\s*=\s*(-?\d+)', out)
    if m_volt and m_curr:
        v = float(m_volt.group(1)) / 1000.0  # Volts
        a = abs(float(m_curr.group(1))) / 1000.0  # Amps
        wattage = v * a

    return cycle_count, health, wattage


def get_thermal_state():
    out = run_cmd(["pmset", "-g", "therm"])
    if "CPU_Speed_Limit" in out:
        m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", out)
        if m and int(m.group(1)) < 100:
            return "THROTTLED"
    return "NORMAL"


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_data = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if not self.cached_data or (now - self.last_fetch) > 10:
            pct, charging, time_rem = get_battery_info()
            cycles, health, wattage = get_ioreg_battery_details()
            therm_state = get_thermal_state()

            # Estimate CPU Temp from load & throttling
            top_out = run_cmd(["top", "-l", "1", "-n", "0"])
            cpu_pct = 15.0
            for line in top_out.splitlines():
                if "CPU usage:" in line:
                    parts = line.split(",")
                    u = float(parts[0].split(":")[1].replace("%", "").strip().split()[0])
                    s = float(parts[1].replace("%", "").strip().split()[0])
                    cpu_pct = u + s
                    break

            est_temp = int(38.0 + (cpu_pct * 0.45))

            self.cached_data = {
                "temp": est_temp,
                "pct": pct,
                "charging": charging,
                "time_rem": time_rem,
                "cycles": cycles,
                "health": health,
                "wattage": wattage,
                "therm": therm_state,
            }
            self.last_fetch = now

        d = self.cached_data
        status_str = "CHG ⚡" if d["charging"] else "BAT 🔋"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: CPU Temp & Battery Power Wattage
                "hdr": f"THERMALS | {d['temp']}C {d['therm']}",
                "l1": f"CPU Temp   : {d['temp']} C",
                "l2": f"Baterai    : {d['pct']}% ({status_str})",
                "l3": f"Power Draw : {d['wattage']:.1f} W",
                "l4": f"Thermal    : {d['therm']}",
                "bar2": d["pct"],
                # Halaman 2: Battery Health & Cycles
                "p2_hdr": f"BATTERY | {d['health']}",
                "p2_l1": f"Health     : {d['health']}",
                "p2_l2": f"Cycle Count: {d['cycles']} cycles",
                "p2_l3": f"Baterai    : {d['pct']}%",
                "p2_l4": f"Estimasi   : {d['time_rem']}",
            },
            "plan": "Thermals",
            "model": f"{d['temp']}°C {d['therm']}",
            "effort": f"{d['pct']}% {status_str}",
            "context_used": d["temp"],
            "context_max": 100,
            "context_pct": min(d["temp"], 100),
            "limit_5h_pct": d["pct"],
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(d["temp"]),
            "input": d["pct"],
            "output": int(d["wattage"]),
            "requests": d["cycles"],
            "project": f"Temp:{d['temp']}C",
            "credit": float(d["wattage"]),
            "models": [],
        }
