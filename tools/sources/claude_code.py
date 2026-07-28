"""
Sumber data: Claude Code.

Membaca transcript sesi di ~/.claude/projects/**/*.jsonl.
"""

import glob
import json
import os
from datetime import datetime, timedelta

from pricing import context_window, cost_for, display_name, effort_label
from sources.base import TokenSource

CLAUDE_PROJECTS = os.path.expanduser("~/.claude/projects")
CLAUDE_CONFIG = os.path.expanduser("~/.claude.json")

# Jendela batas pemakaian.
FIVE_HOUR_WINDOW = timedelta(hours=5)
WEEKLY_RESET_WEEKDAY = 6   # 6 = Minggu (sesuai "Reset Min 02.00")
WEEKLY_RESET_HOUR = 2

# Model yang TIDAK ikut menaikkan "Batas 5 jam".
#
# Dasarnya pengamatan pada panel /usage: memakai Fable 5 tidak menggerakkan
# bar 5 jam, sementara bar mingguan berlabel "semua model" tetap ikut naik.
# Kalau suatu saat kebijakannya berubah, kosongkan set ini lalu kalibrasi ulang.
MODELS_OUTSIDE_5H = {
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
}


def _counts_toward_5h(model: str) -> bool:
    m = (model or "").strip()
    for prefix in ("anthropic.", "us.anthropic.", "eu.anthropic."):
        if m.startswith(prefix):
            m = m[len(prefix):]
    return m not in MODELS_OUTSIDE_5H

NAME = "claude-code"
DISPLAY_NAME = "Claude Code"


