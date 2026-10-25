---
name: youtube-long
description: YouTube 長片生產線，四種 agent（Claude Code／Codex／OpenCode／Antigravity）共用同一份流程。當使用者要處理 raw 裡的新影片、一次跑完長片（剪口播去靜音→轉字幕→疑慮字幕確認→標題→封面→發布資訊→打包），或只要其中幾步（只去靜音、剪片加字幕不要行銷素材）時使用。字幕走同層的 audio-to-srt 技能，封面走全域 draw 與同層的 cover 技能，剪 Shorts 接 youtube-shorts 技能。
---

# youtube-long：YouTube 長片生產線

一支原始影片進來 → 交付一整包可直接上架的素材。**同一份流程，四種 agent 共用**，差別只在「封面底圖怎麼生」與「輸出資料夾後綴」（見適配表）。

## 總覽

```
1 去靜音 → 2 字幕（audio-to-srt）→ 🛑STOP1 疑慮術語 → 時間碼硬關卡
  → 3 🛑STOP2 標題 → 4 封面（draw → cover）→ 5 發布資訊與打包
（要 Shorts 再接 youtube-shorts 技能）
```

| 使用者要的 | 跑哪幾步 |
|---|---|
| 一次跑完整支長片 | 0–5 |
| 只想去靜音 | 0–1 |
| 只要影片＋字幕，不要行銷素材 | 0–2，交付 `cut.mp4`、`.srt`、`.txt` 後停 |
| 只想轉字幕（不必剪片） | 直接用 `audio-to-srt` 技能 |

- **🛑 STOP**：關卡都必須**停下等使用者拍板**，不准自己猜了就往下衝。
- **硬關卡**：`validate_srt.py` 不通過（段數不一致／時間碼對不上）→ **中止交付並回報**，不得硬出。

---

## Agent 適配表（唯一需要分辨 agent 的地方）

| Agent | 封面底圖 | 輸出資料夾後綴 |
|-------|---------|---------------|
| **Claude Code** | 全域 `draw` 技能（Codex CLI 代生或 gpt-image-2） | ` [Claude]` |
| **Codex** | 內建 image 生圖工具 | ` [Codex]` |
| **OpenCode** | 全域 `draw` 技能（同 Claude） | ` [OpenCode]` |
| **Antigravity** | 內建 `generate_image` | ` [Antigravity]` |

判斷原則一句話：**有內建生圖就用內建，沒有就用 `draw` 技能**（它自己會選路線）。疊字一律用同層的 `cover` 技能。

其餘所有步驟四種 agent 完全相同，不要各自發明流程。

---

## 路徑與專案契約

1. 本技能在專案內使用：`<PROJECT_ROOT>` 是 `media-youtube-publish/`，技能在 `skills/youtube-long/`。
2. 同層技能直接引用，不複製：字幕腳本在 `skills/audio-to-srt/scripts/`，封面疊字在 `skills/cover/`。
3. 開工前先讀（存在才讀）：`AGENTS.md`、`handoff.md`、`README.md`。
4. 資料夾：輸入 `raw/<video-id>/`、中間檔 `working/<video-id>/`、交付 `output/<標題> [<Agent>]/`。
5. 影片、音訊、API key 一律不進 Git。

```powershell
$SkillDir = (Resolve-Path "./skills/youtube-long").Path
$SrtDir   = (Resolve-Path "./skills/audio-to-srt").Path
$CoverDir = (Resolve-Path "./skills/cover").Path
```

首次安裝或要分享給別人，先讀 [setup.md](references/setup.md)。

## 不可省略的原則

- **先剪片、再轉字幕**，SRT 時間碼才會對齊成片。順序顛倒必錯位。
- 先用約 45 秒代表性片段試剪，讓使用者確認節奏；除非使用者已指定參數或明確授權全自動跑完。
- 字幕預設走本地 Whisper。只有本機沒裝引擎、要改走 Groq 時才會把音訊送到第三方服務；內容可能敏感時先取得同意。
- 絕不顯示、回傳、寫入或提交 API key。
- 不自行修正不確定的人名、產品名、縮寫、數字或校名；列出字幕段號讓使用者確認。
- 每次生人物封面都**重新讀取原始人物基準照**，不沿用舊封面或衍生圖片。
- PowerShell 路徑一律用 `-LiteralPath` 或完整引號，避免 `[Claude]` 這類中括號被當萬用字元。
- **路徑分隔符一律正斜線**（macOS 的反斜線不是分隔符，`Test-Path` 會靜默回 `False`）。

