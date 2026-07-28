#ifndef CONFIG_H
#define CONFIG_H

// ============================================
//  OLED Display Configuration
// ============================================
#define SCREEN_WIDTH    128
#define SCREEN_HEIGHT   64
#define OLED_I2C_ADDR   0x3C    // Alamat I2C OLED SSD1306
#define OLED_RESET      -1      // Reset pin (-1 jika tidak dipakai)

// ============================================
//  I2C Pin Configuration (ESP32 Default)
// ============================================
#define I2C_SDA         21      // GPIO21 - SDA
#define I2C_SCL         22      // GPIO22 - SCL

// ============================================
//  Serial Configuration
// ============================================
#define SERIAL_BAUD     115200

// ============================================
//  Display Timing
// ============================================
#define SPLASH_DURATION 2000    // Durasi splash screen (ms)
#define SCROLL_SPEED    50      // Kecepatan animasi scroll (ms)

// ============================================
//  Mode Warna
// ============================================
// PENTING: modul SSD1306 128x64 "dual color" punya strip KUNING fisik di
// 16 baris teratas dan BIRU di 48 baris sisanya. Warna itu ada di lapisan
// panel, bukan data piksel -- jadi TIDAK BISA diubah lewat software.
// Tiap piksel cuma punya status nyala/mati; warnanya ditentukan posisinya.
//
// YELLOW_ONLY=1 memadatkan semua konten ke 16 baris teratas, sehingga yang
// menyala hanya area kuning. Konsekuensinya ruang jadi jauh lebih sempit.
#ifndef YELLOW_ONLY
    #define YELLOW_ONLY 0
#endif
#define YELLOW_ROWS     16

// ============================================
//  Navigasi Halaman
// ============================================
// Set ENABLE_BUTTONS ke 0 jika tidak ingin memakai tombol hardware sama sekali.
#ifndef ENABLE_BUTTONS
    #define ENABLE_BUTTONS  1
#endif

// Set pin ke -1 jika ingin menonaktifkan tombol tertentu.
#ifndef BUTTON_PIN
    #define BUTTON_PIN      0     // GPIO0 (Tombol BOOT)
#endif
#ifndef BUTTON_EXT_PIN
    #define BUTTON_EXT_PIN  4     // GPIO4 (Tombol Eksternal)
#endif

#define BUTTON_DEBOUNCE 50      // ms
#define BUTTON_LONG_MS  800     // tahan segini untuk toggle auto-cycle

#define PAGE_COUNT      4
#define AUTO_CYCLE_MS   5000    // ganti halaman tiap 5 detik saat auto-cycle

// ============================================
//  Profil Tampilan (IDE / AI)
// ============================================
// Satu file per IDE/AI di include/profiles/.
// Dipilih lewat build flag di platformio.ini; default: Claude Code.
// Menambah profil baru = bikin satu file header lalu tambah cabang di sini.

#if defined(PROFILE_ANTIGRAVITY)
    #include "profiles/antigravity.h"
#else
    #include "profiles/claude_code.h"
#endif

// Alias lama supaya kode yang sudah ada tetap jalan.
#define PROJECT_NAME    PROFILE_NAME
#define PROJECT_VER     PROFILE_VER

#endif // CONFIG_H
