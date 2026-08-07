"""
Sumber data: Daily Productivity Dashboard (Modul #25 - productivity).

Dashboard produktivitas harian 24 jam yang secara otomatis menampilkan
aktivitas yang harus dilakukan berdasarkan jam saat ini (Asia/Jakarta GMT+7).

Fitur:
- Jam digital besar (HH:MM)
- Hari & tanggal dalam Bahasa Indonesia
- Aktivitas saat ini + aktivitas berikutnya
- Progress hari (%) + countdown
- Animasi transisi + quote motivasi saat pergantian aktivitas
- Morning greeting (06:30) & Evening review (22:00)
"""

import random
import time
from datetime import datetime, timedelta, timezone
from sources.base import TokenSource

NAME = "productivity"
DISPLAY_NAME = "Productivity"

# ============================================================
#  TimeManager — Waktu Asia/Jakarta (GMT+7)
# ============================================================
WIB = timezone(timedelta(hours=7))

HARI_INDO = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN_INDO = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


class TimeManager:
    """Wrapper waktu lokal Asia/Jakarta dengan format Bahasa Indonesia."""

    @staticmethod
    def now():
        return datetime.now(WIB)

    @staticmethod
    def format_day(dt):
        return HARI_INDO[dt.weekday()]

    @staticmethod
    def format_date(dt):
        return f"{dt.day} {BULAN_INDO[dt.month]}"

    @staticmethod
    def format_clock(dt):
        return dt.strftime("%H:%M")

    @staticmethod
    def minutes_since_midnight(dt):
        return dt.hour * 60 + dt.minute


# ============================================================
#  ScheduleManager — Jadwal Aktivitas Harian
# ============================================================
# Format: (jam, menit, nama_aktivitas, ikon_1char)
SCHEDULE = [
    (6,  30, "Morning Routine",     "~"),
    (7,   0, "Sarapan + Kopi",      "*"),
    (7,  30, "Deep Work",           "#"),
    (10, 30, "Istirahat",           "."),
    (10, 45, "Desain Template",     "#"),
    (12,  0, "Makan Siang",         "*"),
    (13,  0, "Desain Lanjutan",     "#"),
    (15,  0, "Konten Sosmed",       "@"),
    (15, 30, "Olahraga",            "!"),
    (16, 30, "Makan Buah",          "*"),
    (17,  0, "Development",         "#"),
    (19,  0, "Makan Malam",         "*"),
    (20,  0, "Cek Sosmed",          "@"),
    (20, 30, "Hiburan",             "."),
    (22,  0, "Persiapan Tidur",     "."),
    (22, 30, "Tidur",               "z"),
]

# Kategori untuk evening review
REVIEW_CATEGORIES = [
    "Ollo/Canvas",
    "Design",
    "Content",
    "Health",
    "Dev",
    "Rest",
]


class ScheduleManager:
    """Pengelola jadwal aktivitas harian."""

    def __init__(self):
        self.schedule = SCHEDULE
        # Pre-compute semua waktu dalam menit sejak midnight
        self.times_min = [(h * 60 + m) for h, m, _, _ in self.schedule]

    def _find_index(self, now_min):
        """Cari index aktivitas yang sedang berlangsung."""
        idx = -1
        for i, t in enumerate(self.times_min):
            if now_min >= t:
                idx = i
            else:
                break
        return idx

    def current(self, dt):
        """Return (nama, ikon) aktivitas saat ini."""
        now_min = TimeManager.minutes_since_midnight(dt)
        idx = self._find_index(now_min)
        if idx < 0:
            return ("Tidur", "z")
        _, _, name, icon = self.schedule[idx]
        return (name, icon)

    def next_activity(self, dt):
        """Return (nama, jam_mulai_str) aktivitas berikutnya."""
        now_min = TimeManager.minutes_since_midnight(dt)
        idx = self._find_index(now_min)

        next_idx = idx + 1
        if next_idx >= len(self.schedule):
            next_idx = 0

        h, m, name, _ = self.schedule[next_idx]
        return (name, f"{h:02d}:{m:02d}")

    def get_upcoming_items(self, dt, count=4):
        """Return list string (jam, nama) 4 aktivitas mendatang dari aktivitas saat ini."""
        now_min = TimeManager.minutes_since_midnight(dt)
        idx = self._find_index(now_min)
        if idx < 0:
            idx = 0

        items = []
        n = len(self.schedule)
        for i in range(count):
            item_idx = (idx + i) % n
            h, m, name, _ = self.schedule[item_idx]
            time_str = f"{h:02d}:{m:02d}"
            prefix = ">" if i == 0 else " "
            items.append(f"{prefix} {time_str} |{name}")
        return items

    def day_progress(self, dt):
        """Hitung persentase hari (06:30=0% → 22:30=100%)."""
        now_min = TimeManager.minutes_since_midnight(dt)
        start = 6 * 60 + 30   # 06:30
        end = 22 * 60 + 30     # 22:30
        if now_min <= start:
            return 0
        if now_min >= end:
            return 100
        return int(((now_min - start) / (end - start)) * 100)


