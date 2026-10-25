---
name: audio-to-srt
description: 音訊/影片檔自動生成乾淨 SRT 字幕檔。當使用者要「把音訊轉字幕」「做 SRT」「語音轉文字 + 時間碼」「影片上字幕」時請一定要使用此技能。兩條路線同用 Whisper large-v3-turbo、同樣 word-level 時間碼：本地 faster-whisper（預設，音訊不離開本機）或 Groq（雲端備援）。逐段清字並嚴守時間碼對齊。四種 agent（Claude Code／Codex／OpenCode／Antigravity）共用。
---

# audio-to-srt：音訊 → 乾淨 SRT

## 何時觸發
使用者提供音訊/影片檔（mp3/wav/m4a/mp4/mov/mkv）並要求：
- 轉字幕、生成 SRT、上字幕
- 語音轉文字且要有時間碼
- 字幕清洗、修錯字、潤斷句

## 兩條轉錄路線

| 路線 | 腳本 | 模型 | 時間碼 | 速度 | 隱私 |
|------|------|------|--------|------|------|
| **本地（預設）** | `transcribe_local.py` | large-v3-turbo（faster-whisper） | **word-level** | 有 GPU 快、CPU 慢 | 音訊不離開本機 |
| Groq（備援） | `transcribe_groq.py` | whisper-large-v3-turbo | **word-level** | 快 | 上傳到 Groq |

兩條路線輸出同格式的 JSON，**只有 Step 4 不同**，Step 5 之後（resegment → apply_vocab → 清字 → 驗證）完全共用。
本機沒裝 faster-whisper（例如沒有 GPU、不想裝的筆電）才走 Groq；走 Groq 前若內容可能敏感，先問使用者。

## 核心原則（最重要，違反即失敗）

1. **時間碼神聖不可侵犯**：清字過程 SRT 每塊的 `HH:MM:SS,mmm --> HH:MM:SS,mmm` 那一行**完全不准改動**
2. **段落邊界不可動**：清字階段不得合併兩段、不得拆分一段、不得新增或刪除段落（resegment 階段才能切，且以 word-level 時間碼為準）
3. **只改文字，不改語意**：修錯字、加標點、順語感，但不得增刪內容

---

## 流程

### Step 1：環境檢查
```bash
ffmpeg -version 2>&1 | head -1                                   # 兩條路線都要
python -c "import faster_whisper" && echo "本地 OK"               # 本地路線
```
沒裝本地引擎 → 看有沒有 Groq key（環境變數 `GROQ_API_KEY` 或 `~/.groq_api_key`）。
兩者皆無 → 提示使用者 `python -m pip install faster-whisper` 或設定 Groq key，並中止。

### Step 2：準備工作目錄
在音訊檔同層建立 `_subtitles/` 存放中間產物。

### Step 3：（本地首次）安裝引擎
```bash
python -m pip install faster-whisper
# 有 NVIDIA GPU 時再加（沒裝也能跑，會用 CPU）：
python -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```
第一次執行會從 Hugging Face 下載 large-v3-turbo（約 1.6 GB），之後走快取。

### Step 4：轉錄，產出 word-level JSON

**本地（預設）**：
```bash
python "%USERPROFILE%/.claude/skills/audio-to-srt/scripts/transcribe_local.py" \
  "輸入檔.mp4" \
  --out _subtitles/輸入檔.raw.json
```
- `--device auto`（預設）：有 GPU 就用、推論失敗自動退回 CPU；`--device cpu` 強制 CPU
- `--engine auto`（預設）：先找 faster-whisper，再找 openai-whisper
- 實測（RTX 5060 Ti）：3 分鐘音訊 GPU 約 6 秒；35 秒音訊 CPU 約 12 秒
- 每個 30 秒視窗獨立辨識（不吃前文，防重複幻覺），偶爾會有整個視窗漂成簡體——Step 7 清字時改回繁體

**Groq（備援）**：
```bash
python ".../scripts/transcribe_groq.py" \
  "輸入檔.mp4" \
  --out _subtitles/輸入檔.raw.json
```
Groq 上限 25 MB，超過會吐 **502 Bad Gateway**（Cloudflare 擋掉）。腳本偵測到檔案 > 24 MB 時，
**自動**用 ffmpeg 壓成 16kHz / mono / 32kbps 暫存檔上傳，完成後刪除。78 分鐘片實測從 75 MB → 18 MB，
辨識品質仍佳；壓縮後仍 > 24 MB（罕見）會中止，屆時手動切段。

兩者都產出含 `segments` 與 `words`（每個字都有 start/end）的 JSON；詞彙 prompt 共用 `references/vocabulary.md`。

### Step 5：依 word-level 時間碼重新斷句 → raw SRT
```bash
python ".../scripts/resegment.py" \
  _subtitles/輸入檔.raw.json \
  --audio "輸入檔.mp3" \
  --out _subtitles/輸入檔.raw.srt
```
切點優先序：強標點 `。！？` > segment 邊界 > 弱標點 `，、` > 硬切（往回找標點）。
參數：`MAX_DUR=3.0s`、`MAX_CHARS=15`、`MIN_DUR=0.6s`。

**防孤兒殘尾（2026-07 修正）**：舊版會把「一句話的最後一個字」截到下一段開頭
（如上段結尾『…需要的程』、下段開頭『式,完全免費!』）。已內建兩層防護：
1. **前瞻守衛 `punct_ahead()`**：segment 邊界切（規則 2）與硬超標切（規則 5）
   在動刀前先看後面 1–2 個詞內有沒有標點收尾，有就寬限不切，等標點處自然收尾。
