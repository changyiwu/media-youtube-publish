#!/usr/bin/env python3
"""本地 Whisper STT，產出與 transcribe_groq.py 同格式的 word-level JSON。

需要 Python 3.9+。音訊不離開這台電腦。

用法：
  python transcribe_local.py <audio_file> [--out raw.json] [--model large-v3-turbo]
                             [--engine auto|faster-whisper|whisper] [--device auto|cuda|cpu]

輸出：模仿 Groq verbose_json，頂層有 `words`（每個詞的 start/end）與 `segments`，
所以後面的 resegment.py／apply_vocab.py／validate_srt.py 一行都不用改。

引擎（擇一安裝即可，--engine auto 會依序嘗試）：
  - faster-whisper：`pip install faster-whisper`（建議，快、省 VRAM）
    GPU 另需 `pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"`
  - openai-whisper：`pip install openai-whisper`（需要 PyTorch 與 ffmpeg）

**本專案唯一的第三方套件例外**（見 AGENTS.md〈相容性〉）：引擎只在函式內 import，
沒裝時一開始就明確報錯，不會跑到一半才爆；preflight.py 會檢查有沒有裝。

--initial_prompt 與 Groq 路線共用 ../references/vocabulary.md（build_prompt 直接借
transcribe_groq.py 的），改那份檔案兩條路線都會生效；也可用 --prompt 直接覆寫。
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from transcribe_groq import DEFAULT_VOCAB, build_prompt

ENGINES = ("faster-whisper", "whisper")
MODULE_BY_ENGINE = {"faster-whisper": "faster_whisper", "whisper": "whisper"}
PROGRESS_EVERY = 60.0   # 每轉完這麼多秒音訊印一次進度


def add_nvidia_dll_dirs() -> None:
    """Windows：把 pip 裝的 nvidia-cublas／cudnn 的 DLL 目錄掛上搜尋路徑。

    ctranslate2 用 LoadLibrary 動態載入 cuBLAS／cuDNN，pip 套件的 DLL 不在 PATH 上，
    不掛的話 GPU 會在第一次推論時才報「cublas64_12.dll not found」。
    """
    if os.name != "nt":
        return
    spec = importlib.util.find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return
    for root in spec.submodule_search_locations:
        for bin_dir in sorted(Path(root).glob("*/bin")):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def pick_engine(requested: str) -> str:
    candidates = ENGINES if requested == "auto" else (requested,)
    for engine in candidates:
        if importlib.util.find_spec(MODULE_BY_ENGINE[engine]) is not None:
            return engine
    if requested == "auto":
        sys.exit(
            "[ERR] 找不到本地 Whisper 引擎；請執行 python -m pip install faster-whisper"
            "（或 openai-whisper），或改走 Groq 路線"
        )
    sys.exit(f"[ERR] 指定的引擎 {requested} 沒有安裝")


def cuda_available(engine: str) -> bool:
    try:
        if engine == "faster-whisper":
            import ctranslate2
            return ctranslate2.get_cuda_device_count() > 0
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def report_progress(state: dict, end: float, duration: float) -> None:
    if end - state["last"] < PROGRESS_EVERY:
        return
    state["last"] = end
    pct = f"（{end / duration * 100:.0f}%）" if duration else ""
    elapsed = time.time() - state["t0"]
    print(f"[INFO] 已轉 {end / 60:.1f} 分鐘{pct}，耗時 {elapsed:.0f}s")


def decode_with_ffmpeg(audio: Path):
    """用 ffmpeg 解成 16 kHz mono float32，回傳 numpy array。

    不讓 faster-whisper 自己用 PyAV 解碼：av 19 拿掉了它會傳的 metadata_errors 參數，
    一開檔就 TypeError。ffmpeg 本來就是流程必備，版本相依少一層。
    """
    import numpy as np

    if not shutil.which("ffmpeg"):
        sys.exit("[ERR] 找不到 ffmpeg，本地 Whisper 需要它解碼音訊")
    cmd = ["ffmpeg", "-nostdin", "-i", str(audio), "-vn", "-ac", "1",
           "-ar", "16000", "-f", "f32le", "-"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-500:]
        sys.exit(f"[ERR] ffmpeg 解碼失敗：\n{err}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def run_faster_whisper(audio: Path, model_name: str, device: str,
                       compute_type: str, prompt: str):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    seg_iter, info = model.transcribe(
        decode_with_ffmpeg(audio),
        language="zh",
        initial_prompt=prompt or None,
        # initial_prompt 只進第一個 30 秒視窗，之後吃的是前文；前文一出現簡體就自我強化，
        # 實測 35 秒樣本有 35 個簡體字。hotwords 每個視窗都會帶上，同一段降到 0。
        # 但 hotwords＋前文會疊出重複幻覺（3 分鐘樣本出現「我親自我親自…」、多出 180 字），
        # 所以關掉 condition_on_previous_text：每個視窗只看 prompt，不看前文。
        # 仍可能有零星視窗漂成簡體，交給清字階段（cleanup_rules.md）
        hotwords=prompt or None,
        condition_on_previous_text=False,
        word_timestamps=True,
    )
    segments, words = [], []
    state = {"last": 0.0, "t0": time.time()}
    # seg_iter 是 generator，真正的推論在這個迴圈裡才發生
    for seg in seg_iter:
        segments.append({"id": len(segments), "start": seg.start,
                         "end": seg.end, "text": seg.text})
        for w in seg.words or []:
            words.append({"word": w.word, "start": w.start, "end": w.end})
        report_progress(state, seg.end, info.duration)
    return segments, words, info.duration


def run_openai_whisper(audio: Path, model_name: str, device: str, prompt: str):
    import whisper

    model = whisper.load_model(model_name, device=device)
    options = dict(language="zh", initial_prompt=prompt or None,
                   condition_on_previous_text=False, word_timestamps=True,
                   fp16=(device == "cuda"), verbose=None)
    try:
        # 與 faster-whisper 的 hotwords 同理：每個視窗都帶 prompt，防簡體漂移（20250625 版起才有）
        result = model.transcribe(str(audio), carry_initial_prompt=True, **options)
    except TypeError:
        print("[WARN] 這版 openai-whisper 不支援 carry_initial_prompt，長片後段可能漂成簡體")
        result = model.transcribe(str(audio), **options)
    segments, words = [], []
    for seg in result.get("segments", []):
        segments.append({"id": len(segments), "start": seg["start"],
                         "end": seg["end"], "text": seg["text"]})
        for w in seg.get("words", []):
            words.append({"word": w["word"], "start": w["start"], "end": w["end"]})
    duration = segments[-1]["end"] if segments else 0.0
    return segments, words, duration


def transcribe(engine: str, audio: Path, model_name: str, device: str,
               compute_type: str, prompt: str):
    if engine == "faster-whisper":
        return run_faster_whisper(audio, model_name, device, compute_type, prompt)
    return run_openai_whisper(audio, model_name, device, prompt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--model", default="large-v3-turbo",
                    help="Whisper 模型名（預設 large-v3-turbo，與 Groq 路線同款）")
    ap.add_argument("--engine", choices=("auto",) + ENGINES, default="auto")
    ap.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    ap.add_argument("--compute-type", default=None,
                    help="faster-whisper 精度（預設 GPU float16／CPU int8）")
    ap.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB,
                    help=f"詞彙表 markdown（預設 {DEFAULT_VOCAB}）")
    ap.add_argument("--prompt", default=None,
                    help="直接指定 initial prompt，覆寫 --vocab 組出來的結果")
    args = ap.parse_args()

    if not args.audio.exists():
        sys.exit(f"[ERR] 找不到音訊檔：{args.audio}")

    out = args.out or args.audio.with_suffix(".whisper.json")
    prompt = args.prompt if args.prompt is not None else build_prompt(args.vocab)

    add_nvidia_dll_dirs()
    engine = pick_engine(args.engine)
    device = args.device
    if device == "auto":
        device = "cuda" if cuda_available(engine) else "cpu"

    def compute_for(dev: str) -> str:
        return args.compute_type or ("float16" if dev == "cuda" else "int8")

    print(f"[INFO] 引擎 {engine}，模型 {args.model}，裝置 {device}")
    t0 = time.time()
    try:
        segments, words, duration = transcribe(
            engine, args.audio, args.model, device, compute_for(device), prompt)
    except RuntimeError as e:
        # GPU 驅動／DLL 問題常在第一次推論才爆；auto 模式退回 CPU，明確指定 cuda 就照實報錯
        if args.device != "auto" or device != "cuda":
            raise
        print(f"[WARN] GPU 失敗（{str(e)[:200]}），改用 CPU 重跑，會慢很多")
        device = "cpu"
        segments, words, duration = transcribe(
            engine, args.audio, args.model, device, compute_for(device), prompt)

    words = [w for w in words if w["word"].strip()]
    data = {
        "task": "transcribe",
        "language": "zh",
        "duration": duration,
        "text": "".join(s["text"] for s in segments).strip(),
        "segments": segments,
        "words": words,
        "x_local": {"engine": engine, "model": args.model, "device": device},
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    elapsed = time.time() - t0
    print(f"[OK] 輸出 {out}（{len(words)} 詞 / {len(segments)} 段 / "
          f"{duration:.1f}s，耗時 {elapsed:.0f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
