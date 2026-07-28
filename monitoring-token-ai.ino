#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Variabel penampung data token & biaya
String inTokens = "0";
String outTokens = "0";
String estCost = "$0.000";
bool dataReceived = false;

// Fungsi untuk memperbarui tampilan di layar OLED
void updateDisplay(String statusText) {
  display.clearDisplay();
  
  // Header / Title
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(F("=== ANTIGRAVITY ==="));
  display.println(F("---------------------"));

  if (!dataReceived) {
    // Tampilan saat menunggu data pertama kali dari PC
    display.setCursor(0, 24);
    display.println(F("Status: Waiting..."));
    display.setCursor(0, 40);
    display.println(F("Connect Python Script"));
  } else {
    // Tampilan Metrik Token & Biaya
    display.setCursor(0, 20);
    display.print(F("In Tokens  : "));
    display.println(inTokens);

    display.setCursor(0, 34);
    display.print(F("Out Tokens : "));
    display.println(outTokens);

    display.setCursor(0, 48);
    display.print(F("Cost Est.  : $"));
    display.println(estCost);
  }

  display.display();
}

void setup() {
  // Komunikasi Serial USB (Baudrate 115200)
  Serial.begin(115200);

  // Inisialisasi Layar OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("OLED gagal terdeteksi! Periksa kabel SCL/SDA."));
    for(;;);
  }

  // Tampilan awal saat ESP32 baru dinyalakan
  updateDisplay("BOOTING");
}

void loop() {
  // Mengecek apakah ada data masuk dari PC via Serial USB
  if (Serial.available() > 0) {
    // Membaca satu baris data hingga karakter newline ('\n')
    String incomingData = Serial.readStringUntil('\n');
    incomingData.trim(); // Menghilangkan spasi/enter tambahan

    if (incomingData.length() > 0) {
      // Parsing data berdasarkan koma (Format: InTokens,OutTokens,Cost)
      int firstComma = incomingData.indexOf(',');
      int secondComma = incomingData.indexOf(',', firstComma + 1);

      if (firstComma != -1 && secondComma != -1) {
        inTokens = incomingData.substring(0, firstComma);
        outTokens = incomingData.substring(firstComma + 1, secondComma);
        estCost = incomingData.substring(secondComma + 1);
        
        dataReceived = true;
        updateDisplay("UPDATED");
      }
    }
  }
}