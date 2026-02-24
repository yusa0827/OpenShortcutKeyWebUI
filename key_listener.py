# listener.py
# -*- coding: utf-8 -*-
import json
import time
import subprocess
from pathlib import Path

import keyboard

CONFIG_PATH = Path("shortcut_config.json")


def open_url(url: str) -> None:
    subprocess.Popen(f'start chrome "{url}"', shell=True)


def run_cmd(cmd: str) -> None:
    subprocess.Popen(cmd, shell=True)


def execute(sc: dict) -> None:
    title = sc.get("title", "")
    hotkey = sc.get("hotkey", "")
    action_type = sc.get("action_type", "run_cmd")
    value = sc.get("value", "")
    print(f"[EXEC] {title} | {hotkey} | {action_type} | {value}")

    # ★トリガーが走った証拠（標準Windows音）
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass

    # ★トリガーが走った証拠（小さいファイルを更新）
    try:
        from pathlib import Path
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

    out = []
    for sc in shortcuts:
        hk = (sc.get("hotkey") or "").strip().lower()
        if not hk:
            continue
        sc = dict(sc)
        sc["hotkey"] = hk
        out.append(sc)
    return out


def register_hotkeys(shortcuts: list[dict]) -> list[int]:
    hook_ids: list[int] = []
    for sc in shortcuts:
        hk = sc["hotkey"]
        hid = keyboard.add_hotkey(hk, lambda s=sc: execute(s))
        hook_ids.append(hid)
    return hook_ids


def unregister_hotkeys(hook_ids: list[int]) -> None:
    for hid in hook_ids:
        try:
            keyboard.remove_hotkey(hid)
        except Exception:
            pass


def main() -> None:
    print("[LISTENER] start (Ctrl+C to stop)")
    hook_ids: list[int] = []

    # 初回ロード（設定が無ければ待つ）
    last_err = None
    while True:
        try:
            shortcuts = load_shortcuts()
            hook_ids = register_hotkeys(shortcuts)
            print(f"[LISTENER] registered {len(hook_ids)} keys (initial)")
            break
        except Exception as e:
            if str(e) != str(last_err):
                print("[LISTENER] wait config...", e)
                last_err = e
            time.sleep(1)

    # ファイル更新時だけ貼り替え
    last_mtime = CONFIG_PATH.stat().st_mtime
    try:
        while True:
            time.sleep(0.5)

            try:
                mtime = CONFIG_PATH.stat().st_mtime
            except FileNotFoundError:
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    shortcuts = load_shortcuts()
                    unregister_hotkeys(hook_ids)
                    hook_ids = register_hotkeys(shortcuts)
                    print(f"[LISTENER] config reloaded, registered {len(hook_ids)} keys")
                except Exception as e:
                    print("[LISTENER] reload failed:", e)

    except KeyboardInterrupt:
        print("\n[LISTENER] stopping...")
    finally:
        unregister_hotkeys(hook_ids)


if __name__ == "__main__":
    main()