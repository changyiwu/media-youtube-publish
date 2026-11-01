#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_subs_manual.py 的單元測試。

涵蓋：
  - 切點落在詞的邊界／詞中間時的時間碼
  - 切點檔與原文不符時拒絕輸出
  - 顯示時間只延長到下一句之前
  - 輸出的 SRT 通過 validate_srt

執行：
  python test_build_subs_manual.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_subs_manual as bsm  # noqa: E402
import validate_srt  # noqa: E402

WORDS = [
    {"word": "我們", "start": 0.0, "end": 0.4},
    {"word": "來", "start": 0.4, "end": 0.6},
    {"word": "找一下", "start": 0.6, "end": 1.2},
    {"word": " Google", "start": 1.2, "end": 1.6},
    {"word": " Play", "start": 1.6, "end": 2.0},
    {"word": "應用程式", "start": 3.0, "end": 4.0},
]


class TestBuildEntries(unittest.TestCase):
    def test_cut_on_word_boundary(self):
        entries = bsm.build_entries(["我們來找一下", "Google Play", "應用程式"], bsm.char_timeline(WORDS), [])
        self.assertEqual([e[2] for e in entries], ["我們來找一下", "Google Play", "應用程式"])
        self.assertAlmostEqual(entries[0][1], 1.2)
        self.assertAlmostEqual(entries[1][0], 1.2)
        self.assertAlmostEqual(entries[2][0], 3.0)

    def test_cut_inside_word_does_not_overlap(self):
        entries = bsm.build_entries(["我們來找一下Google Play應用", "程式"], bsm.char_timeline(WORDS), [])
        self.assertAlmostEqual(entries[0][1], 3.5)
        self.assertAlmostEqual(entries[1][0], 3.5)

    def test_fixes_only_change_text(self):
        entries = bsm.build_entries(["我們來找一下Google Play應用程式"], bsm.char_timeline(WORDS), [("Play", "Store")])
        self.assertIn("Google Store", entries[0][2])
        self.assertAlmostEqual(entries[0][1], 4.0)


class TestExtendDisplay(unittest.TestCase):
    def test_never_reaches_next_entry(self):
        entries = [[0.0, 0.2, "一二三四五六七八九十"], [0.5, 2.0, "下一句"]]
        self.assertEqual(bsm.extend_display(entries, 7.0, 0.8), 1)
        self.assertAlmostEqual(entries[0][1], 0.45)


class TestCli(unittest.TestCase):
    def run_cli(self, tmp, seg_text):
        src = tmp / "raw.json"
        src.write_text(json.dumps({"words": WORDS}, ensure_ascii=False), encoding="utf-8")
        segs = tmp / "segments.txt"
        segs.write_text(seg_text, encoding="utf-8-sig")
        out = tmp / "raw.srt"
        result = subprocess.run(
            [sys.executable, str(HERE / "build_subs_manual.py"), str(src), "--segments", str(segs), "--out", str(out)],
            capture_output=True,
        )
        return result, out

    def test_srt_passes_validate(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            result, out = self.run_cli(tmp, "我們來找一下\nGoogle Play\n應用程式\n")
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertEqual(validate_srt.validate(out, out), 0)

    def test_mismatch_refuses_output(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            result, out = self.run_cli(tmp, "我們來找一下\nGoogle Play\n應用程序\n")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(out.exists())

    def test_dump_text_prints_pause_mark_when_piped(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            src = tmp / "raw.json"
            src.write_text(json.dumps({"words": WORDS}, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HERE / "build_subs_manual.py"), str(src), "--dump-text"],
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertIn("⏸1.0⏸", result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
