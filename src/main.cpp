/**
 * ============================================
 *  I2C OLED Token Monitor
 *  ESP32 DevKit V1 + SSD1306 128x64
 * ============================================
 *
 * Menerima data monitoring via Serial USB dan menampilkannya
 * di layar OLED dalam beberapa halaman.
 *
 * Nama yang tampil diatur lewat profil (include/profiles/...),
 * default: Claude Code.
 *
 * --- Protokol serial (satu field per baris) ---
 *   PLAN:Pro
 *   MODEL:Opus 5
 *   EFFORT:Tinggi
 *   CTX:428.6k/1.0M,43        <- label, persen
 *   L5H:22,4j 39m             <- persen, sisa waktu
 *   LWK:3,6h 11j
 *   COST:$17.77
 *   TOK:25.1M,54.2K           <- input, output
 *   REQ:72
 *   PAGE:1                    <- opsional, pindah halaman dari PC
 *   END                       <- wajib: tanda gambar ulang
 *
 * Format lama "in,out,cost" masih diterima (dianggap TOK + COST).
 *
 * --- Navigasi ---
 *   Tombol BOOT (GPIO0) atau tombol eksternal (GPIO4 -> GND):
 *     tekan singkat = halaman berikutnya
 *     tahan ~1 detik = on/off auto-cycle
 *
 * Platform: PlatformIO + Arduino Framework
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ============================================
//  State
// ============================================
// Satu baris riwayat pemakaian per model.
struct ModelRow {
    String name = "-";
    String cost = "";
    int    pct  = 0;
};

struct Stats {
    String plan       = "-";
    String project    = "-";
    String credit     = "-";
    ModelRow models[3];
    String model      = "-";
    String effort     = "-";
    String ctxLabel   = "-";
    int    ctxPct     = 0;
    int    l5hPct     = 0;
    String l5hReset   = "-";
    int    lwkPct     = 0;
    String lwkReset   = "-";
    String cost       = "$0.000";
    String tokIn      = "0";
    String tokOut     = "0";
    String requests   = "0";
};

struct CustomScreen {
    bool active = false;
    int  subPage = 0;      // 0 = Page 1, 1 = Page 2, 2 = Page 3
    int  maxSubPages = 1;  // Jumlah sub-halaman yang tersedia
    String hdrTitle = "";
    String hdrSub = "";
    String line1 = "";
    int    bar1  = -1;
    String line2 = "";
    int    bar2  = -1;
    String line3 = "";
    String line4 = "";
    String line5 = "";
    String bigText = "";

    // SubPage 2
    String p2HdrTitle = "";
    String p2HdrSub = "";
    String p2Line1 = "";
    String p2Line2 = "";
    String p2Line3 = "";
    String p2Line4 = "";
    String p2Line5 = "";

    // SubPage 3 (Special Rotating Ticker Animation)
    String p3HdrTitle = "";
    String p3HdrSub = "";
    String p3Line1 = "";
    String p3Line2 = "";
    String p3Line3 = "";
    String p3Line4 = "";
    String p3Line5 = "";

    // Graphical Spectrum Equalizer Payload (Comma separated 20 bar values 0-10)
    String eqBars = "";
};

Stats stats;
// ⚠️ GUARDRAIL: Double-buffering Layar untuk Mencegah Flicker / Micro-Glitch.
// Semua serial payload di-parse ke incomingCustomScreen, lalu di-commit
// ke customScreen HANYA saat perintah 'END' diterima.
CustomScreen customScreen;
CustomScreen incomingCustomScreen;

bool dataReceived = false;
// Dihitung per-blok: 'END' hanya sah kalau memang ada field data sebelumnya.
// Tanpa ini, 'END' polos bikin layar tampil 0 semua.
int fieldsInBlock = 0;

int  currentPage = 0;
// Default manual: ganti halaman lewat tombol. Tahan tombol ~1 detik
// kalau ingin halaman berjalan otomatis.
bool autoCycle = false;
unsigned long lastPageChange = 0;
unsigned long lastRedraw = 0;

// ============================================
//  Helper tampilan
// ============================================
void printCentered(const char *text, int16_t y, uint8_t size = 1) {
    display.setTextSize(size);
    int16_t width = (int16_t)strlen(text) * (6 * size);
    int16_t x = (SCREEN_WIDTH - width) / 2;
    if (x < 0) x = 0;
    display.setCursor(x, y);
    display.print(text);
    display.setTextSize(1);
}

void printRight(const String &text, int16_t y) {
    int16_t width = (int16_t)text.length() * 6;
    int16_t x = SCREEN_WIDTH - width;
    if (x < 0) x = 0;
    display.setCursor(x, y);
    display.print(text);
}

/**
 * Bar progres. Persen di atas 100 tetap digambar penuh, tapi
 * diberi arsir supaya kelihatan bahwa nilainya melewati batas.
 */
void drawBar(int16_t x, int16_t y, int16_t w, int16_t h, int pct) {
    display.drawRect(x, y, w, h, SSD1306_WHITE);
    int clamped = pct < 0 ? 0 : (pct > 100 ? 100 : pct);
    int fill = ((w - 2) * clamped) / 100;
    if (fill > 0) {
        display.fillRect(x + 1, y + 1, fill, h - 2, SSD1306_WHITE);
    }
    if (pct > 100) {
        // Arsir vertikal menandakan sudah lewat 100%.
        for (int16_t i = x + 2; i < x + w - 2; i += 3) {
            display.drawFastVLine(i, y + 1, h - 2, SSD1306_BLACK);
        }
    }
}

/**
 * Header yang pas mengisi strip kuning (baris 0-15), lalu garis pemisah
 * tepat di batas warna. Dua baris teks 8px = 16px, jadi area kuning
 * terpakai penuh dan tidak ada teks yang terpotong dua warna.
 *
 *   baris 0-7   : judul halaman + indikator halaman
 *   baris 8-15  : nilai utama halaman tsb (kiri & kanan)
 *   baris 16    : garis pemisah = batas kuning/biru
 */
void drawMarqueeLine(int16_t x, int16_t y, const String &prefix, const String &text, int maxCharsLimit = 21);

void drawHeader(const char *title, const String &leftVal, const String &rightVal) {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    if (rightVal.length() > 0) {
        int rightLen = rightVal.length();
        int maxTitleChars = 21 - rightLen - 1;
        drawMarqueeLine(0, 0, "", title, maxTitleChars);
        printRight(rightVal, 0);
    } else if (!customScreen.active) {
        display.setCursor(0, 0);
        display.print(title);
        String pageInfo = String(currentPage + 1) + "/" + String(PAGE_COUNT);
        printRight(pageInfo, 0);

        if (autoCycle && (millis() / 500) % 2 == 0) {
            display.fillCircle(SCREEN_WIDTH - 24, 3, 2, SSD1306_WHITE);
        }

        display.setCursor(0, 8);
        display.print(leftVal);
        printRight(rightVal, 8);
    } else {
        drawMarqueeLine(0, 0, "", title, 21);
    }

    display.drawFastHLine(0, YELLOW_ROWS, SCREEN_WIDTH, SSD1306_WHITE);
}

// ============================================
//  Halaman
// ============================================

// Halaman 1: jendela konteks + model yang sedang dipakai
// KUNING: judul + "442.0k/1.0M  44%"   BIRU: bar besar + model + effort
void pageContext() {
    drawHeader("KONTEKS", stats.ctxLabel, String(stats.ctxPct) + "%");

    drawBar(0, 21, SCREEN_WIDTH, 12, stats.ctxPct);

    display.setCursor(0, 39);
    display.print(F("Model : "));
    display.print(stats.model);

    display.setCursor(0, 51);
    display.print(F("Effort: "));
    display.print(stats.effort);
}

// Halaman 2: batas 5 jam + mingguan (estimasi lokal)
// KUNING: judul + paket    BIRU: dua bar + sisa waktu reset
void pageLimits() {
    drawHeader("BATAS", "Paket", stats.plan);

    display.setCursor(0, 21);
    display.print(F("5 jam"));
    printRight(String(stats.l5hPct) + "% " + stats.l5hReset, 21);
    drawBar(0, 30, SCREEN_WIDTH, 9, stats.l5hPct);

    display.setCursor(0, 44);
    display.print(F("Mingguan"));
    printRight(String(stats.lwkPct) + "% " + stats.lwkReset, 44);
    drawBar(0, 53, SCREEN_WIDTH, 9, stats.lwkPct);
}

// Halaman 3: rincian token & biaya
// KUNING: judul + biaya & jumlah request   BIRU: rincian token + project
void pageTokens() {
    drawHeader("TOKEN", stats.cost, stats.requests + " req");

    display.setCursor(0, 23);
    display.print(F("Input : "));
    display.print(stats.tokIn);

    display.setCursor(0, 37);
    display.print(F("Output: "));
    display.print(stats.tokOut);

    display.setCursor(0, 51);
    display.print(F("Proj  : "));
    display.print(stats.project);
}

