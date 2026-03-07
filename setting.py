"""依存モジュールのインストール/バージョン確認スクリプト。

実行方法:
  python setting.py
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Dict

REQUIRED_PACKAGES = {
    "streamlit": "1.54.0",
    "keyboard": "0.13.5",
    "pystray": "0.19.5",
}


def install_packages() -> None:
    """requirements.txt から依存関係をインストールする。"""
    print("[INFO] 依存モジュールをインストールします...")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
        ]
    )


def get_installed_versions() -> Dict[str, str]:
    """インストール済みバージョンを取得する。"""
    versions: Dict[str, str] = {}
    for module_name in REQUIRED_PACKAGES:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "unknown")
        versions[module_name] = str(version)
    return versions


def verify_versions() -> bool:
    """必要バージョンと一致しているか確認する。"""
    installed = get_installed_versions()

    print("\n[INFO] モジュールの動作確認バージョン")
    all_ok = True

    for name, required in REQUIRED_PACKAGES.items():
        current = installed.get(name, "unknown")
        status = "OK" if current == required else "NG"
        print(f"- {name:<10} required={required:<8} installed={current:<8} [{status}]")
        if current != required:
            all_ok = False

    return all_ok


def main() -> None:
    try:
        install_packages()
        ok = verify_versions()
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] pip install に失敗しました: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] 予期しないエラー: {exc}")
        sys.exit(1)

    if ok:
        print("\n[SUCCESS] 依存モジュールのインストールとバージョン確認が完了しました。")
        sys.exit(0)

    print("\n[WARNING] インストールは完了しましたが、指定バージョンと一致しないモジュールがあります。")
    sys.exit(2)


if __name__ == "__main__":
    main()
