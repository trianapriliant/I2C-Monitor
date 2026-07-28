"""
Sumber data: Interactive Todo Checklist.

Membaca daftar tugas harian dari file ~/todo.txt (atau tools/data/todo.txt).
Mendukung interaksi tombol ESP32:
- Short Press (BTN_SHORT): Toggle status tugas aktif [ ] <-> [x]
- Double Press (BTN_DOUBLE): Pindah kursor penanda ke tugas berikutnya
"""

import os
import time
from sources.base import TokenSource

NAME = "todo"
DISPLAY_NAME = "Interactive Todo"

DEFAULT_TODO_PATH = os.path.expanduser("~/todo.txt")
FALLBACK_TODO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "todo.txt")


def get_todo_file():
    if os.path.exists(DEFAULT_TODO_PATH):
        return DEFAULT_TODO_PATH
    os.makedirs(os.path.dirname(FALLBACK_TODO_PATH), exist_ok=True)
    if not os.path.exists(FALLBACK_TODO_PATH):
        with open(FALLBACK_TODO_PATH, "w", encoding="utf-8") as f:
            f.write("[ ] Selesaikan firmware ESP32\n")
            f.write("[ ] Review PR GitHub\n")
            f.write("[ ] Kopi & rehat sejenak\n")
            f.write("[x] Setup OLED Monitor\n")
    return FALLBACK_TODO_PATH


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.todo_file = get_todo_file()
        self.tasks = []
        self.active_idx = 0
        self.load_tasks()

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def load_tasks(self):
        try:
            with open(self.todo_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            tasks = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                done = line.startswith("[x]") or line.startswith("[X]")
                text = line[3:].strip() if (line.startswith("[ ]") or done) else line
                tasks.append({"done": done, "text": text})
            self.tasks = tasks
        except Exception:
            self.tasks = [
                {"done": False, "text": "Selesaikan firmware ESP32"},
                {"done": False, "text": "Review PR GitHub"},
                {"done": True, "text": "Setup OLED Monitor"},
            ]

    def save_tasks(self):
        try:
            with open(self.todo_file, "w", encoding="utf-8") as f:
                for t in self.tasks:
                    mark = "[x]" if t["done"] else "[ ]"
                    f.write(f"{mark} {t['text']}\n")
        except Exception:
            pass

    def handle_event(self, event_type):
        if not self.tasks:
            return

        if event_type == "BTN_SHORT":
            # Toggle task under cursor
            if 0 <= self.active_idx < len(self.tasks):
                self.tasks[self.active_idx]["done"] = not self.tasks[self.active_idx]["done"]
                self.save_tasks()
        elif event_type == "BTN_DOUBLE":
            # Move cursor to next task
            self.active_idx = (self.active_idx + 1) % len(self.tasks)

    def snapshot(self):
        self.load_tasks()
        total = len(self.tasks)
        done_count = sum(1 for t in self.tasks if t["done"])
        pct = int((done_count / total * 100)) if total > 0 else 0

        # Build lines (up to 4 tasks)
        lines = []
        for idx, t in enumerate(self.tasks[:4]):
            mark = "[x]" if t["done"] else "[ ]"
            cursor = ">" if idx == self.active_idx else " "
            txt = t["text"][:16]
            lines.append(f"{cursor}{mark} {txt}")

        while len(lines) < 4:
            lines.append("")

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Active Todo List
                "hdr": f"TODO ({done_count}/{total}) | {pct}%",
                "l1": lines[0],
                "l2": lines[1],
                "l3": lines[2],
                "l4": lines[3],
                "bar2": pct,
                # Halaman 2: Help & Path Info
                "p2_hdr": f"TODO HELP | 2/2",
                "p2_l1": f"File : {os.path.basename(self.todo_file)}",
                "p2_l2": f"Klik 1x: Selesai [x]",
                "p2_l3": f"Klik 2x: Pilih baris",
                "p2_l4": f"Progress: {done_count}/{total} ({pct}%)",
            },
            "plan": "Todo",
            "model": f"{done_count}/{total} Selesai",
            "effort": f"{pct}% progress",
            "context_used": done_count,
            "context_max": max(total, 1),
            "context_pct": pct,
            "limit_5h_pct": pct,
            "limit_5h_mins": 300,
            "limit_week_pct": pct,
            "limit_week_mins": 4320,
            "cost": float(done_count),
            "input": total - done_count,
            "output": done_count,
            "requests": total,
            "project": f"Todo:{done_count}/{total}",
            "credit": float(pct),
            "models": [],
        }
