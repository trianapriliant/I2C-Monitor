"""
Sumber data: Network & Ping Latency Monitor.

Mengukur Latency Ping (8.8.8.8 & 1.1.1.1), Wi-Fi SSID, IP Lokal & Publik, dan Kecepatan Upload/Download.
Halaman 1: Ping Latency & Wi-Fi Quality
Halaman 2: IP Address (Lokal/Publik) & Bandwidth Speed (KB/s)
"""

import json
import re
import socket
import subprocess
import time
import urllib.request
from sources.base import TokenSource

NAME = "network"
DISPLAY_NAME = "Network Monitor"


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def measure_ping(target):
    try:
        out = run_cmd(["ping", "-c", "1", "-t", "2", target])
        m = re.search(r"time=(\d+(?:\.\d+)?)", out)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return -1.0


def get_wifi_ssid():
    out = run_cmd(
        [
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "-I",
        ]
    )
    m = re.search(r"\bSSID:\s*(.+)", out)
    if m:
        return m.group(1).strip()
    return "Ethernet/Wi-Fi"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_public_ip = None
        self.last_ip_fetch = 0
        self.last_net_bytes = None
        self.last_net_time = 0
        self.down_speed = 0.0
        self.up_speed = 0.0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def fetch_public_ip(self):
        now = time.time()
        if self.cached_public_ip and (now - self.last_ip_fetch) < 300:
            return self.cached_public_ip
        try:
            req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    self.cached_public_ip = resp.read().decode("utf-8").strip()
                    self.last_ip_fetch = now
                    return self.cached_public_ip
        except Exception:
            pass
        return "Offline"

    def sample_network_speed(self):
        now = time.time()
        out = run_cmd(["netstat", "-ib"])
        r_bytes, t_bytes = 0, 0
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 10 and (parts[0].startswith("en") or parts[0].startswith("eth")):
                try:
                    r_bytes += int(parts[6])
                    t_bytes += int(parts[9])
                except Exception:
                    pass

        if self.last_net_bytes and self.last_net_time > 0:
            dt = max(now - self.last_net_time, 0.5)
            d_rx = r_bytes - self.last_net_bytes[0]
            d_tx = t_bytes - self.last_net_bytes[1]
            if d_rx >= 0 and d_tx >= 0:
                self.down_speed = (d_rx / dt) / 1024.0  # KB/s
                self.up_speed = (d_tx / dt) / 1024.0  # KB/s

        self.last_net_bytes = (r_bytes, t_bytes)
        self.last_net_time = now

    def snapshot(self):
        self.sample_network_speed()

        ping_google = measure_ping("8.8.8.8")
        ping_cf = measure_ping("1.1.1.1")
        ssid = get_wifi_ssid()
        local_ip = get_local_ip()
        public_ip = self.fetch_public_ip()

        avg_ping = ping_google if ping_google > 0 else ping_cf
        if avg_ping < 0:
            quality = "DISCONNECTED"
        elif avg_ping < 35:
            quality = "EXCELLENT"
        elif avg_ping < 90:
            quality = "GOOD"
        else:
            quality = "POOR/HIGH LATENCY"

        google_str = f"{ping_google:.0f} ms" if ping_google > 0 else "FAIL"
        cf_str = f"{ping_cf:.0f} ms" if ping_cf > 0 else "FAIL"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Ping Latency & Quality
                "hdr": f"NETWORK | {quality}",
                "l1": f"Ping 8.8.8.8 : {google_str}",
                "l2": f"Ping 1.1.1.1 : {cf_str}",
                "l3": f"Wi-Fi SSID   : {ssid[:12]}",
                "l4": f"Kualitas     : {quality}",
                # Halaman 2: IP Address & Speed
                "p2_hdr": f"IP & SPEED | {local_ip}",
                "p2_l1": f"IP Local  : {local_ip}",
                "p2_l2": f"IP Public : {public_ip}",
                "p2_l3": f"Speed Down: {self.down_speed:.1f} KB/s",
                "p2_l4": f"Speed Up  : {self.up_speed:.1f} KB/s",
            },
            "plan": "Network",
            "model": quality,
            "effort": f"{google_str} ping",
            "context_used": int(avg_ping) if avg_ping > 0 else 0,
            "context_max": 200,
            "context_pct": min(int(avg_ping / 2), 100) if avg_ping > 0 else 100,
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(avg_ping) if avg_ping > 0 else 999.0,
            "input": int(self.down_speed),
            "output": int(self.up_speed),
            "requests": int(avg_ping) if avg_ping > 0 else 0,
            "project": f"SSID:{ssid[:10]}",
            "credit": float(self.down_speed),
            "models": [],
        }
