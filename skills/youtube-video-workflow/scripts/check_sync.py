#!/usr/bin/env python3
"""驗證總控技能自帶的可攜腳本，與各單步驟技能的原始檔逐位元一致。

背景：`youtube-video-workflow` 是「自帶腳本的可攜版本」，刻意複製一份單步驟技能的
腳本與參考檔（見 AGENTS.md）。重複是設計選擇，代價是改了一邊忘了另一邊——這支就是
把「記得同步」從人腦移到機器。

用法：
    python check_sync.py            # 不一致就 exit 1
    python check_sync.py --quiet    # 只印問題

不引入第三方套件、維持 Python 3.9+ 相容（見 AGENTS.md〈相容性〉）。
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

# 必須與總控保持一致的檔案。
# 格式：單步驟技能名 -> [(該技能內的相對路徑, 總控內的相對路徑), ...]
# 兩邊路徑分開寫，是因為 cleanup_rules.md / cleanup-rules.md 底線與連字號不同名。
MANIFEST = {
    "smart-cut": [
        ("scripts/smart_cut.py", "scripts/smart_cut.py"),
    ],
    "audio-to-srt": [
        ("scripts/apply_vocab.py", "scripts/apply_vocab.py"),
        ("scripts/resegment.py", "scripts/resegment.py"),
        ("scripts/srt_to_txt.py", "scripts/srt_to_txt.py"),
        ("scripts/transcribe_groq.py", "scripts/transcribe_groq.py"),
        ("scripts/transcribe_local.py", "scripts/transcribe_local.py"),
        ("scripts/validate_srt.py", "scripts/validate_srt.py"),
        ("references/replacements.md", "references/replacements.md"),
        ("references/vocabulary.md", "references/vocabulary.md"),
        ("references/cleanup_rules.md", "references/cleanup-rules.md"),
    ],
    "video-editing-and-subtitles": [
        ("scripts/finalize_subtitles.py", "scripts/finalize_subtitles.py"),
        ("scripts/find_dubious_terms.py", "scripts/find_dubious_terms.py"),
    ],
    "short-video-workflow": [
        ("scripts/add_end_card.py", "scripts/add_end_card.py"),
        ("scripts/burn_subtitles.py", "scripts/burn_subtitles.py"),
        ("scripts/clip_cut.py", "scripts/clip_cut.py"),
        ("scripts/make_vertical.py", "scripts/make_vertical.py"),
    ],
}

# 刻意不共用的檔案，不列入清單漂移警告。
EXEMPT = {
    "audio-to-srt": {"scripts/test_cross_segment.py"},
}

WORKFLOW_SKILL = "youtube-video-workflow"
WATCHED_DIRS = ("scripts", "references")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_watched(skill_dir: Path):
    """列出技能內受監看的檔案（相對路徑），略過衍生物。"""
    for sub in WATCHED_DIRS:
        base = skill_dir / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            yield path.relative_to(skill_dir).as_posix()


def check(skills_root: Path, quiet: bool = False) -> int:
    workflow_dir = skills_root / WORKFLOW_SKILL
    if not workflow_dir.is_dir():
        print("[SKIP] 找不到 {} 技能，跳過同步檢查".format(WORKFLOW_SKILL))
        return 0

    problems = []
    checked = 0
    skipped_skills = []

    for skill, pairs in MANIFEST.items():
        skill_dir = skills_root / skill
        if not skill_dir.is_dir():
            # 全域安裝環境可能只裝了總控，這不是錯誤。
            skipped_skills.append(skill)
            continue

        registered = set()
        for src_rel, wf_rel in pairs:
            registered.add(src_rel)
            src = skill_dir / src_rel
            dst = workflow_dir / wf_rel

            if not src.is_file():
                problems.append("[ERR] 原始檔不存在：{}/{}".format(skill, src_rel))
                continue
            if not dst.is_file():
                problems.append(
                    "[ERR] 總控缺少對應檔：{}/{}（來源 {}/{}）".format(
                        WORKFLOW_SKILL, wf_rel, skill, src_rel
                    )
                )
                continue

            checked += 1
            if sha256(src) != sha256(dst):
                problems.append(
                    "[ERR] 內容不一致：{}/{}  ≠  {}/{}".format(
                        skill, src_rel, WORKFLOW_SKILL, wf_rel
                    )
                )
            elif not quiet:
                print("[OK] {}/{}".format(skill, src_rel))

        # 清單漂移：技能裡新增了檔案卻沒登記，會靜默地不被檢查。
        for rel in iter_watched(skill_dir):
            if rel in registered or rel in EXEMPT.get(skill, set()):
                continue
            problems.append(
                "[ERR] 未登記的檔案：{}/{}"
                "（新增後請決定要不要共用：要共用就複製到總控並登記進 MANIFEST，"
                "不共用就加進 EXEMPT）".format(skill, rel)
            )

    if skipped_skills and not quiet:
        print("[SKIP] 未找到下列技能，略過：{}".format("、".join(skipped_skills)))

    if problems:
        print("")
        for line in problems:
            print(line)
        print("")
        print("[ERR] 可攜副本與原始檔不同步。修正方式：確認哪一邊是新的，複製過去讓兩邊一致。")
        return 1

    if checked == 0:
        print("[SKIP] 沒有可比對的檔案（單步驟技能都不在旁邊），未做同步驗證")
        return 0

    print("[OK] 可攜副本與原始檔一致（比對 {} 個檔案）".format(checked))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="檢查總控可攜副本是否與單步驟技能同步")
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="技能根目錄；預設由本檔位置往上推兩層",
    )
    parser.add_argument("--quiet", action="store_true", help="只印問題")
    args = parser.parse_args()

    # scripts/check_sync.py -> youtube-video-workflow -> skills/
    skills_root = args.skills_root or Path(__file__).resolve().parents[2]
    return check(skills_root, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
