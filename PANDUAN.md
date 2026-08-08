# Panduan Pemakaian I2C OLED Monitor

Panduan praktis pengoperasian harian 17 mode tampilan, tombol interaktif, dan kalibrasi. Untuk arsitektur dan detail teknis, lihat [README.md](README.md).

---

## 🛠️ Persiapan Sekali Setup

```bash
pip3 install pyserial
chmod +x monitor.sh monitor
```

Colok ESP32 ke port USB Mac, lalu upload firmware:

```bash
./monitor flash
```

---

## ⚡ Perintah Pengoperasian Harian

```bash
./monitor menu       # buka menu interaktif terminal (0-99)
./monitor start      # jalankan di background (default: claude-code)
./monitor status     # cek status monitor jalan atau tidak
./monitor stop       # hentikan monitor
./monitor log        # lihat log langsung di terminal (Ctrl+C untuk keluar)
```

---

## 🔄 Cara Berganti Mode Tampilan

Kamu bisa berpindah mode secara instan lewat perintah `switch`, menu interaktif, atau rotasi otomatis:

```bash
# Berpindah mode langsung:
./monitor switch visualizer  # Audio Equalizer Spectrum Visualizer
./monitor switch thermals    # Mac CPU Temp & Battery Health
./monitor switch calendar    # Agenda Calendar & Meeting Alert
./monitor switch docker      # Docker Containers & Local Servers
./monitor switch worldclock  # World Clock Multi-Timezone
./monitor switch github      # GitHub & CI/CD Status
./monitor switch spotify     # Media Player & Synced Lyrics
./monitor switch crypto      # Crypto Ticker 3-Halaman
./monitor switch pomodoro    # Focus Timer Interaktif
./monitor switch network     # Network Ping & Traffic Speed
./monitor switch stocks      # Stock Market & Kurs USD/IDR
./monitor switch todo        # Interactive Daily Todo List
./monitor switch companion   # Maskot Piksel Reaktif
./monitor switch sysmon      # PC System Monitor
./monitor switch weather     # Jam Digital & Cuaca Lokal
./monitor switch claude-code # Token Monitor Claude AI

# Rotasi otomatis antar semua mode tiap N detik:
./monitor rotate 10
```

---

## 🔘 Tombol Interaktif ESP32

Tombol bawaan **BOOT (GPIO0)** atau **Tombol Eksternal di GPIO4** memiliki fungsi interaktif tergantung pada mode yang aktif:

### 1. **Fungsi Umum (Mode Standar)**
* **Klik 1x (Short Press)**: Pindah ke sub-halaman berikutnya (misal: Halaman 1 ➔ Halaman 2 ➔ Halaman 3).
* **Tahan ~1 Detik (Long Hold)**: Mengaktifkan / mematikan **Auto-Cycle** (pergantian sub-halaman otomatis).

### 2. **Mode Pomodoro (`./monitor switch pomodoro`)**
* **Klik 1x**: Start / Pause timer Pomodoro.
* **Klik 2x**: Reset timer ke awal sesi.
* **Tahan ~1 Detik (Hold)**: Berganti preset Pomodoro secara berurutan (`25/5/30` ➔ `50/10/60` ➔ `90/10/60`).

### 3. **Mode Interactive Todo (`./monitor switch todo`)**
* **Klik 1x**: Centang / coret status tugas yang ditunjuk `[ ]` ➔ `[x]` (otomatis tersimpan ke `~/todo.txt`).
* **Klik 2x**: Memindahkan kursor penanda `>` ke baris tugas berikutnya.

---

## 📊 Daftar 17 Mode & Sub-Halaman

