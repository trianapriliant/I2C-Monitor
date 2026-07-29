#!/usr/bin/env python3
"""
Video & Animation Converter for I2C OLED Monitor (SSD1306 128x64)
Diadaptasi & Diintegrasikan dari ESP32_Video_Display (younes-makhchan/ESP32_Video_Display).

Mengonversi file GIF / PNG / MP4 / AVI menjadi file biner monokrom 1-bit (video.bin)
di mana setiap frame berukuran 128x64 piksel = 1024 bytes.
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def pack_pil_image(img, target_width=128, target_height=64):
    """Konversi objek PIL Image ke 1024-byte 1-bit monochrome bit-array"""
    img_resized = img.convert("L").resize((target_width, target_height), Image.Resampling.LANCZOS)
    img_bw = img_resized.point(lambda p: 255 if p > 127 else 0, mode="1")
    return bytearray(img_bw.tobytes())


def convert_gif_with_pil(gif_path, output_path, target_width=128, target_height=64):
    """Konversi animasi GIF menggunakan Pillow (tanpa butuh OpenCV)"""
    print(f"[INFO] Memproses GIF via Pillow: {gif_path}")
    img = Image.open(gif_path)

    output_data = bytearray()
    frame_count = 0

    for frame in ImageSequence.Iterator(img):
        frame_bytes = pack_pil_image(frame, target_width, target_height)
        output_data.extend(frame_bytes)
        frame_count += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(output_data)

    print(f"[SUCCESS] File biner berhasil dibuat dari GIF: {output_path}")
    print(f" - Total frame: {frame_count}")
    print(f" - Ukuran file: {len(output_data)} bytes ({len(output_data) // 1024} KB)")
    return frame_count, len(output_data)


def convert_video_with_cv2(video_path, output_path, target_width=128, target_height=64):
    """Konversi file video MP4/AVI menggunakan OpenCV"""
    if not HAS_CV2:
        print("[ERROR] OpenCV belum terpasang. Untuk MP4, install dengan: pip install opencv-python")
        return 0, 0

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"[ERROR] Gagal membuka video: {video_path}")
        return 0, 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"[INFO] Memproses MP4 via OpenCV: {video_path} ({total_frames} frames @ {fps:.1f} FPS)")

    output_data = bytearray()
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        resized = cv2.resize(gray, (target_width, target_height), interpolation=cv2.INTER_AREA)
        _, binary = cv2.threshold(resized, 128, 255, cv2.THRESH_BINARY)

        pixels = binary.flatten()
        for i in range(0, len(pixels), 8):
            byte_val = 0
            for j in range(8):
                if i + j < len(pixels):
                    if pixels[i + j] > 127:
                        byte_val |= (1 << (7 - j))
            output_data.append(byte_val)

        frame_count += 1
        if frame_count % 100 == 0:
            print(f"  Sudah diproses {frame_count}/{total_frames} frame...")

    cap.release()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(output_data)

    print(f"[SUCCESS] File biner berhasil dibuat dari MP4: {output_path}")
    print(f" - Total frame: {frame_count}")
    print(f" - Ukuran file: {len(output_data)} bytes ({len(output_data) // 1024} KB)")
    return frame_count, len(output_data)


def main():
    if len(sys.argv) < 2:
        print("Converter Video/GIF ke 1-Bit OLED Binary for ESP32")
        print("Penggunaan: python3 tools/video_converter.py <file_video.gif/mp4> [output.bin]")
        sys.exit(1)

    v_path = Path(sys.argv[1])
    o_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/video.bin")

    if not v_path.exists():
        print(f"[ERROR] File {v_path} tidak ditemukan!")
        sys.exit(1)

    ext = v_path.suffix.lower()
    if ext in (".gif", ".png", ".jpg", ".jpeg") and HAS_PIL:
        convert_gif_with_pil(v_path, o_path)
    elif HAS_CV2:
        convert_video_with_cv2(v_path, o_path)
    elif HAS_PIL:
        convert_gif_with_pil(v_path, o_path)
    else:
        print("[ERROR] Butuh Pillow atau OpenCV. Install via: pip install pillow opencv-python")


if __name__ == "__main__":
    main()