# ============================================================
#  QuotesManager — Motivational Quotes
# ============================================================
QUOTES = [
    "One task at a time.",
    "Progress > Perfect.",
    "Stay focused.",
    "Keep building.",
    "Small steps every day.",
    "You got this!",
    "Consistency is key.",
    "Make it happen.",
    "Trust the process.",
    "Done > Perfect.",
    "Ship it.",
    "Focus on impact.",
]


class QuotesManager:
    """Pengelola quote motivasi acak."""

    def __init__(self):
        self._last_quote = ""

    def random_quote(self):
        """Ambil quote acak (tidak mengulangi yang terakhir)."""
        pool = [q for q in QUOTES if q != self._last_quote]
        q = random.choice(pool)
        self._last_quote = q
        return q


# ============================================================
#  PomodoroManager — Siklus Pomodoro Otomatis (25m Focus / 5m Break)
# ============================================================
WORK_ACTIVITIES = ["Deep Work", "Desain Template", "Desain Lanjutan", "Development", "Tidur"]  # 'Tidur' included so user can test live right now!


class PomodoroManager:
    """Pengelola siklus Pomodoro (25m Focus / 5m Break) otomatis saat fase kerja."""

    def __init__(self, focus_min=25, break_min=5):
        self.focus_sec = focus_min * 60
        self.break_sec = break_min * 60
        self.current_act = ""
        self.active = False
        self.state = "FOCUS"  # FOCUS atau BREAK
        self.phase_start = 0.0
        self.session = 1

    def update(self, current_act):
        now = time.time()
        is_work = any(w.lower() in current_act.lower() for w in WORK_ACTIVITIES)

        if not is_work:
            self.active = False
            self.current_act = ""
            return {"active": False}

        # Jika baru pertama kali masuk fase kerja atau ganti aktivitas kerja
        if not self.active or current_act != self.current_act:
            self.active = True
            self.current_act = current_act
            self.state = "FOCUS"
            self.phase_start = now
            self.session = 1

        duration = self.focus_sec if self.state == "FOCUS" else self.break_sec
        elapsed = now - self.phase_start
        remaining = max(0, int(duration - elapsed))

        # Pergantian fasa otomatis jika durasi habis
        if remaining <= 0:
            if self.state == "FOCUS":
                self.state = "BREAK"
                self.phase_start = now
                duration = self.break_sec
                remaining = duration
            else:
                self.state = "FOCUS"
                self.phase_start = now
                self.session += 1
                duration = self.focus_sec
                remaining = duration

        rem_m, rem_s = divmod(remaining, 60)
        time_str = f"{rem_m:02d}:{rem_s:02d}"
        pct = int(((duration - remaining) / duration) * 100)

        return {
            "active": True,
            "state": self.state,
            "session": self.session,
            "time_str": time_str,
            "pct": pct,
            "activity": current_act,
        }


# ============================================================
#  AnimationManager — State Machine Mode Tampilan
# ============================================================
MODE_NORMAL = "normal"
MODE_MORNING = "morning"
MODE_EVENING = "evening"
MODE_TRANSITION = "transition"
MODE_PREVIEW = "preview"
MODE_POMODORO = "pomodoro"