| Mode | Sub-Halaman | Isi Tampilan |
| :--- | :--- | :--- |
| **`visualizer`** | Halaman 1<br>Halaman 2 | 16-Bar Equalizer Spectrum Visualizer + Judul Lagu & Artis<br>Detail Track Time & Spectrum Wave Line 2 |
| **`thermals`** | Halaman 1<br>Halaman 2 | Suhu CPU Mac (°C), Status Thermal, Daya Wattage Baterai, % Baterai<br>Battery Health Status, Cycle Count, & Time Remaining |
| **`calendar`** | Halaman 1<br>Halaman 2 | Meeting Terdekat + Hitung Mundur Waktu (`In 15m: Daily Standup`) + Total Agenda<br>Daftar 4 Agenda Meeting Hari Ini |
| **`docker`** | Halaman 1<br>Halaman 2 | Count Running/Stopped Containers + Total Containers + Bar % Active<br>Daftar Status Kontainer (`Postgres: OK`, `Redis: OK`, `Nginx: OFF`) |
| **`worldclock`**| Halaman 1<br>Halaman 2 | Jakarta (WIB), Tokyo (JST), London (GMT) + Tanggal<br>San Francisco (PST), New York (EST), Sydney (AEST) |
| **`spotify`** | Halaman 1<br>Halaman 2 | Now Playing Dashboard (Judul, Artis, Durasi, Progress Bar)<br>**Synced Lyrics 1-Baris Full Layar** (Typewriter animation, Slow Marquee Judul) |
| **`crypto`** | Halaman 1<br>Halaman 2<br>Halaman 3 | Top 5 Cryptos (`BTC`, `ETH`, `SOL`, `BNB`, `USDT`) + Kurs IDR<br>Altcoins (`XRP`, `DOGE`, `ADA`, `AVAX`, `DOT`) + Kurs IDR<br>Animasi Ticker Carousel 10 Altcoins |
| **`github`** | Halaman 1<br>Halaman 2 | Daily Commits, Open PRs, Open Issues, Public Repos, Followers<br>Status GitHub Actions Build Terbaru (`SUCCESS` / `FAILED`) |
| **`network`** | Halaman 1<br>Halaman 2 | Ping Latency (Google `8.8.8.8` & Cloudflare `1.1.1.1`) + Wi-Fi SSID + Quality<br>IP Lokal (`192.168.x.x`), IP Publik, Speed Down/Up (KB/s) |
| **`stocks`** | Halaman 1<br>Halaman 2 | Saham Tech (`AAPL`, `NVDA`, `GOOGL`, `MSFT`, `AMZN`) + % 24j<br>Kurs Mata Uang (`USD/IDR`, `EUR/IDR`, `SGD/IDR`, `JPY/IDR`) |
| **`todo`** | Halaman 1<br>Halaman 2 | Daftar Tugas `[ ]` / `[x]` + Kursor `>` + Bar % Selesai<br>Panduan Tombol + Path File (`~/todo.txt`) |
| **`companion`**| Halaman 1<br>Halaman 2 | Maskot Piksel Reaktif (`HOT`, `DANCING`, `SLEEPING`, `WORKING`) + Wajah Animasi<br>Detail Metrik CPU, Status Musik, Frame # |
| **`sysmon`** | Halaman 1 | CPU Load %, RAM Usage (MB/GB), Disk Free/Used %, Nama Device |
| **`weather`**| Halaman 1 | Jam Digital Centered Presisi (HH:MM:SS) + Temperatur & Kondisi Cuaca |
| **`pomodoro`**| Halaman 1 | Status Timer (`00:00`), Mode (`KERJA`/`REHAT`), Keterangan Preset & Tombol |
| **`claude-code`**| 4 Halaman | `KONTEKS` (bar 5j/mgg), `BATAS`, `TOKEN` (biaya), `MODEL` (3 model teratas) |
| **`antigravity`**| Halaman 1 | Token In/Out, Biaya USD, Total Request |

---

## 🎯 Kalibrasi Budget Token AI (Khusus Mode Claude Code)

Bar batas 5 jam & mingguan pada mode `claude-code` dihitung berdasarkan estimasi lokal. Supaya angkanya presisi menyamai panel `/usage` Claude Code:

1. Buka panel `/usage` di Claude Code.
2. Catat persentase 5 jam dan mingguan (misal `60%` dan `6%`).
3. Jalankan:
   ```bash
   ./monitor calibrate 60,6
   ```

---

## ❓ Troubleshooting

| Gejala | Penyebab & Solusi |
| :--- | :--- |
| Layar berkedip / glitch saat ganti lirik | Sudah diatasi dengan **Double-Buffering Shadow Commit** di firmware terbaru (`./monitor flash`). |
| "ESP32 tidak terdeteksi" | Kabel terlepas, atau kabel USB tipe *charge-only* (tanpa jalur data). Ganti kabel data USB. |
| Upload gagal: "port is busy" | Monitor background masih berjalan dan memegang port serial. Jalankan `./monitor stop` dulu. |
| Lirik lagu lambat terpotong `~~~ ~~ ~` | Sudah disesuaikan di `spotify.py` agar jeda instrumen hanya aktif jika jeda musik > 10 detik. |
