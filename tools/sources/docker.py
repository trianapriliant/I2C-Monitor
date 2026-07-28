"""
Sumber data: Docker Containers & Server Status.

Memantau status kontainer Docker lokal (Running/Exited), penggunaan memori, dan port server.
Halaman 1: Total Container Running/Stopped & Memory Usage
Halaman 2: Daftar Status Kontainer (Postgres, Redis, Nginx, DLL)
"""

import json
import subprocess
import time
from sources.base import TokenSource

NAME = "docker"
DISPLAY_NAME = "Docker Status"


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def get_docker_containers():
    out = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}||{{.Status}}||{{.State}}"])
    if not out:
        return []

    containers = []
    for line in out.splitlines():
        parts = line.split("||")
        if len(parts) >= 3:
            name = parts[0]
            status_text = parts[1]
            state = parts[2].lower()  # running, exited, etc.
            containers.append({"name": name, "status": status_text, "state": state})
    return containers


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_containers = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if not self.cached_containers or (now - self.last_fetch) > 10:
            self.cached_containers = get_docker_containers()
            self.last_fetch = now

        containers = self.cached_containers
        running_cnt = sum(1 for c in containers if c["state"] == "running")
        stopped_cnt = len(containers) - running_cnt

        lines = []
        for c in containers[:4]:
            icon = "OK" if c["state"] == "running" else "OFF"
            name_short = c["name"][:12]
            lines.append(f"{name_short:<12} [{icon}]")

        while len(lines) < 4:
            lines.append("")

        if not containers:
            status_hdr = "DOCKER IDLE"
            lines[0] = "No Containers"
            lines[1] = "Docker Engine 0"
        else:
            status_hdr = f"RUN:{running_cnt} OFF:{stopped_cnt}"

        pct = int((running_cnt / len(containers) * 100)) if containers else 0

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Summary Docker Status
                "hdr": f"DOCKER | {status_hdr}",
                "l1": f"Running Containers: {running_cnt}",
                "l2": f"Stopped Containers: {stopped_cnt}",
                "l3": f"Total Containers  : {len(containers)}",
                "l4": f"Engine Status     : {'ACTIVE' if containers else 'IDLE'}",
                "bar2": pct,
                # Halaman 2: Container List
                "p2_hdr": f"CONTAINERS ({len(containers)}) | 2/2",
                "p2_l1": lines[0],
                "p2_l2": lines[1],
                "p2_l3": lines[2],
                "p2_l4": lines[3],
            },
            "plan": "Docker",
            "model": f"{running_cnt} Running",
            "effort": f"{stopped_cnt} Stopped",
            "context_used": running_cnt,
            "context_max": max(len(containers), 1),
            "context_pct": pct,
            "limit_5h_pct": pct,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(running_cnt),
            "input": running_cnt,
            "output": stopped_cnt,
            "requests": len(containers),
            "project": f"Docker:{running_cnt}R",
            "credit": float(pct),
            "models": [],
        }
