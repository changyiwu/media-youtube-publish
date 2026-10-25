#!/usr/bin/env python3
"""驗證「正本在本 repo、副本在隔壁專案」的檔案逐位元一致。

背景：發布資訊範本是五個媒體專案共用的，正本在本 repo，另外四個專案各放一份副本
（見 AGENTS.md）。改了正本卻忘了覆蓋副本，各專案就會悄悄用到舊範本——這支把
「記得同步」從人腦移到機器。

本 repo 內的技能已經沒有腳本副本：技能都在專案內使用，長片、短片直接引用
audio-to-srt 等技能的腳本，不再各帶一份。

用法：
    python check_sync.py            # 不一致就 exit 1
    python check_sync.py --quiet    # 只印問題

不引入第三方套件、維持 Python 3.9+ 相容（見 AGENTS.md〈相容性〉）。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

# (本 repo skills/ 內的正本, [相對 agents/ 的副本路徑, ...])。改正本後整份覆蓋到各副本。
# 副本所在專案不在這台就略過，不算錯。
DOWNSTREAM = [
    (
        "youtube-long/references/發布資訊範本.md",
        [
            "media-short-film/templates/發布資訊範本.md",
            "media-3d-studio/templates/發布資訊範本.md",
            "media-music-video/templates/發布資訊範本.md",
            "media-video-specs/templates/發布資訊範本.md",
        ],
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(skills_root: Path, quiet: bool = False) -> int:
    # skills/ -> media-youtube-publish/ -> agents/
    agents_root = skills_root.parent.parent
    problems = []
    checked = 0

    for local_rel, copies in DOWNSTREAM:
        local = skills_root / local_rel
        if not local.is_file():
            problems.append("[ERR] 正本不存在：{}".format(local_rel))
            continue
        for copy_rel in copies:
            copy = agents_root / copy_rel
            if not copy.parent.parent.is_dir():
                continue  # 這台沒有那個專案
            checked += 1
            if not copy.is_file():
                problems.append("[ERR] 副本不存在：{}（從 {} 複製過去）".format(copy_rel, local_rel))
            elif sha256(local) != sha256(copy):
                problems.append(
                    "[ERR] 副本與正本不一致：{}  ≠  {}（以正本為準，整份覆蓋過去）".format(copy_rel, local_rel)
                )
            elif not quiet:
                print("[OK] {}（= {}）".format(copy_rel, local_rel))

    if problems:
        print("")
        for line in problems:
            print(line)
        print("")
        print("[ERR] 跨專案副本與正本不同步。修正方式：把正本整份複製過去。")
        return 1

    if checked == 0:
        print("[SKIP] 這台沒有任何副本所在的專案，未做同步驗證")
        return 0

    print("[OK] 跨專案副本與正本一致（比對 {} 個檔案）".format(checked))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="檢查跨專案副本是否與本 repo 的正本一致")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="技能根目錄；預設由本檔位置往上推兩層",
    )
    parser.add_argument("--quiet", action="store_true", help="只印問題")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # scripts/check_sync.py -> youtube-long -> skills/
    skills_root = args.skills_root or Path(__file__).resolve().parents[2]
    return check(skills_root, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
