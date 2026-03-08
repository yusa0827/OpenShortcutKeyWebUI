````markdown
# ESP32-S3 Zero / Mini を Arduino IDE で開発するメモ

## 1. 概要

ESP32-S3 Zero / Mini は Arduino IDE で開発できます。  
ESP32-S3 は Espressif の Arduino core（Arduino-ESP32）でサポートされています。

ボード名が完全一致で表示されない場合でも、まずは `ESP32S3 Dev Module` を選べば動作することが多いです。  
実機が WROOM-2 系の場合も、まずは `ESP32S3 Dev Module` 系設定で動作確認できます。

---

## 2. 開発環境

- Arduino IDE 2.x
- Arduino-ESP32
- 対象ボード例
  - TENSTAR ESP32-S3-Zero
  - ESP32-S3 Mini
  - ESP32-S3 Dev Module 系

---

## 3. Arduino IDE セットアップ

### 3.1 Boards Manager URL を追加

Arduino IDE で以下を開きます。

- `File` → `Preferences`

`Additional Boards Manager URLs` に以下を追加します。

```text
https://espressif.github.io/arduino-esp32/package_esp32_index.json
````

これは ESP32 用ボード定義を追加するための URL です。
JSON ファイルを手動でダウンロードするのではなく、**追加URLとして登録**します。

---

### 3.2 Boards Manager でインストール

以下を開きます。

* `Tools` → `Board` → `Boards Manager`

検索欄で以下を検索してインストールします。

```text
ESP32 by Espressif Systems
```

これは **ボード定義パッケージ** です。

---

### 3.3 Board を選択

以下を開きます。

* `Tools` → `Board`

まずは以下を選びます。

```text
ESP32S3 Dev Module
```

ボード名が完全一致しない場合でも、ESP32-S3 Zero / Mini ではこの設定で動くことが多いです。

---

## 4. Tools 設定

動作確認時の設定例です。

* Board: `ESP32S3 Dev Module`
* Flash Size: `4MB`
* PSRAM: `Disabled`
* USB Mode: `USB-OTG (TinyUSB)`
* USB CDC On Boot: `Enabled`
* Upload Mode: `UART0 / Hardware CDC`
* JTAG Adapter: `Disabled`

### 補足

* `Flash Mode` は環境差が出ることがあります。
* `DIO 80MHz` で動く場合もありますが、不安定なら周波数を下げることを検討します。
* まずは最小構成で起動確認し、必要に応じて設定を詰めます。

---

## 5. 必要なインストール

### 5.1 Boards Manager でインストールするもの

```text
ESP32 by Espressif Systems
```

### 5.2 Library Manager でインストールするもの

```text
Adafruit GFX Library
Adafruit SSD1306
```

---

## 6. ライブラリの入れ方

Arduino IDE で以下のどちらかを開きます。

* 左側の本棚アイコン（Library Manager）
* `Sketch` → `Include Library` → `Manage Libraries...`

検索欄に以下を入力して、それぞれインストールします。

* `Adafruit GFX`
* `Adafruit SSD1306`

依存関係の確認が出た場合は、まとめてインストールします。

---

## 7. 使用する OLED と前提

このメモでは、以下のような OLED を想定しています。

* SSD1306
* 128x64
* I2C 接続
* I2C アドレスは `0x3C` が多い

表示されない場合は `0x3D` も試します。

---

## 8. 配線

OLED と、アナログ 2 軸 + SW 付きジョイスティックを接続した例です。

### 8.1 OLED（I2C）

| OLED | ESP32-S3 |
| ---- | -------- |
| GND  | GND      |
| VCC  | 3V3      |
| SDA  | GPIO17   |
| SCL  | GPIO18   |

### 8.2 ジョイスティック（アナログ）

| Joystick | ESP32-S3 |
| -------- | -------- |
| GND      | GND      |
| VCC      | 3V3      |
| VRx      | GPIO1    |
| VRy      | GPIO2    |
| SW       | GPIO4    |

---

## 9. 配線時の注意

* OLED とジョイスティックは **3.3V** で給電する
* **5V を直接入れない**
* **GND は共通**にする
* `GPIO1 / GPIO2 / GPIO4 / GPIO17 / GPIO18` は今回の配線例
* 別の GPIO に変更してもよいが、その場合はコード内の `#define` も修正する

---

## 10. USB ポートの注意

ESP32-S3 系基板は、基板によって USB ポートが複数ある場合があります。

* 書き込み用ポート
* USB Device 用ポート
* シリアルモニタに使うポート

が分かれていることがあります。

そのため、書き込みできない場合やシリアルが出ない場合は、

* 接続している USB ポートが正しいか
* Arduino IDE の `Tools` → `Port` で正しい COM ポートを選んでいるか

を確認します。

---

## 11. 書き込みと確認の基本手順

1. Arduino IDE を起動
2. ESP32 ボード定義をインストール
3. Board を `ESP32S3 Dev Module` に設定
4. Port を選択
5. 必要ライブラリをインストール
6. 配線する
7. サンプルコードを貼り付ける
8. `Upload` を押して書き込む
9. `Serial Monitor` を開いて確認する

### Serial Monitor 設定

このサンプルでは以下を使います。

```text
115200
```

コード内で `Serial.begin(115200);` を使っているため、Serial Monitor 側も `115200` に合わせます。

---

## 12. 動作確認用サンプルコード

OLED にジョイスティックの値と方向を表示するサンプルです。

