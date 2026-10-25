# 安裝、個人化與分享規格

## 1. 安裝位置

本專案的技能**在專案內使用**（見 `AGENTS.md`〈Skills 用哪一個〉）。`youtube-long` 會直接引用同層技能，所以要整包一起放：

```text
<project>/skills/
├── youtube-long/      # 長片生產線（本技能）
├── youtube-shorts/    # 長片 → Shorts（選用）
├── audio-to-srt/      # 字幕；youtube-long 第 2 步直接用它的腳本
└── cover/             # 封面疊字；youtube-long 第 4 步用
```

分享給別人時**四個資料夾一起複製**，只複製 `youtube-long` 會在字幕步驟斷掉（`preflight.py` 會擋下）。
封面底圖另外需要全域的 `draw` 技能（有內建生圖的 agent 不需要）。

`audio-to-srt` 與 `cover` 也可以用 `skill-sync` 裝到各 agent 的全域技能目錄，給其他專案用；
`youtube-long`、`youtube-shorts` 不需要裝到全域。

## 2. 系統需求

- Python 3.10 以上
- ffmpeg 與 ffprobe（加入 PATH）
- auto-editor：`python -m pip install auto-editor`
- 字幕：本地 `faster-whisper`（預設），或 Groq 帳號與 API key（備援）
- 封面：agent 內建生圖或全域 `draw` 技能生底圖；疊字用 `pillow`（`cover` 技能）

本專案的 Groq 呼叫使用 Python 標準函式庫，不需要安裝 `groq` 套件。

驗證：

```powershell
python "./skills/youtube-long/scripts/preflight.py"
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
    ├── youtube-long/
    ├── audio-to-srt/
    └── cover/
```

`AGENTS.md`、`handoff.md`、`assets/style/`、`assets/persona/` 都是選用。存在就讀；不存在仍可剪片、轉字幕、產不含真人的封面。

## 5. 個人化清單（拿到這套技能的人必看）

| 項目 | 要改什麼 |
|------|---------|
| `audio-to-srt/references/vocabulary.md` | 換成自己的頻道名、人名、產品名與常用術語 |
| `audio-to-srt/references/replacements.md` 的表格 | 加入自己內容裡「Whisper 常聽錯 → 正確」的對照；個人規則可放 `~/.audio-to-srt/replacements.md` |
| `audio-to-srt/scripts/find_dubious_terms.py` 的 `DEFAULT_TERMS` | 加入自己常講、容易被聽錯的專有名詞 |
| `youtube-long/references/marketing-spec.md` | 調整標題風格、貼文口吻與字數；平台規則與結構在同資料夾的 `發布資訊範本.md` |
| `assets/persona/` | 放自己的人物基準照（原始照，不是生成圖） |
| `assets/style/cover-style.md` | 從範本 `cover-style.example.md` 複製後，定義自己的色票、構圖、字型與禁止事項（個人檔，不進 git） |
| `assets/style/reference-thumbnails.png` | 選放 9–12 張既有封面拼成一張圖 |

不做個人化也能剪片與轉字幕，但機械詞彙替換會不符合你的內容，人物封面也不會像你。

## 6. 分享前檢查

- 資料夾內沒有 `.groq_api_key`、`.env`、影片、音訊、逐字稿或人物私密照片
- 沒有 `__pycache__`、`.pyc`、工作中間檔或輸出成品
- `python -m py_compile` 可編譯全部腳本
- 在乾淨測試專案跑 `preflight.py`，確認錯誤訊息清楚
- 明確告知接收者：**Groq 會收到音訊內容**，生圖服務會收到封面參考素材
