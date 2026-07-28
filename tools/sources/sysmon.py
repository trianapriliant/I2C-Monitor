"""
Sumber data: PC System Monitor (SysMon).

Memantau statistik CPU, RAM, Disk, dan Uptime sistem PC / Mac secara akurat.
"""

import os
import re
import shutil
import subprocess
import time
from sources.base import TokenSource

NAME = "sysmon"
DISPLAY_NAME = "SysMon PC"


def get_cpu_pct():
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except ImportError:
        pass
    try:
        # macOS top command sample 2 (realtime CPU usage)
        out = subprocess.check_output(
            "top -l 2 -n 0 -s 1 | grep 'CPU usage'", shell=True
        ).decode()
        lines = out.strip().splitlines()
        target = lines[1] if len(lines) >= 2 else lines[0]
        m_idle = re.search(r"(\d+(?:\.\d+)?)%\s+idle", target)
        if m_idle:
            return max(0.0, min(100.0, 100.0 - float(m_idle.group(1))))
        m_user = re.search(r"(\d+(?:\.\d+)?)%\s+user", target)
        m_sys = re.search(r"(\d+(?:\.\d+)?)%\s+sys", target)
        if m_user and m_sys:
            return min(100.0, float(m_user.group(1)) + float(m_sys.group(1)))
    except Exception:
        pass
    return 15.0


def get_ram_stats():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.used / (1024**3), mem.total / (1024**3), mem.percent
    except ImportError:
        pass
    try:
        # Accurate macOS vm_stat & sysctl calculation
        total_mem = int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
        )
        total_gb = total_mem / (1024**3)
        vm = subprocess.check_output(["vm_stat"]).decode()
        page_size = 4096
        if "page size of" in vm:
            m = re.search(r"page size of (\d+) bytes", vm)
            if m:
                page_size = int(m.group(1))
        stats = {}
        for line in vm.splitlines():
            if ":" in line:
                k, v = line.split(":")
                v_clean = re.sub(r"[^\d]", "", v)
                if v_clean:
                    stats[k.strip()] = int(v_clean)
        active = stats.get("Pages active", 0) * page_size
        inactive = stats.get("Pages inactive", 0) * page_size
        wired = stats.get("Pages wired down", 0) * page_size
        compressed = stats.get("Pages occupied by compressor", 0) * page_size
        file_backed = stats.get("File-backed pages", 0) * page_size
        app_mem = max(0, active + inactive - file_backed)
        used_mem = app_mem + wired + compressed
        used_gb = used_mem / (1024**3)
        ram_pct = int((used_mem / total_mem) * 100)
        return used_gb, total_gb, min(ram_pct, 100)
    except Exception:
        pass
    return 8.0, 16.0, 50.0


def get_disk_stats():
    try:
        total, used, free = shutil.disk_usage("/")
        pct = int((used / total) * 100)
        return used / (1024**3), total / (1024**3), pct
    except Exception:
        return 120.0, 500.0, 30


def get_uptime_str():
    try:
        out = subprocess.check_output("uptime", shell=True).decode().strip()
        if "up " in out:
            up_part = out.split("up ")[1].split(",")[0].strip()
            return up_part
    except Exception:
        pass
    return "1 hari"


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

    def snapshot(self):
        cpu_pct = int(get_cpu_pct())
        used_ram, tot_ram, ram_pct = get_ram_stats()
        used_disk, tot_disk, disk_pct = get_disk_stats()
        uptime = get_uptime_str()

        import socket
        hostname = socket.gethostname().split(".")[0][:15]

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"{hostname[:20]}",
                "l1": f"CPU : {cpu_pct}%",
                "bar1": cpu_pct,
                "l2": f"RAM : {used_ram:.1f}G/{tot_ram:.0f}G ({ram_pct}%)",
                "bar2": ram_pct,
                "l3": f"Disk: {disk_pct}% | Up: {uptime}",
            },
            "plan": "System",
            "model": hostname,
            "effort": f"CPU {cpu_pct}%",
            "context_used": int(used_ram * 1024),
            "context_max": int(tot_ram * 1024),
            "context_pct": ram_pct,
            "limit_5h_pct": cpu_pct,
            "limit_5h_mins": 300,
            "limit_week_pct": ram_pct,
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": int(used_ram * 10),
            "output": int(tot_ram * 10),
            "requests": disk_pct,
            "project": f"Disk {disk_pct}%",
            "credit": 0.0,
            "models": [
                {"model": "CPU Usage", "cost": 0.0, "pct": cpu_pct},
                {"model": "RAM Usage", "cost": 0.0, "pct": ram_pct},
                {"model": "Disk Space", "cost": 0.0, "pct": disk_pct},
            ],
        }
