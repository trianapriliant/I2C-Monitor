#!/usr/bin/env python3
"""
I2C OLED Token Monitor (sisi PC)

Membaca statistik token dari sumber yang dipilih (default: Claude Code),
lalu mengirimkannya ke ESP32 lewat Serial USB dengan format CSV:

    InTokens,OutTokens,Cost\\n

Contoh: 1.2M,340K,4.512

Pemakaian:
    python3 tools/token_monitor.py                     # Claude Code, scope hari ini
    python3 tools/token_monitor.py --scope all         # total seluruh riwayat
    python3 tools/token_monitor.py --scope project     # hanya project ini
    python3 tools/token_monitor.py --dry-run           # tampilkan saja, tanpa serial
    python3 tools/token_monitor.py --port /dev/cu.usbserial-XXXX
    python3 tools/token_monitor.py --source claude-code

Menambah IDE / AI lain: lihat tools/sources/__init__.py
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Jalan dari mana saja: pastikan folder tools/ ada di import path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import available_sources, get_source  # noqa: E402


# ============================================
#  Formatting untuk layar OLED 128x64
# ============================================
def fmt_tokens(n):
    """Layar cuma muat ~8 karakter per nilai, jadi disingkat."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_cost(c):
    if c >= 1000:
        return f"{c:.0f}"
    if c >= 100:
        return f"{c:.1f}"
    return f"{c:.3f}"


def fmt_ctx(used, total):
    """Contoh: 428.6k/1.0M"""
    def short(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        return f"{n / 1_000:.1f}k"
    return f"{short(used)}/{short(total)}"


def fmt_duration(minutes):
    """Sisa waktu ringkas: 4j 39m / 6h 11j"""
    if minutes <= 0:
        return "-"
    days, rem = divmod(int(minutes), 60 * 24)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days}h {hours}j"
    if hours:
        return f"{hours}j {mins}m"
    return f"{mins}m"


def build_payload(snap):
    """Satu field per baris, ditutup 'END' sebagai tanda gambar ulang."""
    if "custom" in snap:
        c = snap["custom"]
        lines = [f"MODE:{c.get('mode', 'custom')}"]
        if "hdr" in c:
            lines.append(f"HDR:{c['hdr']}")
        if "big" in c:
            lines.append(f"BIG:{c['big']}")
        if "l1" in c:
            lines.append(f"L1:{c['l1']}")
        if "bar1" in c:
            lines.append(f"BAR1:{c['bar1']}")
        if "l2" in c:
            lines.append(f"L2:{c['l2']}")
        if "bar2" in c:
            lines.append(f"BAR2:{c['bar2']}")
        if "l3" in c:
            lines.append(f"L3:{c['l3']}")
        if "l4" in c:
            lines.append(f"L4:{c['l4']}")
        if "l5" in c:
            lines.append(f"L5:{c['l5']}")
        if "p2_hdr" in c:
            lines.append(f"P2_HDR:{c['p2_hdr']}")
        if "p2_l1" in c:
            lines.append(f"P2_L1:{c['p2_l1']}")
        if "p2_l2" in c:
            lines.append(f"P2_L2:{c['p2_l2']}")
        if "p2_l3" in c:
            lines.append(f"P2_L3:{c['p2_l3']}")
        if "p2_l4" in c:
            lines.append(f"P2_L4:{c['p2_l4']}")
        if "p2_l5" in c:
            lines.append(f"P2_L5:{c['p2_l5']}")
        if "p3_hdr" in c:
            lines.append(f"P3_HDR:{c['p3_hdr']}")
        if "p3_l1" in c:
            lines.append(f"P3_L1:{c['p3_l1']}")
        if "p3_l2" in c:
            lines.append(f"P3_L2:{c['p3_l2']}")
        if "p3_l3" in c:
            lines.append(f"P3_L3:{c['p3_l3']}")
        if "p3_l4" in c:
            lines.append(f"P3_L4:{c['p3_l4']}")
        if "p3_l5" in c:
            lines.append(f"P3_L5:{c['p3_l5']}")
        lines.append("END")
        return "\n".join(lines) + "\n"

    lines = [
        "MODE:token",
        f"PLAN:{snap['plan']}",
        f"MODEL:{snap['model']}",
        f"EFFORT:{snap['effort']}",
        f"CTX:{fmt_ctx(snap['context_used'], snap['context_max'])},{snap['context_pct']}",
        f"L5H:{snap['limit_5h_pct']},{fmt_duration(snap['limit_5h_mins'])}",
        f"LWK:{snap['limit_week_pct']},{fmt_duration(snap['limit_week_mins'])}",
        f"COST:${fmt_cost(snap['cost'])}",
        f"TOK:{fmt_tokens(snap['input'])},{fmt_tokens(snap['output'])}",
        f"REQ:{snap['requests']}",
        f"PROJ:{snap['project'][:20]}",
        f"CRED:${fmt_cost(snap['credit'])}",
    ]

    for i in range(3):
        if i < len(snap["models"]):
            m = snap["models"][i]
            lines.append(f"MDL{i + 1}:{m['model']},${fmt_cost(m['cost'])},{m['pct']}")
        else:
            lines.append(f"MDL{i + 1}:-,,0")

    lines.append("END")
    return "\n".join(lines) + "\n"



