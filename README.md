# コンセプト
ショートカットキーで、自分がやりたいアクションを実行できること

# モジュールのインストール
pip install keyboard 
pip install streamlit

# 構成
```
┌──────────────────────────┐
│   shortcut_webui.py      │
│   （Streamlit）           │
│   設定編集UI              │
└─────────────┬────────────┘
              │ 書き込み
              ▼
        shortcut_config.json
              ▲ 読み込み
              │
┌─────────────┴────────────┐
│   key_listener.py        │
│  常駐ホットキー監視        │
│  keyboardフック           │
└─────────────┬────────────┘
              │
              ▼
        実行処理（open_url / run_cmd）
              │
              ▼
        Chrome起動など
```

# テスト 手順
キーのリスナーを起動
python key_listener.py
push_F13_key.py で F13 キーを入力
python push_F13_key.py
結果
chrome のブラウザで ChatGPT が表示されると成功

# 今の構成のメリット
✅ WebUIが落ちても常駐は動く
✅ F5で壊れない
✅ 市販品と同じ思想（UIと実行分離）
✅ 拡張しやすい