---

## 0. 執行前檢查

```powershell
python "$SkillDir/scripts/preflight.py"
```

檢查 Python、ffmpeg、ffprobe、auto-editor、本地 Whisper／Groq key、同層技能與登記的套件。`[ERR]` 先修正再繼續。

## 1. 收件與去靜音

1. 確認唯一輸入影片，建立 `working/<video-id>/` 與 `working/<video-id>/_subtitles/`。
2. 用 ffprobe 取得原始長度、解析度、幀率與音軌。
3. 從約全片三分之一處擷取 45 秒代表性樣本試剪，讓使用者聽節奏：
   - 剪到字 → threshold 降到 `0.02`、margin 提到 `0.5sec,0.5sec`
   - 太鬆或雜訊多 → threshold 提到 `0.05`／`0.06`
   - 停頓多、聽起來太急 → margin 拉到 `0.3sec` 以上
4. 使用者確認後才用相同參數剪完整片。

```powershell
python "$SkillDir/scripts/smart_cut.py" `
  "raw/<video-id>/source.mp4" `
  --out "working/<video-id>/<video-id>.cut.mp4" `
  --threshold 0.04 `
  --margin "0.25sec,0.25sec"
```

腳本底層是 auto-editor：比對平均與宣告幀率，不同就先轉 CFR（防 VFR 黑畫面），在本機暫存區剪完再複製回目標路徑（防雲端硬碟寫入消失）。

剪完用 ffprobe 比對原長與新長，抽查開頭／中段／尾段畫面與音訊，回報剪除比例（例：`原長 14:00 → 新長 1:42（剪掉 88%）`）。
含背景音樂的段落可能被誤判為靜音，要先標記、事後補回。

## 2. 字幕（照 audio-to-srt 技能）

**完整規則、參數與清字原則以 [`../audio-to-srt/SKILL.md`](../audio-to-srt/SKILL.md) 為準**，這裡只列長片的串法：

```powershell
$Work = "working/<video-id>"
$Cut  = "$Work/<video-id>.cut.mp4"
$Sub  = "$Work/_subtitles"

python "$SrtDir/scripts/transcribe_local.py" $Cut --out "$Sub/raw.json"
# 沒裝本地引擎時改 Groq：python "$SrtDir/scripts/transcribe_groq.py" $Cut --out "$Sub/raw.json"
python "$SrtDir/scripts/resegment.py" "$Sub/raw.json" --audio $Cut --out "$Sub/raw.srt"
python "$SrtDir/scripts/apply_vocab.py" "$Sub/raw.srt" --out "$Sub/vocab.srt"
python "$SrtDir/scripts/find_dubious_terms.py" "$Sub/vocab.srt" --out "$Sub/dubious-terms.md"
```

### 🛑 STOP 1：疑慮術語確認（不准跳過）

1. 讀完整 `vocab.srt` 與 `dubious-terms.md`。
2. 只修正能從上下文確定的項目；**仍有疑慮的段落連段號、原文、建議一起列給使用者，然後停下**。
3. 收到確認後套用修正、驗證、產出：

```powershell
python "$SrtDir/scripts/finalize_subtitles.py" "$Sub/vocab.srt" `
  --out "$Sub/clean.srt" --replace "舊字->新字" --replace "390:AGE->Agent"
python "$SrtDir/scripts/validate_srt.py" --raw "$Sub/vocab.srt" --clean "$Sub/clean.srt"
python "$SrtDir/scripts/srt_to_txt.py" "$Sub/clean.srt" --out "$Work/<video-id>.txt"
Copy-Item -LiteralPath "$Sub/clean.srt" -Destination "$Work/<video-id>.srt" -Force
```

**時間碼硬關卡**：`validate_srt.py` 段數不一致或時間碼對不上 → 中止，回報差異，不得交付。

## 3. 🛑 STOP 2：標題確認

1. 讀清字後的完整逐字稿。
2. 照 [marketing-spec.md](references/marketing-spec.md) 產 **10 個**標題候選（好奇／價值／痛點三種風格穿插），分組讓使用者好比較。
3. 寫進 `working/<video-id>/titles.md`。
4. **把候選列給使用者並停下，不要自己挑、不要往下跑。**

使用者選定後，移除 Windows 不合法字元 `？！：／＼?!:/\<>|"*`、避免以空白或句點結尾，建立 `output/<標題> [<Agent>]/`。**資料夾加後綴、裡面的檔案不加。**

