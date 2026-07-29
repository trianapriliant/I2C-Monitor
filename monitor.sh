#!/usr/bin/env bash
#
# Pintasan untuk I2C OLED Token & Multi-Mode Monitor.
# Jalankan tanpa argumen untuk melihat daftar perintah.
#
set -euo pipefail

cd "$(dirname "$0")"

PIO="python3 -m platformio"
LOG="/tmp/token_monitor.log"

# ------------------------------------------------------------
#  Bantuan
# ------------------------------------------------------------
usage() {
    cat <<'EOF'
I2C OLED Multi-Mode & Token Monitor

PENGGUNAAN & SWITCHER:
  ./monitor.sh switch <mode>   ganti mode tampilan OLED di background
  ./monitor.sh menu            buka menu interaktif terminal untuk pilih mode
  ./monitor.sh list            tampilkan daftar semua mode tampilan
  ./monitor.sh rotate [detik]  rotasi otomatis antar mode (default: 10 detik)

KONTROL UTAMA:
  ./monitor.sh start [source]  jalankan monitor di background (default: claude-code)
  ./monitor.sh run   [source]  jalankan di depan layar, Ctrl+C untuk berhenti
  ./monitor.sh stop            hentikan monitor
  ./monitor.sh status          cek monitor jalan atau tidak
  ./monitor.sh log             ikuti log secara langsung

UTILITAS:
  ./monitor.sh flash           build + upload firmware (layar penuh)
  ./monitor.sh flash yellow    upload versi area kuning saja
  ./monitor.sh serial          lihat output mentah dari board
  ./monitor.sh calibrate 60,6  hitung budget dari angka panel /usage
  ./monitor.sh page 4          pindah ke halaman tertentu

MODE YANG TERSEDIA:
  - claude-code   (Token Monitor Claude Code)
  - antigravity   (Token Monitor Antigravity AI)
  - sysmon        (PC CPU, RAM, Disk Monitor)
  - crypto        (Crypto BTC/ETH/SOL & USD/IDR Ticker)
  - weather       (Jam Digital & Cuaca Lokal)
  - spotify       (Media / Music Player macOS)
  - pomodoro      (Focus & Break Timer 25m/5m)
  - github        (GitHub Commits, PRs, Issues & Actions)
  - network       (Network Latency Ping, Speed & IP)
  - stocks        (Stock Market Tech & Forex Rates)
  - todo          (Interactive Daily Todo List)
  - companion     (Pixel Art Desk Mascot Companion)
EOF
}

# ------------------------------------------------------------
#  Deteksi port serial
# ------------------------------------------------------------
find_port() {
    local port
    port=$(ls /dev/cu.usbserial-* /dev/cu.usbmodem* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -1 || true)
    if [ -z "$port" ]; then
        echo "ESP32 tidak terdeteksi. Pastikan kabelnya tercolok." >&2
        return 1
    fi
    echo "$port"
}

require_deps() {
    python3 -c 'import serial' 2>/dev/null || {
        echo "pyserial belum terpasang. Jalankan: pip3 install pyserial" >&2
        exit 1
    }
}

is_running() { pgrep -f "token_monitor.py" >/dev/null 2>&1; }

stop_monitor() {
    if is_running; then
        pkill -f "token_monitor.py" || true
        sleep 1
        echo "Monitor dihentikan."
    else
        echo "Monitor memang tidak jalan."
    fi
}

start_source() {
    local src="$1"
    require_deps
    stop_monitor >/dev/null
    local interval=3
    if [ "$src" = "visualizer" ] || [ "$src" = "stage" ]; then
        interval=0.04  # ~25fps untuk real-time audio FFT spectrum & karaoke stage (low-latency)
    elif [ "$src" = "spotify" ] || [ "$src" = "pomodoro" ] || [ "$src" = "companion" ] || [ "$src" = "network" ]; then
        interval=0.5
    fi
    nohup python3 -u tools/token_monitor.py --source "$src" --interval "$interval" \
        > "$LOG" 2>&1 &
    sleep 3
    if is_running; then
        echo "Monitor jalan (Mode: $src). Log: $LOG"
        grep -E '^\[[0-9]' "$LOG" | tail -1 || true
    else
        echo "Monitor gagal start:" >&2
        cat "$LOG" >&2
        exit 1
    fi
}

