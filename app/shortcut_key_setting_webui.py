from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import streamlit as st
import keyboard

CONFIG_PATH = "shortcut_config.json"

# ===============================
# データ構造
# ===============================
@dataclass
class Shortcut:
    id: str
    title: str
    hotkey: str
    action_type: str  # "open_url" / "run_cmd" / "open_cmd"
    value: str


def new_id() -> str:
    return uuid.uuid4().hex


DEFAULT_SHORTCUTS: List[Shortcut] = [
    Shortcut(
        id=new_id(),
        title="Open ChatGPT",
        hotkey="f13",
        action_type="open_url",
        value="https://chat.openai.com",
    )
]

ACTION_TYPES = ["open_url", "run_cmd", "open_cmd"]


# ===============================
# 設定 I/O（旧互換あり）
# ===============================
def _normalize_hotkey(hk: str) -> str:
    return (hk or "").strip().lower()


def _normalize_action_type(at: str) -> str:
    at = (at or "").strip()
    if at not in ACTION_TYPES:
        return "run_cmd"
    return at


def load_config() -> List[Shortcut]:
    """
    旧フォーマット互換:
      - title が無い → title = hotkey
      - id が無い → 自動生成
      - action_type 未知 → run_cmd
    """
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_SHORTCUTS)
        return [Shortcut(**asdict(s)) for s in DEFAULT_SHORTCUTS]

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
    except Exception:
        save_config(DEFAULT_SHORTCUTS)
        return [Shortcut(**asdict(s)) for s in DEFAULT_SHORTCUTS]

    shortcuts: List[Shortcut] = []
    for item in data.get("shortcuts", []):
        sid = item.get("id") or new_id()
        hotkey = _normalize_hotkey(item.get("hotkey", ""))
        action_type = _normalize_action_type(item.get("action_type") or "run_cmd")
        value = (item.get("value") or "").strip()

        title = item.get("title")
        if not title:
            title = hotkey or "Unnamed"

        # open_cmd は value 不要
        if action_type == "open_cmd":
            value = ""

        shortcuts.append(
            Shortcut(
                id=sid,
                title=title,
                hotkey=hotkey,
                action_type=action_type,
                value=value,
            )
        )

    if not shortcuts:
        shortcuts = [Shortcut(**asdict(s)) for s in DEFAULT_SHORTCUTS]

    return shortcuts


def save_config(shortcuts: List[Shortcut]) -> None:
    # 保存時に揺れを正規化しておく
    normalized: List[Shortcut] = []
    for s in shortcuts:
        ss = Shortcut(**asdict(s))
        ss.hotkey = _normalize_hotkey(ss.hotkey)
        ss.title = (ss.title or "").strip() or (ss.hotkey or "Unnamed")
        ss.action_type = _normalize_action_type(ss.action_type or "run_cmd")
        ss.value = (ss.value or "").strip()

        if ss.action_type == "open_cmd":
            ss.value = ""

        normalized.append(ss)

    data = {"shortcuts": [asdict(s) for s in normalized]}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ===============================
# 実行処理
# ===============================
def open_url_in_chrome(url: str) -> None:
    subprocess.Popen(f'start chrome "{url}"', shell=True)


def run_command(cmd: str) -> None:
    # 新しいコンソールウィンドウで実行
    subprocess.Popen(
        f'cmd.exe /c start "" {cmd}',
        shell=True,
    )