# ============================================
#  Serial
# ============================================
def find_port():
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    candidates = [
        p.device for p in list_ports.comports()
        if "usbserial" in p.device or "usbmodem" in p.device or "SLAB" in p.device
    ]
    return candidates[0] if candidates else None


def open_serial(port, baud):
    import serial

    # DTR/RTS dimatikan sebelum open. Ini membantu di sebagian platform,
    # tapi macOS tetap meng-assert DTR saat port dibuka, jadi board tetap
    # reboot -- lihat wait_until_ready() di bawah.
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 1
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def wait_until_ready(ser, timeout=8.0):
    """
    Membuka port biasanya me-reset ESP32. Selama boot + splash screen
    (~2 detik) firmware belum membaca serial, jadi payload pertama akan
    hilang kalau langsung dikirim.

    Tunggu sampai firmware mencetak tanda siap.
    """
    deadline = time.time() + timeout
    quiet_deadline = time.time() + 1.0   # kalau sunyi total, board tidak reboot
    buf = ""
    while time.time() < deadline:
        try:
            chunk = ser.read(ser.in_waiting or 1)
        except Exception:
            break
        if chunk:
            buf += chunk.decode("utf-8", errors="replace")
            if "Siap menerima data serial" in buf:
                return True
        elif not buf and time.time() > quiet_deadline:
            # Tidak ada output sama sekali -> firmware sudah jalan dari tadi.
            return True
        # Kalau sudah ada output tapi belum ada tanda siap, jangan menyerah:
        # boot dan splash screen memang keluar bertahap dengan jeda.
    time.sleep(0.5)
    return False


