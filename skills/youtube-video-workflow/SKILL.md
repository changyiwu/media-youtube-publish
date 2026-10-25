---
name: youtube-video-workflow
description: 通用的 YouTube 影片自動化生產總控技能，四種 agent（Claude Code／Codex／OpenCode／Antigravity）共用同一份流程。當使用者要求處理 raw 裡的新影片、一次跑完整 YouTube 生產線（剪口播→轉字幕→疑慮字幕確認→標題→封面→metadata→打包→可選短片）、剪口播去靜音、把影片轉 SRT 字幕、產標題候選、做封面、寫 YouTube 描述／社群貼文／SEO 標籤、剪 Shorts 短片，或說「使用 youtube-video-workflow」時使用。封面依執行中的 agent 自動選路：有內建生圖就用內建，沒有才呼叫 cover-image/draw.py。
---

# youtube-video-workflow：YouTube 影片生產總控（通用版）

一支原始影片進來 → 交付一整包可直接上架的素材。**同一份流程，四種 agent 共用**，差別只在「封面怎麼生」與「輸出資料夾標籤」兩件事（見下方適配表）。

## 一條龍總覽

```
階段 1 長片：剪口播 → 轉字幕 → 🛑STOP1 疑慮字幕確認 → 時間碼硬關卡
            → 🛑STOP2 標題確認 → 封面 → metadata → 打包
階段 2 短片（可選）：讀完整字幕 → 亮點偵測 → 🛑STOP3 三候選確認
            → 切片組片 → 短片標題 → 短片 metadata → 打包
```

- **🛑 STOP**：三個關卡都必須**停下等使用者拍板**，不准自己猜了就往下衝。
- **硬關卡**：`validate_srt.py` 不通過（段數不一致／時間碼對不上）→ **中止交付並回報**，不得硬出。
- **防斷字**：斷句靠 `resegment.py` 的切點優先序；短片切片一律對齊字幕段落邊界，**不准切到一句話中間**。
- 使用者沒要短片就停在階段 1 收尾。

---

## Agent 適配表（唯一需要分辨 agent 的地方）

| Agent | 封面生成路線 | 需要 `OPENAI_API_KEY` | 輸出資料夾後綴 |
|-------|-------------|----------------------|---------------|
| **Claude Code** | 呼叫 `skills/cover-image/draw.py`（gpt-image-2） | ✅ | ` [Claude]` |
| **Codex** | 用**內建 image 生圖工具**，不要跑 draw.py | ❌ | ` [Codex]` |
| **OpenCode** | 呼叫 `skills/cover-image/draw.py`（同 Claude 路線） | ✅ | ` [OpenCode]` |
| **Antigravity** | 用**內建 `generate_image`**，不要跑 draw.py | ❌ | ` [Antigravity]` |

判斷原則一句話：**你有內建生圖就用內建，沒有才走 draw.py**。短片資料夾後綴則是 ` [<Agent>] (Short)`。

其餘所有步驟（剪片、字幕、標題、metadata、打包、交班）四種 agent 完全相同，不要各自發明流程。

---

## 路徑與專案契約

1. 把 `SKILL.md` 所在資料夾解析為 `<SKILL_DIR>`（技能可能裝在專案內，也可能裝在全域技能目錄）。
2. 把目前工作目錄解析為 `<PROJECT_ROOT>`。
3. 開工前先讀（存在才讀，不存在就跳過）：`AGENTS.md`、`handoff.md`、`README.md`。
4. 預設資料夾：輸入 `raw/<video-id>/`、中間檔 `working/<video-id>/`、交付 `output/<標題> [<Agent>]/`。
5. 影片、音訊、API key 一律不進 Git。

首次安裝或要分享給別人，先讀 [setup.md](references/setup.md)。

## 不可省略的原則

