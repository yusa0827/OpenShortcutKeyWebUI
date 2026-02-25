# listener.py (Windows API版: RegisterHotKey + WM_HOTKEY)
# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes
import json
import time
import subprocess
import threading
import queue
from pathlib import Path

# ====== 設定 ======
CONFIG_PATH = Path("shortcut_config.json")

POLL_INTERVAL_SEC = 0.5   # 設定ファイル更新チェック間隔
DEBOUNCE_SEC = 0.30       # 同一hotkeyの連打抑止（秒）

# Windows constants
WM_HOTKEY = 0x0312

MOD_ALT     = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT   = 0x0004
MOD_WIN     = 0x0008
MOD_NOREPEAT = 0x4000  # Win7以降: キー押しっぱなしのリピート抑制（効く環境なら効く）

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def open_url(url: str) -> None:
    # 既存コード踏襲（chrome起動）
    subprocess.Popen(f'start chrome "{url}"', shell=True)


def run_cmd(cmd: str) -> None:
    subprocess.Popen(cmd, shell=True)


def execute(sc: dict) -> None:
    title = sc.get("title", "")
    hotkey = sc.get("hotkey", "")
    action_type = sc.get("action_type", "run_cmd")
    value = sc.get("value", "")
    print(f"[EXEC] {title} | {hotkey} | {action_type} | {value}")

    # トリガーが走った証拠（Windows標準音）
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass

    # トリガーが走った証拠（ファイル更新）
    try:
        Path("last_trigger.txt").write_text(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {title} | {hotkey}\n",
            encoding="utf-8"
        )
    except Exception:
        pass

    # 実行本体
    if action_type == "open_url":
        open_url(value)
    else:
        run_cmd(value)


def load_shortcuts() -> list[dict]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    shortcuts = data.get("shortcuts", [])
    if not isinstance(shortcuts, list):
        raise ValueError("shortcuts must be a list")

    out: list[dict] = []
    for sc in shortcuts:
        hk = (sc.get("hotkey") or "").strip().lower()
        if not hk:
            continue
        item = dict(sc)
        item["hotkey"] = hk
        out.append(item)
    return out


# ---- Hotkey parsing (e.g. "ctrl+alt+f13") ----
def vk_from_key_name(key: str) -> int:
    """
    よく使うキーだけ対応（必要なら追加OK）
    """
    key = key.lower().strip()

    # Fx
    if key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)  # F1=0x70 ... F24=0x87

    # A-Z
    if len(key) == 1 and "a" <= key <= "z":
        return ord(key.upper())

    # 0-9
    if len(key) == 1 and "0" <= key <= "9":
        return ord(key)

    # 少しだけ特殊キー
    special = {
        "tab": 0x09,
        "enter": 0x0D,
        "return": 0x0D,
        "esc": 0x1B,
        "escape": 0x1B,
        "space": 0x20,
        "backspace": 0x08,
        "delete": 0x2E,
        "ins": 0x2D,
        "insert": 0x2D,
        "home": 0x24,
        "end": 0x23,
        "pgup": 0x21,
        "pageup": 0x21,
        "pgdn": 0x22,
        "pagedown": 0x22,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
    }
    if key in special:
        return special[key]

    raise ValueError(f"Unsupported key: {key!r} (try f1-f24, a-z, 0-9, tab/enter/esc/space etc.)")


def parse_hotkey(hotkey: str) -> tuple[int, int]:
    """
    returns: (modifiers, vk)
    hotkey examples:
      - "f13"
      - "ctrl+f13"
      - "ctrl+alt+f13"
      - "win+shift+f13"
    """
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")

    mods = 0
    key_part = None

    for p in parts:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p in ("alt",):
            mods |= MOD_ALT
        elif p in ("shift",):
            mods |= MOD_SHIFT
        elif p in ("win", "windows", "meta"):
            mods |= MOD_WIN
        else:
            # 最後に残ったものをキーとみなす（複数あるならエラー）
            if key_part is not None:
                raise ValueError(f"hotkey has multiple keys: {hotkey!r}")
            key_part = p

    if key_part is None:
        raise ValueError(f"no key specified in hotkey: {hotkey!r}")

    vk = vk_from_key_name(key_part)

    # 押しっぱなしリピート抑制（効く環境なら効く）
    mods |= MOD_NOREPEAT

    return mods, vk


