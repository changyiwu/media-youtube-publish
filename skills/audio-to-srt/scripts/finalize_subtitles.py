#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
finalize_subtitles.py - 通用字幕精修套用腳本。
支援多次指定 --replace "舊字->新字" 的參數，並執行內建的大小寫統一與常見錯字修正。

跨段偵測：
  Whisper 斷句後，一個詞可能被切在相鄰兩段的邊界（例如「痊癒」→ 段A 結尾「痊」+ 段B 開頭「癒」）。
  全域替換規則（不含段號的 --replace 與內建 BUILTIN_REPLACEMENTS）會在「虛擬接合」後的
  長字串上偵測，命中跨段詞時把結果按原長度比例就近分配回兩段，
  保持段數不變、時間碼不變、段號不變（validate_srt.py 仍通過）。
  針對特定段落的規則（如 "390:AGE->Agent"）本就只作用於單段，維持原本逐段套用。
"""
import argparse
import re
from pathlib import Path

# 內建通用替換邏輯（機械替換）
BUILTIN_REPLACEMENTS = [
    ("Antigravity", "AntiGravity"),
    ("antigravity", "AntiGravity"),
    ("Anti-Gravity", "AntiGravity"),
    ("胡椒它的", "呼叫它的"),
]


# ---------------------------------------------------------------------------
# 跨段替換引擎（與 audio-to-srt/scripts/apply_vocab.py 同款，額外支援 regex op）
# ---------------------------------------------------------------------------

def _group(span):
    """連續 owner 序列壓成 [(owner, 字數), ...]。"""
    groups = []
    for o in span:
        if groups and groups[-1][0] == o:
            groups[-1][1] += 1
        else:
            groups.append([o, 1])
    return [(o, c) for o, c in groups]


def _distribute(new_text, groups):
    """把 new_text 依 groups 原字數比例切回各段，回傳 [(owner, 子字串), ...]。"""
    g = len(groups)
    n = len(new_text)
    if g == 1:
        return [(groups[0][0], new_text)]
    if n == 0:
        return [(o, "") for o, _ in groups]

    total = sum(c for _, c in groups)
    quotas = [n * c / total for _, c in groups]
    counts = [int(q) for q in quotas]
    remainder = n - sum(counts)
    order = sorted(range(g), key=lambda i: quotas[i] - counts[i], reverse=True)
    for k in range(remainder):
        counts[order[k]] += 1
    if n >= g:
        for i in range(g):
            if counts[i] == 0:
                j = max(range(g), key=lambda k: counts[k])
                counts[j] -= 1
                counts[i] += 1

    res = []
    p = 0
    for (o, _), c in zip(groups, counts):
        res.append((o, new_text[p:p + c]))
        p += c
    return res


def _apply_literal(joined, owner, old, new):
    out_chars, out_owner = [], []
    pos = 0
    idx = joined.find(old, pos)
    while idx != -1:
        out_chars.append(joined[pos:idx])
        out_owner.extend(owner[pos:idx])
        span = owner[idx:idx + len(old)]
        for o, sub in _distribute(new, _group(span)):
            out_chars.append(sub)
            out_owner.extend([o] * len(sub))
        pos = idx + len(old)
        idx = joined.find(old, pos)
    out_chars.append(joined[pos:])
    out_owner.extend(owner[pos:])
    return "".join(out_chars), out_owner


def _apply_regex(joined, owner, pattern, new):
    out_chars, out_owner = [], []
    pos = 0
    for m in pattern.finditer(joined):
        s, e = m.start(), m.end()
        if e == s:  # 跳過零寬度匹配，避免無限/空替換
            continue
        out_chars.append(joined[pos:s])
        out_owner.extend(owner[pos:s])
        span = owner[s:e]
        for o, sub in _distribute(new, _group(span)):
            out_chars.append(sub)
            out_owner.extend([o] * len(sub))
        pos = e
    out_chars.append(joined[pos:])
    out_owner.extend(owner[pos:])
    return "".join(out_chars), out_owner


def apply_cross_segment(bodies, ops):
    """對 bodies 依序套用 ops，回傳長度與順序相同的新 bodies。

    ops：[("literal", old, new) | ("regex", compiled_pattern, new), ...]
    """
    joined = "".join(bodies)
    owner = []
    for i, b in enumerate(bodies):
        owner.extend([i] * len(b))

    for kind, pat, new in ops:
        if kind == "literal":
            if not pat:
                continue
            joined, owner = _apply_literal(joined, owner, pat, new)
        else:
            joined, owner = _apply_regex(joined, owner, pat, new)

    new_bodies = [[] for _ in bodies]
    for ch, o in zip(joined, owner):
        new_bodies[o].append(ch)
    result = ["".join(parts) for parts in new_bodies]
    for i, b in enumerate(bodies):
        if result[i] == "" and b != "":
            result[i] = b
    return result


def apply_per_segment_rules(text: str, custom_replaces: list, seg_num: str) -> str:
    """套用針對特定段號的規則（如 "390:AGE->Agent"），只作用於單段。"""
    for old, new in custom_replaces:
        if ":" in old:
            target_seg, actual_old = old.split(":", 1)
            if target_seg.strip() == seg_num:
                text = text.replace(actual_old, new)
    return text


def build_global_ops(custom_replaces: list) -> list:
    """把全域規則（不含段號）整理成跨段引擎用的 ops，順序：自訂優先、內建在後。"""
    ops = []
    for old, new in custom_replaces:
        if ":" in old:
            continue  # 段號規則不在此處理
        ops.append(("regex", re.compile(re.escape(old), re.IGNORECASE), new))
    for old, new in BUILTIN_REPLACEMENTS:
        ops.append(("literal", old, new))
    return ops


def apply_replacements(text: str, custom_replaces: list, seg_num: str) -> str:
    """單段套用（保留給其他呼叫端 / 相容用途）：全域規則 + 段號規則。

    注意：跨段偵測請走 process_srt → apply_cross_segment；此函式僅作用於單段。
    """
    text = apply_per_segment_rules(text, custom_replaces, seg_num)
    for kind, pat, new in build_global_ops(custom_replaces):
        if kind == "literal":
            text = text.replace(pat, new)
        else:
            text = pat.sub(new, text)
    return text


def process_srt(src_path: Path, dst_path: Path, custom_replaces: list) -> None:
    if not src_path.exists():
        print(f"[ERR] 找不到輸入字幕檔：{src_path}")
        return

    content = src_path.read_text(encoding="utf-8")
    segs = re.split(r'(\r?\n\r?\n)', content)

    text_positions = []
    headers = []
    seg_nums = []
    bodies = []
    for si, seg in enumerate(segs):
        if not seg.strip() or seg.isspace() or "-->" not in seg:
            continue
        lines = seg.splitlines(keepends=False)
        if len(lines) < 3:
            continue
        text_positions.append(si)
        headers.append("\n".join(lines[:2]))
        seg_nums.append(lines[0].strip())
        bodies.append("\n".join(lines[2:]))

    # 1. 段號專屬規則先逐段套用（單段，無跨段問題）
    bodies_step1 = [
        apply_per_segment_rules(b, custom_replaces, seg_nums[k])
        for k, b in enumerate(bodies)
    ]
    # 2. 全域規則走跨段引擎
    new_bodies = apply_cross_segment(bodies_step1, build_global_ops(custom_replaces))

    n_replaced = sum(1 for a, b in zip(bodies, new_bodies) if a != b)

    out = list(segs)
    for k, si in enumerate(text_positions):
        out[si] = headers[k] + "\n" + new_bodies[k]

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text("".join(out), encoding="utf-8")
    print(f"[OK] 已輸出精修字幕：{dst_path}")
    print(f"     共 {n_replaced} 段字幕被修改。")

def main() -> int:
    ap = argparse.ArgumentParser(description="字幕套用修正與精修")
    ap.add_argument("src", type=Path, help="輸入的 SRT 字幕路徑 (如 .vocab.srt)")
    ap.add_argument("--out", type=Path, required=True, help="輸出的精修後 SRT 路徑")
    ap.add_argument("--replace", action="append", default=[], 
                    help="替換規則，格式為 '舊字->新字' (可多次指定)。支援特定段落，如 '390:AGE->Agent'")
    args = ap.parse_args()

    custom_replaces = []
    for r in args.replace:
        if "->" in r:
            old, new = r.split("->", 1)
            custom_replaces.append((old.strip(), new.strip()))
        else:
            print(f"[WARN] 忽略無效替換規則格式（應為 '舊字->新字'）：{r}")

    process_srt(args.src, args.out, custom_replaces)
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
