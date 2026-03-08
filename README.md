# OpenShortcutKey

ショートカットキーで任意のアクション（URLを開く / コマンド実行）を呼び出すためのツールです。  
このリポジトリの `app/` 配下には、用途の異なる複数アプリが入っています。

## 動作環境

- Python 3.11 系（README作成時の確認: 3.11.9）
- 主対象OS: Windows（`RegisterHotKey` や `cmd.exe` を使うため）

## セットアップ

以下のいずれかで依存関係をインストールします。

```bash
python setting.py
```

または

```bash
pip install -r requirements.txt
```

主な依存パッケージ:

- streamlit
- keyboard
- pystray

---

## `app/` 配下のアプリの使い方

### 1. 設定WebUI（Streamlit）

ファイル:
- `app/key_setting/shortcut_key_setting_webui.py`

用途:
- ショートカット定義の追加 / 編集 / 削除
- 設定保存（`config/shortcut_config.json`）
- （WebUI内から）keyboardライブラリによる簡易監視の開始/停止

起動方法（リポジトリルートで実行）:

```bash
python -m streamlit run app/key_setting/shortcut_key_setting_webui.py
```

使い方:
1. ブラウザで表示されるWebUIを開く。
2. 既存ショートカットを編集、または「追加」で新規作成。
3. 「保存」で `config/shortcut_config.json` に保存。
4. 必要に応じて「監視を開始（保存済み）」でWebUI内監視を開始。

補足:
- `action_type` は `open_url` / `run_cmd` / `open_cmd` を選択可能です。
- `open_cmd` は `value` 不要です。

### 2. 常駐ホットキーリスナー（WinAPI RegisterHotKey）

ファイル:
- `app/key_listener/shortcut_key_listener.py`

用途:
- `config/shortcut_config.json` を読み取り、Windowsの `RegisterHotKey` でホットキーを常駐監視
- 押下時に `open_url` または `run_cmd` を実行
- 設定ファイル更新をポーリングして再読込

起動方法（リポジトリルートで実行）:

```bash
python app/key_listener/shortcut_key_listener.py
```

基本運用:
1. 先にWebUIでショートカット設定を保存。
2. 別ターミナルでリスナーを起動。
3. 例: `ctrl+f1` などを押して動作確認。
4. 終了は `Ctrl + C`。

補足:
- WebUI内の `keyboard` 監視より、このWinAPI版の方が安定運用向きです。
- 起動後に `last_trigger.txt` へ最終トリガー情報が出力されます。

### 3. キー送信GUI（F13〜F16）

ファイル:
- `app/key_sender/gui/ctrl_f1_f4_key_sender_gui.py`

用途:
- GUIボタンで `F13`〜`F16` キーイベントを送信（テスト用）

起動方法（リポジトリルートで実行）:

```bash
python app/key_sender/gui/ctrl_f1_f4_key_sender_gui.py
```

使い方:
1. GUIを起動。
2. F13/F14/F15/F16ボタンをクリック。
3. `keyboard.send()` により対応キーが送出されます。

注意:
- ファイル名は `ctrl_f1_f4...` ですが、実際に送信しているのは `F13〜F16` です。

### 4. ESP32-S3 向けキー送信側（Arduino）

ディレクトリ:
- `app/key_sender/esp32-s3_arduino/`

用途:
- ESP32-S3 を使った送信デバイス側のスケッチ

使い方:
- 詳細手順は以下を参照してください。
  - `app/key_sender/esp32-s3_arduino/README.md`
- サンプルは `sample/` 配下にあります。

---

## 推奨の使い始め手順

1. 依存をインストール
2. WebUIを起動してショートカットを設定・保存
3. WinAPI版リスナーを起動
4. 必要ならキー送信GUIやESP32デバイス側からキー入力を送って確認

---

## 設定ファイル

- `config/shortcut_config.json`
  - `shortcuts` 配列に、`title` / `hotkey` / `action_type` / `value` を保持