class HotkeyListener:
    """
    RegisterHotKey でホットキー登録し、
    WM_HOTKEY を受け取って実行キューへ積む。
    """
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._id_to_sc: dict[int, dict] = {}
        self._registered_ids: set[int] = set()
        self._next_id = 1

        self._job_q: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()

        self._last_fire: dict[str, float] = {}

        self._worker_th = threading.Thread(target=self._worker, daemon=True)
        self._worker_th.start()

    def stop(self) -> None:
        self._stop.set()

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                sc = self._job_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                execute(sc)
            except Exception as e:
                print("[EXEC] failed:", e)
            finally:
                self._job_q.task_done()

    def _enqueue(self, sc: dict) -> None:
        hk = sc.get("hotkey", "")
        now = time.time()
        last = self._last_fire.get(hk, 0.0)
        if hk and (now - last) < DEBOUNCE_SEC:
            return
        self._last_fire[hk] = now
        self._job_q.put(sc)

    def unregister_all(self) -> None:
        with self._lock:
            for hid in list(self._registered_ids):
                try:
                    user32.UnregisterHotKey(None, hid)
                except Exception:
                    pass
            self._registered_ids.clear()
            self._id_to_sc.clear()
            self._next_id = 1

    def register_shortcuts(self, shortcuts: list[dict]) -> None:
        """
        いったん全解除してから再登録（安全）
        """
        with self._lock:
            self.unregister_all()

            for sc in shortcuts:
                hk = sc.get("hotkey", "")
                try:
                    mods, vk = parse_hotkey(hk)
                except Exception as e:
                    print(f"[LISTENER] skip invalid hotkey {hk!r}: {e}")
                    continue

                hid = self._next_id
                self._next_id += 1

                ok = user32.RegisterHotKey(None, hid, mods, vk)
                if not ok:
                    err = kernel32.GetLastError()
                    print(f"[LISTENER] RegisterHotKey failed: {hk!r} (id={hid}) err={err}")
                    continue

                self._registered_ids.add(hid)
                self._id_to_sc[hid] = sc

            print(f"[LISTENER] registered {len(self._registered_ids)} hotkeys")

    def message_loop_tick(self) -> None:
        """
        WM_HOTKEY を非ブロッキングで処理（PeekMessage）
        """
        msg = wintypes.MSG()
        # 0x0001 = PM_REMOVE
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001) != 0:
            if msg.message == WM_HOTKEY:
                hid = int(msg.wParam)
                sc = None
                with self._lock:
                    sc = self._id_to_sc.get(hid)
                if sc is not None:
                    self._enqueue(sc)

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


def main() -> None:
    print("[LISTENER] start (Ctrl+C to stop) [WinAPI RegisterHotKey]")

    listener = HotkeyListener()

    # 初回ロード（設定が無ければ待つ）
    last_err = None
    shortcuts: list[dict] = []
    while True:
        try:
            shortcuts = load_shortcuts()
            listener.register_shortcuts(shortcuts)
            break
        except Exception as e:
            if str(e) != str(last_err):
                print("[LISTENER] wait config...", e)
                last_err = e
            time.sleep(1)

    # 変更監視用
    last_mtime = None
    try:
        last_mtime = CONFIG_PATH.stat().st_mtime
    except FileNotFoundError:
        last_mtime = None

    try:
        while True:
            # WM_HOTKEY を捌く
            listener.message_loop_tick()

            # 設定ファイル更新を監視
            try:
                mtime = CONFIG_PATH.stat().st_mtime
            except FileNotFoundError:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            if last_mtime is None:
                last_mtime = mtime
            elif mtime != last_mtime:
                last_mtime = mtime
                try:
                    shortcuts = load_shortcuts()
                    listener.register_shortcuts(shortcuts)
                    print("[LISTENER] config reloaded")
                except Exception as e:
                    print("[LISTENER] reload failed:", e)

            time.sleep(POLL_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\n[LISTENER] stopping...")
    finally:
        listener.unregister_all()
        listener.stop()


if __name__ == "__main__":
    main()