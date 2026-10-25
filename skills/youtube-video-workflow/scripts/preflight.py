#!/usr/bin/env python3
"""檢查 YouTube 影片工作流執行環境；不輸出任何 API key。"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def tool_status(name: str) -> bool:
    path = shutil.which(name)
    if path:
        print(f"[OK] {name}: {path}")
        return True
    print(f"[ERR] 找不到 {name}，請安裝並加入 PATH")
    return False


def auto_editor_status() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "auto_editor", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        print(f"[ERR] auto-editor 無法啟動：{exc}")
        return False

    combined = (result.stdout or "") + (result.stderr or "")
    # `python -m auto_editor --version` 正常時 exit code 是 255，不能拿 returncode 判斷；
    # 但模組不存在時 stderr 會是 "No module named auto_editor"，必須擋掉，
    # 否則會把錯誤訊息當成版本號印成 [OK]。
    if "No module named" not in combined:
        output = (result.stdout or result.stderr).strip().splitlines()
        if output:
            print(f"[OK] auto-editor: {output[0]}")
            return True

    exe = shutil.which("auto-editor")
    if exe:
        print(f"[OK] auto-editor: {exe}")
        return True

    print("[ERR] 找不到 auto-editor；請執行 python -m pip install auto-editor")
    return False


def groq_key_status() -> bool:
    if os.environ.get("GROQ_API_KEY", "").strip():
        print("[OK] Groq API key: 已由環境變數提供")
        return True
    key_file = Path.home() / ".groq_api_key"
    try:
        present = key_file.is_file() and bool(key_file.read_text(encoding="utf-8").strip())
    except OSError:
        present = False
    if present:
        print(f"[OK] Groq API key: 已由 {key_file} 提供")
        return True
    print("[WARN] 找不到 Groq API key；Groq 字幕路線無法使用")
    print("       請設定 GROQ_API_KEY 或建立 ~/.groq_api_key；不要把 key 貼到對話中")
    return False


def local_whisper_status() -> bool:
    """本地 Whisper 路線（transcribe_local.py）的引擎有沒有裝。

    只看套件找不找得到、不真的載入：import faster_whisper 要好幾秒，而且 GPU 能不能用
    要到第一次推論才知道，那一層交給 transcribe_local.py 自己退回 CPU。
    """
    for module, package in (("faster_whisper", "faster-whisper"), ("whisper", "openai-whisper")):
        if importlib.util.find_spec(module) is not None:
            print(f"[OK] 本地 Whisper: {package}")
            return True
    print("[WARN] 沒有本地 Whisper 引擎；本地字幕路線無法使用")
    print("       需要時執行 python -m pip install faster-whisper")
    return False


def sync_status() -> bool:
    """檢查總控自帶的可攜副本是否與單步驟技能一致。

    刻意只警告、不擋關：副本不同步會讓產出偷偷用到舊版腳本，但不影響「這台機器跑不跑得動」，
    而 preflight 判定的是後者。要當硬關卡時直接跑 check_sync.py（不一致會 exit 1）。
    """
    try:
        from check_sync import check
    except ImportError as exc:
        print(f"[WARN] 無法載入 check_sync：{exc}")
        return False

    skills_root = Path(__file__).resolve().parents[2]
    if check(skills_root, quiet=True) != 0:
        print("[WARN] 上列副本不同步；剪輯仍可執行，但流程可能用到舊版腳本")
        return False
    return True


def main() -> int:
    print(f"[OK] Python: {sys.version.split()[0]} ({sys.executable})")
    python_ok = sys.version_info >= (3, 10)
    if not python_ok:
        print("[ERR] 需要 Python 3.10 以上")

    ffmpeg_ok = tool_status("ffmpeg")
    ffprobe_ok = tool_status("ffprobe")
    editor_ok = auto_editor_status()
    groq_ok = groq_key_status()
    local_ok = local_whisper_status()
    sync_status()

    required_ok = python_ok and ffmpeg_ok and ffprobe_ok and editor_ok
    if required_ok:
        if groq_ok or local_ok:
            print("[OK] 剪輯與字幕環境可用")
        else:
            print("[WARN] 剪輯環境可用，但 Groq 與本地 Whisper 都沒有，字幕步驟會停止")
        return 0
    print("[ERR] 前置檢查未通過，請先修正必要項目")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