// Halaman 4: riwayat pemakaian per model
// KUNING: judul + kredit terpakai   BIRU: 3 model teratas + bar porsi biaya
//
// Kredit ditaruh di sini karena yang menggerakkannya adalah model tertentu
// (Fable 5), jadi konteksnya paling nyambung dengan rincian per model.
void pageModels() {
    drawHeader("MODEL", "Kredit", stats.credit);

    const int16_t rowY[3] = { 20, 35, 50 };
    for (uint8_t i = 0; i < 3; i++) {
        const ModelRow &m = stats.models[i];
        if (m.name == "-" || m.name.length() == 0) continue;

        display.setCursor(0, rowY[i]);
        display.print(m.name);
        printRight(m.cost + " " + String(m.pct) + "%", rowY[i]);
        drawBar(0, rowY[i] + 9, SCREEN_WIDTH, 5, m.pct);
    }
}

// --------------------------------------------
//  Varian ringkas: hanya memakai 16 baris kuning
// --------------------------------------------
#if YELLOW_ONLY

void pageContextCompact() {
    display.setCursor(0, 0);
    display.print(stats.model);
    printRight(String(stats.ctxPct) + "%", 0);
    drawBar(0, 9, SCREEN_WIDTH, 7, stats.ctxPct);
}

void pageLimitsCompact() {
    display.setCursor(0, 0);
    display.print("5j " + String(stats.l5hPct) + "%");
    printRight("Mg " + String(stats.lwkPct) + "%", 0);
    drawBar(0, 9, 62, 7, stats.l5hPct);
    drawBar(66, 9, 62, 7, stats.lwkPct);
}

void pageTokensCompact() {
    display.setCursor(0, 0);
    display.print(stats.cost);
    printRight(stats.requests + "req", 0);
    display.setCursor(0, 8);
    display.print(stats.tokIn + ">" + stats.tokOut);
}

void pageWaitingCompact() {
    display.setCursor(0, 0);
    display.print(F("Menunggu data..."));
    display.setCursor(0, 8);
    display.print(F(PROFILE_NAME));
}

#endif  // YELLOW_ONLY

// Layar tunggu, ikut dibagi di batas warna:
// KUNING: nama profil + versi   BIRU: instruksi
void pageWaiting() {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    printCentered(PROFILE_NAME, 0);
    printCentered(PROFILE_SUBTITLE, 8);
    display.drawFastHLine(0, YELLOW_ROWS, SCREEN_WIDTH, SSD1306_WHITE);

    display.setCursor(0, 24);
    display.print(F("Menunggu data..."));
    display.setCursor(0, 40);
    display.print(F("Jalankan di PC:"));
    display.setCursor(0, 52);
    display.print(F("./monitor.sh start"));
}

void drawMarqueeLine(int16_t x, int16_t y, const String &prefix, const String &text, int maxCharsLimit) {
    display.setCursor(x, y);
    display.print(prefix);
    
    int prefixLen = prefix.length();
    int availableChars = maxCharsLimit - prefixLen;
    if (availableChars < 4) availableChars = 4;

    if (text.length() <= (size_t)availableChars) {
        display.print(text);
    } else {
        String padded = text + F("   *   ") + text;
        int scrollOffset = (millis() / 250) % (text.length() + 7);
        String visible = padded.substring(scrollOffset, scrollOffset + availableChars);
        display.print(visible);
    }
}

static String lastLyricLine = "";
static unsigned long lyricStartTime = 0;

void drawWrappedLyric(const String &text, int &y, int maxLines) {
    String str = text;
    str.trim();
    if (str.startsWith(">")) {
        str = str.substring(1);
        str.trim();
    }

    if (str.indexOf("~") >= 0 || str.indexOf("♪") >= 0) {
        int animFrame = (millis() / 350) % 3;
        const char *waveStr = "~~~  ~~  ~";
        if (animFrame == 1) waveStr = "~  ~~~  ~~";
        else if (animFrame == 2) waveStr = "~~  ~  ~~~";
        printCentered(waveStr, 34);
        return;
    }

    if (str != lastLyricLine) {
        lastLyricLine = str;
        lyricStartTime = millis();
    }

    unsigned long elapsed = millis() - lyricStartTime;
    // Kecepatan ketik: 30 ms per karakter
    int charLimit = (int)(elapsed / 30);
    if (charLimit < 0) charLimit = 0;

    bool isTyping = false;
    if (charLimit < (int)str.length()) {
        str = str.substring(0, charLimit);
        isTyping = true;
    }

    int start = 0;
    int len = str.length();
    int lineCount = 0;

    while (start < len && lineCount < maxLines) {
        int end = start + 21;
        if (end >= len) {
            end = len;
        } else {
            int spacePos = str.lastIndexOf(' ', end);
            if (spacePos > start) {
                end = spacePos;
            }
        }

        display.setCursor(0, y);
        display.print(str.substring(start, end));
        y += 9;
        lineCount++;

        start = end;
        while (start < len && str.charAt(start) == ' ') {
            start++;
        }
    }

    // Tampilkan cursor berkedip saat masih mengetik
    if (isTyping && lineCount <= maxLines) {
        if ((millis() / 150) % 2 == 0) {
            display.print(F("_"));
        }
    }
}