2. **孤兒救援 `rescue_orphan_tails()`**：切完後最終掃描，凡「前段沒標點收尾」且
   段首是「≤2 字＋標點」的殘尾，整批搬回前一段。
   發語詞（『好,』『嗯,』『欸,』…）在兩層都有白名單保護，不會被誤判誤搬。
實測：兩支 40 分鐘影片的真孤兒殘尾 11→0、16→0，發語詞開頭段完好。

`--audio` 會在斷句後呼叫 `ffmpeg silencedetect` 偵測真實靜音（預設 -35 dB、0.25 s），
將每段的 end 縮到靜音起點、下一段的 start 延到靜音終點，讓字幕在靜音處自動留白。
不傳 `--audio` 時維持舊行為（word timestamps 本身無靜音間隔）。

### Step 6：套用詞彙修正（機械式替換）
```bash
python ".../scripts/apply_vocab.py" \
  _subtitles/輸入檔.raw.srt \
  --out _subtitles/輸入檔.vocab.srt
```
規則**不在程式裡**，讀 `references/replacements.md`（表格由上到下依序執行，順序有意義）：
- **保護詞**：`Google Cloud`、`Cloudflare`、`iCloud`、`SoundCloud` 等替換前先遮蔽、跑完還原
- **GPT-Codex 變體**（含 DexDex/Dex Dex/dex dex → Codex）：必須最先處理，避免 Cloud→Claude 後誤判
- **Antigravity / Netlify / clasp / Apps Script** 等工具名誤聽
- **Claude 生態**：ClockCode/CloudCode/ClawCode → Claude Code、克勞德 → Claude
- **Cloud → Claude**（放最後，避免先動到 Cloud Code）
- **常見錯字**：斷考→段考、烤卷→考卷 等

英文規則會自動加詞邊界（`Cloud → Claude` 不會動到 `iCloud`）；**中文規則沒有邊界可言**，
凡是可能出現在正常語句裡的中文字串一律別寫進去，交給清字階段判斷。

自己的規則放 `~/.audio-to-srt/replacements.md`（格式相同，先於內建規則執行，升級不會被覆蓋），
要暫時停用加 `--no-user-rules`。

**只動文字行，時間碼絕不動。**

### Step 7：逐段精修（由 agent 親自讀、親自改）
- 讀 `輸入檔.vocab.srt`
- 依 `references/cleanup_rules.md` 逐段清理（修標點、刪贅詞）
- 每段只改第 3 行之後的文字
- 產出 `_subtitles/輸入檔.clean.srt`

**清字檢查清單：**
- [ ] 段數是否等於 vocab.srt？（不可增減）
- [ ] 時間碼行是否完全沒動？
- [ ] `references/vocabulary.md` 詞彙是否正確呈現？

### Step 8：驗證
```bash
python ".../scripts/validate_srt.py" \
  --raw _subtitles/輸入檔.vocab.srt \
  --clean _subtitles/輸入檔.clean.srt
```
段數一致、時間碼逐一吻合、單調遞增、文字非空。

### Step 9：產出純文字稿
```bash
python ".../scripts/srt_to_txt.py" \
  _subtitles/輸入檔.clean.srt \
  --out 輸入檔.txt
```
適合：YouTube 描述、IG/FB 貼文、封面金句、後製字稿。

### Step 10：交付
**音訊同層放兩份**：
- `輸入檔.srt` — 字幕檔（複製自 clean.srt）
- `輸入檔.txt` — 純文字稿

`_subtitles/` 中間檔保留供稽核。
回報：總段數、總時長、平均段長、txt 字數、主要修改類型。

---

## 檔案結構

```
skills/audio-to-srt/
├── SKILL.md                      # 本檔
├── scripts/
│   ├── transcribe_groq.py        # Groq STT，產 word-level JSON
│   ├── transcribe_local.py       # 本地 Whisper STT，產同格式 JSON
│   ├── resegment.py              # 依 word-level 時間碼重新斷句
│   ├── apply_vocab.py            # 詞彙機械替換（只動文字行）
│   ├── srt_to_txt.py             # SRT → 純文字稿
│   └── validate_srt.py           # 時間碼驗證
└── references/
    ├── cleanup_rules.md          # 清字規則（逐段不跨段）
    ├── replacements.md           # 機械替換規則＋保護詞（apply_vocab.py 讀這份）
    └── vocabulary.md             # 自訂詞彙表
```

## 路線選擇決策樹

```
本機裝了 faster-whisper（preflight 會列）？
├─ 有 → 本地
└─ 無 → 有 GROQ_API_KEY？
        ├─ 有 → Groq（內容可能敏感先問使用者；不同意就裝 faster-whisper 走本地）
        └─ 無 → 提示裝 faster-whisper 或設 Groq key，中止
```

## 踩過的坑

- Whisper 辨識準但斷句差 → word-level 時間碼 + resegment 解決
- Groq 25 MB 上限 → ffmpeg 降取樣（已內建）；本地路線沒有檔案大小上限
- 舊版本地路線只有 segment-level 時間碼、接不上 resegment → 改用 `transcribe_local.py` 開 word timestamps，輸出 Groq 同格式
- Cloud / Claude / Codex 互相誤判 → apply_vocab 順序講究：先處理 GPT-Codex 變體（含 DexDex），再 Claude，最後 Cloud→Claude
- Windows cp950 編碼 → 直接呼叫 `whisper` CLI 時一律加 `PYTHONUTF8=1`（`transcribe_local.py` 已自行用 UTF-8 寫檔）
- 中文檔名上傳 Groq 編碼壞掉 → transcribe_groq.py 內部改用 `audio.<ext>` 上傳