- **先剪片、再轉字幕**，SRT 時間碼才會對齊成片。順序顛倒必錯位。
- 先用約 45 秒代表性片段試剪，讓使用者確認節奏；除非使用者已指定參數或明確授權全自動跑完。
- Groq 會把音訊送到第三方服務。內容可能敏感時先取得同意；不同意就停止上傳，改走本地 Whisper（`transcribe_local.py`）。
- 絕不顯示、回傳、寫入或提交 API key。只從 `GROQ_API_KEY` 或 `~/.groq_api_key` 讀取。
- 不自行修正不確定的人名、產品名、縮寫、數字或校名；列出字幕段號讓使用者確認。
- 不增刪字幕段落、不改時間碼。`validate_srt.py` 未通過就停止交付。
- 每次生人物封面都**重新讀取原始人物基準照**，不沿用舊封面或衍生圖片。
- PowerShell 路徑一律用 `-LiteralPath` 或完整引號，避免空白與 `[Claude]` 這類中括號被當萬用字元。
- **路徑分隔符一律正斜線**。macOS 的反斜線是合法檔名字元、不是分隔符，`Test-Path` 會靜默回 `False`；正斜線在 Windows 與 macOS 的 pwsh 都通。

---

## 0. 執行前檢查

```powershell
$SkillDir = (Resolve-Path "./skills/youtube-video-workflow").Path
python "$SkillDir/scripts/preflight.py"
```

技能裝在全域位置時，把 `$SkillDir` 設成實際 `SKILL.md` 的父資料夾。缺 Python、ffmpeg、ffprobe 或 auto-editor 時依輸出修正後再繼續。

## 1. 收件與試剪

1. 確認唯一輸入影片，建立 `working/<video-id>/` 與 `working/<video-id>/_subtitles/`。
2. 用 ffprobe 取得原始長度、解析度、幀率與音軌。
3. 從約全片三分之一處擷取 45 秒代表性樣本試剪，讓使用者聽節奏：
   - 剪到字 → threshold 降到 `0.02`、margin 提到 `0.5sec,0.5sec`
   - 太鬆 → threshold 提到 `0.05`／`0.06`
4. 使用者確認後才用相同參數剪完整片。

```powershell
python "$SkillDir/scripts/smart_cut.py" `
  "raw/<video-id>/source.mp4" `
  --out "working/<video-id>/<video-id>.cut.mp4" `
  --threshold 0.04 `
  --margin "0.25sec,0.25sec"
```

腳本會比對平均幀率與宣告幀率，只要不同就先轉 CFR，再在本機暫存區完成 auto-editor，最後複製回目標路徑——避免 VFR 黑畫面與雲端硬碟寫入消失。

剪完用 ffprobe 比對原長與新長，抽查開頭／中段／尾段畫面與音訊，回報剪除比例（例：`原長 14:00 → 新長 1:42（剪掉 88%）`）。

## 2. 字幕管線

```powershell
$Work = "working/<video-id>"
$Cut  = "$Work/<video-id>.cut.mp4"
$Sub  = "$Work/_subtitles"

python "$SkillDir/scripts/transcribe_groq.py" $Cut --out "$Sub/raw.json"
# 或本地（音訊不上傳）：python "$SkillDir/scripts/transcribe_local.py" $Cut --out "$Sub/raw.json"
python "$SkillDir/scripts/resegment.py" "$Sub/raw.json" --audio $Cut --out "$Sub/raw.srt"
python "$SkillDir/scripts/apply_vocab.py" "$Sub/raw.srt" --out "$Sub/vocab.srt"
python "$SkillDir/scripts/find_dubious_terms.py" "$Sub/vocab.srt" --out "$Sub/dubious-terms.md"
```

兩支轉錄腳本擇一，輸出同格式的 `raw.json`，後面的指令完全相同。

- `transcribe_groq.py`：雲端，快。檔案超過 Groq 上限時會用 ffmpeg 產 16 kHz／mono／32 kbps 暫存音訊，不動原檔
- `transcribe_local.py`：本機 faster-whisper（同款 large-v3-turbo），有 NVIDIA GPU 時自動用、失敗退回 CPU；第一次跑會下載約 1.6 GB 模型

兩支都可直接餵 `cut.mp4`，不必自己先抽音訊。

### 🛑 STOP 1：疑慮術語確認（不准跳過）

1. 讀完整 `vocab.srt` 與 `dubious-terms.md`。
2. 只修正能從上下文確定的項目；**仍有疑慮的段落連段號、原文、建議一起列給使用者，然後停下**。
3. 收到確認後套用修正：

```powershell
python "$SkillDir/scripts/finalize_subtitles.py" "$Sub/vocab.srt" `
  --out "$Sub/clean.srt" `
  --replace "舊字->新字" `
  --replace "390:AGE->Agent"