static int eqPeaks[20] = {0};
static unsigned long lastEqPeakDecay = 0;
// Simple pseudo-random based on seed
static uint32_t eqRand(uint32_t seed) {
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

// Fast integer sine approximation (0-255 output, 0-1023 input angle)
static int fastSin(int angle) {
    angle = angle % 1024;
    if (angle < 0) angle += 1024;
    // Quarter-wave lookup approximation
    int q = angle >> 8; // quadrant 0-3
    int idx = angle & 0xFF;
    int val;
    if (q == 0) val = idx;
    else if (q == 1) val = 255 - idx;
    else if (q == 2) val = -idx;
    else val = -(255 - idx);
    return val; // range ~ -255 to +255
}

void drawSpectrumEqualizer() {
    drawHeader(customScreen.hdrTitle.c_str(), "", customScreen.hdrSub);

    // Render song title + artist marquee at Y = 17
    if (customScreen.line2.length() > 0) {
        String info = customScreen.line2;
        if (customScreen.line3.length() > 0 && customScreen.line3 != info) {
            info += " - " + customScreen.line3;
        }
        drawMarqueeLine(0, 17, "", info);
    }

    int numBars = 20;
    int barWidth = 4;
    int barGap = 2;
    int segHeight = 2;
    int segGap = 1;
    int maxSegs = 10;
    int totalWidth = numBars * barWidth + (numBars - 1) * barGap;
    int startX = (SCREEN_WIDTH - totalWidth) / 2;
    int floorY = 63;
    unsigned long ms = millis();

    // Determine mode: real FFT data (contains commas) vs procedural fallback
    bool hasRealData = (customScreen.eqBars.indexOf(',') >= 0);

    // Parse real FFT values if available
    int realVals[20] = {0};
    if (hasRealData) {
        int idx = 0, lastPos = 0;
        String str = customScreen.eqBars;
        for (int i = 0; i <= (int)str.length() && idx < 20; i++) {
            if (i == (int)str.length() || str.charAt(i) == ',') {
                realVals[idx] = str.substring(lastPos, i).toInt();
                idx++;
                lastPos = i + 1;
            }
        }
    }

    bool isPlaying = hasRealData || (customScreen.eqBars == "1");

    for (int i = 0; i < numBars; i++) {
        int v = 0;
        if (hasRealData) {
            // Real FFT data from Python audio capture
            v = realVals[i];
            if (v < 0) v = 0;
            if (v > maxSegs) v = maxSegs;
        } else if (isPlaying) {
            // Fallback: procedural animation when no BlackHole
            int t = (int)(ms / 40);
            int w1 = fastSin(t * 7 + i * 51) * 5 / 255;
            int w2 = fastSin(t * 11 - i * 37) * 4 / 255;
            int w3 = fastSin(t * 5 + i * 83) * 3 / 255;
            int jitter = (int)(eqRand((uint32_t)(ms / 80) * 31 + i * 17) % 3);
            v = w1 + w2 + w3 + 5 + jitter;
            if (v < 1) v = 1;
            if (v > maxSegs) v = maxSegs;
        } else {
            v = ((i % 5 == 0) && ((ms / 500) % 2 == 0)) ? 2 : 1;
        }

        // Floating peak hold
        if (v >= eqPeaks[i]) {
            eqPeaks[i] = v;
        }

        int x = startX + i * (barWidth + barGap);

        // Draw segmented stacked blocks
        for (int s = 0; s < v; s++) {
            int y = floorY - (s * (segHeight + segGap)) - segHeight;
            display.fillRect(x, y, barWidth, segHeight, SSD1306_WHITE);
        }

        // Draw floating peak indicator line
        if (eqPeaks[i] > 0) {
            int peakY = floorY - (eqPeaks[i] * (segHeight + segGap)) - segHeight;
            display.drawFastHLine(x, peakY, barWidth, SSD1306_WHITE);
        }
    }

    // Decay peaks every ~120ms
    if (ms - lastEqPeakDecay > 120) {
        lastEqPeakDecay = ms;
        for (int i = 0; i < 20; i++) {
            if (eqPeaks[i] > 0) eqPeaks[i]--;
        }
    }
}

void drawStageKaraoke() {
    // 1. Top Yellow Strip (Y=0..15): Dedicated Track Title & Artist Marquee
    String trackInfo = customScreen.line1;
    if (trackInfo.length() == 0) {
        trackInfo = customScreen.hdrTitle;
    }
    drawMarqueeLine(0, 0, "STAGE ", trackInfo);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    // Parse Stage Karaoke payload: active_word||word_progress
    String wordToDisplay = "";
    String progressInfo = "";

    String l2 = customScreen.line2;
    int p1 = l2.indexOf("||");
    if (p1 >= 0) {
        wordToDisplay = l2.substring(0, p1);
        progressInfo = l2.substring(p1 + 2);
    } else {
        wordToDisplay = l2;
        progressInfo = customScreen.line3;
    }

    if (wordToDisplay.length() == 0) {
        wordToDisplay = customScreen.line3;
    }

    // 2. Parse FFT bass energy for Beat Shaking
    int bassEnergy = 0;
    int realVals[20] = {0};
    bool hasRealData = (customScreen.eqBars.indexOf(',') >= 0);

    if (hasRealData) {
        int idx = 0, lastPos = 0;
        String str = customScreen.eqBars;
        for (int i = 0; i <= (int)str.length() && idx < 20; i++) {
            if (i == (int)str.length() || str.charAt(i) == ',') {
                realVals[idx] = str.substring(lastPos, i).toInt();
                idx++;
                lastPos = i + 1;
            }
        }
        // Bass average from bands 0..3
        bassEnergy = (realVals[0] + realVals[1] + realVals[2] + realVals[3]) / 4;
    } else if (customScreen.eqBars == "1") {
        bassEnergy = ((millis() / 200) % 2 == 0) ? 7 : 2;
    }

    // Beat Micro-Shaking Offset
    unsigned long ms = millis();
    int shakeX = 0;
    int shakeY = 0;
    if (bassEnergy >= 5) {
        shakeX = (int)(eqRand((uint32_t)(ms / 50) + 1) % 3) - 1; // -1, 0, +1
        shakeY = (int)(eqRand((uint32_t)(ms / 50) + 7) % 3) - 1; // -1, 0, +1
    }

    // 3. Blue Block Stage (Y=16..63): Rock-Solid BIG Active Word Display (Size 2 Font)
    if (wordToDisplay.length() > 0) {
        if (wordToDisplay.length() <= 10) {
            // Render BIG Text Size 2 (12x16px per char) - Stable & Crisp
            int charW = 12;
            int textW = wordToDisplay.length() * charW;
            int startX = (SCREEN_WIDTH - textW) / 2;
            if (startX < 0) startX = 0;
            display.setTextSize(2);
            display.setCursor(startX, 18);
            display.print(wordToDisplay);
            display.setTextSize(1);
        } else {
            // Fallback to Size 1 for long words
            printCentered(wordToDisplay.c_str(), 22, 1);
        }
    }

    // 4. Beat-Reactive Dancing Line Animation at Y = 38
    int waveY = 38;
    int amplitude = (bassEnergy >= 5) ? 3 : 1;
    for (int x = 0; x < SCREEN_WIDTH; x += 2) {
        int angle = (int)(x * 12 + ms * 8 / 10);
        int dy = (fastSin(angle) * amplitude) / 255;
        display.drawPixel(x, waveY + dy, SSD1306_WHITE);
        display.drawPixel(x + 1, waveY + dy, SSD1306_WHITE);
    }

    // 5. Compact 20-Band Equalizer at Floor Y = 42..63 (21px height)
    int numBars = 20;
    int barWidth = 4;
    int barGap = 2;
    int segHeight = 2;
    int segGap = 1;
    int maxSegs = 7;
    int totalWidth = numBars * barWidth + (numBars - 1) * barGap; // 118
    int startX = (SCREEN_WIDTH - totalWidth) / 2;
    int floorY = 63;

    for (int i = 0; i < numBars; i++) {
        int v = 0;
        if (hasRealData) {
            v = realVals[i] * 7 / 10; // scale 0-10 -> 0-7
            if (v < 0) v = 0;
            if (v > maxSegs) v = maxSegs;
        } else if (bassEnergy > 0) {
            int t = (int)(ms / 40);
            int w1 = fastSin(t * 7 + i * 51) * 3 / 255;
            int w2 = fastSin(t * 11 - i * 37) * 2 / 255;
            v = w1 + w2 + 3;
            if (v < 1) v = 1;
            if (v > maxSegs) v = maxSegs;
        } else {
            v = (i % 5 == 0) ? 1 : 0;
        }

        if (v >= eqPeaks[i]) {
            eqPeaks[i] = v;
        }

        int x = startX + i * (barWidth + barGap);

        for (int s = 0; s < v; s++) {
            int y = floorY - (s * (segHeight + segGap)) - segHeight;
            display.fillRect(x, y, barWidth, segHeight, SSD1306_WHITE);
        }

        if (eqPeaks[i] > 0) {
            int peakY = floorY - (eqPeaks[i] * (segHeight + segGap)) - segHeight;
            display.drawFastHLine(x, peakY, barWidth, SSD1306_WHITE);
        }
    }

    if (ms - lastEqPeakDecay > 120) {
        lastEqPeakDecay = ms;
        for (int i = 0; i < 20; i++) {
            if (eqPeaks[i] > 0) eqPeaks[i]--;
        }
    }
}

void drawVideoDisplay() {
    // 1. Top Yellow Strip (Y=0..15): Dedicated Marquee Header
    String presetTitle = customScreen.hdrTitle;
    if (presetTitle.startsWith("VIDEO | ")) {
        presetTitle = presetTitle.substring(8);
    }
    drawMarqueeLine(0, 0, "VIDEO ", presetTitle);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    // Parse preset index from customScreen.eqBars or line2
    int presetIdx = 0;
    int comma = customScreen.eqBars.indexOf(',');
    if (comma > 0) {
        presetIdx = customScreen.eqBars.substring(0, comma).toInt();
    }

    unsigned long ms = millis();
    int cx = 64;
    int cy = 39;

    if (presetIdx == 0) {
        // Preset 0: Starfield 3D Warp
        static struct Star3D { float x, y, z; } stars[36];
        static bool initialized = false;
        if (!initialized) {
            for (int i = 0; i < 36; i++) {
                stars[i].x = (float)((eqRand(i * 17 + 1) % 160) - 80);
                stars[i].y = (float)((eqRand(i * 31 + 3) % 100) - 50);
                stars[i].z = (float)((eqRand(i * 47 + 5) % 100) + 1);
            }
            initialized = true;
        }

        for (int i = 0; i < 36; i++) {
            stars[i].z -= 2.5f;
            if (stars[i].z <= 1.0f) {
                stars[i].x = (float)((eqRand((uint32_t)(ms + i * 13)) % 160) - 80);
                stars[i].y = (float)((eqRand((uint32_t)(ms + i * 29)) % 100) - 50);
                stars[i].z = 100.0f;
            }

            float k = 40.0f / stars[i].z;
            int px = (int)(cx + stars[i].x * k);
            int py = (int)(cy + stars[i].y * k);

            if (px >= 0 && px < SCREEN_WIDTH && py >= 16 && py < SCREEN_HEIGHT) {
                display.drawPixel(px, py, SSD1306_WHITE);
                if (stars[i].z < 30.0f) {
                    int prevPx = (int)(cx + stars[i].x * (40.0f / (stars[i].z + 4.0f)));
                    int prevPy = (int)(cy + stars[i].y * (40.0f / (stars[i].z + 4.0f)));
                    display.drawLine(px, py, prevPx, prevPy, SSD1306_WHITE);
                }
            }
        }
    } else if (presetIdx == 1) {
        // Preset 1: 3D Rotating Wireframe Cube
        float angleX = ms * 0.0015f;
        float angleY = ms * 0.0022f;
        float angleZ = ms * 0.0009f;

        float vertices[8][3] = {
            {-15, -15, -15}, { 15, -15, -15}, { 15,  15, -15}, {-15,  15, -15},
            {-15, -15,  15}, { 15, -15,  15}, { 15,  15,  15}, {-15,  15,  15}
        };

        int edges[12][2] = {
            {0,1}, {1,2}, {2,3}, {3,0},
            {4,5}, {5,6}, {6,7}, {7,4},
            {0,4}, {1,5}, {2,6}, {3,7}
        };

        int projX[8];
        int projY[8];

        for (int i = 0; i < 8; i++) {
            float x = vertices[i][0];
            float y = vertices[i][1];
            float z = vertices[i][2];

            float y1 = y * cos(angleX) - z * sin(angleX);
            float z1 = y * sin(angleX) + z * cos(angleX);

            float x2 = x * cos(angleY) + z1 * sin(angleY);
            float z2 = -x * sin(angleY) + z1 * cos(angleY);

            float x3 = x2 * cos(angleZ) - y1 * sin(angleZ);
            float y3 = x2 * sin(angleZ) + y1 * cos(angleZ);

            float distance = 60.0f;
            float fov = 40.0f;
            float scale = fov / (distance + z2);

            projX[i] = (int)(cx + x3 * scale);
            projY[i] = (int)(cy + y3 * scale);
        }

        for (int e = 0; e < 12; e++) {
            int v1 = edges[e][0];
            int v2 = edges[e][1];
            display.drawLine(projX[v1], projY[v1], projX[v2], projY[v2], SSD1306_WHITE);
        }
    } else if (presetIdx == 2) {
        // Preset 2: Retro Synthwave 3D Grid & Sun
        display.drawCircle(cx, 26, 8, SSD1306_WHITE);
        display.drawFastHLine(cx - 10, 26, 20, SSD1306_BLACK);
        display.drawFastHLine(0, 32, SCREEN_WIDTH, SSD1306_WHITE);

        for (int x = -100; x <= 228; x += 16) {
            display.drawLine(64, 32, x, 63, SSD1306_WHITE);
        }

        int scrollOffset = (int)(ms / 30) % 8;
        for (int y = 33 + scrollOffset; y < 64; y += (y - 30) / 3 + 1) {
            display.drawFastHLine(0, y, SCREEN_WIDTH, SSD1306_WHITE);
        }
    } else {
        // Preset 3: Bad Apple / Dancing Vector Sprite
        int frame = (int)(ms / 100) % 8;
        int poseY = (int)(fastSin(ms * 12 / 10) * 3) / 255;

        display.drawCircle(cx, 24 + poseY, 5, SSD1306_WHITE);
        display.drawLine(cx, 29 + poseY, cx, 43 + poseY, SSD1306_WHITE);
        int armAngle = (int)(fastSin(ms * 15 / 10) * 12) / 255;
        display.drawLine(cx, 33 + poseY, cx - 12, 30 + armAngle + poseY, SSD1306_WHITE);
        display.drawLine(cx, 33 + poseY, cx + 12, 30 - armAngle + poseY, SSD1306_WHITE);
        int legStep = (frame % 2 == 0) ? 6 : -4;
        display.drawLine(cx, 43 + poseY, cx - 8 + legStep, 58, SSD1306_WHITE);
        display.drawLine(cx, 43 + poseY, cx + 8 - legStep, 58, SSD1306_WHITE);

        printCentered("BAD APPLE ANIMATION", 56, 1);
    }
}

void drawArcadeGame() {
    drawMarqueeLine(0, 0, "ARCADE ", customScreen.line1);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    unsigned long ms = millis();
    int gameIdx = 0;
    int comma = customScreen.eqBars.indexOf(',');
    if (comma > 0) gameIdx = customScreen.eqBars.substring(0, comma).toInt();

    if (gameIdx == 0) {
        // Flappy Bird OLED
        int birdY = 36 + (int)(fastSin(ms * 8 / 10) * 8) / 255;
        display.fillRect(24, birdY, 8, 6, SSD1306_WHITE); // Bird body
        display.drawPixel(30, birdY + 1, SSD1306_BLACK);  // Eye
        display.drawFastHLine(32, birdY + 3, 3, SSD1306_WHITE); // Beak

        // Pipes
        int pipeX1 = (128 - ((int)(ms / 25) % 150));
        if (pipeX1 >= -12 && pipeX1 < 128) {
            display.drawRect(pipeX1, 15, 12, 12, SSD1306_WHITE);
            display.drawRect(pipeX1, 42, 12, 22, SSD1306_WHITE);
        }
        printCentered("SCORE: 42", 56, 1);
    } else if (gameIdx == 1) {
        // Snake Game
        int t = (int)(ms / 150);
        int headX = 40 + (t % 10) * 4;
        int headY = 32;
        for (int i = 0; i < 6; i++) {
            display.fillRect(headX - i * 4, headY, 3, 3, SSD1306_WHITE);
        }
        display.fillRect(84, 32, 4, 4, SSD1306_WHITE); // Food
        printCentered("SNAKE SCORE: 120", 56, 1);
    } else {
        // Pong
        int ballX = 30 + (int)(fastSin(ms * 10 / 10) * 30) / 255;
        int ballY = 36 + (int)(fastSin(ms * 14 / 10) * 12) / 255;
        display.fillRect(8, 28 + (int)(fastSin(ms * 10 / 10) * 10) / 255, 3, 16, SSD1306_WHITE);
        display.fillRect(117, 28 - (int)(fastSin(ms * 10 / 10) * 10) / 255, 3, 16, SSD1306_WHITE);
        display.fillRect(ballX + 30, ballY, 3, 3, SSD1306_WHITE);
        printCentered("PONG 03 : 02", 56, 1);
    }
}

void drawNewsFeed() {
    drawMarqueeLine(0, 0, "NEWS ", customScreen.hdrTitle);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    String headline = customScreen.line1;
    if (headline.length() == 0) headline = customScreen.line2;

    int y = 20;
    if (headline.length() > 0) {
        // Multi-line wrapped text rendering for RSS headline
        int maxCharsPerLine = 21;
        for (int i = 0; i < (int)headline.length() && y < 54; i += maxCharsPerLine) {
            String chunk = headline.substring(i, min(i + maxCharsPerLine, (int)headline.length()));
            display.setCursor(0, y);
            display.print(chunk);
            y += 10;
        }
    }
    display.drawFastHLine(0, 55, SCREEN_WIDTH, SSD1306_WHITE);
    display.setCursor(0, 56);
    display.print(customScreen.line3);
}

void drawMatrixRain() {
    drawMarqueeLine(0, 0, "MATRIX ", customScreen.hdrTitle);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    unsigned long ms = millis();
    // 16 columns of falling characters
    for (int col = 0; col < 16; col++) {
        int x = col * 8;
        int speed = (col % 3 + 1) * 2;
        int headY = 15 + ((int)(ms / 20 * speed + col * 17) % 55);

        for (int trail = 0; trail < 4; trail++) {
            int y = headY - trail * 7;
            if (y >= 16 && y < 64) {
                char ch = (char)(33 + ((col * 13 + trail * 7 + (int)(ms / 100)) % 90));
                display.setCursor(x, y);
                display.print(ch);
            }
        }
    }
}

void drawCuteEyes() {
    drawMarqueeLine(0, 0, "EYES ", customScreen.hdrTitle);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    unsigned long ms = millis();
    int moodIdx = 0;
    bool isBlinking = false;

    int comma = customScreen.eqBars.indexOf(',');
    if (comma > 0) {
        moodIdx = customScreen.eqBars.substring(0, comma).toInt();
        isBlinking = (customScreen.eqBars.substring(comma + 1).toInt() == 1);
    }

    // Eye dimensions & positions
    int eyeW = 32;
    int eyeH = 26;
    int leftX = 20;
    int rightX = 76;
    int eyeY = 24;

    // Pupil shift offsets based on mood
    int offsetX = 0;
    int offsetY = 0;

    if (moodIdx == 2) offsetX = -6; // Look Left
    else if (moodIdx == 3) offsetX = 6; // Look Right

    // Periodic Blink
    if (isBlinking || ((ms / 3500) % 7 == 0 && (ms % 3500) < 150)) {
        // Blinking line
        display.drawFastHLine(leftX, eyeY + 13, eyeW, SSD1306_WHITE);
        display.drawFastHLine(rightX, eyeY + 13, eyeW, SSD1306_WHITE);
        return;
    }

    if (moodIdx == 1) {
        // Happy Eyes (Inverted Arc / Cheerful ^ ^)
        display.drawRoundRect(leftX, eyeY, eyeW, eyeH, 8, SSD1306_WHITE);
        display.drawRoundRect(rightX, eyeY, eyeW, eyeH, 8, SSD1306_WHITE);
        display.fillTriangle(leftX, eyeY + 14, leftX + eyeW, eyeY + 14, leftX + eyeW/2, eyeY + eyeH, SSD1306_BLACK);
        display.fillTriangle(rightX, eyeY + 14, rightX + eyeW, eyeY + 14, rightX + eyeW/2, eyeY + eyeH, SSD1306_BLACK);
    } else if (moodIdx == 4) {
        // Sleepy / Drowsy Eyes (- -)
        display.drawRoundRect(leftX, eyeY + 8, eyeW, 12, 4, SSD1306_WHITE);
        display.drawRoundRect(rightX, eyeY + 8, eyeW, 12, 4, SSD1306_WHITE);
        display.fillRect(leftX + 8, eyeY + 12, 16, 4, SSD1306_WHITE);
        display.fillRect(rightX + 8, eyeY + 12, 16, 4, SSD1306_WHITE);
    } else if (moodIdx == 5) {
        // Wink Eye (Left open, Right winking line)
        display.fillRoundRect(leftX, eyeY, eyeW, eyeH, 8, SSD1306_WHITE);
        display.fillCircle(leftX + 16 + offsetX, eyeY + 13 + offsetY, 6, SSD1306_BLACK);
        display.fillCircle(leftX + 20, eyeY + 9, 3, SSD1306_WHITE); // Glint
        display.drawFastHLine(rightX, eyeY + 13, eyeW, SSD1306_WHITE);
    } else {
        // Normal Expressive Eyes
        display.fillRoundRect(leftX, eyeY, eyeW, eyeH, 8, SSD1306_WHITE);
        display.fillRoundRect(rightX, eyeY, eyeW, eyeH, 8, SSD1306_WHITE);

        // Pupils
        display.fillCircle(leftX + 16 + offsetX, eyeY + 13 + offsetY, 6, SSD1306_BLACK);
        display.fillCircle(rightX + 16 + offsetX, eyeY + 13 + offsetY, 6, SSD1306_BLACK);

        // Pupil Glint Dots (Cute highlights)
        display.fillCircle(leftX + 20 + offsetX, eyeY + 9 + offsetY, 3, SSD1306_WHITE);
        display.fillCircle(rightX + 20 + offsetX, eyeY + 9 + offsetY, 3, SSD1306_WHITE);
    }
}

void drawOrbitSimulation() {
    drawMarqueeLine(0, 0, "ORBIT ", customScreen.hdrTitle);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    unsigned long ms = millis();
    int sunX = 50;
    int sunY = 39;

    // Central Sun
    display.fillCircle(sunX, sunY, 6, SSD1306_WHITE);

    // Orbit 1 (Mercury)
    display.drawCircle(sunX, sunY, 12, SSD1306_WHITE);
    int p1X = sunX + (int)(fastSin(ms * 8 / 10) * 12) / 255;
    int p1Y = sunY + (int)(cos(ms * 0.008f) * 12);
    display.fillCircle(p1X, p1Y, 2, SSD1306_WHITE);

    // Orbit 2 (Earth & Moon)
    display.drawCircle(sunX, sunY, 22, SSD1306_WHITE);
    int eX = sunX + (int)(fastSin(ms * 4 / 10) * 22) / 255;
    int eY = sunY + (int)(cos(ms * 0.004f) * 22);
    display.fillCircle(eX, eY, 3, SSD1306_WHITE);

    // Moon orbiting Earth
    int mX = eX + (int)(fastSin(ms * 15 / 10) * 6) / 255;
    int mY = eY + (int)(cos(ms * 0.015f) * 6);
    display.drawPixel(mX, mY, SSD1306_WHITE);

    // Moon Phase Display Graphic at top right
    int phaseIdx = 0;
    int comma = customScreen.eqBars.indexOf(',');
    if (comma > 0) phaseIdx = customScreen.eqBars.substring(0, comma).toInt();

    display.drawCircle(108, 38, 10, SSD1306_WHITE);
    if (phaseIdx == 0) display.fillCircle(108, 38, 9, SSD1306_BLACK); // New Moon
    else if (phaseIdx == 4) display.fillCircle(108, 38, 9, SSD1306_WHITE); // Full Moon
    else display.fillRect(108, 29, 9, 18, SSD1306_WHITE); // Half/Crescent
}

void drawNcsCircleVisualizer() {
    // 1. Top Yellow Strip (Y=0..15): Song Title & Artist Marquee Header
    String info = customScreen.line2;
    if (customScreen.line3.length() > 0 && customScreen.line3 != info) {
        info += " - " + customScreen.line3;
    }
    drawMarqueeLine(0, 0, "NCS ", info);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    // 2. Parse FFT Data (20 Bands)
    int realVals[20] = {0};
    bool hasRealData = (customScreen.eqBars.indexOf(',') >= 0);

    if (hasRealData) {
        int idx = 0, lastPos = 0;
        String str = customScreen.eqBars;
        for (int i = 0; i <= (int)str.length() && idx < 20; i++) {
            if (i == (int)str.length() || str.charAt(i) == ',') {
                realVals[idx] = str.substring(lastPos, i).toInt();
                idx++;
                lastPos = i + 1;
            }
        }
    }

    int bassEnergy = 0;
    int midEnergy = 0;
    if (hasRealData) {
        bassEnergy = (realVals[0] + realVals[1] + realVals[2] + realVals[3]) / 4;
        midEnergy = (realVals[4] + realVals[5] + realVals[6] + realVals[7] + realVals[8]) / 5;
    } else if (customScreen.eqBars == "1") {
        bassEnergy = ((millis() / 200) % 2 == 0) ? 7 : 2;
        midEnergy = ((millis() / 150) % 3 == 0) ? 6 : 3;
    }

    int cx = 64;
    int cy = 39;
    unsigned long ms = millis();

    // Base Pulsing Sphere Radius
    int baseRadius = 10 + (bassEnergy * 5 / 10); // 10..15px

    // -------------------------------------------------------------------
    // Layer A: 3D Interlocking Rotating Mesh Rings (Spherical Latitude Grid)
    // -------------------------------------------------------------------
    float rot3D = (ms % 6000) * (2.0f * M_PI / 6000.0f);

    // Tilted Ring 1 (Latitude 45 deg)
    float rx1 = baseRadius * 1.3f;
    float ry1 = baseRadius * 0.5f;
    for (int deg = 0; deg < 360; deg += 20) {
        float rad = deg * (M_PI / 180.0f) + rot3D;
        int px = cx + (int)(cos(rad) * rx1);
        int py = cy + (int)(sin(rad) * ry1);
        if (px >= 0 && px < SCREEN_WIDTH && py >= 16 && py < SCREEN_HEIGHT) {
            display.drawPixel(px, py, SSD1306_WHITE);
        }
    }

    // Tilted Ring 2 (Latitude -45 deg)
    float rx2 = baseRadius * 0.6f;
    float ry2 = baseRadius * 1.2f;
    for (int deg = 0; deg < 360; deg += 20) {
        float rad = deg * (M_PI / 180.0f) - rot3D * 1.3f;
        int px = cx + (int)(cos(rad) * rx2);
        int py = cy + (int)(sin(rad) * ry2);
        if (px >= 0 && px < SCREEN_WIDTH && py >= 16 && py < SCREEN_HEIGHT) {
            display.drawPixel(px, py, SSD1306_WHITE);
        }
    }

    // Inner Pulsing Core
    display.drawCircle(cx, cy, baseRadius, SSD1306_WHITE);
    display.drawCircle(cx, cy, max(2, baseRadius - 4), SSD1306_WHITE);
    display.fillCircle(cx, cy, max(1, baseRadius - 7), SSD1306_WHITE);

    // -------------------------------------------------------------------
    // Layer B: 36-Point Organic Audio Wave Perimeter (Continuous Outer Wave Aura)
    // -------------------------------------------------------------------
    int numPoints = 36;
    float step = (2.0f * M_PI) / numPoints;
    float rotWave = (ms % 8000) * (2.0f * M_PI / 8000.0f);

    int prevWX = 0, prevWY = 0;
    int firstWX = 0, firstWY = 0;

    for (int i = 0; i < numPoints; i++) {
        float angle = i * step + rotWave;
        float cosA = cos(angle);
        float sinA = sin(angle);

        int bandIdx = (i % 20);
        int val = 0;
        if (hasRealData) {
            val = realVals[bandIdx];
        } else if (bassEnergy > 0) {
            int t = (int)(ms / 40);
            val = (fastSin(t * 7 + i * 37) * 5 / 255) + 3;
        }

        // Spike / Wave Amplitude
        int spikeLen = (val * 13 / 10);
        if (spikeLen < 1) spikeLen = 1;

        // Radial ray line outwards
        int x1 = cx + (int)(cosA * baseRadius);
        int y1 = cy + (int)(sinA * baseRadius);
        int x2 = cx + (int)(cosA * (baseRadius + spikeLen));
        int y2 = cy + (int)(sinA * (baseRadius + spikeLen));

        if (x1 >= 0 && x1 < SCREEN_WIDTH && y1 >= 16 && y1 < SCREEN_HEIGHT &&
            x2 >= 0 && x2 < SCREEN_WIDTH && y2 >= 16 && y2 < SCREEN_HEIGHT) {
            display.drawLine(x1, y1, x2, y2, SSD1306_WHITE);
        }

        // Outer Continuous Organic Wave Perimeter Line
        if (i == 0) {
            firstWX = x2;
            firstWY = y2;
        } else {
            if (prevWX >= 0 && prevWX < SCREEN_WIDTH && prevWY >= 16 && prevWY < SCREEN_HEIGHT &&
                x2 >= 0 && x2 < SCREEN_WIDTH && y2 >= 16 && y2 < SCREEN_HEIGHT) {
                display.drawLine(prevWX, prevWY, x2, y2, SSD1306_WHITE);
            }
        }
        prevWX = x2;
        prevWY = y2;

        // Floating Outer Sparks / Particle Cloud
        if (val > 4) {
            int sparkR = baseRadius + spikeLen + 3 + (val % 3);
            int sparkX = cx + (int)(cosA * sparkR);
            int sparkY = cy + (int)(sinA * sparkR);
            if (sparkX >= 0 && sparkX < SCREEN_WIDTH && sparkY >= 16 && sparkY < SCREEN_HEIGHT) {
                display.drawPixel(sparkX, sparkY, SSD1306_WHITE);
            }
        }
    }

    // Connect final point back to first point to close outer wave loop
    if (prevWX >= 0 && prevWX < SCREEN_WIDTH && prevWY >= 16 && prevWY < SCREEN_HEIGHT &&
        firstWX >= 0 && firstWX < SCREEN_WIDTH && firstWY >= 16 && firstWY < SCREEN_HEIGHT) {
        display.drawLine(prevWX, prevWY, firstWX, firstWY, SSD1306_WHITE);
    }

    // -------------------------------------------------------------------
    // Layer C: Left & Right Side Hype Mini Equalizer Bars
    // -------------------------------------------------------------------
    // Left Side 5 Mini Frequency Equalizer Bars (X=2..18)
    int leftBands[5] = {realVals[0], realVals[1], realVals[2], realVals[3], realVals[4]};
    if (!hasRealData && bassEnergy > 0) {
        for (int b = 0; b < 5; b++) leftBands[b] = (fastSin((int)(ms / 30) * 8 + b * 50) * 4 / 255) + 3;
    }

    for (int b = 0; b < 5; b++) {
        int barX = 2 + b * 4;
        int barVal = leftBands[b];
        int barH = barVal * 28 / 10; // Max 28px height
        if (barH > 0) {
            display.fillRect(barX, 62 - barH, 3, barH, SSD1306_WHITE);
            if (barVal > 3) {
                display.drawPixel(barX + 1, 62 - barH - 2, SSD1306_WHITE);
            }
        }
    }

    // Right Side 5 Mini Frequency Equalizer Bars (X=106..122)
    int rightBands[5] = {realVals[15], realVals[16], realVals[17], realVals[18], realVals[19]};
    if (!hasRealData && bassEnergy > 0) {
        for (int b = 0; b < 5; b++) rightBands[b] = (fastSin((int)(ms / 30) * 8 + (b + 5) * 50) * 4 / 255) + 3;
    }

    for (int b = 0; b < 5; b++) {
        int barX = 106 + b * 4;
        int barVal = rightBands[b];
        int barH = barVal * 28 / 10; // Max 28px height
        if (barH > 0) {
            display.fillRect(barX, 62 - barH, 3, barH, SSD1306_WHITE);
            if (barVal > 3) {
                display.drawPixel(barX + 1, 62 - barH - 2, SSD1306_WHITE);
            }
        }
    }

    // -------------------------------------------------------------------
    // Layer D: Dynamic HYPE Bass Energy Shockwaves & Corner Lightning Flash Rays
    // -------------------------------------------------------------------
    if (bassEnergy >= 4) {
        // High Bass / Hype Condition Trigger!
        int waveR = 8 + ((ms / 40) % 24); // Expanding shockwave arc radius (8..31px)

        // Left & Right Speaker Shockwave Arcs
        display.drawCircle(0, 39, waveR, SSD1306_WHITE);
        if (waveR > 6) display.drawCircle(0, 39, waveR - 6, SSD1306_WHITE);

        display.drawCircle(127, 39, waveR, SSD1306_WHITE);
        if (waveR > 6) display.drawCircle(127, 39, waveR - 6, SSD1306_WHITE);

        // Extreme Hype Drop: Flash top-left and top-right energetic corner bolts
        if (bassEnergy >= 6) {
            int boltLen = (bassEnergy * 2);
            display.drawLine(0, 16, boltLen, 16 + boltLen, SSD1306_WHITE);
            display.drawLine(127, 16, 127 - boltLen, 16 + boltLen, SSD1306_WHITE);
        }
    }
}

void drawCenterMirrorWaveformVisualizer() {
    // 1. Top Yellow Strip (Y=0..15): Song Title & Artist Marquee Header
    String info = customScreen.line2;
    if (customScreen.line3.length() > 0 && customScreen.line3 != info) {
        info += " - " + customScreen.line3;
    }
    drawMarqueeLine(0, 0, "WAVE ", info);
    display.drawFastHLine(0, 14, SCREEN_WIDTH, SSD1306_WHITE);

    // 2. Parse 20 FFT Bands
    int realVals[20] = {0};
    bool hasRealData = (customScreen.eqBars.indexOf(',') >= 0);

    if (hasRealData) {
        int idx = 0, lastPos = 0;
        String str = customScreen.eqBars;
        for (int i = 0; i <= (int)str.length() && idx < 20; i++) {
            if (i == (int)str.length() || str.charAt(i) == ',') {
                realVals[idx] = str.substring(lastPos, i).toInt();
                idx++;
                lastPos = i + 1;
            }
        }
    }

    int bassEnergy = 0;
    if (hasRealData) {
        bassEnergy = (realVals[0] + realVals[1] + realVals[2] + realVals[3]) / 4;
    } else if (customScreen.eqBars == "1") {
        bassEnergy = ((millis() / 200) % 2 == 0) ? 7 : 2;
    }

    unsigned long ms = millis();
    int cy = 39; // Center Baseline Axis

    // Draw horizontal center baseline axis line
    display.drawFastHLine(0, cy, SCREEN_WIDTH, SSD1306_WHITE);

    // 32 Symmetrical Center-Mirror Spectrum Bars (3px width, 1px gap -> 32 * 4 = 128px)
    static int wavePeaks[32] = {0};
    static unsigned long lastWaveDecay = 0;

    for (int i = 0; i < 32; i++) {
        // Map 32 bars to 20 FFT bands smoothly
        int bandIdx = (i * 20) / 32;
        int val = 0;
        if (hasRealData) {
            val = realVals[bandIdx];
        } else if (bassEnergy > 0) {
            int t = (int)(ms / 40);
            val = (fastSin(t * 8 + i * 35) * 6 / 255) + 3;
        }

        // Half-height of vertical bar expanding upward and downward from center
        int halfH = val * 19 / 10; // Max 19px up and 19px down (Total height 38px)
        if (halfH < 1) halfH = 1;

        // Peak tracking for floating mirror dots
        if (halfH > wavePeaks[i]) {
            wavePeaks[i] = halfH;
        }

        int x = i * 4;
        int barW = 3;
        int topY = cy - halfH;

        // Draw symmetrical vertical bar around center
        display.fillRect(x, topY, barW, (halfH * 2) + 1, SSD1306_WHITE);

        // Draw floating mirror peak dots (Top & Bottom)
        if (wavePeaks[i] > 2) {
            int peakTopY = cy - wavePeaks[i] - 2;
            int peakBotY = cy + wavePeaks[i] + 2;

            if (peakTopY >= 16) display.drawFastHLine(x, peakTopY, barW, SSD1306_WHITE);
            if (peakBotY < 64)  display.drawFastHLine(x, peakBotY, barW, SSD1306_WHITE);
        }
    }

    // Decay peak hold every ~100ms
    if (ms - lastWaveDecay > 100) {
        lastWaveDecay = ms;
        for (int i = 0; i < 32; i++) {
            if (wavePeaks[i] > 0) wavePeaks[i]--;
        }
    }

    // Dynamic Bass Pulse Overlay in Center Line (Hype Energy Waveform)
    if (bassEnergy >= 5) {
        int pulseR = 4 + (bassEnergy * 3 / 10);
        display.fillCircle(64, cy, pulseR, SSD1306_BLACK);
        display.drawCircle(64, cy, pulseR, SSD1306_WHITE);
        display.fillCircle(64, cy, max(1, pulseR - 3), SSD1306_WHITE);
    }
}

void pageCustomScreen() {
    if (customScreen.hdrTitle.startsWith("STAGE")) {
        drawStageKaraoke();
        return;
    }

    if (customScreen.hdrTitle.startsWith("VIDEO")) {
        drawVideoDisplay();
        return;
    }

    if (customScreen.hdrTitle.startsWith("SPECTRUM")) {
        if (customScreen.subPage == 2) {
            drawCenterMirrorWaveformVisualizer();
        } else if (customScreen.subPage == 1) {
            drawNcsCircleVisualizer();
        } else {
            drawSpectrumEqualizer();
        }
        return;
    }

    if (customScreen.hdrTitle.startsWith("ARCADE")) {
        drawArcadeGame();
        return;
    }

    if (customScreen.hdrTitle.startsWith("NEWS")) {
        drawNewsFeed();
        return;
    }

    if (customScreen.hdrTitle.startsWith("MATRIX")) {
        drawMatrixRain();
        return;
    }

    if (customScreen.hdrTitle.startsWith("EYES")) {
        drawCuteEyes();
        return;
    }

    if (customScreen.hdrTitle.startsWith("ORBIT")) {
        drawOrbitSimulation();
        return;
    }

    if (customScreen.subPage == 0 && customScreen.eqBars.length() > 0) {
        drawSpectrumEqualizer();
        return;
    }

    if (customScreen.subPage == 2 && customScreen.maxSubPages > 2) {
        // Halaman 3: Special Animated Altcoin Carousel Ticker (Clean Size 1)
        drawHeader(customScreen.p3HdrTitle.c_str(), "", customScreen.p3HdrSub);

        int y = 22;
        if (customScreen.p3Line1.length() > 0) {
            int bracketFrame = (millis() / 250) % 3;
            String bLeft = (bracketFrame == 0) ? "<  " : ((bracketFrame == 1) ? " < " : "  <");
            String bRight = (bracketFrame == 0) ? "  >" : ((bracketFrame == 1) ? " > " : ">  ");
            String titleWithAnim = bLeft + " " + customScreen.p3Line1 + " " + bRight;
            printCentered(titleWithAnim.c_str(), y, 1);
            y += 12;
        }

        if (customScreen.p3Line2.length() > 0) {
            printCentered(customScreen.p3Line2.c_str(), y, 1);
            y += 12;
        }

        if (customScreen.p3Line3.length() > 0) {
            printCentered(customScreen.p3Line3.c_str(), y, 1);
        }
        return;
    }

    if (customScreen.subPage == 1 && customScreen.maxSubPages > 1) {
        // Halaman 2: Custom SubPage View
        drawHeader(customScreen.p2HdrTitle.c_str(), "", customScreen.p2HdrSub);

        if (customScreen.p2Line1.length() > 0) {
            int y = (customScreen.p2Line5.length() > 0) ? 17 : 18;
            int step = (customScreen.p2Line5.length() > 0) ? 9 : 10;
            display.setCursor(0, y); display.print(customScreen.p2Line1); y += step;
            if (customScreen.p2Line2.length() > 0) { display.setCursor(0, y); display.print(customScreen.p2Line2); y += step; }
            if (customScreen.p2Line3.length() > 0) { display.setCursor(0, y); display.print(customScreen.p2Line3); y += step; }
            if (customScreen.p2Line4.length() > 0) { display.setCursor(0, y); display.print(customScreen.p2Line4); y += step; }
            if (customScreen.p2Line5.length() > 0) { display.setCursor(0, y); display.print(customScreen.p2Line5); }
        } else if (customScreen.p2Line2.length() > 0) {
            int y = 19;
            drawWrappedLyric(customScreen.p2Line2, y, 5);
        }
        return;
    }

    // Halaman 1: Default Custom View (Player / Dashboard)
    drawHeader(customScreen.hdrTitle.c_str(), "", customScreen.hdrSub);

    if (customScreen.bigText.length() > 0) {
        printCentered(customScreen.bigText.c_str(), 22, 2);

        if (customScreen.line2.length() > 0) {
            printCentered(customScreen.line2.c_str(), 40);
        }
        if (customScreen.line3.length() > 0) {
            printCentered(customScreen.line3.c_str(), 52);
        }
    } else if (customScreen.bar1 < 0 && customScreen.bar2 < 0 && customScreen.line5.length() > 0) {
        // Tampilan 5 baris presisi tanpa progress bar (Halaman 1 Crypto)
        int y = 17;
        int step = 9;
        display.setCursor(0, y); display.print(customScreen.line1); y += step;
        if (customScreen.line2.length() > 0) { display.setCursor(0, y); display.print(customScreen.line2); y += step; }
        if (customScreen.line3.length() > 0) { display.setCursor(0, y); display.print(customScreen.line3); y += step; }
        if (customScreen.line4.length() > 0) { display.setCursor(0, y); display.print(customScreen.line4); y += step; }
        if (customScreen.line5.length() > 0) { display.setCursor(0, y); display.print(customScreen.line5); }
    } else {
        int y = 20;
        if (customScreen.line1.length() > 0) {
            int colon = customScreen.line1.indexOf(':');
            if (colon > 0) {
                String prefix = customScreen.line1.substring(0, colon + 1) + " ";
                String val = customScreen.line1.substring(colon + 1);
                val.trim();
                drawMarqueeLine(0, y, prefix, val);
            } else {
                drawMarqueeLine(0, y, "", customScreen.line1);
            }
            y += 10;
        }
        if (customScreen.bar1 >= 0) {
            drawBar(0, y, SCREEN_WIDTH, 6, customScreen.bar1);
            y += 9;
        }

        if (customScreen.line2.length() > 0) {
            int colon = customScreen.line2.indexOf(':');
            if (colon > 0) {
                String prefix = customScreen.line2.substring(0, colon + 1) + " ";
                String val = customScreen.line2.substring(colon + 1);
                val.trim();
                drawMarqueeLine(0, y, prefix, val);
            } else {
                drawMarqueeLine(0, y, "", customScreen.line2);
            }
            y += 10;
        }
        if (customScreen.bar2 >= 0) {
            drawBar(0, y, SCREEN_WIDTH, 6, customScreen.bar2);
            y += 9;
        }

        if (customScreen.line3.length() > 0) {
            display.setCursor(0, y);
            display.print(customScreen.line3);
            y += 10;
        }
        if (customScreen.line4.length() > 0) {
            display.setCursor(0, y);
            display.print(customScreen.line4);
            y += 10;
        }
        if (customScreen.line5.length() > 0) {
            display.setCursor(0, y);
            display.print(customScreen.line5);
        }
    }
}

void render() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

#if YELLOW_ONLY
    if (!dataReceived) {
        pageWaitingCompact();
    } else {
        switch (currentPage) {
            case 0:  pageContextCompact(); break;
            case 1:  pageLimitsCompact();  break;
            default: pageTokensCompact();  break;
        }
    }
#else
    if (!dataReceived) {
        pageWaiting();
    } else if (customScreen.active) {
        pageCustomScreen();
    } else {
        switch (currentPage) {
            case 0:  pageContext(); break;
            case 1:  pageLimits();  break;
            case 2:  pageTokens();  break;
            default: pageModels();  break;
        }
    }
#endif

    display.display();
}

