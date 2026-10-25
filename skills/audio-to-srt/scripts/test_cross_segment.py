#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨段詞彙替換的單元測試。

涵蓋：
  - 段內替換（行為與舊版一致）
  - 跨兩段邊界的詞（核心修復：痊癒→全域 等被切斷的詞）
  - 替換後段數不變、時間碼不變、段號不變（過 validate_srt）
  - 分隔符 / CRLF / 多行字幕不被破壞

執行：
  python test_cross_segment.py        # 或 python -m unittest test_cross_segment
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


apply_vocab = _load("apply_vocab", HERE / "apply_vocab.py")
validate_srt = _load("validate_srt", HERE / "validate_srt.py")
finalize = _load("finalize_subtitles", HERE / "finalize_subtitles.py")


def make_srt(blocks, newline="\n"):
    """blocks: [(idx, tc, text), ...] → SRT 字串。"""
    parts = []
    for idx, tc, text in blocks:
        parts.append(f"{idx}{newline}{tc}{newline}{text}")
    return (newline + newline).join(parts) + newline + newline


def parse(path):
    return validate_srt.parse_srt(Path(path))


class TestDistribute(unittest.TestCase):
    def test_single_owner_keeps_whole(self):
        # 未跨段：整串歸同一段，等同舊行為
        self.assertEqual(
            apply_vocab._distribute("全域", [(7, 2)]),
            [(7, "全域")],
        )

    def test_two_owners_equal_split(self):
        # 痊(段315) + 癒(段316) → 全/域 各回一段
        out = apply_vocab._distribute("全域", apply_vocab._group([315, 316]))
        self.assertEqual(out, [(315, "全"), (316, "域")])

    def test_no_empty_group_when_long_enough(self):
        # new 比段數多時，每段至少 1 字，不可清空任何來源段
        out = apply_vocab._distribute("ABCDE", apply_vocab._group([1, 2]))
        for _, sub in out:
            self.assertGreaterEqual(len(sub), 1)
        self.assertEqual("".join(s for _, s in out), "ABCDE")


class TestApplyVocab(unittest.TestCase):
    def _run(self, src_text):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.srt"
            dst = Path(d) / "out.srt"
            # 用 bytes 寫入，避免 Windows 的換行轉換破壞手工 CRLF
            src.write_bytes(src_text.encode("utf-8"))
            apply_vocab.process_srt(src, dst)
            rc = validate_srt.validate(src, dst)
            return parse(dst), rc

    def test_cross_boundary_quanyu(self):
        # 真實案例：痊癒 被切在段界
        src = make_srt([
            ("315", "00:00:10,000 --> 00:00:12,000", "應該要改成痊"),
            ("316", "00:00:12,000 --> 00:00:14,000", "癒包含的東西"),
        ])
        clean, rc = self._run(src)
        self.assertEqual(rc, 0, "validate_srt 必須通過（段數/時間碼/段號一致）")
        self.assertEqual(len(clean), 2, "段數不可改變")
        self.assertEqual(clean[0][1], "00:00:10,000 --> 00:00:12,000")
        self.assertEqual(clean[1][1], "00:00:12,000 --> 00:00:14,000")
        # 痊癒 → 全域，按比例就近分配：段315 結尾「全」、段316 開頭「域」
        self.assertTrue(clean[0][2].endswith("全"), clean[0][2])
        self.assertTrue(clean[1][2].startswith("域"), clean[1][2])
        joined = clean[0][2] + clean[1][2]
        self.assertIn("全域", joined)
        self.assertNotIn("痊", joined)

    def test_within_segment_unchanged_behaviour(self):
        # 段內命中：行為與舊版一致
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "請打開Cloud Code"),
        ])
        clean, rc = self._run(src)
        self.assertEqual(rc, 0)
        self.assertEqual(clean[0][2], "請打開Claude Code")

    def test_cross_boundary_english_token(self):
        # 英文詞被切：Cloud → Claude，跨段
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "這是Clo"),
            ("2", "00:00:02,000 --> 00:00:04,000", "ud 平台"),
        ])
        clean, rc = self._run(src)
        self.assertEqual(rc, 0)
        joined = clean[0][2] + clean[1][2]
        self.assertIn("Claude", joined)
        self.assertNotIn("Cloud", joined)

    def test_crlf_and_separators_preserved(self):
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "改成痊"),
            ("2", "00:00:02,000 --> 00:00:04,000", "癒了"),
        ], newline="\r\n")
        clean, rc = self._run(src)
        self.assertEqual(rc, 0)
        self.assertEqual(len(clean), 2)


