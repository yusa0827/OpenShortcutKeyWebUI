#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <USB.h>
#include <USBHIDKeyboard.h>
USBHIDKeyboard Keyboard;

// ===== PIN =====
#define I2C_SDA 8
#define I2C_SCL 9

#define JOY_X_PIN 1
#define JOY_Y_PIN 2
#define JOY_SW_PIN 4

// （あれば）内蔵LED。無いボードもあるので無効化可
#ifndef LED_BUILTIN
#define LED_BUILTIN -1
#endif

// ===== OLED =====
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ===== Joystick threshold =====
static const int ADC_MAX = 4095;
static const int CENTER  = ADC_MAX / 2;
static const int DEAD = 450;   // 中央付近
static const int TH   = 900;   // 方向判定（UPにしたい強さ）

enum Dir { DIR_CENTER, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT };

Dir dir_from_xy(int x, int y) {
  int dx = x - CENTER;
  int dy = y - CENTER;

  if (abs(dx) < DEAD && abs(dy) < DEAD) return DIR_CENTER;

  if (abs(dy) >= abs(dx)) {
    // 上下逆ならここを入れ替え
    if (dy < -TH) return DIR_UP;
    if (dy >  TH) return DIR_DOWN;
  } else {
    if (dx >  TH) return DIR_RIGHT;
    if (dx < -TH) return DIR_LEFT;
  }
  return DIR_CENTER;
}

const char* dir_name(Dir d) {
  switch (d) {
    case DIR_UP: return "UP";
    case DIR_DOWN: return "DOWN";
    case DIR_LEFT: return "LEFT";
    case DIR_RIGHT: return "RIGHT";
    default: return "CENTER";
  }
}

// ===== UP x5 -> F13 =====
static const int UP_TARGET = 5;
int up_count = 0;

Dir last_dir = DIR_CENTER;
unsigned long last_up_edge_ms = 0;
static const unsigned long EDGE_COOLDOWN_MS = 220;

String last_event = "boot";

static void oled_draw(int x, int y, bool sw, Dir d) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.println("UP x5 => F13 (HID)");
  display.print("X: "); display.println(x);
  display.print("Y: "); display.println(y);
  display.print("SW: "); display.println(sw ? "PRESSED" : "released");
  display.print("DIR: "); display.println(dir_name(d));

  display.print("UP: ");
  display.print(up_count);
  display.print("/");
  display.println(UP_TARGET);

  // イベントを強調表示（2行）
  display.println("----------------");
  display.setTextSize(1);
  display.println(last_event);
  display.display();
}

static void blink_led_once() {
  if (LED_BUILTIN < 0) return;
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(60);
  digitalWrite(LED_BUILTIN, LOW);
}

static void send_f13_once() {
  Keyboard.press(KEY_F13);
  delay(20);
  Keyboard.releaseAll();
}

unsigned long last_tick_ms = 0;
uint32_t tick_n = 0;

void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("=== JOY UPx5 -> HID F13 (verbose) ===");
  Serial.printf("I2C SDA=%d SCL=%d | JOY X=%d Y=%d SW=%d\n", I2C_SDA, I2C_SCL, JOY_X_PIN, JOY_Y_PIN, JOY_SW_PIN);

  // USB HID
  USB.begin();
  Keyboard.begin();
  Serial.println("[USB] HID keyboard started");

  // I2C + OLED
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println("[OLED] init failed (0x3C/0x3D).");
      while (true) delay(1000);
    }
  }
  Serial.println("[OLED] init OK");

  analogReadResolution(12);
  pinMode(JOY_SW_PIN, INPUT_PULLUP);

  last_event = "READY: move UP 5 times";
  oled_draw(0, 0, false, DIR_CENTER);
}

void loop() {
  // 100ms周期で読む
  static unsigned long last_read_ms = 0;
  if (millis() - last_read_ms < 100) return;
  last_read_ms = millis();

  int x = analogRead(JOY_X_PIN);
  int y = analogRead(JOY_Y_PIN);
  bool sw = (digitalRead(JOY_SW_PIN) == LOW);
  Dir d = dir_from_xy(x, y);

  // 1秒ごとtick
  if (millis() - last_tick_ms >= 1000) {
    last_tick_ms += 1000;
    Serial.printf("[TICK %lu] X=%4d Y=%4d SW=%d DIR=%s UP=%d/%d\n",
                  (unsigned long)tick_n, x, y, sw ? 1 : 0, dir_name(d), up_count, UP_TARGET);
    tick_n++;
  }

  // UPエッジ検出（CENTER→UP の瞬間）
  bool up_edge = (last_dir != DIR_UP) && (d == DIR_UP);
  if (up_edge) {
    unsigned long now = millis();
    if (now - last_up_edge_ms >= EDGE_COOLDOWN_MS) {
      last_up_edge_ms = now;
      up_count++;

      // ★ここが「分かりやすい」ログ
      Serial.printf(">>> UP EDGE  (%d/%d)\n", up_count, UP_TARGET);
      last_event = String("UP EDGE -> ") + up_count + "/" + UP_TARGET;

      if (up_count >= UP_TARGET) {
        Serial.println("### SENT F13 ###");
        last_event = "### SENT F13 ###";

        send_f13_once();
        blink_led_once();

        up_count = 0;
        Serial.println(">>> UP COUNT RESET (0/5)");
      }
    } else {
      Serial.println(">>> UP EDGE ignored (cooldown)");
    }
  }

  last_dir = d;
  oled_draw(x, y, sw, d);
}