// ============================================
//  Parsing serial
// ============================================
void applyField(const String &key, const String &value) {
    if (fieldsInBlock == 0) {
        incomingCustomScreen = CustomScreen();
        incomingCustomScreen.subPage = customScreen.subPage;
        incomingCustomScreen.active = customScreen.active;
    }

    if (key == "MODE") {
        if (value == "token" || value == "claude-code" || value == "antigravity") {
            incomingCustomScreen.active = false;
        } else {
            incomingCustomScreen.active = true;
        }
    } else if (key == "HDR") {
        incomingCustomScreen.active = true;
        int p = value.indexOf('|');
        if (p >= 0) {
            incomingCustomScreen.hdrTitle = value.substring(0, p);
            incomingCustomScreen.hdrSub = value.substring(p + 1);
        } else {
            incomingCustomScreen.hdrTitle = value;
            incomingCustomScreen.hdrSub = "";
        }
    } else if (key == "L1") {
        incomingCustomScreen.line1 = value;
        incomingCustomScreen.active = true;
    } else if (key == "BAR1") {
        incomingCustomScreen.bar1 = value.toInt();
    } else if (key == "L2") {
        incomingCustomScreen.line2 = value;
    } else if (key == "BAR2") {
        incomingCustomScreen.bar2 = value.toInt();
    } else if (key == "L3") {
        incomingCustomScreen.line3 = value;
    } else if (key == "L4") {
        incomingCustomScreen.line4 = value;
    } else if (key == "L5") {
        incomingCustomScreen.line5 = value;
    } else if (key == "BIG") {
        incomingCustomScreen.bigText = value;
        incomingCustomScreen.active = true;
    } else if (key == "EQ") {
        incomingCustomScreen.eqBars = value;
        incomingCustomScreen.active = true;
    } else if (key == "P2_HDR") {
        incomingCustomScreen.maxSubPages = max(incomingCustomScreen.maxSubPages, 2);
        int p = value.indexOf('|');
        if (p >= 0) {
            incomingCustomScreen.p2HdrTitle = value.substring(0, p);
            incomingCustomScreen.p2HdrSub = value.substring(p + 1);
        } else {
            incomingCustomScreen.p2HdrTitle = value;
            incomingCustomScreen.p2HdrSub = "";
        }
    } else if (key == "P2_L1") {
        incomingCustomScreen.p2Line1 = value;
        incomingCustomScreen.maxSubPages = max(incomingCustomScreen.maxSubPages, 2);
    } else if (key == "P2_L2") {
        incomingCustomScreen.p2Line2 = value;
    } else if (key == "P2_L3") {
        incomingCustomScreen.p2Line3 = value;
    } else if (key == "P2_L4") {
        incomingCustomScreen.p2Line4 = value;
    } else if (key == "P2_L5") {
        incomingCustomScreen.p2Line5 = value;
    } else if (key == "P3_HDR") {
        incomingCustomScreen.maxSubPages = max(incomingCustomScreen.maxSubPages, 3);
        int p = value.indexOf('|');
        if (p >= 0) {
            incomingCustomScreen.p3HdrTitle = value.substring(0, p);
            incomingCustomScreen.p3HdrSub = value.substring(p + 1);
        } else {
            incomingCustomScreen.p3HdrTitle = value;
            incomingCustomScreen.p3HdrSub = "";
        }
    } else if (key == "P3_L1") {
        incomingCustomScreen.p3Line1 = value;
        incomingCustomScreen.maxSubPages = max(incomingCustomScreen.maxSubPages, 3);
    } else if (key == "P3_L2") {
        incomingCustomScreen.p3Line2 = value;
    } else if (key == "P3_L3") {
        incomingCustomScreen.p3Line3 = value;
    } else if (key == "P3_L4") {
        incomingCustomScreen.p3Line4 = value;
    } else if (key == "P3_L5") {
        incomingCustomScreen.p3Line5 = value;
    } else if (key == "PLAN") {
        stats.plan = value;
    } else if (key == "MODEL") {
        stats.model = value;
    } else if (key == "EFFORT") {
        stats.effort = value;
    } else if (key == "COST") {
        stats.cost = value;
    } else if (key == "REQ") {
        stats.requests = value;
    } else if (key == "PROJ") {
        stats.project = value;
    } else if (key == "CRED") {
        stats.credit = value;
    } else if (key.startsWith("MDL")) {
        int slot = key.substring(3).toInt() - 1;
        if (slot >= 0 && slot < 3) {
            int c1 = value.indexOf(',');
            int c2 = value.lastIndexOf(',');
            if (c1 > 0 && c2 > c1) {
                stats.models[slot].name = value.substring(0, c1);
                stats.models[slot].cost = value.substring(c1 + 1, c2);
                stats.models[slot].pct  = value.substring(c2 + 1).toInt();
            }
        }
    } else if (key == "CTX") {
        int comma = value.lastIndexOf(',');
        if (comma > 0) {
            stats.ctxLabel = value.substring(0, comma);
            stats.ctxPct   = value.substring(comma + 1).toInt();
        }
    } else if (key == "L5H" || key == "LWK") {
        int comma = value.indexOf(',');
        if (comma > 0) {
            int pct = value.substring(0, comma).toInt();
            String reset = value.substring(comma + 1);
            if (key == "L5H") { stats.l5hPct = pct; stats.l5hReset = reset; }
            else              { stats.lwkPct = pct; stats.lwkReset = reset; }
        }
    } else if (key == "TOK") {
        int comma = value.indexOf(',');
        if (comma > 0) {
            stats.tokIn  = value.substring(0, comma);
            stats.tokOut = value.substring(comma + 1);
        }
    } else if (key == "PAGE") {
        int p = value.toInt();
        if (p >= 1 && p <= PAGE_COUNT) {
            currentPage = p - 1;
            lastPageChange = millis();
        }
    }
}