class Source(TokenSource):
    """
    Memindai file .jsonl secara inkremental: tiap poll hanya membaca
    byte baru di ujung file, jadi murah walaupun transcript-nya ratusan MB.

    Deduplikasi wajib: satu response API muncul di beberapa baris dengan
    message.id yang sama (streaming), dan usage-nya kumulatif. Tanpa dedup,
    totalnya bisa 2-3x lipat dari yang sebenarnya.
    """

    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None, root=CLAUDE_PROJECTS):
        super().__init__(scope=scope, project=project)
        self.root = root
        # 'all' = seluruh riwayat; sisanya dibatasi hari ini.
        self.today_only = (scope != "all")
        # 'project' = nama project ditentukan manual.
        # 'active'  = ikut project yang paling terakhir dipakai (otomatis).
        self.project_filter = project if scope == "project" else None
        self.follow_active = (scope == "active")
        self.offsets = {}        # path -> posisi byte terakhir yang dibaca
        self.records = {}        # message.id -> dict metrik
        self.latest = None       # entri terbaru (context window / model / effort)
        self.project_roots = {}  # project_id -> cwd terpendek yang pernah dilihat

    def available(self):
        return os.path.isdir(self.root)

    # ---------- info paket ----------

    def plan_name(self):
        """Ambil nama paket dari ~/.claude.json (mis. claude_pro -> Pro)."""
        try:
            with open(CLAUDE_CONFIG, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError):
            return "-"
        org_type = (cfg.get("oauthAccount") or {}).get("organizationType") or ""
        if org_type.startswith("claude_"):
            return org_type[len("claude_"):].capitalize()
        return org_type or "-"

    # ---------- internal ----------

    def _paths(self):
        # Selalu baca semua transcript. Penyaringan project dilakukan saat
        # menjumlahkan, bukan saat membaca, supaya mode 'active' bisa
        # berpindah sendiri begitu kamu ganti project tanpa restart.
        return glob.glob(os.path.join(self.root, "*", "*.jsonl"))

    def _parse_ts(self, ts):
        """ISO-8601 UTC dari transcript -> datetime waktu lokal."""
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt.astimezone()

    def project_label(self, project_id):
        """
        Nama project yang enak dibaca.

        Identitasnya memakai nama folder transcript (stabil per project),
        bukan `cwd` -- `cwd` ikut berubah tiap agent masuk subfolder, jadi
        satu project bisa terbaca sebagai beberapa nama berbeda.
        Untuk labelnya dipakai cwd TERPENDEK yang pernah muncul, karena
        itulah akar project-nya.
        """
        root = self.project_roots.get(project_id)
        if root:
            return os.path.basename(root) or root
        return project_id

    def _ingest(self, line, project_id="?"):
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return  # baris ditulis separuh saat file sedang aktif ditulis

        msg = entry.get("message")
        if not isinstance(msg, dict):
            return
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            return

        model = msg.get("model") or ""
        if model == "<synthetic>":
            return  # entri lokal Claude Code, bukan panggilan API berbayar

        msg_id = msg.get("id") or entry.get("requestId") or entry.get("uuid")
        if not msg_id:
            return

        creation = usage.get("cache_creation") or {}
        w5 = creation.get("ephemeral_5m_input_tokens", 0) or 0
        w1h = creation.get("ephemeral_1h_input_tokens", 0) or 0
        if not (w5 or w1h):
            w5 = usage.get("cache_creation_input_tokens", 0) or 0

        ts = self._parse_ts(entry.get("timestamp"))
        cache_write_total = w5 + w1h

        cwd = entry.get("cwd") or ""
        if cwd:
            known = self.project_roots.get(project_id)
            if known is None or len(cwd) < len(known):
                self.project_roots[project_id] = cwd
        project = project_id

        record = {
            "ts": ts,
            "date": ts.date() if ts else None,
            "project": project,
            "model": model,
            "input": usage.get("input_tokens", 0) or 0,
            "output": usage.get("output_tokens", 0) or 0,
            "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
            "cache_write": cache_write_total,
            "cost": cost_for(model, usage),
        }

        # Baris duplikat: ambil yang output_tokens-nya paling besar (paling lengkap).
        prev = self.records.get(msg_id)
        if prev is None or record["output"] >= prev["output"]:
            self.records[msg_id] = record

        # Entri terbaru dipakai untuk context window, model, dan effort.
        # input + cache_read + cache_write = besar prompt yang dikirim,
        # itulah isi context window pada request tersebut.
        if ts and (self.latest is None or ts >= self.latest["ts"]):
            self.latest = {
                "ts": ts,
                "model": model,
                "project": project,
                "effort": entry.get("effort") or (self.latest or {}).get("effort"),
                "context": record["input"] + record["cache_read"] + cache_write_total,
            }

    # ---------- API ----------

    def poll(self):
        new_lines = 0
        for path in self._paths():
            try:
                size = os.path.getsize(path)
            except OSError:
                continue

            offset = self.offsets.get(path, 0)
            if size == offset:
                continue
            if size < offset:
                offset = 0  # file dipangkas/diganti, baca ulang dari awal

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(offset)
                    data = fh.read()
            except OSError:
                continue

            # Baris terakhir mungkin belum lengkap; sisakan untuk poll berikutnya.
            if data and not data.endswith("\n"):
                cut = data.rfind("\n")
                if cut == -1:
                    continue  # belum ada baris utuh sama sekali
                data = data[: cut + 1]

            project_id = os.path.basename(os.path.dirname(path))
            for line in data.splitlines():
                if line.strip():
                    self._ingest(line, project_id)
                    new_lines += 1

            self.offsets[path] = offset + len(data.encode("utf-8"))

        return new_lines

    def active_project_id(self):
        """Id project yang paling terakhir dipakai."""
        return (self.latest or {}).get("project")

    def active_project(self):
        """Nama project yang paling terakhir dipakai."""
        pid = self.active_project_id()
        return self.project_label(pid) if pid else "-"

    def _target_project(self):
        """Id project yang sedang disaring, atau None kalau semua project."""
        if self.follow_active:
            return self.active_project_id()
        if self.project_filter:
            # Cocokkan lewat label supaya bisa ditulis "I2C Monitor",
            # bukan nama folder transcript yang ter-encode.
            for pid in self.project_roots:
                if self.project_label(pid) == self.project_filter:
                    return pid
            return self.project_filter
        return None

    def _in_scope(self, rec, today=None):
        """Satu tempat untuk semua aturan penyaringan."""
        if self.today_only:
            if today is None:
                today = datetime.now().date()
            if rec["date"] != today:
                return False
        target = self._target_project()
        if target and rec["project"] != target:
            return False
        return True

    def _window_cost(self, since, only_5h_models=False):
        """
        Total biaya untuk request sejak waktu `since`.

        Batas pemakaian dihitung lintas project (kuota memang berlaku
        per akun), jadi di sini hanya jendela waktunya yang menyaring.

        `only_5h_models=True` membuang model yang tidak ikut batas 5 jam
        (lihat MODELS_OUTSIDE_5H). Model yang dibuang juga tidak dipakai
        untuk menentukan awal blok 5 jam.
        """
        total = 0.0
        oldest = None
        excluded = 0.0
        for rec in self.records.values():
            ts = rec["ts"]
            if ts is None or ts < since:
                continue
            if only_5h_models and not _counts_toward_5h(rec["model"]):
                excluded += rec["cost"]
                continue
            total += rec["cost"]
            if oldest is None or ts < oldest:
                oldest = ts
        return total, oldest, excluded

    def model_breakdown(self, limit=3):
        """
        Rincian pemakaian per model dalam scope aktif,
        diurutkan dari biaya terbesar.
        """
        today = datetime.now().date()
        per_model = {}
        total = 0.0
        for rec in self.records.values():
            if not self._in_scope(rec, today):
                continue
            entry = per_model.setdefault(
                rec["model"], {"cost": 0.0, "input": 0, "output": 0, "requests": 0}
            )
            entry["cost"] += rec["cost"]
            entry["input"] += rec["input"] + rec["cache_read"] + rec["cache_write"]
            entry["output"] += rec["output"]
            entry["requests"] += 1
            total += rec["cost"]

        rows = []
        for model, agg in sorted(per_model.items(), key=lambda kv: -kv[1]["cost"]):
            rows.append({
                "model": display_name(model),
                "cost": agg["cost"],
                "input": agg["input"],
                "output": agg["output"],
                "requests": agg["requests"],
                "pct": round(agg["cost"] / total * 100) if total else 0,
            })
        return rows[:limit]

    def _five_hour_block(self, now):
        """
        Batas 5 jam Claude Code memakai BLOK TETAP, bukan jendela bergulir.

        Blok dimulai dari request pertama dan berumur 5 jam; setelah itu
        hitungannya kembali ke nol, dan blok baru dimulai pada request
        berikutnya. Kalau dipakai jendela bergulir, angkanya akan meluruh
        perlahan alih-alih reset -- jadi jauh melenceng dari panel begitu
        blok berakhir.

        Return: (biaya_di_blok, biaya_model_dikecualikan, menit_sampai_reset)
        """
        counted = sorted(
            rec["ts"] for rec in self.records.values()
            if rec["ts"] and _counts_toward_5h(rec["model"])
        )
        if not counted:
            return 0.0, 0.0, 0

        # Majukan anchor tiap kali satu blok habis.
        anchor = None
        for ts in counted:
            if anchor is None or ts >= anchor + FIVE_HOUR_WINDOW:
                anchor = ts

        block_end = anchor + FIVE_HOUR_WINDOW
        if now >= block_end:
            return 0.0, 0.0, 0     # blok sudah habis, belum ada request baru

        biaya = 0.0
        luar = 0.0
        for rec in self.records.values():
            ts = rec["ts"]
            if ts is None or ts < anchor or ts >= block_end:
                continue
            if _counts_toward_5h(rec["model"]):
                biaya += rec["cost"]
            else:
                luar += rec["cost"]

        mins = max(0, int((block_end - now).total_seconds() // 60))
        return biaya, luar, mins

    def _weekly_reset(self, now):
        """Reset mingguan berikutnya: Minggu 02.00 waktu lokal."""
        days_ahead = (WEEKLY_RESET_WEEKDAY - now.weekday()) % 7
        reset = (now + timedelta(days=days_ahead)).replace(
            hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0
        )
        if reset <= now:
            reset += timedelta(days=7)
        return reset

    def credit_cost_today(self):
        """
        Biaya model yang ditagihkan ke "Kredit penggunaan" (bukan kuota paket).

        Diverifikasi terhadap panel: pemakaian Fable 5 senilai $22.86
        berbarengan dengan kenaikan kredit $24.46 (selisih ~6%, wajar karena
        di sini dipakai tarif API resmi).
        """
        today = datetime.now().date()
        return sum(
            rec["cost"] for rec in self.records.values()
            if rec["date"] == today and not _counts_toward_5h(rec["model"])
        )

    def snapshot(self, budget_5h=None, budget_week=None, credit_baseline=0.0):
        """
        Data lengkap untuk tampilan multi-halaman.

        CATATAN: `limit_5h` dan `limit_week` adalah ESTIMASI LOKAL.
        Persentase resmi Anthropic hanya ada di header response API dan
        tidak pernah ditulis ke disk, jadi tidak bisa dibaca dari sini.
        Angkanya dihitung terhadap budget yang kamu set sendiri.
        """
        now = datetime.now().astimezone()
        agg = self.totals()

        latest = self.latest or {}
        model = latest.get("model") or ""
        ctx_used = latest.get("context", 0)
        ctx_max = context_window(model)

        cost_5h, cost_5h_luar, mins_5h = self._five_hour_block(now)

        # Mingguan berlabel "semua model" di panel, jadi tanpa pengecualian.
        week_reset = self._weekly_reset(now)
        cost_week, _, _ = self._window_cost(week_reset - timedelta(days=7))
        mins_week = max(0, int((week_reset - now).total_seconds() // 60))

        def pct(value, budget):
            if not budget or budget <= 0:
                return 0
            return max(0, min(999, round(value / budget * 100)))

        return {
            "plan": self.plan_name(),
            "project": self.active_project(),
            "models": self.model_breakdown(limit=3),
            "model": display_name(model) if model else "-",
            "effort": effort_label(latest.get("effort")),
            "context_used": ctx_used,
            "context_max": ctx_max,
            "context_pct": pct(ctx_used, ctx_max),
            "limit_5h_pct": pct(cost_5h, budget_5h),
            "limit_5h_mins": mins_5h,
            "limit_5h_cost": cost_5h,
            # Biaya model yang dikecualikan dari batas 5 jam (mis. Fable 5).
            "limit_5h_excluded_cost": cost_5h_luar,
            "credit": credit_baseline + self.credit_cost_today(),
            "limit_week_pct": pct(cost_week, budget_week),
            "limit_week_mins": mins_week,
            "limit_week_cost": cost_week,
            "cost": agg["cost"],
            "input": agg["input"] + agg["cache_read"] + agg["cache_write"],
            "output": agg["output"],
            "requests": agg["requests"],
        }

    def totals(self):
        today = datetime.now().date()
        agg = {
            "input": 0, "output": 0, "cache_read": 0,
            "cache_write": 0, "cost": 0.0, "requests": 0,
        }
        for rec in self.records.values():
            if not self._in_scope(rec, today):
                continue
            agg["input"] += rec["input"]
            agg["output"] += rec["output"]
            agg["cache_read"] += rec["cache_read"]
            agg["cache_write"] += rec["cache_write"]
            agg["cost"] += rec["cost"]
            agg["requests"] += 1
        return agg
