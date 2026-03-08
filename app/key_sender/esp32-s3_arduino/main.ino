#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <USB.h>
#include <USBHIDKeyboard.h>
USBHIDKeyboard Keyboard;

// ===== PIN (ESP32-S3-Zero) =====
#define I2C_SDA 8
#define I2C_SCL 9

#define JOY_X_PIN 1
#define JOY_Y_PIN 2
#define JOY_SW_PIN 4

// ===== OLED =====
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ===== ADC =====
static const int ADC_MAX = 4095;
static const int ADC_CENTER = ADC_MAX / 2;

// 方向判定しきい値（必要なら調整）
static const int DEAD = 450;
static const int TH   = 900;

enum Dir { DIR_CENTER, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT };

static const char* dir_name(Dir d) {
  switch (d) {
    case DIR_UP: return "UP";
    case DIR_DOWN: return "DOWN";
    case DIR_LEFT: return "LEFT";
    case DIR_RIGHT: return "RIGHT";
    default: return "CENTER";
  }
}

static Dir dir_from_xy_raw(int x, int y) {
  int dx = x - ADC_CENTER;
  int dy = y - ADC_CENTER;

  if (abs(dx) < DEAD && abs(dy) < DEAD) return DIR_CENTER;

  if (abs(dy) >= abs(dx)) {
    // 上下逆に感じたら UP/DOWN を入れ替える
    if (dy < -TH) return DIR_UP;
    if (dy >  TH) return DIR_DOWN;
  } else {
    if (dx >  TH) return DIR_RIGHT;
    if (dx < -TH) return DIR_LEFT;
  }
  return DIR_CENTER;
}

// 0..4095 -> 0..100
static int norm100(int v) {
  long n = (long)v * 100L / ADC_MAX;
  if (n < 0) n = 0;
  if (n > 100) n = 100;
  return (int)n;
}

static bool sw_pressed() {
  return digitalRead(JOY_SW_PIN) == LOW;
}


static void type_thank_you_fast() {
  const uint8_t msg[] = { 't','h','a','n','k',' ','y','o','u','!' };
  for (size_t i = 0; i < sizeof(msg); i++) {
    Keyboard.write(msg[i]);
  }
}

// エッジ検出（押しっぱなし連発防止）
static Dir last_dir = DIR_CENTER;
static unsigned long last_edge_ms = 0;
static const unsigned long EDGE_COOLDOWN_MS = 200;

static bool dir_edge(Dir now, Dir target) {
  bool edge = (last_dir != target) && (now == target);
  if (!edge) return false;
  unsigned long t = millis();
  if (t - last_edge_ms < EDGE_COOLDOWN_MS) return false;
  last_edge_ms = t;
  return true;
}

// ===== UI State =====
enum Screen { SCR_MENU, SCR_SHORTCUT, SCR_PASS_INPUT, SCR_PASS_RESULT };
Screen screen = SCR_MENU;
int menu_sel = 0; // 0: shortcut, 1: passphrase
String last_event = "boot";

// ===== Shortcut screen state (UP x2 -> F13) =====
static const int UP_TARGET = 2;   // ★ 5 -> 2 に変更
int up_count = 0;

// ===== Passphrase state =====
// パスフレーズ: ↑ ↓ ↑ ↓
static const Dir PASS_SEQ[4] = { DIR_UP, DIR_DOWN, DIR_UP, DIR_DOWN };
int pass_idx = 0;
bool pass_ok = false;
unsigned long pass_result_until_ms = 0;

// ★ pass OK の5秒後に "thank you!" を打つ予約
bool thankyou_pending = false;
unsigned long thankyou_due_ms = 0;

// ===== HID =====
static void send_f13_once() {
  Keyboard.press(KEY_F13);
  delay(20);
  Keyboard.releaseAll();
}

static void type_thank_you_once() {
  // 文字列入力（HIDでタイプ）
  Keyboard.print("thank you!");
  // Enterも押したいなら次行を有効化
  // Keyboard.write(KEY_RETURN);
}

// ===== OLED Draw =====
static void oled_clear_text() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
}

