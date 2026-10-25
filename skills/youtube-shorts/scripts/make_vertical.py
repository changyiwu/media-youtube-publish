#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_vertical.py - 16:9 短片轉 9:16 直式（YouTube Shorts 用）。

做法（模糊背景填充，內容不裁切）：
  1. 同一畫面複製兩路：一路放大裁滿 1080x1920 再高斯模糊當背景，
     一路等比縮到寬 1080 置中當前景。
  2. 內容完整保留（螢幕示範不能裁掉 UI），上下由模糊背景補滿。
  3. 輸入建議用「已燒字幕版」，字幕直接跟著前景走，不用重燒。

用法：
  python make_vertical.py 輸入.mp4 --out 輸出_直式9x16.mp4
"""
import argparse
import subprocess
import sys
from pathlib import Path

FILTER = (
    "[0:v]split=2[a][b];"
    "[a]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,gblur=sigma=25[bg];"
    "[b]scale=1080:-2[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
)


def main() -> int:
    ap = argparse.ArgumentParser(description="16:9 短片轉 9:16 直式（模糊背景填充）")
    ap.add_argument("input", type=Path, help="輸入 mp4（建議用已燒字幕版）")
    ap.add_argument("--out", type=Path, required=True, help="輸出 mp4")
    ap.add_argument("--crf", type=int, default=20)
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"[ERR] 找不到輸入檔：{args.input}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(args.input),
        "-filter_complex", FILTER,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        str(args.out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(r.stderr[-800:])
        sys.exit(f"[ERR] ffmpeg 轉檔失敗：{args.out}")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(args.out)],
        capture_output=True, text=True, errors="replace",
    )
    res = probe.stdout.strip()
    if res != "1080,1920":
        sys.exit(f"[ERR] 輸出解析度異常：{res}（應為 1080,1920）")
    print(f"[OK] 直式輸出 {args.out}（1080x1920）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