python "$SkillDir/scripts/validate_srt.py" --raw "$Sub/vocab.srt" --clean "$Sub/clean.srt"
python "$SkillDir/scripts/srt_to_txt.py" "$Sub/clean.srt" --out "$Work/<video-id>.txt"
Copy-Item -LiteralPath "$Sub/clean.srt" -Destination "$Work/<video-id>.srt" -Force
```

段落限定替換用 `段號:舊->新` 格式（例 `390:AGE->Agent`），避免誤傷（如 Gemini 裡的 Gem）。

清字規則讀 [cleanup-rules.md](references/cleanup-rules.md)；專有名詞讀 [vocabulary.md](references/vocabulary.md)——**這兩份要換成你自己頻道的用詞**。

**時間碼硬關卡**：`validate_srt.py` 段數不一致或時間碼對不上 → 中止，回報差異，不得交付。

## 3. 🛑 STOP 2：標題確認

1. 讀清字後的完整逐字稿。
2. 產 **10 個**標題候選，分組讓使用者好比較：痛點／解放型、教學／Know-how 型、對比／反問型、具體／案例型 各 2–3 個。
3. 寫進 `working/<video-id>/titles.md`。
4. **把候選列給使用者並停下，不要自己挑、不要往下跑。**

使用者選定後，移除 Windows 不合法字元 `？！：／＼?!:/\<>|"*`、避免以空白或句點結尾，建立 `output/<標題> [<Agent>]/`。**資料夾加後綴、裡面的檔案不加。**

## 4. 封面

**生封面前 SOP（缺一不可、每支影片都要重做）：**

1. 若專案已有這一集的現成封面，且使用者沒要求重做 → 直接沿用。
2. 讀 `assets/style/cover-style.md`（頻道風格指南：色票、構圖、字體、禁止事項）。
3. 讀 `assets/style/reference-thumbnails.png`（若有，看頻道既有封面內化風格）。
4. **重新讀 `assets/persona/` 內的人物基準照**——不可拿上一張封面或任何衍生圖當輸入，模型會放大誤差、越生越不像。
5. 依 `cover-style.md` 的主題配色規則決定本支主色。
6. 依適配表選封面生成路線：

**有內建生圖（Codex／Antigravity）**：把人物基準照當 reference image 傳給內建工具，產出後複製到 `output/<標題> [<Agent>]/cover.png`。若內建工具不支援 reference image，只能用 prompt 約束人物特徵，並**明確回報這個限制**，不要宣稱像本人。

**沒有內建生圖（Claude Code／OpenCode）**：

```powershell
python skills/cover-image/draw.py "<prompt>" `
  --edit "assets/persona/<你的人物照>.png" `
  --size 1536x1024 --quality low `
  --name cover --outdir "output/<標題> [<Agent>]"
