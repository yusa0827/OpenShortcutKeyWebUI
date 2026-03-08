#include <USB.h>
#include <USBHIDKeyboard.h>

// USB HID キーボード
USBHIDKeyboard Keyboard;

unsigned long last_tick_ms = 0;
unsigned long last_f13_ms  = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  // USB(デバイス)開始
  USB.begin();
  Keyboard.begin();

  Serial.println("HELLO ESP32-S3! (CDC + HID)");
}

void loop() {
  // 1秒ごとに tick
  if (millis() - last_tick_ms >= 1000) {
    last_tick_ms += 1000;
    Serial.println("tick");
  }

  // 30秒ごとに F13 を送る（スパム防止で間隔長め）
  if (millis() - last_f13_ms >= 30000) {
    last_f13_ms = millis();

    // F13 押して離す
    Keyboard.press(KEY_F13);
    delay(20);
    Keyboard.releaseAll();

    Serial.println("sent F13");
  }
}