interactive_menu() {
    echo "========================================"
    echo "  I2C OLED Monitor - Mode Switcher"
    echo "========================================"
    echo " 1) Claude Code Token Monitor"
    echo " 2) Antigravity AI Token Monitor"
    echo " 3) PC System Monitor (CPU/RAM/Disk)"
    echo " 4) Crypto & USD/IDR Ticker"
    echo " 5) Jam Digital & Cuaca Lokal"
    echo " 6) Media Player (Spotify/Music)"
    echo " 7) Pomodoro Focus Timer"
    echo " 8) GitHub & Actions CI/CD Status"
    echo " 9) Network Ping & Speed Monitor"
    echo "10) Stock Market & Forex Rates"
    echo "11) Interactive Todo List"
    echo "12) Pixel Art Desk Mascot Companion"
    echo "13) Audio Equalizer Spectrum Visualizer"
    echo "14) Mac Thermals & Battery Health"
    echo "15) Agenda Calendar & Meeting Alert"
    echo "16) Docker Containers & Local Servers"
    echo "17) World Clock Multi-Timezone"
    echo "18) Stage Karaoke & Beat Sync Visualizer"
    echo "99) Rotasi Otomatis (Semua Mode)"
    echo " 0) Stop Monitor"
    echo "========================================"
    read -rp "Pilih mode (0-99): " choice

    case "$choice" in
        1) start_source "claude-code" ;;
        2) start_source "antigravity" ;;
        3) start_source "sysmon" ;;
        4) start_source "crypto" ;;
        5) start_source "weather" ;;
        6) start_source "spotify" ;;
        7) start_source "pomodoro" ;;
        8) start_source "github" ;;
        9) start_source "network" ;;
        10) start_source "stocks" ;;
        11) start_source "todo" ;;
        12) start_source "companion" ;;
        13) start_source "visualizer" ;;
        14) start_source "thermals" ;;
        15) start_source "calendar" ;;
        16) start_source "docker" ;;
        17) start_source "worldclock" ;;
        18) start_source "stage" ;;
        99)
            stop_monitor >/dev/null
            nohup python3 -u tools/token_monitor.py --rotate 10 --interval 3 > "$LOG" 2>&1 &
            echo "Rotasi otomatis berjalan (tiap 10s)."
            ;;
        0) stop_monitor ;;
        *) echo "Pilihan tidak valid." ;;
    esac
}

# ------------------------------------------------------------
#  Perintah
# ------------------------------------------------------------
cmd="${1:-help}"
shift || true

case "$cmd" in
    switch)
        if [ $# -lt 1 ]; then
            echo "PILIHAN MODE: claude-code, antigravity, sysmon, crypto, weather, spotify, pomodoro" >&2
            echo "Contoh: ./monitor.sh switch sysmon" >&2
            exit 1
        fi
        start_source "$1"
        ;;

    menu)
        interactive_menu
        ;;

    list)
        PYTHONPATH=tools python3 -c "from sources import available_sources; print('\n'.join(available_sources()))"
        ;;

    rotate)
        sec="${1:-10}"
        stop_monitor >/dev/null
        nohup python3 -u tools/token_monitor.py --rotate "$sec" --interval 3 > "$LOG" 2>&1 &
        echo "Rotasi otomatis berjalan (ganti mode tiap $sec detik). Log: $LOG"
        ;;

    start)
        src="${1:-claude-code}"
        start_source "$src"
        ;;

    run)
        require_deps
        stop_monitor >/dev/null
        python3 tools/token_monitor.py --source "${1:-claude-code}" --interval 3
        ;;

    stop)   stop_monitor ;;

    status)
        if is_running; then
            echo "Jalan (PID $(pgrep -f token_monitor.py | tr '\n' ' '))"
            grep -E '^\[[0-9]' "$LOG" 2>/dev/null | tail -1 || true
        else
            echo "Tidak jalan."
        fi
        ;;

    log)    tail -f "$LOG" ;;

    flash)
        stop_monitor >/dev/null
        env="esp32dev"
        [ "${1:-}" = "yellow" ] && env="esp32dev-yellow"
        [ "${1:-}" = "antigravity" ] && env="antigravity"
        port=$(find_port)
        echo "Upload $env ke $port ..."
        $PIO run -e "$env" -t upload --upload-port "$port"
        echo "Selesai. Jalankan './monitor.sh start' untuk mulai lagi."
        ;;

    serial)
        stop_monitor >/dev/null
        port=$(find_port)
        echo "Menampilkan output board dari $port (Ctrl+C untuk berhenti)"
        $PIO device monitor --port "$port" --baud 115200
        ;;

    calibrate)
        if [ $# -lt 1 ]; then
            echo "Contoh: ./monitor.sh calibrate 60,6" >&2
            exit 1
        fi
        python3 tools/token_monitor.py --calibrate "$1" --dry-run
        ;;

    page)
        require_deps
        [ $# -ge 1 ] || { echo "Contoh: ./monitor.sh page 4" >&2; exit 1; }
        was_running=false
        is_running && was_running=true
        stop_monitor >/dev/null
        python3 tools/token_monitor.py --page "$1" --once
        $was_running && exec "$0" start
        ;;

    help|--help|-h) usage ;;
    *) echo "Perintah tidak dikenal: $cmd" >&2; echo; usage; exit 1 ;;
esac