# ============================================
#  Main
# ============================================
def main():
    ap = argparse.ArgumentParser(description="Kirim statistik token ke OLED ESP32")
    ap.add_argument("--source", default="claude-code",
                    choices=available_sources(), help="Sumber data (default: claude-code)")
    ap.add_argument("--port", help="Port serial (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--interval", type=float, default=3.0, help="Detik antar update (default: 3)")
    ap.add_argument("--scope", choices=["today", "all", "active", "project"], default="today",
                    help="today = semua project hari ini, all = seluruh riwayat, "
                         "active = ikut project yang sedang dipakai, "
                         "project = project tertentu (pakai --project)")
    ap.add_argument("--project", help="Nama folder project (untuk --scope project)")
    ap.add_argument("--dry-run", action="store_true", help="Tampilkan di terminal saja, tanpa serial")
    ap.add_argument("--once", action="store_true", help="Kirim sekali lalu keluar")
    ap.add_argument("--page", type=int, choices=[1, 2, 3],
                    help="Paksa halaman tertentu di OLED")
    # Bar 'batas' di bawah ini ESTIMASI LOKAL: persentase resmi Anthropic
    # cuma ada di header response API dan tidak ditulis ke disk. Angkanya
    # dihitung terhadap budget di bawah, jadi sesuaikan dengan kebiasaanmu.
    # Default hasil kalibrasi terhadap panel /usage (2026-07-26, paket Pro),
    # setelah Fable 5 dikeluarkan dari hitungan batas 5 jam.
    # Kalau bar-nya mulai melenceng dari panel, jalankan ulang:
    #   ./monitor.sh calibrate <persen5jam>,<persenMingguan>
    ap.add_argument("--budget-5h", type=float, default=80.0,
                    help="Budget biaya per blok 5 jam, USD (default: 80)")
    ap.add_argument("--budget-week", type=float, default=1064.0,
                    help="Budget biaya per minggu, USD (default: 1064)")
    ap.add_argument("--credit-baseline", type=float, default=0.0,
                    help="Kredit yang sudah terpakai sebelum hari ini, USD. "
                         "Lihat 'Kredit penggunaan' di panel /usage.")
    ap.add_argument("--calibrate", metavar="P5H,PMINGGU",
                    help="Hitung budget dari angka panel Claude Code. "
                         "Contoh: --calibrate 60,6 (5 jam 60%%, mingguan 6%%)")
    ap.add_argument("--rotate", type=float, metavar="DETIK",
                    help="Berganti sumber data secara otomatis setiap N detik")
    args = ap.parse_args()

    project = args.project
    if args.scope == "project" and not project:
        project = os.path.basename(os.getcwd())

    sources_list = [args.source]
    if args.rotate:
        sources_list = [s for s in available_sources() if s != "base"]
    
    current_source_idx = 0
    last_rotate_time = time.time()

    source = get_source(sources_list[current_source_idx], scope=args.scope, project=project)
    if not source.available():
        print(f"[WARN] Data untuk sumber '{source.DISPLAY_NAME}' tidak tersedia di mesin ini.")

    ser = None
    if not args.dry_run:
        port = args.port or find_port()
        if not port:
            print("[FATAL] Port serial tidak terdeteksi. Colokkan ESP32 atau pakai --port / --dry-run.")
            return 1
        try:
            ser = open_serial(port, args.baud)
        except Exception as exc:
            print(f"[FATAL] Gagal membuka {port}: {exc}")
            return 1
        print(f"[OK] Terhubung ke {port} @ {args.baud}")
        print("[INFO] Menunggu ESP32 siap (boot + splash screen)...")
        if wait_until_ready(ser):
            print("[OK] ESP32 siap menerima data")
        else:
            print("[WARN] Tanda siap tidak terdeteksi, lanjut saja")

    print(f"[INFO] Sumber: {source.DISPLAY_NAME}")
    print(f"[INFO] Scope: {args.scope}" + (f" ({project})" if project else ""))
    if args.rotate:
        print(f"[INFO] Rotasi otomatis aktif setiap {args.rotate} detik")
    print("[INFO] Memindai data awal...")

    last_payload = None
    last_sent_at = 0.0
    last_evt_time = 0.0
    RESEND_EVERY = 30.0

    try:
        while True:
            now = time.time()
            if args.rotate and (now - last_rotate_time) >= args.rotate:
                current_source_idx = (current_source_idx + 1) % len(sources_list)
                src_name = sources_list[current_source_idx]
                try:
                    source = get_source(src_name, scope=args.scope, project=project)
                    print(f"\n[ROTASI] Pindah ke modul: {source.DISPLAY_NAME}")
                except Exception as exc:
                    print(f"[WARN] Gagal memuat modul {src_name}: {exc}")
                last_rotate_time = now

            try:
                source.poll()
            except Exception:
                pass

            try:
                snap = source.snapshot(budget_5h=args.budget_5h, budget_week=args.budget_week,
                                       credit_baseline=args.credit_baseline)
            except TypeError:
                snap = source.snapshot()
            except Exception as exc:
                print(f"[ERR] Gagal mengambil snapshot dari {source.DISPLAY_NAME}: {exc}")
                time.sleep(1)
                continue

            payload = build_payload(snap)
            if args.page:
                payload = f"PAGE:{args.page}\n" + payload


            stale = (time.time() - last_sent_at) >= RESEND_EVERY
            if payload != last_payload or stale or args.once:
                if ser:
                    ser.write(payload.encode("ascii", errors="replace"))
                    ser.flush()
                last_sent_at = time.time()
                if payload != last_payload:
                    stamp = datetime.now().strftime("%H:%M:%S")
                    luar = snap.get("limit_5h_excluded_cost", 0.0)
                    catatan = f" (+${luar:.2f} di luar 5j)" if luar > 0.005 else ""
                    print(
                        f"[{stamp}] {snap['project']}"
                        f" | {snap['model']}/{snap['effort']}"
                        f" | ctx {snap['context_pct']}%"
                        f" | 5j {snap['limit_5h_pct']}%{catatan}"
                        f" | mgg {snap['limit_week_pct']}%"
                        f" | ${snap['cost']:.4f}"
                        f" | req {snap['requests']}"
                    )
                last_payload = payload

            if args.once:
                break

            # Tampilkan balasan board (mis. event tombol) sambil menunggu
            # siklus berikutnya, supaya bisa dipantau tanpa menutup port.
            deadline = time.time() + args.interval
            while time.time() < deadline:
                if ser and ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    for raw in chunk.splitlines():
                        raw = raw.strip()
                        if raw and not raw.startswith("[OK] Data diterima"):
                            print(f"    <- {raw}")
                            if raw.startswith("EVT:"):
                                now_evt = time.time()
                                if (now_evt - last_evt_time) > 0.4:
                                    last_evt_time = now_evt
                                    evt_type = "BTN_SHORT"
                                    if "BTN_DOUBLE" in raw:
                                        evt_type = "BTN_DOUBLE"
                                    elif "BTN_HOLD" in raw:
                                        evt_type = "BTN_HOLD"
                                    if hasattr(source, "handle_event"):
                                        source.handle_event(evt_type)
                                        deadline = time.time()  # Instant refresh!
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan.")
    finally:
        if ser:
            ser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
