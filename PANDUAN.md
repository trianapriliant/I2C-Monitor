# Panduan Pemakaian I2C OLED Monitor

Panduan praktis pengoperasian harian 12 mode tampilan, tombol interaktif, dan kalibrasi. Untuk arsitektur dan detail teknis, lihat [README.md](README.md).

---

## 🛠️ Persiapan Sekali Setup

```bash
pip3 install pyserial
chmod +x monitor.sh
```

Colok ESP32 ke port USB Mac, lalu upload firmware:

```bash
./monitor.sh flash
```

---

## ⚡ Perintah Pengoperasian Harian

```bash
./monitor.sh menu       # buka menu interaktif terminal (0-99)
./monitor.sh start      # jalankan di background (default: claude-code)
./monitor.sh status     # cek status monitor jalan atau tidak
./monitor.sh stop       # hentikan monitor
./monitor.sh log        # lihat log langsung di terminal (Ctrl+C untuk keluar)
```

---

## 🔄 Cara Berganti Mode Tampilan

Kamu bisa berpindah mode secara instan lewat perintah `switch`, menu interaktif, atau rotasi otomatis:

```bash
# Berpindah mode langsung:
./monitor.sh switch spotify     # Media Player & Synced Lyrics
./monitor.sh switch crypto      # Crypto Ticker 3-Halaman
./monitor.sh switch pomodoro    # Focus Timer Interaktif
./monitor.sh switch github      # GitHub & CI/CD Status
./monitor.sh switch network     # Network Ping & Traffic Speed
./monitor.sh switch stocks      # Stock Market & Kurs USD/IDR
./monitor.sh switch todo        # Interactive Daily Todo List
./monitor.sh switch companion   # Maskot Piksel Reaktif
./monitor.sh switch sysmon      # PC System Monitor
./monitor.sh switch weather     # Jam Digital & Cuaca Lokal
./monitor.sh switch claude-code # Token Monitor Claude AI

# Rotasi otomatis antar semua mode tiap N detik:
./monitor.sh rotate 10
```

---

## 🔘 Tombol Interaktif ESP32

Tombol bawaan **BOOT (GPIO0)** atau **Tombol Eksternal di GPIO4** memiliki fungsi interaktif tergantung pada mode yang aktif:

### 1. **Fungsi Umum (Mode Standar)**
* **Klik 1x (Short Press)**: Pindah ke sub-halaman berikutnya (misal: Halaman 1 ➔ Halaman 2 ➔ Halaman 3).
* **Tahan ~1 Detik (Long Hold)**: Mengaktifkan / mematikan **Auto-Cycle** (pergantian sub-halaman otomatis).

### 2. **Mode Pomodoro (`./monitor.sh switch pomodoro`)**
* **Klik 1x**: Start / Pause timer Pomodoro.
* **Klik 2x**: Reset timer ke awal sesi.
* **Tahan ~1 Detik (Hold)**: Berganti preset Pomodoro secara berurutan (`25/5/30` ➔ `50/10/60` ➔ `90/10/60`).

### 3. **Mode Interactive Todo (`./monitor.sh switch todo`)**
* **Klik 1x**: Centang / coret status tugas yang ditunjuk `[ ]` ➔ `[x]` (otomatis tersimpan ke `~/todo.txt`).
* **Klik 2x**: Memindahkan kursor penanda `>` ke baris tugas berikutnya.

---

## 📊 Daftar 12 Mode & Sub-Halaman

| Mode | Sub-Halaman | Isi Tampilan |
| :--- | :--- | :--- |
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
   ./monitor.sh calibrate 60,6
   ```

---

## ❓ Troubleshooting

| Gejala | Penyebab & Solusi |
| :--- | :--- |
| Layar berkedip / glitch saat ganti lirik | Sudah diatasi dengan **Double-Buffering Shadow Commit** di firmware terbaru (`./monitor.sh flash`). |
| "ESP32 tidak terdeteksi" | Kabel terlepas, atau kabel USB tipe *charge-only* (tanpa jalur data). Ganti kabel data USB. |
| Upload gagal: "port is busy" | Monitor background masih berjalan dan memegang port serial. Jalankan `./monitor.sh stop` dulu. |
| Lirik lagu lambat terpotong `~~~ ~~ ~` | Sudah disesuaikan di `spotify.py` agar jeda instrumen hanya aktif jika jeda musik > 10 detik. |
