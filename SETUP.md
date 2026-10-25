# SETUP — 安裝與個人化

這個專案是一條「**原始影片 → AI agent 接力 → 完整 YouTube 上架包**」的生產線。
跟著跑一次，就能在 Claude Code、Codex、OpenCode、Antigravity 任一個 agent 裡重現整套流程。

---

## 0. 這條線在做什麼

1. **smart-cut** — auto-editor 自動剪掉沒講話的片段（去靜音，內建 VFR 防黑畫面）
2. **audio-to-srt** — 本地 Whisper（或 Groq）轉成乾淨 SRT，逐段清字 + 疑慮術語人工勘誤
3. **10 個標題候選** — 停下等你挑
4. **平行產出** — 封面圖（人物基準照 + 頻道風格）、YouTube 描述、社群貼文、SEO 標籤
5. **打包** — 影片 + 字幕 + 純文字 + 封面 + metadata，放進 `output/<標題> [<Agent>]/`
6. **（可選）短片** — 從長片字幕抓亮點剪 ≤2 分鐘 Shorts，含 9:16 直式版

一次跑完整條線：對 agent 說「使用 `youtube-video-workflow` 處理 `raw/<video-id>`」。

---

## 1. 系統前置

| 工具 | 用途 | 安裝 |
|------|------|------|
| Python 3.10+ | 跑技能腳本 | python.org |
| ffmpeg / ffprobe | 影音處理 | `winget install Gyan.FFmpeg`（Win）／`brew install ffmpeg`（Mac） |
| auto-editor | 去靜音剪輯 | `pip install auto-editor` |
| faster-whisper | 本地字幕（預設路線） | `pip install faster-whisper`；有 NVIDIA GPU 再加 `pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"` |
| openai（Python SDK） | 封面生圖（只有 Claude Code／OpenCode 需要） | `pip install openai` |
| Git | 版控（選用） | git-scm.com |

> 第一次跑本地字幕會下載約 1.6 GB 的 large-v3-turbo 模型。沒有 GPU 也能跑（CPU，較慢）；
> 不想裝本地引擎就改用 Groq（見下節），Groq 呼叫用標準函式庫，**不需要**裝 `groq` 套件。

---

## 2. API Key

### Groq（字幕備援，**選填**——裝了 faster-whisper 就不需要）