def open_cmd_window() -> None:
    # ★必ず新しいコンソールを作って cmd を開く（開いたまま）
    subprocess.Popen(
        ["cmd.exe", "/k"],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

def execute(sc: Shortcut) -> None:
    print(f"[EXEC] {sc.title} | {sc.hotkey} | {sc.action_type} | {sc.value}")

    if sc.action_type == "open_url":
        open_url_in_chrome(sc.value)
    elif sc.action_type == "open_cmd":
        open_cmd_window()
    else:
        run_command(sc.value)


# ===============================
# 常駐監視スレッド（安全解除）
# ===============================
def listener_loop(shortcuts: List[Shortcut], stop_event: threading.Event, status: Dict[str, str]) -> None:
    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass

    hook_ids = []
    errors = []
    registered = 0

    for sc in shortcuts:
        hk = _normalize_hotkey(sc.hotkey)
        if not hk:
            continue
        try:
            hid = keyboard.add_hotkey(hk, lambda s=sc: execute(s))
            hook_ids.append(hid)
            registered += 1
        except Exception as e:
            errors.append(f"{hk}: {e}")

    if errors:
        status["state"] = "warning"
        status["msg"] = "一部登録に失敗:\n" + "\n".join(errors)
    else:
        status["state"] = "running"
        status["msg"] = f"監視中: {registered} 件のホットキーを登録しました（保存済み設定）"

    while not stop_event.is_set():
        time.sleep(0.2)

    for hid in hook_ids:
        try:
            keyboard.remove_hotkey(hid)
        except Exception:
            pass

    status["state"] = "stopped"
    status["msg"] = "停止中"


# ===============================
# Streamlit state helpers
# ===============================
def ensure_state() -> None:
    if "shortcuts" not in st.session_state:
        st.session_state.shortcuts = load_config()

    if "listener_thread" not in st.session_state:
        st.session_state.listener_thread = None

    if "stop_event" not in st.session_state:
        st.session_state.stop_event = threading.Event()

    if "listener_status" not in st.session_state:
        st.session_state.listener_status = {"state": "stopped", "msg": "停止中"}

    if "ui_last_tick" not in st.session_state:
        st.session_state.ui_last_tick = 0.0

    # 追加用の入力状態（初回だけ初期化）
    if "add_title" not in st.session_state:
        st.session_state.add_title = "New Shortcut"
    if "add_hotkey" not in st.session_state:
        st.session_state.add_hotkey = "f14"
    if "add_action_type" not in st.session_state:
        st.session_state.add_action_type = "open_url"
    if "add_value_url" not in st.session_state:
        st.session_state.add_value_url = "https://chat.openai.com"
    if "add_value_cmd" not in st.session_state:
        st.session_state.add_value_cmd = ""


def listener_running() -> bool:
    t = st.session_state.listener_thread
    return t is not None and t.is_alive()


def start_listener_from_saved_config() -> None:
    if listener_running():
        return

    # まず今のUI状態を JSON に保存してから起動
    save_config(st.session_state.shortcuts)

    # その保存内容を読み直して起動（確実に「保存済み設定」で起動）
    shortcuts = load_config()

    st.session_state.stop_event = threading.Event()
    st.session_state.listener_thread = threading.Thread(
        target=listener_loop,
        args=(shortcuts, st.session_state.stop_event, st.session_state.listener_status),
        daemon=True,
    )
    st.session_state.listener_thread.start()


def stop_listener() -> None:
    if listener_running():
        st.session_state.stop_event.set()
        time.sleep(0.2)


def soft_autorefresh(interval_sec: float = 0.5) -> None:
    now = time.time()
    if now - st.session_state.ui_last_tick >= interval_sec:
        st.session_state.ui_last_tick = now
        st.rerun()


# ===============================
# UI: CSS（雰囲気を一気に変える）
# ===============================
def inject_css() -> None:
    st.markdown(
        """
<style>
/* 全体 */
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; }
h1, h2, h3 { letter-spacing: -0.02em; }

/* ヘッダーカード */
.hero {
  padding: 18px 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(70,140,255,0.14), rgba(170,90,255,0.10));
  border: 1px solid rgba(255,255,255,0.10);
  margin-bottom: 14px;
}
.hero-title { font-size: 28px; font-weight: 800; margin: 0; }
.hero-sub { margin: 6px 0 0 0; opacity: 0.75; }

/* カード */
.card {
  padding: 14px 14px;
  border-radius: 16px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 10px 30px rgba(0,0,0,0.10);
}

/* バッジ */
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  opacity: 0.92;
  border: 1px solid rgba(255,255,255,0.16);
}
.badge-blue { background: rgba(60,130,255,0.20); }
.badge-green { background: rgba(30,200,120,0.18); }
.badge-amber { background: rgba(255,190,60,0.20); }
.badge-gray { background: rgba(160,160,160,0.16); }

.kv { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.kv .k { opacity: 0.7; font-size: 12px; }
.kv .v { font-weight: 700; }

/* Streamlitの部品を少し丸く */
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div,
div[data-testid="stTextArea"] textarea {
  border-radius: 12px !important;
}

/* ボタンを“それっぽく” */
div.stButton > button {
  border-radius: 12px !important;
  padding: 0.55rem 0.85rem !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def badge_action(action_type: str) -> str:
    if action_type == "open_url":
        return '<span class="badge badge-blue">OPEN URL</span>'
    if action_type == "open_cmd":
        return '<span class="badge badge-amber">OPEN CMD</span>'
    return '<span class="badge badge-gray">RUN CMD</span>'


def badge_state(state: str) -> str:
    if state == "running":
        return '<span class="badge badge-green">RUNNING</span>'
    if state == "warning":
        return '<span class="badge badge-amber">WARNING</span>'
    return '<span class="badge badge-gray">STOPPED</span>'


# ===============================
# WebUI
# ===============================
st.set_page_config(page_title="OpenShortcutKeyWebUI", layout="wide")
ensure_state()
inject_css()

state = st.session_state.listener_status.get("state", "stopped")
msg = st.session_state.listener_status.get("msg", "停止中")

st.markdown(
    f"""
<div class="hero">
  <div class="kv">
    <div class="hero-title">OpenShortcutKeyWebUI</div>
    {badge_state(state)}
  </div>
  <p class="hero-sub">設定(UI)と常駐監視(実行)を同じPythonプロセスで動作。保存と監視は分離して安定化。</p>
</div>
""",
    unsafe_allow_html=True,
)

left, right = st.columns([1.25, 1])

# -------------------------------
# 左: 編集・追加・保存
# -------------------------------
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("ショートカット（編集）")
    st.caption("ホットキーは `ctrl+alt+f1` のように指定できます。")

    for sc in list(st.session_state.shortcuts):
        label = f"{sc.title}  •  {sc.hotkey}  •  {sc.action_type}"
        with st.expander(label, expanded=False):
            st.markdown(
                f"""
<div class="kv">
  <span class="badge badge-gray">{sc.hotkey or 'no-hotkey'}</span>
  {badge_action(sc.action_type)}
</div>
""",
                unsafe_allow_html=True,
            )

            sc.title = st.text_input("タイトル", sc.title, key=f"title_{sc.id}")

            sc.hotkey = st.text_input(
                "ホットキー（例: f13 / ctrl+alt+f1）",
                sc.hotkey,
                key=f"hotkey_{sc.id}",
            )
            sc.hotkey = _normalize_hotkey(sc.hotkey)

            sc.action_type = st.selectbox(
                "動作タイプ",
                ACTION_TYPES,
                index=ACTION_TYPES.index(sc.action_type) if sc.action_type in ACTION_TYPES else 1,
                key=f"type_{sc.id}",
                help="open_url: ChromeでURL / run_cmd: コマンド実行 / open_cmd: cmd.exe を開く",
            )

            if sc.action_type == "open_url":
                sc.value = st.text_input(
                    "URL",
                    sc.value,
                    key=f"value_url_{sc.id}",
                    help="例: https://chat.openai.com",
                )
            elif sc.action_type == "run_cmd":
                sc.value = st.text_input(
                    "コマンド",
                    sc.value,
                    key=f"value_cmd_{sc.id}",
                    help='例: notepad / "C:\\\\path\\\\app.exe" --arg',
                )
            else:
                sc.value = ""
                st.caption("cmd.exe を開きます（入力不要）")

            del_col, _ = st.columns([1, 3])
            with del_col:
                if st.button("削除", key=f"del_{sc.id}", type="secondary"):
                    st.session_state.shortcuts = [x for x in st.session_state.shortcuts if x.id != sc.id]
                    st.rerun()

    st.divider()

    st.subheader("追加")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.session_state.add_title = st.text_input("タイトル", st.session_state.add_title)
        st.session_state.add_hotkey = st.text_input("ホットキー", st.session_state.add_hotkey)
    with c2:
        st.session_state.add_action_type = st.selectbox(
            "動作タイプ",
            ACTION_TYPES,
            index=ACTION_TYPES.index(st.session_state.add_action_type)
            if st.session_state.add_action_type in ACTION_TYPES
            else 0,
        )

    if st.session_state.add_action_type == "open_url":
        st.session_state.add_value_url = st.text_input("URL", st.session_state.add_value_url)
    elif st.session_state.add_action_type == "run_cmd":
        st.session_state.add_value_cmd = st.text_input(
            "コマンド",
            st.session_state.add_value_cmd,
            help='例: notepad / "C:\\\\path\\\\app.exe" --arg',
        )
    else:
        st.caption("cmd.exe を開きます（入力不要）")

    if st.button("追加する"):
        action_type = st.session_state.add_action_type

        if action_type == "open_url":
            value = st.session_state.add_value_url.strip()
        elif action_type == "run_cmd":
            value = st.session_state.add_value_cmd.strip()
        else:
            value = ""

        st.session_state.shortcuts.append(
            Shortcut(
                id=new_id(),
                title=(st.session_state.add_title.strip() or "Untitled"),
                hotkey=_normalize_hotkey(st.session_state.add_hotkey),
                action_type=action_type,
                value=value,
            )
        )

        # 追加後に入力欄をリセット
        st.session_state.add_title = "New Shortcut"
        st.session_state.add_hotkey = "f14"
        st.session_state.add_action_type = "open_url"
        st.session_state.add_value_url = "https://chat.openai.com"
        st.session_state.add_value_cmd = ""

        st.rerun()

    st.divider()

    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("保存", type="primary"):
            save_config(st.session_state.shortcuts)
            st.success(f"保存しました: {CONFIG_PATH}")
    with a2:
        if st.button("初期化", type="secondary"):
            st.session_state.shortcuts = [Shortcut(**asdict(s)) for s in DEFAULT_SHORTCUTS]
            save_config(st.session_state.shortcuts)
            st.info("初期状態に戻しました")
            st.rerun()
    with a3:
        if st.button("テスト実行", type="secondary"):
            open_url_in_chrome("https://chat.openai.com")
            st.toast("ChromeでChatGPTを開きました", icon="✅")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------
# 右: 監視開始/停止 + 状態表示
# -------------------------------
with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("常駐監視")

    if state == "running":
        st.success(msg)
    elif state == "warning":
        st.warning(msg)
    else:
        st.info(msg)

    st.caption("Fn はOSに届かないことが多いので、動作確認は `ctrl+alt+f1` など推奨。")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("監視を開始（保存済み）", type="primary"):
            start_listener_from_saved_config()
            st.toast("監視を開始しました", icon="🟢")
            st.rerun()

    with b2:
        if st.button("監視を停止", type="secondary"):
            stop_listener()
            st.toast("監視を停止しました", icon="🛑")
            st.rerun()

    st.divider()
    st.subheader("トラブルシュート")
    st.markdown(
        """
- **反応しない**: Windowsなら Streamlit を **管理者** で実行。
- **Fn+F1が取れない**: Fn は多くのキーボードで OS に届きません（`ctrl+alt+f1` でテスト）。
- **Chromeが起動しない**: `run_cmd` にして Chrome のフルパス指定。
  - 例: `"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" https://chat.openai.com`
- **cmd を開く**: 動作タイプ `open_cmd` を選択（value不要）
""".strip()
    )
    st.markdown("</div>", unsafe_allow_html=True)

if listener_running():
    soft_autorefresh(interval_sec=0.5)