```cpp
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ===== 配線に合わせてここだけ調整 =====
#define I2C_SDA 17
#define I2C_SCL 18

#define JOY_X_PIN 1   // VRx
#define JOY_Y_PIN 2   // VRy
#define JOY_SW_PIN 4  // SW（押すとGNDに落ちる想定）

// ===== OLED設定 =====
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// 方向判定のしきい値
static const int DEAD = 500;
static const int MAXV = 4095;

String dirFromXY(int x, int y) {
  int cx = MAXV / 2;
  int cy = MAXV / 2;
  int dx = x - cx;
  int dy = y - cy;

  if (abs(dx) < DEAD && abs(dy) < DEAD) return "CENTER";

  if (abs(dx) > abs(dy)) {
    return (dx > 0) ? "RIGHT" : "LEFT";
  } else {
    return (dy > 0) ? "DOWN" : "UP";
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  // I2C開始
  Wire.begin(I2C_SDA, I2C_SCL);

  // OLED開始
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED init failed. Try addr 0x3D or wiring.");
    while (true) delay(100);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  // ADC設定
  analogReadResolution(12);

  // SWは押すとLOWの想定
  pinMode(JOY_SW_PIN, INPUT_PULLUP);

  display.setCursor(0, 0);
  display.println("ESP32-S3 OLED+JOY");
  display.println("Starting...");
  display.display();
  delay(500);
}

void loop() {
  int x = analogRead(JOY_X_PIN);
  int y = analogRead(JOY_Y_PIN);
  bool pressed = (digitalRead(JOY_SW_PIN) == LOW);

  String dir = dirFromXY(x, y);

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Joystick Monitor");
  display.println("----------------");

  display.print("X: ");
  display.println(x);

  display.print("Y: ");
  display.println(y);

  display.print("SW: ");
  display.println(pressed ? "PRESSED" : "released");

  display.print("DIR: ");
  display.println(dir);

  display.display();

  Serial.printf("X=%d Y=%d SW=%d DIR=%s\n", x, y, pressed ? 1 : 0, dir.c_str());

  delay(50);
}
```

---

## 13. 期待する動作

正常に動けば、以下が確認できます。

### OLED

* `Joystick Monitor` と表示される
* `X`, `Y`, `SW`, `DIR` が更新される

### Serial Monitor

* `X=... Y=... SW=... DIR=...` が表示される

### ジョイスティック操作

* スティックを倒すと `DIR` が変わる
* ボタンを押すと `SW` が `PRESSED` になる

---

## 14. 注意点 / トラブルシュート

### 14.1 OLED が表示されない

原因として多いのは I2C アドレス違いです。

* まず `0x3C`
* ダメなら `0x3D`

それでも表示されない場合は、以下を確認します。

* 配線ミス
* SDA / SCL の入れ違い
* 3.3V 給電になっているか
* OLED が SSD1306 / I2C モデルか

---

### 14.2 I2C アドレスを確認したい

`0x3C` / `0x3D` のどちらでも表示されない場合は、I2C スキャンで接続先アドレスを確認します。
必要なら別途 I2C スキャン用スケッチを用意して確認します。

---

### 14.3 ジョイスティックの方向が逆

ジョイスティックモジュールによっては、上下左右の向きが逆になることがあります。
その場合は方向判定を入れ替えます。

例:

* `UP` と `DOWN` を入れ替える
* `LEFT` と `RIGHT` を入れ替える

---

### 14.4 中央に戻しても CENTER になりにくい

ジョイスティックの中心値は個体差があります。
必ずしも `2048` ぴったりにはなりません。

その場合は、以下を調整します。

* `DEAD`
* 必要であれば中心値の補正

たとえば中央付近で誤判定が多い場合は、`DEAD` を少し大きくします。

---

### 14.5 SW ボタンがうまく読めない

このサンプルでは以下を前提としています。

* `pinMode(JOY_SW_PIN, INPUT_PULLUP);`
* 押すと `LOW`

モジュールによって仕様が違う場合は、SW の配線と論理を確認します。

---

### 14.6 書き込みできない / 起動が不安定

以下を確認します。

* `Board` が `ESP32S3 Dev Module` になっているか
* `Port` が正しいか
* `Flash Size` が実機に合っているか
* `USB Mode` / `USB CDC On Boot` の設定
* `Flash Mode` が高すぎないか
* 接続している USB ポートが正しいか

---

## 15. 最低限の作業手順まとめ

1. Arduino IDE をインストール
2. Boards Manager URL を追加
3. `ESP32 by Espressif Systems` をインストール
4. `Adafruit GFX Library` と `Adafruit SSD1306` をインストール
5. Board を `ESP32S3 Dev Module` に設定
6. Port を選択
7. OLED とジョイスティックを配線
8. サンプルコードを書き込む
9. Serial Monitor を `115200` で開く
10. OLED 表示とジョイスティック入力を確認する

---

## 16. メモ

* GPIO 配置は配線例なので、必要に応じて変更可能
* GPIO を変えたらコードの `#define` も合わせて変更する
* まずは最小構成で動作確認し、その後に機能追加する

```

このまま `README.md` に貼れます。  
必要なら次に、あなた向けにさらに詰めて

- `TENSTAR ESP32-S3-Zero` 前提に寄せる版
- `I2Cスキャン用コード` を追加した版
- `画像つき配線図用の章` を足した版

のどれかに整えられます。
```
