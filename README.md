# I2C OLED Token & Multi-Mode Monitor

Monitor pemakaian token AI coding assistant, statistik sistem PC, crypto ticker, media player, jam/cuaca, pomodoro timer, GitHub CI/CD, jaringan, saham, todo list, maskot piksel, audio visualizer, thermals Mac, kalender agenda, docker, dan world clock di layar OLED SSD1306 128x64 via ESP32 DevKit V1.

Script Python di PC membaca data secara real-time dan memandunya ke ESP32 lewat Serial USB dengan arsitektur **Double-Buffering Shadow Frame Commit** untuk tampilan 100% bebas kedip (*zero flicker*).

---

## Struktur Proyek

```
include/
  config.h                 pin I2C/tombol, ukuran layar, pemilihan profil
src/
  main.cpp                 firmware ESP32 (Double-buffering & Multi-subpage rendering)
tools/
  token_monitor.py         CLI runner + pengirim serial utama
  pricing.py               tabel harga model Claude AI
  sources/
    base.py                kontrak dasar TokenSource
    claude_code.py         pembaca transcript Claude Code
    antigravity.py         pembaca transcript Antigravity AI
    sysmon.py              PC System Monitor (CPU, RAM, Disk macOS)
    crypto.py              Crypto Ticker 3-Halaman (BTC, ETH, SOL, BNB, USDT, Altcoins)
    weather.py             Jam Digital & Cuaca Lokal
    spotify.py             Media Player & Synced Lyrics (Typewriter animation + 0.7s offset)
    pomodoro.py            Pomodoro Focus Timer (Interaktif State Machine 25/5, 50/10, 90/10)
    github.py              GitHub Commits, PRs, Issues & Actions Build Status
    network.py             Network Latency Ping (8.8.8.8), Speed & IP Address
    stocks.py              Stock Market Tech (AAPL, NVDA) & Forex Rates (USD/IDR)
    todo.py                Interactive Daily Todo List (Tombol Centang Tugas)
    companion.py           Pixel Art Desk Mascot Companion (Maskot Reaktif)
    visualizer.py          Audio Equalizer Spectrum Visualizer (Animasi 16-Bar Equalizer)
    thermals.py            macOS Thermal & Battery Health (CPU Temp, Power Watt, Cycle Count)
    calendar.py            macOS Calendar & Meeting Alert (Countdown Rapat Terdekat)
    docker.py              Docker Containers & Server Status (Running/Exited & Memory)
    worldclock.py          World Clock Multi-Timezone (WIB, JST, GMT, PST, EST, AEST)
    stage.py               Stage Karaoke & Beat Sync Visualizer (Lirik Per Kata, Beat Shake & Dancing Line)
    video.py               Video Animation & 3D FX Streamer (3D Starfield Warp, 3D Cube, Synthwave Grid & Bad Apple)
    arcade.py              Retro OLED Mini Games (Flappy Bird, Snake, Pong with Score System)
    news.py                Breaking News & Tech RSS Feed Reader Ticker (AI & Tech Headlines)
    matrix.py              Matrix Digital Rain ASCII Animation & Cyberpunk HUD Terminal
    eyes.py                Cute Expressive Robo Eyes (Animasi Mata Lucu: Kedip, Lirik, Happy, Sleepy, Wink)
    orbit.py               Solar System 3D Orbit Simulation & Moon Phase Tracker
```

Pemisahannya: **source** di folder `tools/sources/` mengatur pengambilan data di komputer, dan **firmware** `src/main.cpp` menangani rendering grafik OLED di ESP32.

---

## Hardware Pinout

| ESP32   | SSD1306 | Tombol Eksternal (Opsional) |
| ------- | ------- | --------------------------- |
| 3V3     | VCC     | -                           |
| GND     | GND     | Terminal A                  |
| GPIO21  | SDA     | -                           |
| GPIO22  | SCL     | -                           |
| GPIO4   | -       | Terminal B (Pull-Up)        |
| GPIO0   | BOOT    | (Tombol BOOT Bawaan)        |

Alamat I2C default: `0x3C` (dapat diubah di `include/config.h`).

---

## Build & Upload Firmware

```bash
# Upload firmware utama (Layar penuh 128x64)
./monitor.sh flash

# Upload versi area kuning saja
./monitor.sh flash yellow
```

---

## Daftar 17 Mode Tampilan yang Tersedia

