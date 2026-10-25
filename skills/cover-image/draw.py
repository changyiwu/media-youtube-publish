"""
全域生圖腳本（OpenAI gpt-image-2 版）

用法：
  python draw.py "一隻穿西裝的龍蝦，寫實風格"
  python draw.py "演講海報" --size 1536x1024 --name poster
  python draw.py "把背景換成海底" --edit ./image.png --name edited
  python draw.py "加一頂帽子" --edit ./image.png --mask ./mask.png --name masked

會自動讀取以下來源的 OPENAI_API_KEY（依序）：
  1. 當前 shell 環境變數
  2. 當前工作目錄的 .env
  3. 使用者 home 的 ~/.openai.env（全域備援）

輸出：
  預設放在「當前工作目錄/output/」
"""

import os
import sys
import base64
import argparse
from pathlib import Path
from datetime import datetime

MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "low"
DEFAULT_N = 1


def load_env_from_file(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_env():
    load_env_from_file(Path.cwd() / ".env")
    load_env_from_file(Path.home() / ".openai.env")


def resolve_outdir(user_outdir):
    if user_outdir:
        return Path(user_outdir)
    return Path.cwd() / "output"


def _save_results(result, name, n, outdir):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []
    for i, item in enumerate(result.data):
        suffix = f"_{i + 1}" if n > 1 else ""
        out_path = outdir / f"{name}_{stamp}{suffix}.png"
        png_bytes = base64.b64decode(item.b64_json)
        out_path.write_bytes(png_bytes)
        saved.append(out_path)
        print(f"  [OK] {out_path}")
    return saved


def draw(prompt, size, quality, n, name, outdir):
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        print("錯誤：找不到 OPENAI_API_KEY", file=sys.stderr)
        sys.exit(1)
    outdir.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    print(f"畫圖中（{MODEL}, {size}, {quality}, n={n}） -> {outdir}", file=sys.stderr)
    result = client.images.generate(model=MODEL, prompt=prompt, size=size,
                                     quality=quality, n=n)
    return _save_results(result, name, n, outdir)


def edit(prompt, image_path, mask_path, size, quality, n, name, outdir):
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        print("錯誤：找不到 OPENAI_API_KEY", file=sys.stderr)
        sys.exit(1)
    if not image_path.exists():
        print(f"錯誤：找不到來源圖片 {image_path}", file=sys.stderr)
        sys.exit(1)
    outdir.mkdir(parents=True, exist_ok=True)
    client = OpenAI()
    mode = "遮罩改圖" if mask_path else "全圖改圖"
    print(f"改圖中（{mode}, {MODEL}, {size}, {quality}） -> {outdir}", file=sys.stderr)
    kwargs = dict(model=MODEL, image=open(image_path, "rb"),
                  prompt=prompt, size=size, quality=quality, n=n)
    if mask_path:
        if not mask_path.exists():
            print(f"錯誤：找不到遮罩圖片 {mask_path}", file=sys.stderr)
            sys.exit(1)
        kwargs["mask"] = open(mask_path, "rb")
    result = client.images.edit(**kwargs)
    return _save_results(result, name, n, outdir)


def main():
    load_env()
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="+")
    parser.add_argument("--edit", default=None)
    parser.add_argument("--mask", default=None)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY,
                        choices=["low", "medium", "high", "auto"])
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--name", default="image")
    parser.add_argument("--outdir", default=None)
    args = parser.parse_args()
    prompt = " ".join(args.prompt)
    outdir = resolve_outdir(args.outdir)
    if args.edit:
        edit(prompt, Path(args.edit), Path(args.mask) if args.mask else None,
             args.size, args.quality, args.n, args.name, outdir)
    else:
        draw(prompt, args.size, args.quality, args.n, args.name, outdir)


if __name__ == "__main__":
    main()
