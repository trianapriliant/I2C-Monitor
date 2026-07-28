"""
Sumber data: Antigravity AI.

Membaca transcript & log sesi Antigravity di ~/.gemini/antigravity-ide/brain/.
"""

import glob
import json
import os
from datetime import datetime
from sources.base import TokenSource

ANTIGRAVITY_BRAIN = os.path.expanduser("~/.gemini/antigravity-ide/brain")

NAME = "antigravity"
DISPLAY_NAME = "Antigravity"


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None, root=ANTIGRAVITY_BRAIN):
        super().__init__(scope=scope, project=project)
        self.root = root
        self.offsets = {}
        self.records = {}
        self.latest = None

    def available(self):
        return os.path.isdir(self.root)

    def plan_name(self):
        return "Pro"

    def _paths(self):
        if not self.available():
            return []
        pattern = os.path.join(self.root, "*", ".system_generated", "logs", "*.jsonl")
        return glob.glob(pattern)

    def poll(self):
        new_count = 0
        paths = self._paths()
        for path in paths:
            offset = self.offsets.get(path, 0)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue

            if size < offset:
                offset = 0

            if size == offset:
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    fh.seek(offset)
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            step_idx = data.get("step_index", 0)
                            msg_id = f"{path}:{step_idx}"

                            # Extract model & usage if available
                            usage = data.get("usage", {})
                            model = data.get("model", "Gemini 3.6 Flash")
                            
                            inp = usage.get("prompt_tokens", usage.get("input_tokens", 0))
                            out = usage.get("completion_tokens", usage.get("output_tokens", 0))

                            if inp == 0 and out == 0 and data.get("type") == "PLANNER_RESPONSE":
                                text_len = len(json.dumps(data))
                                inp = text_len // 4
                                out = text_len // 8

                            self.records[msg_id] = {
                                "input": inp,
                                "output": out,
                                "model": model,
                                "timestamp": datetime.now(),
                            }

                            self.latest = {
                                "model": model,
                                "effort": "Tinggi",
                                "context_used": inp + out,
                                "context_max": 1000000,
                            }
                            new_count += 1
                        except Exception:
                            continue
                    self.offsets[path] = fh.tell()
            except OSError:
                continue
        return new_count

    def totals(self):
        self.poll()
        tot_in = sum(r["input"] for r in self.records.values())
        tot_out = sum(r["output"] for r in self.records.values())
        cost = (tot_in / 1_000_000 * 0.50) + (tot_out / 1_000_000 * 1.50)
        return {
            "input": tot_in,
            "output": tot_out,
            "cache_read": 0,
            "cache_write": 0,
            "cost": cost,
            "requests": len(self.records),
        }

    def snapshot(self):
        tot = self.totals()
        cost = tot["cost"]
        tot_in = tot["input"]
        tot_out = tot["output"]
        reqs = tot["requests"]

        lat = self.latest or {}
        model = lat.get("model", "Gemini 3.6")
        ctx_used = lat.get("context_used", min(tot_in + tot_out, 1000000))
        ctx_max = lat.get("context_max", 1000000)
        ctx_pct = int((ctx_used / ctx_max * 100)) if ctx_max else 0

        return {
            "source": self.DISPLAY_NAME,
            "plan": self.plan_name(),
            "model": model[:15],
            "effort": lat.get("effort", "Tinggi"),
            "context_used": ctx_used,
            "context_max": ctx_max,
            "context_pct": ctx_pct,
            "limit_5h_pct": min(int(cost / 10.0 * 100), 100),
            "limit_5h_mins": 300,
            "limit_week_pct": min(int(cost / 50.0 * 100), 100),
            "limit_week_mins": 4320,
            "cost": cost,
            "input": tot_in,
            "output": tot_out,
            "requests": reqs,
            "project": "I2C Monitor",
            "credit": cost * 0.1,
            "models": [
                {"model": "Gemini 3.6", "cost": cost, "pct": 100}
            ] if cost > 0 else []
        }
