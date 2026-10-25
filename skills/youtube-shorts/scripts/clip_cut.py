#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clip_cut.py — 從長片切多段 + 組片 + 重編 SRT

用法：
  python clip_cut.py \
    --input-mp4 working/<id>/<id>.cut.mp4 \
    --input-srt working/<id>/<id>.srt \
    --segments "00:00:08.500-00:00:13.200,00:00:45.100-00:01:30.800" \
    --out-dir working/<id>/short-tmp/

輸出：
  short.mp4 — ffmpeg trim+concat（重新編碼確保乾淨切點）
  short.srt — 依新時間軸重編
  short.txt — 純文字稿
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def time_to_seconds(t: str) -> float:
    """支援 HH:MM:SS、HH:MM:SS.mmm、HH:MM:SS,mmm、MM:SS、SS."""
    t = t.strip().replace(',', '.')
    parts = t.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def seconds_to_srt_time(s: float) -> str:
    if s < 0:
        s = 0
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace('.', ',')


def parse_segments(seg_str: str):
    """'A-B,C-D' → [(A_sec, B_sec), (C_sec, D_sec)]，按起始時間排序，並驗證不重疊。"""
    segs = []
    for piece in seg_str.split(','):
        piece = piece.strip()
        if not piece:
            continue
        if '-' not in piece:
            raise ValueError(f"段格式錯誤（缺少 '-'）：{piece}")
        a, b = piece.split('-', 1)
        sa, sb = time_to_seconds(a), time_to_seconds(b)
        if sb <= sa:
            raise ValueError(f"段結束 ≤ 開始：{piece}")
        segs.append((sa, sb))
    segs.sort()
    for i in range(1, len(segs)):
        if segs[i][0] < segs[i - 1][1]:
            raise ValueError(f"段重疊：{segs[i - 1]} 與 {segs[i]}")
    return segs


def check_deps():
    if shutil.which('ffmpeg') is None:
        print("[ERR] 找不到 ffmpeg。", file=sys.stderr)
        sys.exit(1)
    if shutil.which('ffprobe') is None:
        print("[ERR] 找不到 ffprobe。", file=sys.stderr)
        sys.exit(1)


def get_duration(path: Path) -> float:
    out = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path),
    ], text=True).strip()
    return float(out)


def cut_video(input_mp4: Path, segments, out_mp4: Path):
    """以 filter_complex trim+concat，重新編碼。"""
    parts = []
    for i, (a, b) in enumerate(segments):
        parts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]")
    concat_inputs = ''.join(f"[v{i}][a{i}]" for i in range(len(segments)))
    parts.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[v][a]")
    filter_complex = '; '.join(parts)

    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_mp4),
        '-filter_complex', filter_complex,
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        str(out_mp4),
    ]
    print(f"[CMD] ffmpeg trim+concat → {out_mp4}")
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f"[ERR] ffmpeg 失敗，rc={rc}", file=sys.stderr)
        sys.exit(rc)


# ===== SRT 處理 =====
SRT_TIME_RE = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})')


def parse_srt(srt_path: Path):
    """回傳 [(idx, start_sec, end_sec, text_lines), ...]"""
    raw = srt_path.read_text(encoding='utf-8').strip()
    blocks = re.split(r'\n\s*\n', raw)
    entries = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip() != '']
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = SRT_TIME_RE.search(lines[1])
        if not m:
            continue
        s_start = time_to_seconds(m.group(1))
        s_end = time_to_seconds(m.group(2))
        text_lines = lines[2:]
        entries.append((idx, s_start, s_end, text_lines))
    return entries


def cut_srt(input_srt: Path, segments, out_srt: Path):
    """把原 SRT 中落在 segments 內的字幕保留，並依新時間軸（cumulative）位移。"""
    entries = parse_srt(input_srt)

    # 計算每段的時間軸偏移（offset on new timeline）
    new_blocks = []
    cumulative = 0.0
    new_idx = 1
    for (a, b) in segments:
        seg_dur = b - a
        for (orig_idx, s, e, txt) in entries:
            # 字幕條目與該段完全沒有交集 → 跳過
            if e <= a or s >= b:
                continue
            # 截到段邊界
            ns = max(s, a) - a + cumulative
            ne = min(e, b) - a + cumulative
            if ne <= ns:
                continue
            new_blocks.append((new_idx, ns, ne, txt))
            new_idx += 1
        cumulative += seg_dur

    out_lines = []
    for (i, s, e, txt) in new_blocks:
        out_lines.append(str(i))
        out_lines.append(f"{seconds_to_srt_time(s)} --> {seconds_to_srt_time(e)}")
        out_lines.extend(txt)
        out_lines.append('')

    out_srt.write_text('\n'.join(out_lines), encoding='utf-8')
    print(f"[OK] {out_srt}（{len(new_blocks)} 段）")


def srt_to_txt(srt_path: Path, txt_path: Path):
    entries = parse_srt(srt_path)
    paragraphs = []
    cur = []
    for (_, _, _, txt) in entries:
        for line in txt:
            line = line.strip()
            if not line:
                continue
            cur.append(line)
            if line.endswith(('。', '！', '？', '.', '!', '?')):
                paragraphs.append(''.join(cur))
                cur = []
    if cur:
        paragraphs.append(''.join(cur))
    txt_path.write_text('\n\n'.join(paragraphs), encoding='utf-8')
    print(f"[OK] {txt_path}（{len(paragraphs)} 段、{sum(len(p) for p in paragraphs)} 字）")


def main():
    ap = argparse.ArgumentParser(description='從長片切多段 + 組片 + SRT 重編')
    ap.add_argument('--input-mp4', type=Path, required=True)
    ap.add_argument('--input-srt', type=Path, required=True)
    ap.add_argument('--segments', required=True,
                    help='例：00:00:05.000-00:00:10.500,00:01:23-00:01:38')
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--max-duration', type=float, default=120.0,
                    help='短片最長秒數（超過會警告但不阻擋）')
    args = ap.parse_args()

    check_deps()

    if not args.input_mp4.exists():
        print(f"[ERR] 找不到 {args.input_mp4}", file=sys.stderr)
        sys.exit(1)
    if not args.input_srt.exists():
        print(f"[ERR] 找不到 {args.input_srt}", file=sys.stderr)
        sys.exit(1)

    segments = parse_segments(args.segments)
    total = sum(b - a for a, b in segments)
    print(f"[INFO] 段數 {len(segments)}、總時長 {total:.2f}s")
    if total > args.max_duration:
        print(f"[WARN] 短片總長 {total:.1f}s > {args.max_duration}s，建議減少段落")

    # 驗證所有時間碼都在影片範圍內
    full_dur = get_duration(args.input_mp4)
    for a, b in segments:
        if b > full_dur + 0.5:
            print(f"[ERR] 段 {a:.2f}-{b:.2f} 超出影片總長 {full_dur:.2f}", file=sys.stderr)
            sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = args.out_dir / 'short.mp4'
    out_srt = args.out_dir / 'short.srt'
    out_txt = args.out_dir / 'short.txt'

    cut_video(args.input_mp4, segments, out_mp4)
    cut_srt(args.input_srt, segments, out_srt)
    srt_to_txt(out_srt, out_txt)

    new_dur = get_duration(out_mp4)
    print(f"\n[DONE] 短片時長 {new_dur:.2f}s（{len(segments)} 段）")
    print(f"  - {out_mp4}")
    print(f"  - {out_srt}")
    print(f"  - {out_txt}")


if __name__ == '__main__':
    main()
