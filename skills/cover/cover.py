#!/usr/bin/env python3
"""把一張底圖（或影片的一格）做成 YouTube／Reels／貼文封面。

只做「裁切＋（選用）疊大字＋輸出」，不生圖：底圖由各專案自己準備（首幀、渲染圖、
截圖、生圖結果）。輸出不帶任何 metadata。

用法：
    # 路線 A：後製疊字
    python cover.py <底圖或影片> --text 完美數 [--sub 歐幾里得] --font <OFL 字型檔>
                    [--at 秒數] [--focus 0.5,0.4] [--corner tl|tr|bl|br]
                    [--formats yt,reel,post] [--outdir .] [--name cover]
    # 路線 B：底圖已由生圖畫好字，只裁切輸出
    python cover.py <已含字的圖> --no-text [--focus 0.5,0.5] [--formats yt,reel,post]

--text 與 --no-text 必須二選一，避免漏打參數就默默輸出沒字的封面。

字型找法（依序）：--font → 環境變數 COVER_FONT → ~/.config/cover/fonts/ 裡第一個
.otf／.ttf。都找不到就停下來，不自動下載。--no-text 不需要字型。

需要 Pillow；從影片取一格時另需 ffmpeg。維持 Python 3.9+ 相容。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.exit("[ERR] 需要 Pillow：python -m pip install pillow")

# 名稱 -> (寬, 高, 文字安全區 (左, 上, 右, 下) 的比例, 檔名後綴)
# YouTube：右下角有影片長度標籤，文字不壓到右下。
# Reels：上方 12% 與下方 25% 會被介面擋住，主頁格狀預覽只看中間 3:4。
FORMATS = {
    "yt": (1280, 720, (0.05, 0.08, 0.95, 0.80), ""),
    "reel": (1080, 1920, (0.08, 0.20, 0.92, 0.72), "_9x16"),
    "post": (1080, 1350, (0.07, 0.07, 0.93, 0.86), "_4x5"),
}
# 橫圖做直式時，前景圖下緣放在畫面高度的哪裡（Reels 下方 25% 有介面，圖可以伸進去但字不行）
PAD_FG_BOTTOM = {"reel": 0.80, "post": 0.96}
VIDEO_EXT ={".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
YT_MAX_BYTES = 2 * 1024 * 1024


def find_font(arg: str | None) -> Path:
    candidates = []
    if arg:
        candidates.append(Path(arg))
    if os.environ.get("COVER_FONT"):
        candidates.append(Path(os.environ["COVER_FONT"]))
    font_dir = Path.home() / ".config" / "cover" / "fonts"
    if font_dir.is_dir():
        candidates += sorted(p for p in font_dir.iterdir() if p.suffix.lower() in {".otf", ".ttf"})
    for path in candidates:
        if path.is_file():
            return path
    sys.exit(
        "[ERR] 找不到字型。用 --font 指定，或設 COVER_FONT，或把 OFL 授權的字型檔"
        "（例如源石黑體 H、Noto Sans TC）放進 {}".format(font_dir)
    )


def grab_frame(video: Path, at: float) -> Image.Image:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("[ERR] 從影片取格需要 ffmpeg")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "frame.png"
        subprocess.run(
            [ffmpeg, "-v", "error", "-ss", str(at), "-i", str(video), "-frames:v", "1", str(out)],
            check=True,
        )
        return Image.open(out).convert("RGB")


def cover_crop(img: Image.Image, w: int, h: int, focus: tuple[float, float]) -> Image.Image:
    """等比放大到蓋滿 w×h，再以焦點為中心裁切。"""
    scale = max(w / img.width, h / img.height)
    rw, rh = round(img.width * scale), round(img.height * scale)
    img = img.resize((rw, rh), Image.LANCZOS)
    left = min(max(round(focus[0] * rw - w / 2), 0), rw - w)
    top = min(max(round(focus[1] * rh - h / 2), 0), rh - h)
    return img.crop((left, top, left + w, top + h))


def shade(img: Image.Image, where: str, strength: int) -> Image.Image:
    """在文字那一帶加暗角，讓大字在亮底上也讀得到。

    where：top（直式，從上往下淡）或四個角落 tl／tr／bl／br（從角落往外淡）。
    先在 128×128 小圖上算漸層再拉伸，比逐像素計算快得多。
    """
    w, h = img.size
    n = 128
    small = Image.new("L", (n, n))
    if where == "top":
        small.putdata([int(strength * max(0.0, 1 - y / (n * 0.55))) for y in range(n) for _ in range(n)])
    else:
        cx = 0 if where[1] == "l" else n - 1
        cy = 0 if where[0] == "t" else n - 1
        vals = []
        for y in range(n):
            for x in range(n):
                # 以角落為圓心的橢圓漸層，約淡到畫面寬高的 75%
                d = (((x - cx) / (n * 0.75)) ** 2 + ((y - cy) / (n * 0.75)) ** 2) ** 0.5
                vals.append(int(strength * max(0.0, 1 - d)))
        small.putdata(vals)
    mask = small.resize((w, h), Image.BILINEAR)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, mask)


def fit_font(font_path: Path, text: str, max_w: int, max_h: int) -> ImageFont.FreeTypeFont:
    size = max_h
    while size > 12:
        font = ImageFont.truetype(str(font_path), size)
        l, t, r, b = font.getbbox(text)
        if r - l <= max_w and b - t <= max_h:
            return font
        size -= 2
    return ImageFont.truetype(str(font_path), 12)


def pad_compose(img: Image.Image, w: int, h: int, fg_bottom: float) -> tuple[Image.Image, int]:
    """橫式底圖做直式封面：整張圖等寬放下方，上方用同一張圖模糊壓暗當背景。

    直接裁切會把畫面放大兩三倍、字也只能壓在臉上；這樣人物完整、上方留給文字。
    回傳合成圖與前景圖的上緣 y。
    """
    bg = cover_crop(img, w, h, (0.5, 0.5)).filter(ImageFilter.GaussianBlur(radius=w // 25))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (0, 0, 0)), 0.45)
    fg = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    top = round(h * fg_bottom) - fg.height
    bg.paste(fg, (0, top))
    return bg, top


def draw_text(img, font_path, text, sub, corner, box, fill, stroke, accent):
    """在像素框 box=(x0, y0, x1, y1) 內疊小標＋主標。

    corner 為 None（直式）：水平、垂直都置中。
    corner 為 tl／tr／bl／br（橫式）：貼齊框的那個角，字縮到約半寬，盡量不擋主體。
    """
    x0, y0, x1, y1 = box
    if corner:
        main = fit_font(font_path, text, round((x1 - x0) * 0.46), round((y1 - y0) * 0.30))
    else:
        main = fit_font(font_path, text, x1 - x0, round((y1 - y0) * 0.55))
    subf = ImageFont.truetype(str(font_path), max(14, round(main.size * 0.34))) if sub else None

    d = ImageDraw.Draw(img)
    ml, mt, mr, mb = d.textbbox((0, 0), text, font=main)
    mw, mh = mr - ml, mb - mt
    sw = sh = 0
    if subf:
        sl, st, sr, sb = d.textbbox((0, 0), sub, font=subf)
        sw, sh = sr - sl, sb - st
    gap = round(mh * 0.18) if sub else 0
    block_h = sh + gap + mh

    if not corner:
        top = y0 + round((y1 - y0 - block_h) / 2)
    elif corner[0] == "t":
        top = y0
    else:
        top = y1 - block_h

    def x_for(width):
        if not corner:
            return x0 + ((x1 - x0) - width) // 2
        return x0 if corner[1] == "l" else x1 - width

    if subf:
        d.text((x_for(sw) - sl, top - st), sub, font=subf, fill=accent,
               stroke_width=max(2, subf.size // 12), stroke_fill=stroke)
        top += sh + gap
    d.text((x_for(mw) - ml, top - mt), text, font=main, fill=fill,
           stroke_width=max(3, main.size // 12), stroke_fill=stroke)
    return img


def save_clean(img: Image.Image, path: Path, max_bytes: int | None) -> Path:
    """重建像素再存，確保不帶 EXIF／文字區塊；超過大小上限改存 JPEG。"""
    clean = Image.frombytes("RGB", img.size, img.convert("RGB").tobytes())
    clean.save(path, "PNG", optimize=True)
    if max_bytes and path.stat().st_size > max_bytes:
        path.unlink()
        path = path.with_suffix(".jpg")
        clean.save(path, "JPEG", quality=90, optimize=True)
    return path


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def main() -> int:
    ap = argparse.ArgumentParser(description="底圖 → 封面（裁切＋選用疊字＋清 metadata）")
    ap.add_argument("source", type=Path, help="底圖，或影片（搭配 --at）")
    ap.add_argument("--text", help="主標，建議 6 字內（與 --no-text 二選一）")
    ap.add_argument("--no-text", action="store_true",
                    help="不疊字，只裁切輸出（底圖的字已由生圖畫好；與 --text 二選一）")
    ap.add_argument("--sub", default="", help="小標（選用），放在主標上方")
    ap.add_argument("--font", help="OFL 字型檔路徑")
    ap.add_argument("--at", type=float, default=0.0, help="來源是影片時取第幾秒")
    ap.add_argument("--focus", default="0.5,0.5", help="裁切焦點 x,y（0–1），預設正中")
    ap.add_argument("--corner", choices=["tl", "tr", "bl", "br"], default="bl",
                    help="橫式文字放哪個角：左上 tl、右上 tr、左下 bl、右下 br；選不會擋到臉或主體的角")
    ap.add_argument("--formats", default="yt", help="逗號分隔：yt,reel,post")
    ap.add_argument("--fill", default="#FFFFFF", help="主標顏色")
    ap.add_argument("--accent", default="#FFD23F", help="小標顏色")
    ap.add_argument("--stroke", default="#111111", help="描邊顏色")
    ap.add_argument("--shade", type=int, default=150, help="文字側暗角強度 0–255，0 關閉")
    ap.add_argument("--outdir", type=Path, default=Path("."))
    ap.add_argument("--name", default="cover")
    args = ap.parse_args()
    # Windows 主控台預設 cp950，中文路徑會印成亂碼
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if args.no_text == bool(args.text):
        sys.exit("[ERR] --text 與 --no-text 要二選一：要疊字給 --text，底圖已有字給 --no-text")
    if args.no_text and args.sub:
        sys.exit("[ERR] --no-text 不疊字，不能同時給 --sub")
    if not args.source.is_file():
        sys.exit("[ERR] 找不到來源：{}".format(args.source))
    font = None if args.no_text else find_font(args.font)
    focus = tuple(float(v) for v in args.focus.split(","))
    if args.source.suffix.lower() in VIDEO_EXT:
        base = grab_frame(args.source, args.at)
    else:
        base = Image.open(args.source).convert("RGB")

    args.outdir.mkdir(parents=True, exist_ok=True)
    for key in [k.strip() for k in args.formats.split(",") if k.strip()]:
        if key not in FORMATS:
            sys.exit("[ERR] 不認得的格式：{}（可用 {}）".format(key, "、".join(FORMATS)))
        w, h, safe, suffix = FORMATS[key]
        box = [round(safe[0] * w), round(safe[1] * h), round(safe[2] * w), round(safe[3] * h)]
        portrait = h > w
        if portrait and base.width > base.height:
            # 橫圖做直式：模糊背景＋整張圖放下方，字放在圖上方的空白帶
            img, fg_top = pad_compose(base, w, h, PAD_FG_BOTTOM[key])
            box[3] = fg_top - round(h * 0.02)
        else:
            img = cover_crop(base, w, h, focus)
            if args.shade and not args.no_text:
                img = shade(img, "top" if portrait else args.corner, args.shade)
            if portrait:
                box[3] = box[1] + round((box[3] - box[1]) * 0.45)
        if not args.no_text:
            img = draw_text(img, font, args.text, args.sub, None if portrait else args.corner, tuple(box),
                            parse_color(args.fill), parse_color(args.stroke), parse_color(args.accent))
        out = save_clean(img, args.outdir / "{}{}.png".format(args.name, suffix),
                         YT_MAX_BYTES if key == "yt" else None)
        print("[OK] {}  {}×{}  {:.0f} KB".format(out, w, h, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
