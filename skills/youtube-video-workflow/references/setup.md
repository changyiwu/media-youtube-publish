# 安裝、個人化與分享規格

## 1. 安裝位置

分享或安裝時複製**完整** `youtube-video-workflow` 資料夾，不要只複製 `SKILL.md`（腳本與 references 都在裡面）。

放在專案內：

```text
<project>/skills/youtube-video-workflow/
```

或裝到各 agent 的全域技能目錄（四種 agent 各一份）：

```text
~/.claude/skills/youtube-video-workflow/        # Claude Code
~/.codex/skills/youtube-video-workflow/         # Codex
~/.config/opencode/skill/youtube-video-workflow/  # OpenCode
~/.antigravity/skills/youtube-video-workflow/   # Antigravity
```

> 實際目錄依各 agent 版本而定；用全域 `skill-sync` 技能同步最省事，它會自己找路徑、逐檔 hash 比對。

全域安裝後專案不必再放一份；技能會把目前工作目錄當專案根目錄。

## 2. 系統需求

- Python 3.10 以上
- ffmpeg 與 ffprobe（加入 PATH）
- auto-editor：`python -m pip install auto-editor`
- Groq 帳號與 API key（只有字幕步驟需要）
- 封面：agent 內建生圖，或 `OPENAI_API_KEY` + `openai` 套件（走 `cover-image/draw.py` 時）

本技能的 Groq 呼叫使用 Python 標準函式庫，不需要安裝 `groq` 套件。

驗證：

```powershell
python "./skills/youtube-video-workflow/scripts/preflight.py"
```

## 3. Groq API key

支援兩個位置，優先順序：

1. 環境變數 `GROQ_API_KEY`
2. 家目錄純文字檔 `~/.groq_api_key`（整個檔案只放 key）

不要把 key 放進技能資料夾、專案、Git、對話內容或螢幕截圖。也**不要**把 key 檔放在會同步的雲端硬碟裡。

## 4. 最小專案結構

```text
project/
├── raw/
├── working/
├── output/
└── skills/
    └── youtube-video-workflow/
```

`AGENTS.md`、`handoff.md`、`assets/style/`、`assets/persona/` 都是選用。存在就讀；不存在仍可剪片、轉字幕、產不含真人的封面。

## 5. 個人化清單（拿到這份技能的人必看）

| 項目 | 要改什麼 |
|------|---------|
| `references/vocabulary.md` | 換成自己的頻道名、人名、產品名與常用術語 |
| `references/replacements.md` 的表格 | 加入自己內容裡「Whisper 常聽錯 → 正確」的對照；個人規則可放 `~/.audio-to-srt/replacements.md` |
| `scripts/find_dubious_terms.py` 的 `DEFAULT_TERMS` | 加入自己常講、容易被聽錯的專有名詞 |
| `references/marketing-spec.md` | 調整貼文口吻、字數、Emoji 規則與平台規格 |
| `assets/persona/` | 放自己的人物基準照（原始照，不是生成圖） |
| `assets/style/cover-style.md` | 定義自己的色票、構圖、字型與禁止事項 |
| `assets/style/reference-thumbnails.png` | 選放 9–12 張既有封面拼成一張圖 |

不做個人化也能剪片與轉字幕，但機械詞彙替換會不符合你的內容，人物封面也不會像你。

## 6. 分享前檢查

- 資料夾內沒有 `.groq_api_key`、`.env`、影片、音訊、逐字稿或人物私密照片
- 沒有 `__pycache__`、`.pyc`、工作中間檔或輸出成品
- `python -m py_compile` 可編譯全部腳本
- 在乾淨測試專案跑 `preflight.py`，確認錯誤訊息清楚
- 明確告知接收者：**Groq 會收到音訊內容**，生圖服務會收到封面參考素材
