#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define I2C_SDA 8
#define I2C_SCL 9

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

static void i2c_scan() {
  Serial.println();
  Serial.println("[I2C] scan start...");
  int found = 0;

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();

    if (err == 0) {
      Serial.printf("[I2C] FOUND device at 0x%02X\n", addr);
      found++;
    }
  }

  if (found == 0) Serial.println("[I2C] No devices found.");
  else Serial.printf("[I2C] scan done. found=%d\n", found);
  Serial.println();
}

static bool oled_try_init(uint8_t addr) {
  Serial.printf("[OLED] trying SSD1306 addr=0x%02X ...\n", addr);
  bool ok = display.begin(SSD1306_SWITCHCAPVCC, addr);
  if (ok) {
    Serial.printf("[OLED] init OK at 0x%02X\n", addr);
  } else {
    Serial.printf("[OLED] init FAIL at 0x%02X\n", addr);
  }
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("=== ESP32-S3-Zero OLED debug ===");
  Serial.printf("I2C pins: SDA=%d SCL=%d\n", I2C_SDA, I2C_SCL);

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000); // まずは100kHzで安定優先
  Serial.println("[I2C] begin OK. clock=100kHz");

  // 1) I2Cスキャン
  i2c_scan();

  // 2) OLED初期化を 0x3C → 0x3D の順で試す
  bool ok = oled_try_init(0x3C);
  if (!ok) ok = oled_try_init(0x3D);

  if (!ok) {
    Serial.println("[OLED] SSD1306 init failed at both 0x3C and 0x3D.");
    Serial.println("      -> Check wiring/power, or the OLED may be SH1106 / different controller.");
    while (true) delay(1000);
  }

  // 3) 表示テスト
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("OLED OK!");
  display.println("ESP32-S3-Zero");
  display.println("SDA=8 SCL=9");
  display.display();

  Serial.println("[OLED] drew test text to screen.");
}

void loop() {
  static uint32_t n = 0;

  Serial.printf("[LOOP] tick n=%lu\n", (unsigned long)n);

  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.println("Hello OLED!");
  display.print("count: ");
  display.println(n);
  display.display();

  n++;
  delay(1000);
}