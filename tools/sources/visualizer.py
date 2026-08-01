"""
Sumber data: Audio Spectrum Equalizer Visualizer dengan Real Audio FFT.

ARSITEKTUR AUDIO CAPTURE:
1. Menggunakan BlackHole (virtual audio driver macOS) untuk menangkap audio sistem.
2. Audio di-capture di background thread pada 44100 Hz, diproses FFT → 20 frequency bands.
3. Python mengirim 20 band values (0-10) via serial ke ESP32 untuk rendering grafis.
4. Jika BlackHole tidak tersedia, fallback ke animasi prosedural lokal di ESP32.

SETUP (sekali saja):
- brew install blackhole-2ch
- Buka Audio MIDI Setup → buat Multi-Output Device (Speaker + BlackHole 2ch)
- Set Multi-Output Device sebagai output audio di System Settings > Sound
"""

import math
import subprocess
import threading
import time
from sources.base import TokenSource

NAME = "visualizer"
DISPLAY_NAME = "Audio Spectrum"

# Coba import audio libraries
try:
    import numpy as np
    import sounddevice as sd
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False


def find_blackhole_device():
    """Cari device BlackHole 2ch di daftar audio devices."""
    if not HAS_AUDIO:
        return None
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            name = d["name"].lower()
            if "blackhole" in name and d["max_input_channels"] >= 2:
                return i
        return None
    except Exception:
        return None


class AudioCaptureThread(threading.Thread):
    """Background thread yang menangkap audio dari BlackHole dan menjalankan FFT."""

    def __init__(self, device_id):
        super().__init__(daemon=True)
        self.device_id = device_id
        self.sample_rate = 44100
        self.block_size = 1024  # ~23ms per block → ~43 FFT/detik (low-latency)
        self.num_bands = 20
        self.bands = [0] * self.num_bands
        self.lock = threading.Lock()
        self.running = True

        # Smoothing factor: higher = snappier response, lower = smoother
        # 0.6 = fast transient attack with mild smoothing to avoid jitter
        self.smooth = 0.6
        self.smoothed = [0.0] * self.num_bands

        # Frequency bin edges (logarithmic distribution across 20 bands)
        # 60 Hz - 16000 Hz — starts at 60Hz to match FFT resolution (44100/1024 ≈ 43Hz/bin)
        self.freq_edges = np.logspace(
            np.log10(60), np.log10(16000), self.num_bands + 1
        )

    def run(self):
        try:
            with sd.InputStream(
                device=self.device_id,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback,
                latency='low',
            ):
                while self.running:
                    time.sleep(0.1)
        except Exception:
            self.running = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Dipanggil oleh sounddevice setiap block_size samples."""
        try:
            # Mono signal
            signal = indata[:, 0]

            # Apply Hanning window
            windowed = signal * np.hanning(len(signal))

            # FFT
            fft_data = np.abs(np.fft.rfft(windowed))
            freqs = np.fft.rfftfreq(len(windowed), 1.0 / self.sample_rate)

            # Map FFT bins to 20 logarithmic frequency bands
            new_bands = []
            for i in range(self.num_bands):
                lo = self.freq_edges[i]
                hi = self.freq_edges[i + 1]
                mask = (freqs >= lo) & (freqs < hi)
                if np.any(mask):
                    magnitude = np.mean(fft_data[mask])
                else:
                    magnitude = 0.0

                # Scale to 0-10 with wider dynamic range for better visual contrast
                if magnitude > 1e-8:
                    db = 20 * np.log10(magnitude + 1e-10)
                    # Map dB range: -10dB (quiet) → 0, +25dB (loud peak) → 10
                    raw = (db + 10) / 3.5
                    raw = max(0.0, min(10.0, raw))
                else:
                    raw = 0.0

                # Exponential smoothing for fluid bar animation
                self.smoothed[i] = self.smoothed[i] * (1 - self.smooth) + raw * self.smooth
                val = int(round(self.smoothed[i]))
                val = max(0, min(10, val))
                new_bands.append(val)

            with self.lock:
                self.bands = new_bands

        except Exception:
            pass

    def get_bands(self):
        with self.lock:
            return list(self.bands)

    def stop(self):
        self.running = False


def get_media_info():
    script = """
    if application "Spotify" is running then
        tell application "Spotify"
            if player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                set trackPos to player position
                set trackDur to duration of current track
                return trackName & "||" & artistName & "||" & trackPos & "||" & trackDur
            end if
        end tell
    end if
    return "No Track||Spotify Idle||0||100"
    """
    try:
        out = (
            subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
        parts = out.split("||")
        if len(parts) == 4:
            return {
                "title": parts[0] or "No Track",
                "artist": parts[1] or "Spotify Idle",
                "pos": float(parts[2].replace(",", ".")) if parts[2] else 0.0,
                "dur": float(parts[3].replace(",", ".")) if parts[3] else 100.0,
                "playing": parts[0] != "No Track",
            }
    except Exception:
        pass
    return {"title": "No Track", "artist": "Spotify Idle", "pos": 0.0, "dur": 100.0, "playing": False}


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.audio_thread = None
        self.has_real_audio = False
        self.cached_media = None
        self.last_media_fetch = 0

        # Start audio capture if BlackHole available
        if HAS_AUDIO:
            device_id = find_blackhole_device()
            if device_id is not None:
                try:
                    self.audio_thread = AudioCaptureThread(device_id)
                    self.audio_thread.start()
                    self.has_real_audio = True
                    print(f"[INFO] Audio Capture aktif via BlackHole (device #{device_id})")
                except Exception as e:
                    print(f"[WARN] Gagal start audio capture: {e}")

        if not self.has_real_audio:
            print("[INFO] BlackHole tidak ditemukan — fallback ke animasi prosedural di ESP32")

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()

        # Cache media info (AppleScript lambat, jangan panggil terlalu sering)
        if not self.cached_media or (now - self.last_media_fetch) > 2.0:
            self.cached_media = get_media_info()
            self.last_media_fetch = now

        m = self.cached_media

        pos_m, pos_s = divmod(int(m["pos"]), 60)
        dur_m, dur_s = divmod(int(m["dur"] if m["dur"] < 10000 else m["dur"] / 1000), 60)
        time_fmt = f"{pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}"

        # Determine EQ payload
        if self.has_real_audio and self.audio_thread and self.audio_thread.running:
            # Real FFT data → comma-separated 20 band values
            bands = self.audio_thread.get_bands()
            eq_string = ",".join(str(v) for v in bands)
        else:
            # Fallback: send "1" for playing, "0" for paused → ESP32 prosedural animation
            eq_string = "1" if m["playing"] else "0"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"SPECTRUM | {'PLAYING' if m['playing'] else 'PAUSED'}",
                "eq": eq_string,
                "l2": m["title"],
                "l3": m["artist"],
                "p2_hdr": f"NCS CIRCLE | {time_fmt}",
                "p2_l1": f"Lagu : {m['title'][:16]}",
                "p2_l2": f"Artis: {m['artist'][:16]}",
                "p2_l3": f"Time : {time_fmt}",
            },
            "plan": "Visualizer",
            "model": m["title"][:16],
            "effort": m["artist"][:16],
            "context_used": int(m["pos"]),
            "context_max": max(int(m["dur"]), 1),
            "context_pct": int(m["pos"] / max(m["dur"], 1) * 100) if m["dur"] > 0 else 0,
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(m["pos"]),
            "input": 1 if self.has_real_audio else 0,
            "output": 20,
            "requests": 1,
            "project": f"EQ:{m['title'][:10]}",
            "credit": float(m["pos"]),
            "models": [],
        }