## 4. 封面：先生底圖，再疊字

1. 若這一集已有現成封面且使用者沒要求重做 → 直接沿用。
2. 讀 `assets/style/cover-style.md`（色票、構圖、字體、禁止事項）與 `assets/style/reference-thumbnails.png`（若有）。
3. **重新讀 `assets/persona/` 內的人物基準照**——不可拿上一張封面或衍生圖當輸入，誤差會越滾越大。
4. **生底圖**（不寫字、文字那一角留乾淨）：
   - 有內建生圖：把人物基準照當 reference image 傳給內建工具。不支援 reference image 時只能用 prompt 約束人物特徵，並**明確回報這個限制**，不要宣稱像本人。
   - 沒有內建生圖：用全域 `draw` 技能，帶 `--edit "assets/persona/<人物照>.png"`、`--size 1536x1024`，輸出到 `working/<video-id>/cover-base.png`。
   - Prompt 只描述「位置、姿勢、場景、配色」，**不要重新描述五官／髮型／穿著**——那些交給基準照。
   - 沒有人物照時，產不含真人的主題底圖，或請使用者補圖。
5. **疊字**（照 `cover` 技能）：

```powershell
python "$CoverDir/cover.py" "working/<video-id>/cover-base.png" `
  --text "<6 字內主標>" --font "<OFL 字型>" --corner br `
  --formats yt --outdir "output/<標題> [<Agent>]"
```

`--corner` 選不擋到臉的角。用 Read 看一眼確認人物樣貌、主色與文字位置。

## 5. 發布資訊與打包

把 [發布資訊範本.md](references/發布資訊範本.md) 複製成 `output/<標題> [<Agent>]/發布資訊.md`，再照 [marketing-spec.md](references/marketing-spec.md) 依**清字後逐字稿**填寫，刪掉用不到的段落與 `<…>` 佔位。至少包含：

1. 選定標題 + 10 個候選
2. YouTube 說明欄：Hook + 3 個關鍵知識點 + 依 SRT 的章節時間碼 + CTA，開場到 CTA ≤300 字
3. AI 與製作方式揭露、工具名單（每個平台都要有）
4. 標籤：SEO 關鍵字 15–20 個，整理成可直接貼進 YouTube 標籤欄的一行
5. 社群貼文：Facebook、Instagram 各一版＋ Threads 短文
6. 封面與 Studio 設定、發布前檢查

交付 5 個檔案：

```text
output/<標題> [<Agent>]/
├── <標題>.mp4      # 從 working/ 複製過來改名
├── <標題>.srt
├── <標題>.txt
├── cover.png
└── 發布資訊.md
```

**自我檢查清單**：

- [ ] 資料夾名結尾有 ` [<Agent>]` 後綴，檔名沒有
- [ ] 5 個檔案齊全、都能開啟
- [ ] 影片檔名等於 YouTube 標題、時長合理
- [ ] SRT 通過 `validate_srt.py`
- [ ] cover.png 為 1280×720、人物延續基準照、主色正確、字沒擋臉
- [ ] 發布資訊.md 照範本結構、各平台都有 AI 揭露、標籤一行可直接貼上
- [ ] `handoff.md` 已更新本支影片狀態、輸出位置、待審事項、下一步

使用者要 Shorts → 接 [`../youtube-shorts/SKILL.md`](../youtube-shorts/SKILL.md)。

## 失敗處理

- **沒有本地 Whisper 也沒有 Groq key**：停在字幕步驟，建議 `python -m pip install faster-whisper`，或指出 `GROQ_API_KEY` 與 `~/.groq_api_key` 兩個位置，**不要**要求使用者把 key 貼在對話中。
- **VFR 或黑畫面**：不要交付。重轉 CFR 後重剪，抽查多個時間點。
- **雲端硬碟寫入不穩**：保留系統暫存區的成功產物，確認大小與時長後再複製回專案。
- **`auto-editor` 不在 PATH**：沒關係，`smart_cut.py` 會自動改用 `python -m auto_editor`（`--version` 回傳 exit code 255 是正常的）。
- **`resegment.py` 報 FileNotFoundError**：它不會自動建輸出資料夾，先建好 `_subtitles/`。
- **gpt-image-2 回 403 Organization must be verified**：到 platform.openai.com 做 Individual 驗證。
- **使用者打斷或改需求**：立即停止目前階段，依最新指示續跑，不跨越確認關卡。