```

跑完刪掉時間戳檔名版本，只留一份 `cover.png`，並用 Read 看一眼確認人物樣貌與主色正確。

沒有人物照時，產不含真人的主題封面，或請使用者補圖。

**Prompt 撰寫要點**：只描述「位置、姿勢、場景、文字、配色」，**不要重新描述五官／髮型／穿著屬性**——那些交給基準照，重複描述會讓模型妥協走樣。填空範本見 `assets/style/cover-style.md`。

## 5. Metadata 與長片打包

先讀 [marketing-spec.md](references/marketing-spec.md)，依**清字後逐字稿**（不是憑空想像）寫 `metadata.md`，至少包含：

1. 選定標題 + 10 個候選（好奇／價值／痛點三風格穿插）
2. YouTube 描述 ≤300 字：Hook（前兩行吸睛）+ 3 個關鍵知識點列點 + CTA
3. 社群貼文（FB／IG／Threads）：**嚴禁 Emoji**、每段 ≤3 行、150–200 字、結尾留互動問題
4. SEO 關鍵字 15–20 個
5. **「YouTube 標籤欄位（直接複製）」**：半形逗號分隔版 + 「全部一次貼」整合版
6. 依 SRT 產生的建議章節時間碼
7. 上架前 checklist

交付 5 個檔案：

```text
output/<標題> [<Agent>]/
├── <標題>.mp4      # 從 working/ 複製過來改名
├── <標題>.srt
├── <標題>.txt
├── cover.png
└── metadata.md
```

**自我檢查清單**：

- [ ] 資料夾名結尾有 ` [<Agent>]` 後綴，檔名沒有
- [ ] 5 個檔案齊全、都能開啟
- [ ] 影片檔名等於 YouTube 標題、時長合理
- [ ] SRT 通過 `validate_srt.py`
- [ ] cover.png 為 16:9、人物延續基準照、主色正確
- [ ] metadata.md 含「全部一次貼」整合版標籤
- [ ] `handoff.md` 已更新本支影片狀態、輸出位置、待審事項、下一步

## 6. 短片流程（可選）

只有使用者要求 Shorts／短片／亮點時才跑。完整規格見 `skills/short-video-workflow/SKILL.md`，重點關卡：

1. **強制讀完整 `<video-id>.srt`**，不准只看片段就抓亮點。
2. **亮點偵測**：痛點宣告／反問／數字承諾／強斷言／轉折揭密／價值結算，每段給 0–3 分。
3. **🛑 STOP 3：三候選確認**——組 A 痛點型／B 好奇型／C 承諾型三版，各走三幕結構（Hook ≤5s → Body → CTA）、≤120 秒，寫進 `working/<video-id>/shorts-candidates.md`，**列時間碼與劇本給使用者選 A/B/C**（或使用者自給時間碼）。
4. **切片組片**（切點對齊字幕段落邊界）：

```powershell
python "$SkillDir/scripts/clip_cut.py" `
  --input-mp4 "$Work/<video-id>.cut.mp4" `
  --input-srt "$Work/<video-id>.srt" `
  --segments "00:00:08.500-00:00:13.200,00:00:45.100-00:01:30.800" `
  --out-dir "$Work/short-tmp"

python "$SkillDir/scripts/add_end_card.py"   --input-mp4 "$Work/short-tmp/short.mp4" --output-mp4 "$Work/short-tmp/short-with-card.mp4"
python "$SkillDir/scripts/burn_subtitles.py" "$Work/short-tmp/short-with-card.mp4" "$Work/short-tmp/short.srt" "$Work/short-tmp/short-subtitled.mp4"
python "$SkillDir/scripts/make_vertical.py"  "$Work/short-tmp/short-subtitled.mp4" --out "$Work/short-tmp/short-9x16.mp4"
```

5. **短片標題**：出 3 個更短更聳動的候選等使用者選（短片不需要 10 個）。
6. **短片 metadata**：套用 `marketing-spec.md` 的「C. 短片差異」覆寫（標題 3 個、描述 ≤150 字、`#Shorts` 必備、標籤結尾加 `Shorts,短影片`）。
7. 以 `[<Agent>] (Short)` 後綴打包 **7 個檔案**：16:9 乾淨版、16:9 燒字幕版、9:16 直式版、srt、txt、cover.png、metadata.md。

## 失敗處理

- **找不到 Groq key**：preflight 有列本地 Whisper 就改走 `transcribe_local.py`；都沒有才停在字幕步驟，指出 `GROQ_API_KEY` 與 `~/.groq_api_key` 兩個位置，**不要**要求使用者把 key 貼在對話中。
- **Groq 413／檔案仍過大**：切成有重疊的小段轉錄再合併時間碼，不要降到難以辨識的音質。
- **VFR 或黑畫面**：不要交付。重轉 CFR 後重剪，抽查多個時間點。
- **雲端硬碟寫入不穩**：保留系統暫存區的成功產物，確認大小與時長後再複製回專案。
- **中文字幕燒錄失敗**：檢查 ffmpeg 是否含 subtitles／drawtext filter 與字型路徑；仍失敗就交付外掛 SRT，**不要宣稱已燒錄**。
- **gpt-image-2 回 403 Organization must be verified**：到 platform.openai.com 做 Individual 驗證。
- **`auto-editor` 不在 PATH**：沒關係，`smart_cut.py` 會自動 fallback 到 `python -m auto_editor`（`--version` 回傳 exit code 255 是正常的）。
- **`resegment.py` 報 FileNotFoundError**：它不會自動建輸出資料夾，先建好 `_subtitles/`。
- **使用者打斷或改需求**：立即停止目前階段，依最新指示續跑，不跨越確認關卡。