// Format lama: "in,out,cost"
void applyLegacyCsv(const String &line) {
    int c1 = line.indexOf(',');
    int c2 = line.indexOf(',', c1 + 1);
    if (c1 == -1 || c2 == -1) return;
    stats.tokIn  = line.substring(0, c1);
    stats.tokOut = line.substring(c1 + 1, c2);
    stats.cost   = "$" + line.substring(c2 + 1);
    dataReceived = true;
}

void handleLine(String line) {
    line.trim();
    if (line.length() == 0) return;

    if (line == "END") {
        if (fieldsInBlock > 0) {
            dataReceived = true;
            if (incomingCustomScreen.subPage >= incomingCustomScreen.maxSubPages) {
                incomingCustomScreen.subPage = 0;
            }
            customScreen = incomingCustomScreen;
        } else {
            // 'END' tanpa field: jangan tandai ada data, nanti layar isinya 0.
            Serial.println(F("[WARN] END tanpa field, diabaikan"));
        }
        fieldsInBlock = 0;
        render();
        return;
    }

    int colon = line.indexOf(':');
    if (colon > 0) {
        String key = line.substring(0, colon);
        applyField(key, line.substring(colon + 1));
        // PAGE cuma navigasi, bukan data.
        if (key != "PAGE") fieldsInBlock++;
    } else if (line.indexOf(',') > 0) {
        applyLegacyCsv(line);
        render();
        Serial.println(F("[OK] Data diterima (format lama)"));
    } else {
        Serial.print(F("[ERR] Baris tidak dikenal: "));
        Serial.println(line);
    }
}