class TestFinalize(unittest.TestCase):
    def _run(self, src_text, replaces):
        custom = []
        for r in replaces:
            old, new = r.split("->", 1)
            custom.append((old.strip(), new.strip()))
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.srt"
            dst = Path(d) / "out.srt"
            src.write_bytes(src_text.encode("utf-8"))
            finalize.process_srt(src, dst, custom)
            rc = validate_srt.validate(src, dst)
            return parse(dst), rc

    def test_builtin_cross_boundary_antigravity(self):
        # AntiGravity 被切：antigravity → AntiGravity（內建規則、不分大小寫）
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "打開anti"),
            ("2", "00:00:02,000 --> 00:00:04,000", "gravity 編輯器"),
        ])
        clean, rc = self._run(src, [])
        self.assertEqual(rc, 0)
        joined = clean[0][2] + clean[1][2]
        self.assertIn("AntiGravity", joined)

    def test_custom_cross_boundary(self):
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "他說痊"),
            ("2", "00:00:02,000 --> 00:00:04,000", "癒了沒"),
        ])
        clean, rc = self._run(src, ["痊癒->全域"])
        self.assertEqual(rc, 0)
        joined = clean[0][2] + clean[1][2]
        self.assertIn("全域", joined)
        self.assertNotIn("痊", joined)

    def test_per_segment_rule_still_single_segment(self):
        src = make_srt([
            ("390", "00:00:00,000 --> 00:00:02,000", "這個AGE很強"),
            ("391", "00:00:02,000 --> 00:00:04,000", "另一個AGE不動"),
        ])
        clean, rc = self._run(src, ["390:AGE->Agent"])
        self.assertEqual(rc, 0)
        self.assertIn("Agent", clean[0][2])
        self.assertIn("AGE", clean[1][2])  # 段號規則只動 390



class TestBoundaryAndProtect(unittest.TestCase):
    """詞邊界守衛與保護詞（規則外移後才有的行為，2026-08-23 併入）。"""

    def _clean(self, text):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.srt"
            dst = Path(d) / "out.srt"
            src.write_bytes(
                make_srt([("1", "00:00:00,000 --> 00:00:02,000", text)]).encode("utf-8")
            )
            apply_vocab.process_srt(src, dst)
            self.assertEqual(validate_srt.validate(src, dst), 0)
            return parse(dst)[0][2]

    def test_boundary_protects_icloud(self):
        # 詞邊界：Cloud -> Claude 不可動到 iCloud 的字尾
        self.assertEqual(self._clean("備份在iCloud裡面"), "備份在iCloud裡面")

    def test_protect_word_cloudflare(self):
        # 保護詞：Cloudflare 前後都是中文，邊界守衛救不了，靠遮蔽
        self.assertEqual(self._clean("部署到Cloudflare上"), "部署到Cloudflare上")

    def test_protect_word_google_cloud(self):
        # 保護詞：Google Cloud 前後是空白，邊界檢查會放行
        self.assertEqual(self._clean("他用 Google Cloud 跑"), "他用 Google Cloud 跑")

    def test_bare_cloud_still_replaced(self):
        # 反面：獨立的 Cloud 仍要被改成 Claude，保護不能保過頭
        self.assertEqual(self._clean("我用 Cloud 寫程式"), "我用 Claude 寫程式")

    def test_protect_word_across_segment_boundary(self):
        # 保護詞被切在段界：Cloud + flare 接合後仍應整個受保護
        src = make_srt([
            ("1", "00:00:00,000 --> 00:00:02,000", "部署到Cloud"),
            ("2", "00:00:02,000 --> 00:00:04,000", "flare 上面"),
        ])
        with tempfile.TemporaryDirectory() as d:
            s_ = Path(d) / "in.srt"
            dst = Path(d) / "out.srt"
            s_.write_bytes(src.encode("utf-8"))
            apply_vocab.process_srt(s_, dst)
            self.assertEqual(validate_srt.validate(s_, dst), 0)
            clean = parse(dst)
        joined = clean[0][2] + clean[1][2]
        self.assertIn("Cloudflare", joined)
        self.assertNotIn("Claude", joined)

    def test_rules_file_is_source_of_truth(self):
        # 規則外移：改規則檔就會改行為，不必動程式碼
        with tempfile.TemporaryDirectory() as d:
            rules = Path(d) / "r.md"
            rules.write_text(
                "# 測試規則\n\n## 保護詞\n\n- `SoundCloud`\n\n"
                "## 替換規則\n\n| 聽成 | 正確 | 邊界 |\n|---|---|---|\n"
                "| `Cloud` | `Claude` | |\n",
                encoding="utf-8",
            )
            protect, rs = apply_vocab.load_rules(rules, use_user_rules=False)
            self.assertEqual(protect, ["SoundCloud"])
            self.assertEqual(len(rs), 1)
            out = apply_vocab.apply_cross_segment(
                ["丟到SoundCloud跟 Cloud 上"], protect, rs
            )[0]
            self.assertEqual(out, "丟到SoundCloud跟 Claude 上")


if __name__ == "__main__":
    unittest.main(verbosity=2)
