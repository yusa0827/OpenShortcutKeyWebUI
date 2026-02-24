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
    action_type: str  # "open_url" / "run_cmd"
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


# ===============================
# 設定 I/O（旧互換あり）
# ===============================
def _normalize_hotkey(hk: str) -> str:
    return (hk or "").strip().lower()


def load_config() -> List[Shortcut]:
    """
    旧フォーマット互換:
      - title が無い → title = hotkey
      - id が無い → 自動生成
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
        action_type = (item.get("action_type") or "run_cmd").strip()
        value = (item.get("value") or "").strip()

        title = item.get("title")
        if not title:
            title = hotkey or "Unnamed"

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
    data = {"shortcuts": [asdict(s) for s in shortcuts]}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ===============================
# 実行処理
# ===============================
def open_url_in_chrome(url: str) -> None:
    subprocess.Popen(f'start chrome "{url}"', shell=True)


def run_command(cmd: str) -> None:
    subprocess.Popen(cmd, shell=True)


def execute(sc: Shortcut) -> None:
    print(f"[EXEC] {sc.title} | {sc.hotkey} | {sc.action_type} | {sc.value}")
    if sc.action_type == "open_url":
        open_url_in_chrome(sc.value)
    else:
        run_command(sc.value)


# ===============================
# 常駐監視スレッド（安全解除）
# ===============================
def listener_loop(shortcuts: List[Shortcut], stop_event: threading.Event, status: Dict[str, str]) -> None:
    # 環境によって unhook_all_hotkeys が例外になるので守る
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

    # 自動更新用（古いStreamlit向け）
    if "ui_last_tick" not in st.session_state:
        st.session_state.ui_last_tick = 0.0


def listener_running() -> bool:
    t = st.session_state.listener_thread
    return t is not None and t.is_alive()


def start_listener_from_saved_config() -> None:
    if listener_running():
        return

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


# ===============================
# 古いStreamlit向け 自動更新（擬似オートリフレッシュ）
# ===============================
def soft_autorefresh(interval_sec: float = 0.5) -> None:
    """
    追加インストールなしで、一定間隔ごとに st.rerun() する。
    ただし負荷を避けるため、監視が動いている時だけ回すのが基本。
    """
    now = time.time()
    if now - st.session_state.ui_last_tick >= interval_sec:
        st.session_state.ui_last_tick = now
        # 次の実行で状態が反映される
        st.rerun()


# ===============================
# WebUI
# ===============================
st.set_page_config(page_title="OpenShortcutKeyWebUI", layout="wide")
ensure_state()

st.title("ショートカット設定 WebUI（統合版 / 安定版）")
st.caption("設定(UI)と常駐監視(実行)を同じPythonプロセスで動かします。保存と監視は分離。")

left, right = st.columns([1.25, 1])

# -------------------------------
# 左: 編集・追加・保存
# -------------------------------
with left:
    st.subheader("① ショートカット一覧（編集）")

    for sc in list(st.session_state.shortcuts):
        with st.expander(f"{sc.title}  ({sc.hotkey})", expanded=True):
            sc.title = st.text_input("タイトル", sc.title, key=f"title_{sc.id}")

            sc.hotkey = st.text_input(
                "ホットキー（例: f13 / ctrl+alt+f1）",
                sc.hotkey,
                key=f"hotkey_{sc.id}",
            )
            sc.hotkey = _normalize_hotkey(sc.hotkey)

            sc.action_type = st.selectbox(
                "動作タイプ",
                ["open_url", "run_cmd"],
                index=0 if sc.action_type == "open_url" else 1,
                key=f"type_{sc.id}",
                help="open_url: ChromeでURLを開く / run_cmd: コマンド実行",
            )

            sc.value = st.text_input(
                "URL または コマンド",
                sc.value,
                key=f"value_{sc.id}",
                help='例(URL): https://chat.openai.com / 例(コマンド): notepad',
            )

            if st.button("この項目を削除", key=f"del_{sc.id}"):
                st.session_state.shortcuts = [x for x in st.session_state.shortcuts if x.id != sc.id]
                st.rerun()

    st.divider()

    st.subheader("② 追加")
    with st.form("add_form", clear_on_submit=True):
        title = st.text_input("タイトル", "New Shortcut")
        hotkey = st.text_input("ホットキー（例: f13 / ctrl+alt+f1）", "f14")
        action_type = st.selectbox("動作タイプ", ["open_url", "run_cmd"])
        value = st.text_input("URL または コマンド", "https://chat.openai.com")
        ok = st.form_submit_button("追加する")

        if ok:
            st.session_state.shortcuts.append(
                Shortcut(
                    id=new_id(),
                    title=title.strip() or "Untitled",
                    hotkey=_normalize_hotkey(hotkey),
                    action_type=action_type,
                    value=value.strip(),
                )
            )
            st.rerun()

    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("設定を保存（変更を確定）"):
            save_config(st.session_state.shortcuts)
            st.success(f"保存しました: {CONFIG_PATH}")

    with c2:
        if st.button("初期状態に戻す"):
            st.session_state.shortcuts = [Shortcut(**asdict(s)) for s in DEFAULT_SHORTCUTS]
            save_config(st.session_state.shortcuts)
            st.success("初期状態に戻しました")
            st.rerun()

    with c3:
        if st.button("テスト: ChatGPTを開く（即時実行）"):
            open_url_in_chrome("https://chat.openai.com")
            st.info("ChromeでChatGPTを開きました（即時実行）")


# -------------------------------
# 右: 監視開始/停止 + 状態表示
# -------------------------------
with right:
    st.subheader("③ 常駐監視（ホットキーを受けて実行）")

    state = st.session_state.listener_status.get("state", "stopped")
    msg = st.session_state.listener_status.get("msg", "停止中")

    if state == "running":
        st.success(msg)
    elif state == "warning":
        st.warning(msg)
    else:
        st.info(msg)

    st.write(
        "注意: `f13` は物理キーボードに無いことが多いので、"
        "今は `ctrl+alt+f1` などでも動作確認できます。"
    )

    b1, b2 = st.columns(2)
    with b1:
        if st.button("監視を開始（保存済み設定で起動）"):
            start_listener_from_saved_config()
            st.success("監視を開始しました（保存済み設定を使用）")
            st.rerun()

    with b2:
        if st.button("監視を停止"):
            stop_listener()
            st.success("監視を停止しました")
            st.rerun()

    st.divider()
    st.subheader("トラブル時のポイント")
    st.markdown(
        """
- **ホットキーが反応しない**: Windowsなら Streamlit を **管理者** で実行してみてください。
- **Fn+F1が取れない**: Fn は多くのキーボードで OS に届きません。`ctrl+alt+f1` などでテスト推奨。
- **Chromeが起動しない**: `run_cmd` にして Chrome のフルパスで起動してください。
  - 例: `"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" https://chat.openai.com`
"""
    )

# ★ 監視中だけ、UIを定期更新してステータスが追従するようにする（追加インストール不要）
if listener_running():
    soft_autorefresh(interval_sec=0.5)