// ============================================
//  Tombol
// ============================================
/**
 * Deteksi tombol pakai INTERRUPT, bukan polling.
 *
 * Alasannya: render() menulis 1KB ke OLED lewat I2C dan memblokir loop
 * puluhan milidetik. Dengan polling, klik cepat yang jatuh tepat di jendela
 * itu hilang total -- tombol terasa "kadang tidak respons".
 * Interrupt menangkap tepi turun kapan pun terjadi, termasuk saat loop sibuk.
 */
struct ButtonState {
    int8_t                 pin;
    volatile bool          pressed;      // di-set ISR saat tombol ditekan
    volatile unsigned long pressedAt;
    volatile unsigned long lastEventAt;  // untuk menolak bouncing
    bool                   longFired;
};

#if ENABLE_BUTTONS
ButtonState buttons[] = {
#if BUTTON_PIN >= 0
    { BUTTON_PIN,     false, 0, 0, false },
#endif
#if BUTTON_EXT_PIN >= 0
    { BUTTON_EXT_PIN, false, 0, 0, false },
#endif
};
const uint8_t BUTTON_COUNT = sizeof(buttons) / sizeof(buttons[0]);
#else
const uint8_t BUTTON_COUNT = 0;
#endif

void IRAM_ATTR onButtonPress(void *arg) {
    ButtonState *b = (ButtonState *)arg;
    unsigned long now = millis();
    if (!b->pressed && (now - b->lastEventAt) > BUTTON_DEBOUNCE) {
        b->pressed = true;
        b->pressedAt = now;
    }
}