1. 到 [console.groq.com](https://console.groq.com) 註冊、建立 API Key
2. 存到 `~/.groq_api_key`（整個檔案就是 key 字串），或設環境變數 `GROQ_API_KEY`

> **不要**把 key 檔放在會同步的雲端硬碟資料夾裡。

### OpenAI（封面用，**只有 Claude Code／OpenCode 需要**）

> Codex 與 Antigravity 有內建生圖，**跳過這段**。

1. 到 [platform.openai.com](https://platform.openai.com) 註冊
2. **做 Individual 驗證**（Settings → Organization → General）才能用 gpt-image-2
3. 建立 API Key，存到 `~/.openai.env`：
   ```
   OPENAI_API_KEY=sk-...
   ```
4. 帳戶儲值（gpt-image-2 一張 low quality 約 NT$0.3）

### 四種 agent 的封面差異

| Agent | 封面怎麼生 | 要 `OPENAI_API_KEY` 嗎 | 輸出後綴 |
|-------|-----------|----------------------|---------|
| Claude Code | `skills/cover-image/draw.py` | ✅ | ` [Claude]` |
| Codex | 內建 image 生圖 | ❌ | ` [Codex]` |
| OpenCode | `skills/cover-image/draw.py` | ✅ | ` [OpenCode]` |
| Antigravity | 內建 `generate_image` | ❌ | ` [Antigravity]` |

四邊都遵守同一份 `assets/style/cover-style.md` 與 `assets/persona/` 人物基準照，產出風格才會一致。

---

## 3. 個人化清單（**第一次使用必改**）

| 項目 | 檔案 | 怎麼改 |
|------|------|--------|
| **人物形象照** | `assets/persona/` | 放一張自己的半身照（去背 PNG 最佳），並把 `assets/style/cover-style.md` 內的 `<你的人物照>` 換成實際檔名。**照片不進 git**（已在 `.gitignore`） |
| **頻道封面風格** | `assets/style/cover-style.md` | 目前是模板，把所有 `<...>` 佔位符換成你的色票、構圖、字體、配色規則 |
| **頻道封面參考圖** | `assets/style/reference-thumbnails.png` | （選填）截你頻道現有 9–12 張封面拼成一張。agent 生封面前會讀它學風格 |
| **字幕詞彙表** | `skills/youtube-video-workflow/references/vocabulary.md`（與 `skills/audio-to-srt/references/vocabulary.md` 同步） | 把「頻道／人物」段換成你的頻道名與常出現的人名，補上你常講的專有名詞 |
| **詞彙機械替換** | `skills/youtube-video-workflow/references/replacements.md`（與 `skills/audio-to-srt/references/` 同步） | 在表格加一列「聽成 → 正確」。不想動技能本體就改 `~/.audio-to-srt/replacements.md`，會先於內建規則執行 |
| **疑慮術語掃描** | `.../scripts/find_dubious_terms.py` | `DEFAULT_TERMS` 加入你常講、容易被聽錯的專有名詞 |
| **行銷語氣** | `skills/youtube-video-workflow/references/marketing-spec.md` | 調整貼文口吻、字數、Emoji 規則 |
| **GitHub repo** | `AGENTS.md` | 要做版控就 `git init` 並把 `<你的帳號>/<你的 repo>` 填上 |

---

## 4. 可調參數（每支影片可能不同）

### smart-cut（去靜音）

| 參數 | 預設 | 何時要改 |
|------|------|---------|
| `--threshold` | `0.04` | 剪到字 → 降到 `0.02`；剪太鬆 → 升到 `0.05`／`0.06` |
| `--margin` | `"0.25sec,0.25sec"` | 想要每句話前後更多餘音 → `"0.5sec,0.5sec"`；要節奏很俐落 → `"0sec,0.1sec"` |

技能會先用 45 秒樣本試剪讓你聽節奏，確認後才剪全片。

### cover-image（封面）

| 參數 | 預設 | 何時要改 |
|------|------|---------|
| `--quality` | `low`（NT$0.3，99% 場景夠用） | 實體印刷或極致文字精度 → `high`（NT$5.5） |
| `--size` | `1536x1024`（3:2，接近 16:9） | 要嚴格 16:9 可後處理裁成 `1280x720` |

---

## 5. 環境驗證

一鍵檢查：

```bash
python skills/youtube-video-workflow/scripts/preflight.py
```

手動逐條確認（Windows 含中文路徑請用 **PowerShell**，不要用 Git Bash，避免編碼問題）：

```powershell
python --version                  # 要 3.10+
ffmpeg -version                   # 看到版本號即可
python -m auto_editor --version   # exit code 255 是正常的，看到版本號就對了
```

本地 Whisper／Groq key 檢查（有一個就夠）：

```powershell
python -c "import faster_whisper; print('本地 Whisper: ok')"
```


```powershell
python -c "import os, pathlib; f=pathlib.Path('~/.groq_api_key').expanduser(); k=os.getenv('GROQ_API_KEY') or (f.read_text().strip() if f.exists() else ''); print('Groq key:', 'ok' if k else '缺 — 見第 2 節')"
```

---

## 6. 第一次試跑

```bash
# 1. 把影片放進 raw/<video-id>/source.mp4
# 2. 在任一 agent 裡說：
```

> 使用 youtube-video-workflow 處理 `raw/<video-id>`

agent 會：

1. 讀 `handoff.md`（看上次到哪 — 你應該看到「沒有進行中的影片」）
2. 讀 `AGENTS.md`（工作規範）
3. 用 45 秒樣本試剪 → 你確認節奏 → 剪全片
4. 轉字幕 → **停下來**把有疑慮的專有名詞列給你勘誤
5. 生 10 個標題 → **停下來**等你挑
6. 你挑完 → 建資料夾 → 平行產封面 + metadata → 打包
7. 收工前更新 `handoff.md`

---

## 7. 多 agent 接力

四種 agent 都讀同一份 `AGENTS.md`、寫同一份 `handoff.md`。

**重要：兩個 agent 不要同時動同一支影片**，會搶檔案、搶 commit。

輸出資料夾的 ` [Claude]`／` [Codex]`／` [OpenCode]`／` [Antigravity]` 後綴是為了 A/B 比較不同 agent 的產出品質；覺得不需要就在 `AGENTS.md` 的適配表統一改掉。

---

## 8. 常見問題

**Q：生封面跳 `403 Organization must be verified`？**
A：去 platform.openai.com/settings/organization/general 做 Individual 驗證。

**Q：smart-cut 把我講話的句子剪掉了？**
A：threshold 太嚴，從 `0.04` 降到 `0.02`；或把 margin 加大到 `"0.5sec,0.5sec"`，每句話前後多留緩衝。

**Q：threshold 跟 margin 到底是什麼？**
A：`--threshold` 是音量門檻（多小算靜音，`0.04` = 4%，越大剪越多）；`--margin` 是每段語音前後保留的緩衝（格式 `前,後`）。

**Q：字幕時間碼跟剪好的影片對不上？**
A：你對「原始檔」轉字幕了。**先剪後轉**，順序顛倒必錯位。

**Q：剪完影片中途變全黑只剩聲音？**
A：VFR（可變幀率）原始檔，常見於螢幕錄影。`smart_cut.py` 已內建偵測並先轉 CFR；如果還是黑，回報原始檔的 `avg_frame_rate` 與 `r_frame_rate`。

**Q：`resegment.py` 報 FileNotFoundError？**
A：它不會自動建輸出資料夾，先建好 `working/<video-id>/_subtitles/`。

**Q：我想用其他 AI（Gemini、本地 LLM），還能用嗎？**
A：核心腳本（剪片／字幕／生圖）跟 agent 解耦，可以獨立呼叫。但「標題候選／描述撰寫」需要 LLM 推理，要自己接。

**Q：Groq 會看到我的影片內容嗎？**
A：預設不會。字幕預設走本地 Whisper，音訊不離開本機；只有沒裝 faster-whisper、改走 Groq 備援時才會上傳。