static void draw_menu(int xN, int yN, bool sw, Dir d) {
  oled_clear_text();
  display.println("MENU");
  display.println("----------------");
  display.print(menu_sel == 0 ? "> " : "  "); display.println("1. shortcut key");
  display.print(menu_sel == 1 ? "> " : "  "); display.println("2. passphrase");
  display.println("----------------");
  display.print("X:"); display.print(xN);
  display.print(" Y:"); display.print(yN);
  display.print(" SW:"); display.println(sw ? "1" : "0");
  display.print("DIR: "); display.println(dir_name(d));
  display.println(last_event);
  display.display();
}

static void draw_shortcut(int xN, int yN, bool sw, Dir d) {
  oled_clear_text();
  display.println("shortcut key");
  display.println("UP x2 => F13"); // ★
  display.println("----------------");
  display.print("X:"); display.print(xN); display.print(" Y:"); display.println(yN);
  display.print("SW: "); display.println(sw ? "PRESSED" : "released");
  display.print("DIR: "); display.println(dir_name(d));
  display.print("UP: "); display.print(up_count); display.print("/"); display.println(UP_TARGET);
  display.println("----------------");
  display.println(last_event);
  display.display();
}

static void draw_pass_input(int xN, int yN, bool sw, Dir d) {
  oled_clear_text();
  display.println("passphrase");
  display.println("input: U D U D");
  display.println("----------------");
  display.print("step: "); display.print(pass_idx); display.println("/4");
  display.print("last: "); display.println(dir_name(d));
  display.println("----------------");
  display.print("X:"); display.print(xN); display.print(" Y:"); display.println(yN);
  display.println(last_event);
  display.display();
}

static void draw_pass_result() {
  oled_clear_text();
  display.println("passphrase");
  display.println("----------------");

  display.setTextSize(2);
  display.setCursor(0, 20);
  display.println(pass_ok ? "OK" : "NG");

  display.setTextSize(1);
  display.setCursor(0, 52);

  if (pass_ok && thankyou_pending) {
    long ms_left = (long)thankyou_due_ms - (long)millis();
    int sec_left = (ms_left <= 0) ? 0 : (int)((ms_left + 999) / 1000); // 切り上げ
    display.print("typing in ");
    display.print(sec_left);
    display.print("s");
  } else {
    display.println("returning menu...");
  }
  display.display();
}

// ===== setup =====
void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println("=== UI: MENU + HID(F13) + PASS(thank you) ===");
  Serial.printf("I2C SDA=%d SCL=%d | JOY X=%d Y=%d SW=%d\n", I2C_SDA, I2C_SCL, JOY_X_PIN, JOY_Y_PIN, JOY_SW_PIN);

  USB.begin();
  Keyboard.begin();
  Serial.println("[USB] HID keyboard started");

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

  last_event = "READY: UP/DOWN select, SW enter";
}

// ===== loop =====
unsigned long last_tick_ms = 0;
uint32_t tick_n = 0;

static void go_menu(const char* reason) {
  screen = SCR_MENU;
  up_count = 0;
  pass_idx = 0;
  last_event = String("MENU: ") + reason;
  Serial.printf("[UI] -> MENU (%s)\n", reason);
}