class AnimationManager:
    """Deteksi pergantian aktivitas & mode khusus (morning/evening/transition/preview/pomodoro)."""

    def __init__(self, quotes):
        self.quotes = quotes
        self.mode = MODE_NORMAL
        self.mode_start = 0.0
        self.mode_duration = 0.0
        self.last_activity = ""
        self.current_quote = ""
        self._morning_shown_date = ""
        self._evening_shown_date = ""
        self.last_preview_time = time.time()  # Timer preview otomatis

    def update(self, dt, current_act):
        """Dipanggil setiap snapshot. Return mode string saat ini."""
        now = time.time()
        date_key = dt.strftime("%Y-%m-%d")
        now_min = TimeManager.minutes_since_midnight(dt)

        # Jika sedang dalam mode khusus, cek apakah sudah selesai
        if self.mode != MODE_NORMAL:
            elapsed = now - self.mode_start
            if elapsed >= self.mode_duration:
                self.mode = MODE_NORMAL
            else:
                return self.mode

        # Deteksi morning greeting (06:30 - 06:35, sekali per hari)
        if 390 <= now_min <= 395 and self._morning_shown_date != date_key:
            self._morning_shown_date = date_key
            self.mode = MODE_MORNING
            self.mode_start = now
            self.mode_duration = 5.0
            self.current_quote = "Today is a new\nopportunity."
            return self.mode

        # Deteksi evening review (22:00 - 22:05, sekali per hari)
        if 1320 <= now_min <= 1325 and self._evening_shown_date != date_key:
            self._evening_shown_date = date_key
            self.mode = MODE_EVENING
            self.mode_start = now
            self.mode_duration = 10.0
            self.current_quote = "Great day!"
            return self.mode

        # Deteksi pergantian aktivitas → transition
        if current_act != self.last_activity and self.last_activity != "":
            self.mode = MODE_TRANSITION
            self.mode_start = now
            self.mode_duration = 3.0
            self.current_quote = self.quotes.random_quote()
            self.last_activity = current_act
            return self.mode

        # Deteksi preview jadwal otomatis (setiap 60 detik / 1 menit untuk tes)
        # Nanti bisa diubah ke 300 detik (5 menit)
        if (now - self.last_preview_time) >= 60.0:
            self.last_preview_time = now
            self.mode = MODE_PREVIEW
            self.mode_start = now
            self.mode_duration = 30.0  # Tampilkan preview selama 30 detik
            return self.mode

        self.last_activity = current_act
        return MODE_NORMAL


# ============================================================
#  Source — Main Data Source
# ============================================================
class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.time_mgr = TimeManager()
        self.sched_mgr = ScheduleManager()
        self.quotes_mgr = QuotesManager()
        self.anim_mgr = AnimationManager(self.quotes_mgr)
        self.pomo_mgr = PomodoroManager(focus_min=25, break_min=5)

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        dt = self.time_mgr.now()
        clock = self.time_mgr.format_clock(dt)
        day = self.time_mgr.format_day(dt)
        date = self.time_mgr.format_date(dt)
        progress = self.sched_mgr.day_progress(dt)

        curr_name, curr_icon = self.sched_mgr.current(dt)
        next_name, next_start_time = self.sched_mgr.next_activity(dt)

        pomo = self.pomo_mgr.update(curr_name)
        mode = self.anim_mgr.update(dt, curr_name)
        quote = self.anim_mgr.current_quote if mode == MODE_TRANSITION else ""

        if mode == MODE_NORMAL and pomo.get("active", False):
            mode = MODE_POMODORO

        if mode == MODE_PREVIEW:
            preview_items = self.sched_mgr.get_upcoming_items(dt, 4)
            l1_val = preview_items[0] if len(preview_items) > 0 else ""
            l2_val = preview_items[1] if len(preview_items) > 1 else ""
            l3_val = preview_items[2] if len(preview_items) > 2 else ""
            l4_val = preview_items[3] if len(preview_items) > 3 else ""
        elif mode == MODE_POMODORO:
            state_label = f"({pomo['state']} #{pomo['session']})"
            l1_val = f"{curr_name} {state_label}"
            l2_val = next_name
            l3_val = next_start_time
            l4_val = clock  # Jam asli dikirim di l4
            progress = pomo["pct"]  # Bar persen fasa Pomodoro (0-100%)
        else:
            l1_val = curr_name
            l2_val = next_name
            l3_val = next_start_time
            l4_val = quote

        big_text = pomo["time_str"] if mode == MODE_POMODORO else clock

        # Format review list untuk evening mode
        review_str = ""
        if mode == MODE_EVENING:
            review_str = "|".join(REVIEW_CATEGORIES)

        year = str(dt.year)

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"SCHEDULE | {progress}%",
                "big": big_text,
                "l1": l1_val,
                "l2": l2_val,
                "l3": l3_val,
                "l4": l4_val,
                "l5": mode,
                "bar1": progress,
                # Page 2: Detail jadwal berikutnya
                "p2_hdr": f"{date} | {day} | {year}",
                "p2_l1": f"NOW: {curr_icon} {curr_name}",
                "p2_l2": f"NEXT: {next_name} ({next_start_time})",
                "p2_l3": f"Mulai: {next_start_time}",
                "p2_l4": f"Progress: {progress}%",
                "p2_l5": review_str if review_str else self.quotes_mgr.random_quote(),
            },
            "plan": "Productivity",
            "model": curr_name[:16],
            "effort": clock,
            "context_used": progress,
            "context_max": 100,
            "context_pct": progress,
            "limit_5h_pct": 0, "limit_5h_mins": 0,
            "limit_week_pct": 0, "limit_week_mins": 0,
            "cost": 0.0, "credit": 0.0, "requests": 0,
            "input": 0, "output": 0,
            "project": "Dashboard",
            "models": []
        }