void nextPage() {
    if (customScreen.active) {
        if (customScreen.maxSubPages > 1) {
            customScreen.subPage = (customScreen.subPage + 1) % customScreen.maxSubPages;
            Serial.print(F("[INFO] SubHalaman -> "));
            Serial.print(customScreen.subPage + 1);
            Serial.print(F("/"));
            Serial.println(customScreen.maxSubPages);
            render();
        }
        return;
    }
    currentPage = (currentPage + 1) % PAGE_COUNT;
    lastPageChange = millis();
    Serial.print(F("[INFO] Halaman -> "));
    Serial.print(currentPage + 1);
    Serial.print(F("/"));
    Serial.println(PAGE_COUNT);
    render();
}

void toggleAutoCycle() {
    autoCycle = !autoCycle;
    lastPageChange = millis();
    Serial.print(F("[INFO] Auto-cycle: "));
    Serial.println(autoCycle ? F("ON") : F("OFF"));
    render();
}

void handleButtons() {
    if (BUTTON_COUNT == 0) return;
    static unsigned long lastReleaseAt = 0;
    static int clickCount = 0;
    static bool pendingClick = false;

    // Timeout 300ms untuk membedakan single-click dan double-click
    if (pendingClick && (millis() - lastReleaseAt > 300)) {
        pendingClick = false;
        clickCount = 0;
        Serial.println(F("EVT:BTN_SHORT"));
        nextPage();
    }

    for (uint8_t i = 0; i < BUTTON_COUNT; i++) {
        ButtonState &b = buttons[i];
        if (b.pin < 0 || !b.pressed) continue;

        unsigned long held = millis() - b.pressedAt;

        if (digitalRead(b.pin) == LOW) {
            if (!b.longFired && held > BUTTON_LONG_MS) {
                b.longFired = true;
                pendingClick = false;
                clickCount = 0;
                Serial.println(F("EVT:BTN_HOLD"));
                toggleAutoCycle();
            }
        } else {
            if (!b.longFired) {
                clickCount++;
                lastReleaseAt = millis();
                if (clickCount == 1) {
                    pendingClick = true;
                } else if (clickCount >= 2) {
                    pendingClick = false;
                    clickCount = 0;
                    Serial.println(F("EVT:BTN_DOUBLE"));
                    nextPage();
                }
            }
            b.lastEventAt = millis();
            b.longFired = false;
            b.pressed = false;
        }
    }
}