void loop() {
  // 100ms周期
  static unsigned long last_read_ms = 0;
  if (millis() - last_read_ms < 100) return;
  last_read_ms = millis();

  // ★ Pass OK後の「5秒後 thank you!」処理（画面に関係なく動く）
  if (thankyou_pending && (long)(millis() - thankyou_due_ms) >= 0) {
    thankyou_pending = false;
    Serial.println("### HID TYPE (FAST): thank you! ###");
    last_event = "### typed: thank you! ###";
    type_thank_you_fast();
  }

  int x = analogRead(JOY_X_PIN);
  int y = analogRead(JOY_Y_PIN);
  bool sw = sw_pressed();
  Dir d = dir_from_xy_raw(x, y);

  int xN = norm100(x);
  int yN = norm100(y);

  // 1秒ごと tick
  if (millis() - last_tick_ms >= 1000) {
    last_tick_ms += 1000;
    Serial.printf("[TICK %lu] X=%4d(%3d) Y=%4d(%3d) SW=%d DIR=%s SCR=%d\n",
                  (unsigned long)tick_n, x, xN, y, yN, sw ? 1 : 0, dir_name(d), (int)screen);
    tick_n++;
  }

  // ===== Screen logic =====
  if (screen == SCR_MENU) {
    if (dir_edge(d, DIR_UP) || dir_edge(d, DIR_DOWN)) {
      menu_sel = (menu_sel + 1) % 2;
      last_event = String("menu sel -> ") + (menu_sel == 0 ? "shortcut" : "passphrase");
      Serial.printf("[MENU] select=%d\n", menu_sel);
    }

    static bool last_sw = false;
    if (!last_sw && sw) {
      if (menu_sel == 0) {
        screen = SCR_SHORTCUT;
        up_count = 0;
        last_event = "shortcut: UP x2 => F13";
        Serial.println("[UI] -> SHORTCUT");
      } else {
        screen = SCR_PASS_INPUT;
        pass_idx = 0;
        last_event = "pass: enter U D U D";
        Serial.println("[UI] -> PASS_INPUT");
      }
    }
    last_sw = sw;

    draw_menu(xN, yN, sw, d);
  }

  else if (screen == SCR_SHORTCUT) {
    static bool last_sw = false;
    if (!last_sw && sw) {
      go_menu("back from shortcut");
    }
    last_sw = sw;

    if (dir_edge(d, DIR_UP)) {
      up_count++;
      Serial.printf(">>> UP EDGE (%d/%d)\n", up_count, UP_TARGET);
      last_event = String("UP EDGE -> ") + up_count + "/" + UP_TARGET;

      if (up_count >= UP_TARGET) {
        Serial.println("### SENT F13 ###");
        last_event = "### SENT F13 ###";
        send_f13_once();
        up_count = 0;
        Serial.println(">>> UP COUNT RESET (0/2)");
      }
    }

    draw_shortcut(xN, yN, sw, d);
  }

  else if (screen == SCR_PASS_INPUT) {
    static bool last_sw = false;
    if (!last_sw && sw) {
      go_menu("cancel passphrase");
    }
    last_sw = sw;

    Dir input = DIR_CENTER;
    if (dir_edge(d, DIR_UP)) input = DIR_UP;
    else if (dir_edge(d, DIR_DOWN)) input = DIR_DOWN;
    else if (dir_edge(d, DIR_LEFT)) input = DIR_LEFT;
    else if (dir_edge(d, DIR_RIGHT)) input = DIR_RIGHT;

    if (input != DIR_CENTER) {
      Serial.printf("[PASS] input=%s step=%d\n", dir_name(input), pass_idx);

      bool step_ok = (input == PASS_SEQ[pass_idx]);
      if (!step_ok) {
        pass_ok = false;
        screen = SCR_PASS_RESULT;
        pass_result_until_ms = millis() + 1500;
        last_event = "PASS NG";
        Serial.println("[PASS] RESULT = NG");
      } else {
        pass_idx++;
        last_event = String("PASS OK step ") + pass_idx;

        if (pass_idx >= 4) {
          pass_ok = true;
          screen = SCR_PASS_RESULT;
          pass_result_until_ms = millis() + 1500;
          last_event = "PASS OK (typing in 5s)";
          Serial.println("[PASS] RESULT = OK");

          // ★ 5秒後に thank you! をタイプ予約
          thankyou_pending = true;
          thankyou_due_ms = millis() + 5000;
          Serial.println("[PASS] scheduled HID typing: \"thank you!\" in 5 seconds");
        }
      }
    }

    draw_pass_input(xN, yN, sw, d);
  }

  else if (screen == SCR_PASS_RESULT) {
    draw_pass_result();

    if (millis() >= pass_result_until_ms) {
      go_menu(pass_ok ? "pass OK" : "pass NG");
    }
  }

  // エッジ検出用
  last_dir = d;
}