#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""依「人工語意切點」重建字幕（resegment.py 的替代方案）。

移植自 mathruffian-dot/audio-to-srt（ddc560c，MIT，Copyright (c) 2026 mathruffian-dot），
授權全文見 ../THIRD_PARTY_NOTICES.md。

什麼時候用這支：
  resegment.py 的切點優先序是 強標點 > segment 邊界 > 弱標點 > 硬切。
  Whisper 幾乎不輸出標點時（直播、口語逐字稿常見）前三層全部落空，退化成純字數硬切，
  產生「…有沒有這個應用程式目前在」「版的 Chrome 網頁裡面找到這個安裝並建」這種段落。

做法：
  1. 讀完整份逐字稿，依語意寫出一行一句的切點檔
  2. 驗證「切點檔逐字串接 == 轉錄原文」，不符即中止（所以時間碼不可能對錯）
  3. 走訪 word-level 時間碼，把字分配到各段；切點落在一個詞中間時依字數內插
  4. 依等效中文字寬（中文 1、其餘 0.5，標點不計）估算所需秒數，
     只在下一句開始前的空隙內延長顯示時間，絕不吃掉下一句

用法：
  python build_subs_manual.py <raw.json> --dump-text [--traditional]
  python build_subs_manual.py <raw.json> --segments segments.txt --out raw.srt \\
      [--fixes fixes.tsv] [--traditional] [--rate 7.0] [--min-dur 0.8]

  segments.txt：一行一句，內容必須與轉錄原文逐字相符（空白會被忽略）
  fixes.tsv：每行 `舊字串<TAB>新字串`，只套用在顯示文字上，不影響對齊
  --traditional：先用 opencc s2twp 轉繁（需要 opencc-python-reimplemented）

輸出就是 raw.srt，接著走 apply_vocab → 清字 → validate_srt，流程與 resegment 相同。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from resegment import is_cjk, write_srt


def load_words(path: Path, traditional: bool):
    data = json.loads(path.read_text(encoding="utf-8"))
    words = data.get("words") or []
    if not words:
        sys.exit("[ERR] JSON 內沒有 words（word-level 時間碼），本腳本無法運作")
    if traditional:
        try:
            from opencc import OpenCC
        except ImportError:
            sys.exit("[ERR] --traditional 需要 opencc：python -m pip install opencc-python-reimplemented")
        cc = OpenCC("s2twp")
        for w in words:
            w["word"] = cc.convert(w["word"])
    return words


def dump_text(words) -> None:
    """印出含停頓標記的原文（⏸ 明顯停頓、· 短停頓），供人工決定切點。"""
    out = []
    for i, w in enumerate(words):
        out.append(w["word"])
        if i + 1 < len(words):
            gap = words[i + 1]["start"] - w["end"]
            if gap >= 0.60:
                out.append(f"⏸{gap:.1f}⏸")
            elif gap >= 0.30:
                out.append("·")
    print("".join(out))


def strip_space(text: str) -> str:
    return re.sub(r"\s+", "", text)


def width(text: str) -> float:
    """等效中文字寬：中文 1、其餘 0.5（標點不計）。"""
    return sum(1 if is_cjk(c) else 0.5 for c in re.sub(r"[\s,，、。?？!！]", "", text))


def char_timeline(words):
    """把 words 攤成逐字清單：[(字, 開始, 結束), ...]，一個詞的時長依字數平分。"""
    chars = []
    for w in words:
        text = strip_space(w["word"])
        step = (w["end"] - w["start"]) / len(text) if text else 0.0
        for k, ch in enumerate(text):
            chars.append((ch, w["start"] + k * step, w["start"] + (k + 1) * step))
    return chars


def report_mismatch(joined: str, raw: str) -> None:
    print("[ERR] 切點檔與原文不一致，拒絕輸出（避免時間碼錯位）", file=sys.stderr)
    for i, (a, b) in enumerate(zip(joined, raw)):
        if a != b:
            print(f"      第 {i} 字起不同：", file=sys.stderr)
            print(f"        切點檔：{joined[i:i + 40]}", file=sys.stderr)
            print(f"        原文  ：{raw[i:i + 40]}", file=sys.stderr)
            return
    print(f"      長度不同：切點檔 {len(joined)} vs 原文 {len(raw)}", file=sys.stderr)


def load_fixes(path: Path):
    fixes = []
    for ln in path.read_text(encoding="utf-8-sig").splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        old, _, new = ln.partition("\t")
        fixes.append((old, new))
    return fixes


def build_entries(segs, chars, fixes):
    entries, pos = [], 0
    for seg in segs:
        n = len(strip_space(seg))
        text = seg
        for old, new in fixes:
            text = text.replace(old, new)
        entries.append([chars[pos][1], chars[pos + n - 1][2], text.strip().rstrip(",，")])
        pos += n
    return entries


def extend_display(entries, rate: float, min_dur: float) -> int:
    """顯示時間不足時往後延長，只用到下一句開始前的空隙；回傳延長的段數。"""
    n_ext = 0
    for i, e in enumerate(entries):
        nxt = entries[i + 1][0] if i + 1 < len(entries) else e[1] + 2.0
        need = max(min_dur, width(e[2]) / rate)
        if e[1] - e[0] < need:
            new_end = min(e[0] + need, nxt - 0.05)
            if new_end > e[1]:
                e[1] = new_end
                n_ext += 1
    return n_ext


def main() -> int:
    # Windows 預設 cp950，印不出 ⏸
    sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("json_file", type=Path)
    ap.add_argument("--segments", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fixes", type=Path)
    ap.add_argument("--traditional", action="store_true", help="先用 opencc s2twp 轉繁體")
    ap.add_argument("--rate", type=float, default=7.0, help="目標上限：等效中文字/秒")
    ap.add_argument("--min-dur", type=float, default=0.8, help="每段最短顯示秒數")
    ap.add_argument("--dump-text", action="store_true", help="只印出含停頓標記的原文")
    args = ap.parse_args()

    words = load_words(args.json_file, args.traditional)

    if args.dump_text:
        dump_text(words)
        return 0

    if not args.segments or not args.out:
        sys.exit("[ERR] 需要 --segments 與 --out")

    segs = [ln for ln in args.segments.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    chars = char_timeline(words)
    raw = "".join(c[0] for c in chars)
    joined = strip_space("".join(segs))
    if joined != raw:
        report_mismatch(joined, raw)
        return 1

    fixes = load_fixes(args.fixes) if args.fixes else []
    entries = build_entries(segs, chars, fixes)
    n_ext = extend_display(entries, args.rate, args.min_dur)

    write_srt(entries, args.out)
    rates = [width(t) / (b - a) for a, b, t in entries if b > a]
    print(f"[OK] 輸出 {args.out}（{len(entries)} 段）")
    print(f"     延長顯示時間 {n_ext} 段；平均 {sum(rates) / max(len(rates), 1):.1f} 等效字/秒；"
          f"超過 {args.rate} 的有 {len([r for r in rates if r > args.rate])} 段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