| Mode | ID `--source` | Deskripsi & Fitur Utama |
| :--- | :--- | :--- |
| 🤖 **Claude Code** | `claude-code` | Token Monitor Claude Code (Konteks, Batas 5j/Mingguan, Biaya USD, Request). |
| 🚀 **Antigravity AI** | `antigravity` | Token Monitor Antigravity AI (Token In/Out, Cost, Request). |
| 💻 **PC SysMon** | `sysmon` | System Monitor macOS (CPU %, RAM MB/GB, Disk Free/Used, Nama Device). |
| 🪙 **Crypto Ticker** | `crypto` | **3 Halaman Multi-Koin**: Top 5 (`BTC`, `ETH`, `SOL`, `BNB`, `USDT`), Altcoins (`XRP`, `DOGE`, `ADA`, `AVAX`, `DOT`), & Carousel Altcoins. |
| 🌤️ **Jam & Cuaca** | `weather` | Jam Digital Centered presisi + Temperatur & Kondisi Cuaca Lokal. |
| 🎵 **Spotify Player** | `spotify` | Player Dashboard + **Synced Lyrics 1-Baris Full Layar** dengan animasi *Typewriter* ketik per-karakter, *Slow Marquee* judul lagu, & *Offset 0.7s*. |
| ⏱️ **Pomodoro Timer**| `pomodoro` | **Interaktif Tombol**: Klik 1x (Start/Pause), Klik 2x (Reset), Hold (Tahan) untuk ganti preset `25/5/30`, `50/10/60`, `90/10/60`. |
| 🐙 **GitHub Status** | `github` | Commits Today, Daily Streak, Open PRs/Issues, Public Repos, & Status Build GitHub Actions CI/CD. |
| 🌐 **Network Latency**| `network` | Latency Ping Realtime (Google `8.8.8.8` & Cloudflare `1.1.1.1`), Wi-Fi SSID, IP Lokal/Publik, & Speed Up/Down (KB/s). |
| 📈 **Stock Market** | `stocks` | Saham Tech Utama (`AAPL`, `NVDA`, `GOOGL`, `MSFT`, `AMZN`) & Kurs Mata Uang (`USD/IDR`, `EUR/IDR`, `SGD/IDR`). |
| 📝 **Interactive Todo**| `todo` | **Interaktif Tombol**: Membaca `~/todo.txt`, Klik 1x untuk centang `[ ]` ➔ `[x]`, Klik 2x untuk pindah kursor penanda tugas. |
| 🤖 **Desk Mascot** | `companion` | Maskot Piksel Reaktif (`HOT` saat CPU tinggi, `DANCING` saat musik menyala, `SLEEPING` saat malam/idle, `WORKING` saat coding). |
| 📊 **Audio Visualizer**| `visualizer` | **16-Bar Equalizer Spectrum Visualizer** yang menari mengikuti lagu Spotify. |
| ⚡ **Mac Thermals** | `thermals` | Suhu CPU Mac (°C), Status & Daya Baterai (Watt), Cycle Count, & Health Status. |
| 📅 **Agenda Calendar**| `calendar` | Hitung Mundur Meeting Terdekat (`In 15m: Standup`) + Agenda Hari Ini dari macOS Calendar. |
| 🐳 **Docker Status** | `docker` | Status Kontainer Docker lokal (`Postgres: 🟢`, `Redis: 🟢`, `Nginx: 🔴`) & Penggunaan Memory. |
| 🌍 **World Clock** | `worldclock` | Jam Digital Multi-Zona Waktu Dunia (WIB, JST, GMT, PST, EST, AEST). |

---

## Perintah Penggunaan (`monitor.sh`)

```bash
# Menu interaktif terminal (pilih 0-99)
./monitor.sh menu

# Berpindah mode instan di background
./monitor.sh switch visualizer
./monitor.sh switch thermals
./monitor.sh switch calendar
./monitor.sh switch docker
./monitor.sh switch worldclock
./monitor.sh switch github
./monitor.sh switch spotify
./monitor.sh switch crypto
./monitor.sh switch pomodoro
./monitor.sh switch network
./monitor.sh switch stocks
./monitor.sh switch todo
./monitor.sh switch companion
./monitor.sh switch sysmon
./monitor.sh switch weather
./monitor.sh switch claude-code

# Rotasi otomatis semua mode (ganti tiap 10 detik)
./monitor.sh rotate 10

# Perintah kontrol
./monitor.sh start <mode>   # Jalankan mode di background
./monitor.sh status         # Cek status monitor
./monitor.sh log            # Lihat log realtime
./monitor.sh stop           # Hentikan monitor
```

---

## Panduan Lengkap

Panduan pengoperasian harian, kalibrasi budget, dan troubleshooting dapat dibaca pada [PANDUAN.md](PANDUAN.md).