// ============================================
//  Splash Screen
// ============================================
void showSplashScreen() {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

#if YELLOW_ONLY
    // Splash ikut ditahan di area kuning.
    printCentered(PROFILE_NAME, 0);
    for (int i = 0; i <= 80; i += 2) {
        display.fillRect(24, 10, i, 5, SSD1306_WHITE);
        display.display();
        delay(SPLASH_DURATION / 40);
    }
    return;
#endif

    // Nama profil di strip kuning, sisanya di area biru.
    printCentered(PROFILE_NAME, 0);
    printCentered(PROFILE_SUBTITLE, 8);
    display.drawFastHLine(0, YELLOW_ROWS, SCREEN_WIDTH, SSD1306_WHITE);

    printCentered(PROFILE_VER, 26);
    display.drawRect(23, 44, 82, 8, SSD1306_WHITE);
    display.display();

    for (int i = 0; i <= 80; i += 2) {
        display.fillRect(24, 45, i, 6, SSD1306_WHITE);
        display.display();
        delay(SPLASH_DURATION / 40);
    }
}

// ============================================
//  Setup & Loop
// ============================================
void setup() {
    Serial.begin(SERIAL_BAUD);
    // Default readStringUntil() menunggu 1 detik kalau baris belum lengkap;
    // itu bikin tombol terasa lag. 100 ms sudah cukup di 115200 baud.
    Serial.setTimeout(100);
    Serial.println();
    Serial.println(F("================================"));
    Serial.println(F("  " PROFILE_NAME " - " PROFILE_SUBTITLE));
    Serial.println(F("  " PROFILE_VER));
    Serial.println(F("================================"));

    for (uint8_t i = 0; i < BUTTON_COUNT; i++) {
        if (buttons[i].pin >= 0) {
            pinMode(buttons[i].pin, INPUT_PULLUP);
            attachInterruptArg(digitalPinToInterrupt(buttons[i].pin),
                               onButtonPress, &buttons[i], FALLING);
        }
    }

    Wire.begin(I2C_SDA, I2C_SCL);
    // 400 kHz (Fast Mode). Default 100 kHz bikin satu render ~90 ms;
    // di 400 kHz turun jadi ~23 ms, jadi loop jauh lebih responsif.
    Wire.setClock(400000);

    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
        Serial.println(F("[FATAL] OLED tidak terdeteksi!"));
        Serial.println(F("  - Periksa koneksi SDA (GPIO21) dan SCL (GPIO22)"));
        Serial.println(F("  - Periksa alamat I2C (default: 0x3C)"));
        for (;;) delay(1000);
    }

    Serial.println(F("[OK] OLED terdeteksi di 0x3C"));
    showSplashScreen();

    Serial.println(F("[OK] Siap menerima data serial"));
    Serial.println(F("[INFO] Kirim field 'KEY:value' lalu 'END'"));
    Serial.println(F("[INFO] Tombol BOOT: singkat=ganti halaman, tahan=auto-cycle"));
    Serial.println();

    lastPageChange = millis();
    render();
}

void loop() {
    handleButtons();

    if (Serial.available() > 0) {
        handleLine(Serial.readStringUntil('\n'));
    }

    // Auto-cycle halaman
    if (dataReceived && autoCycle && (millis() - lastPageChange > AUTO_CYCLE_MS)) {
        currentPage = (currentPage + 1) % PAGE_COUNT;
        lastPageChange = millis();
        render();
    }

    // Redraw berkala untuk animasi indikator & typewriter animation (25 FPS)
    unsigned long redrawInterval = customScreen.active ? 40 : 500;
    if (millis() - lastRedraw > redrawInterval) {
        lastRedraw = millis();
        render();
    }
}
