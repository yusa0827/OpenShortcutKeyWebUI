#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ===== PIN ASSIGN =====
#define I2C_SDA 8
#define I2C_SCL 9

#define JOY_X_PIN 1   // VRx -> ADC1
#define JOY_Y_PIN 2   // VRy -> ADC1
#define JOY_SW_PIN 4  // SW  -> GPIO (press->GND)

// ===== OLED =====
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ===== helper =====
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
  Serial.printf("[OLED] init %s at 0x%02X\n", ok ? "OK" : "FAIL", addr);
  return ok;
}

// 方向判定（必要なら DEAD を調整）
static const int ADC_MAX = 4095;
static const int DEAD = 500; // 中央付近の遊び

static const char* dir_from_xy(int x, int y) {
  int cx = ADC_MAX / 2;
  int cy = ADC_MAX / 2;
  int dx = x - cx;
  int dy = y - cy;

  if (abs(dx) < DEAD && abs(dy) < DEAD) return "CENTER";

  if (abs(dx) > abs(dy)) return (dx > 0) ? "RIGHT" : "LEFT";
  // Yが上下逆に感じたら UP/DOWN を入れ替える
  return (dy > 0) ? "DOWN" : "UP";
}

unsigned long last_ms = 0;
uint32_t tick_n = 0;

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("=== ESP32-S3-Zero OLED + JOY debug ===");
  Serial.printf("I2C: SDA=%d SCL=%d\n", I2C_SDA, I2C_SCL);
  Serial.printf("JOY: X=%d Y=%d SW=%d\n", JOY_X_PIN, JOY_Y_PIN, JOY_SW_PIN);

  // I2C begin
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000); // 100kHzで安定優先
  Serial.println("[I2C] begin OK. clock=100kHz");

  // I2C scan
  i2c_scan();

  // OLED init
  bool ok = oled_try_init(0x3C);
  if (!ok) ok = oled_try_init(0x3D);
  if (!ok) {
    Serial.println("[OLED] init failed at 0x3C and 0x3D.");
    Serial.println("      -> wiring/power wrong OR controller is not SSD1306 (e.g. SH1106).");
    while (true) delay(1000);
  }

  // ADC
  analogReadResolution(12);

  // SW
  pinMode(JOY_SW_PIN, INPUT_PULLUP); // press -> LOW

  // First screen
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("OLED+JOY OK");
  display.println("SDA=8 SCL=9");
  display.println("X=GPIO1 Y=GPIO2");
  display.println("SW=GPIO4(PULLUP)");
  display.display();

  Serial.println("[SETUP] done.");
}

void loop() {
  if (millis() - last_ms >= 1000) {
    last_ms += 1000;

    int x = analogRead(JOY_X_PIN);
    int y = analogRead(JOY_Y_PIN);
    bool pressed = (digitalRead(JOY_SW_PIN) == LOW);
    const char* dir = dir_from_xy(x, y);

    // Serial log
    Serial.printf("[TICK %lu] X=%4d Y=%4d SW=%d DIR=%s\n",
                  (unsigned long)tick_n, x, y, pressed ? 1 : 0, dir);

    // OLED
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    display.print("tick: "); display.println(tick_n);
    display.print("X: "); display.println(x);
    display.print("Y: "); display.println(y);
    display.print("SW: "); display.println(pressed ? "PRESSED" : "released");
    display.print("DIR: "); display.println(dir);

    display.display();

    tick_n++;
  }
}