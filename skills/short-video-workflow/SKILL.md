---
name: short-video-workflow
description: 從已剪過的長片（cut.mp4 + .srt）擷取亮點片段，組成 ≤2 分鐘的短片。當使用者要『剪 short / 做短片 / 抓亮點 / 剪精華 / 做 YouTube Shorts』時請使用此 Skill。會依字幕亮點偵測產 3 個候選版本（痛點型/好奇型/承諾型），等使用者選；也接受使用者直接給時間碼或描述覆寫。輸出走 `output/<短片標題> [<Agent>] (Short)/`（`<Agent>` 為 Claude／Codex／OpenCode／Antigravity），含 16:9 乾淨版/16:9 字幕版/9:16 直式版/srt/txt/cover/發布資訊 七個檔（YouTube Shorts 發布用直式版）。
---

# short-video-workflow：長片亮點 → ≤2 分鐘短片

## 何時觸發
使用者說：
- 「幫我剪一個 short / 短片」
- 「把這支影片的亮點抓出來做精華」
- 「做一個 2 分鐘的版本」
- 「用 X 段時間碼剪一個短片」

## 前置條件
**必須有**已跑完 `youtube-video-workflow` 的長片產物：
- `working/<video-id>/<video-id>.cut.mp4`（剪口播完的版本）
- `working/<video-id>/<video-id>.srt`（清字完的字幕，時間碼對齊 cut.mp4）

如果這兩個檔案還沒生，先跑長片總控流程。

---

## 規格（來自使用者拍板）

| 項目 | 設定 |
|------|------|
| 影音格式 | **16:9 剪輯為主，另必產一份 9:16 直式版**（YouTube Shorts 發布用）|
| 直式做法 | `make_vertical.py`：內容等比置中不裁切、上下模糊背景填滿、1080×1920 |
| 封面尺寸 | **16:9**（與長片共用樣板） |
| 輸出資料夾 | **`output/<短片標題> [<Agent>] (Short)/`**（後綴同長片，見 `youtube-video-workflow` 適配表）|
| 短片時長上限 | **≤ 120 秒** |
| 開頭 Hook | **≤ 5 秒** |
| 候選版本數 | **3 個**（不同 hook 策略） |
| 內部檔案 | 7 個：`<標題>.mp4`（16:9 乾淨）/ `<標題>_字幕版.mp4`（16:9 燒字幕）/ `<標題>_直式9x16.mp4` / `.srt` / `.txt` / `cover.png` / `發布資訊.md` |

---

## 流程

### Step 1：讀入並確認
- 讀 `working/<video-id>/<video-id>.srt`，理解全片內容與時間碼
- 確認 `cut.mp4` 存在
- 取得長片總時長（ffprobe）

### Step 2：亮點偵測（自動模式）

依以下「亮點偵測檢核表」掃過全部字幕段，標記候選：

| 亮點類型 | 字幕特徵範例 |
|---------|--------------|
| **痛點宣告** | 「每年都要⋯」「最痛苦的⋯」「沒有人喜歡⋯」 |
| **反問句** | 「你還在⋯嗎？」「為什麼⋯？」 |
| **數字承諾** | 「3 步驟」「5 分鐘」「一鍵⋯」 |
| **強斷言** | 「只要⋯就⋯」「最⋯的⋯」「再也不⋯」 |
| **轉折揭密** | 「但其實⋯」「結果⋯」「沒想到⋯」 |
| **價值結算** | 「省了⋯」「賺到⋯」「換來⋯」 |
| **行動指令** | 「你只要⋯」「你可以⋯」 |

把每段給一個 0–3 的亮點分數，記在工作筆記。

### Step 3：組三個候選版本

每個版本走 **三幕結構**：

```
[幕 1] Hook (≤ 5s)：選一段最強的亮點當開頭，抓住注意力
[幕 2] Body (60–100s)：3–6 段邏輯連貫的內容，串起 hook 的承諾
[幕 3] CTA / 收尾 (5–15s)：呼應 hook，給一個記憶點或行動
```

三個版本走**不同 hook 策略**：

| 版本 | Hook 策略 | 適合情境 |
|------|-----------|---------|
| A | **痛點型** Hook（從「你還在⋯」開頭）| 觀眾對痛點有共鳴 |
| B | **好奇型** Hook（從「沒想到⋯」「其實⋯」開頭）| 想做病毒傳播 |
| C | **承諾型** Hook（從「3 分鐘搞定⋯」開頭）| 工具教學類最強 |

**邏輯連貫性檢核**：每個版本內，相鄰段落必須在語意上能接上（前一段結尾 → 下一段開頭不能斷裂）。如果語意接不上，補一段過場字幕或重選。

### Step 4：寫候選清單，等使用者挑

寫到 `working/<video-id>/shorts-candidates.md`：

```markdown
# 短片候選 — <video-id>

## 版本 A：痛點型
- **時長**：1:42
- **時間碼**：00:00:08.500-00:00:13.200, 00:00:45.100-00:01:30.800, 00:01:55.000-00:02:05.000
- **三幕劇本**：
  - Hook：「你還在手動填課程計畫嗎？」（4.7s）
  - Body：示範 3 個步驟讓 Claude 自動填表（45.7s）
  - CTA：「再也不用熬夜寫課程計畫」（10.0s）
- **預估亮點命中率**：8/10

## 版本 B：好奇型
（同上格式）

## 版本 C：承諾型
（同上格式）
```

回報三版給使用者，**停下等使用者選編號 A/B/C**，或：
- 「我自己給你時間碼」→ 跳到 step 5 用使用者給的時間碼
- 「再生 3 版」→ 重跑 step 3，調整 hook 策略

### Step 5：使用者拍板後 — 切片+組片

呼叫包裝腳本：

```bash
python skills/short-video-workflow/scripts/clip_cut.py \
  --input-mp4 "working/<video-id>/<video-id>.cut.mp4" \
  --input-srt "working/<video-id>/<video-id>.srt" \
  --segments "00:00:08.500-00:00:13.200,00:00:45.100-00:01:30.800,00:01:55.000-00:02:05.000" \
  --out-dir "working/<video-id>/short-tmp/"
```

腳本會產出：
- `short-tmp/short.mp4`（ffmpeg trim+concat，重新編碼確保乾淨切點）
- `short-tmp/short.srt`（依新時間軸重編字幕）
- `short-tmp/short.txt`（純文字稿）

跑完後**確認時長 ≤ 120 秒**（ffprobe），超過就回 step 4 重組。

### Step 6：新增結尾字卡與燒錄字幕

1. **添加結尾字卡**：
在影片的最尾端放置一個 3 秒的「詳細影片請看留言」字卡。
呼叫包裝腳本：
```bash
python skills/short-video-workflow/scripts/add_end_card.py \
  --input-mp4 "working/<video-id>/short-tmp/short.mp4" \
  --output-mp4 "working/<video-id>/short-tmp/short_with_card.mp4"
```
這會生成 `short-tmp/short_with_card.mp4`（總長度增加 3 秒，顯示深海軍藍 `#0A192F` 背景、霓虹亮藍字白色描邊的字卡，包含無聲音軌）。

2. **燒錄字幕**：
使用 `burn_subtitles.py` 將 `.srt` 字幕燒錄到影片中：
```bash
python skills/short-video-workflow/scripts/burn_subtitles.py \
  "working/<video-id>/short-tmp/short_with_card.mp4" \
  "working/<video-id>/short-tmp/short.srt" \
  "working/<video-id>/short-tmp/short_subtitled.mp4"
```
這會產出燒錄好字幕並帶有結尾字卡的影片 `short-tmp/short_subtitled.mp4`。

3. **產 9:16 直式版（必做，YouTube Shorts 發布用）**：
以「已燒字幕版」為輸入轉直式，字幕跟著前景走、不用重燒：
```bash
python skills/short-video-workflow/scripts/make_vertical.py \
  "working/<video-id>/short-tmp/short_subtitled.mp4" \
  --out "working/<video-id>/short-tmp/short_916.mp4"
```
做法為模糊背景填充：內容等比縮到寬 1080 置中**不裁切**（螢幕示範不能裁掉 UI），
上下由同畫面放大模糊的背景補滿，輸出 1080×1920。腳本會自動驗證解析度。

### Step 7：給短片定 3 個標題，等使用者挑

短片標題不一定等於長片標題；通常更聳動、更短。
依前述內容生 3 個候選寫到 `working/<video-id>/short-titles.md`，停下等使用者挑（不要 10 個，短片不需要那麼多）。

### Step 8：使用者選定短片標題後 — 建資料夾

- 標題清洗（去除 `？！：／＼?!:/\\<>|"*`）
- 建 `output/<短片標題> [<Agent>] (Short)/`（`<Agent>` 依執行中的 agent 決定）
- 搬移並重新命名檔案到輸出資料夾：
  - 把 `short_with_card.mp4` 改名為 `<短片標題>.mp4`（16:9 乾淨版）
  - 把 `short_subtitled.mp4` 改名為 `<短片標題>_字幕版.mp4`（16:9 燒錄字幕版）
  - 把 `short_916.mp4` 改名為 `<短片標題>_直式9x16.mp4`（**YouTube Shorts 發布用**）
  - 把 `short.srt` 改名為 `<短片標題>.srt`
  - 把 `short.txt` 改名為 `<短片標題>.txt`

### Step 9：產封面（沿用長片封面 SOP）

**生封面前 SOP（缺一不可）**：
1. `Read assets/style/cover-style.md`（頻道風格指南）
2. `Read assets/style/reference-thumbnails.png`（若有）
3. **重新讀** `assets/persona/` 內的人物基準照（不可沿用舊封面或衍生圖）
4. 依 `cover-style.md` 的主題配色規則決定本支主色

**短片封面額外要求**：
- 標題用**最短最聳動**的版本（封面標題可以比 YouTube 標題更精煉）
- 加「SHORT」或「精華」字樣小貼紙作識別（選擇性）
- 16:9 尺寸與長片同樣板

呼叫方式（依 `youtube-video-workflow` 的 Agent 適配表選路）：
- **有內建生圖（Codex／Antigravity）**：用內建工具，人物基準照當 reference image，不呼叫 draw.py
- **沒有內建生圖（Claude Code／OpenCode）**：
  `python skills/cover-image/draw.py "<prompt>" --edit "assets/persona/<你的人物照>.png" --size 1536x1024 --quality low --name cover --outdir "output/<標題> [<Agent>] (Short)/"`

### Step 10：寫發布資訊（短片版本）

把 [references/發布資訊範本.md](references/發布資訊範本.md) 複製成 `output/<短片標題> [<Agent>] (Short)/發布資訊.md`，結構照範本（含 AI 揭露、Threads），內容照下列短片玩法寫：

1. **YouTube 短描述**（≤ 150 字，前 50 字最關鍵）
2. **Hashtag 帶**：開頭 3 個 → `#Shorts #<頻道主題>` 一定要有
3. **社群貼文**（IG Reels、TikTok 各一版本，比長片更短更挑釁）
4. **SEO 關鍵字**：
   - 主關鍵字（3–5 個）
   - 長尾（3–5 個）
   - **YouTube 標籤欄位（直接複製）**：半形逗號分隔，**最後加 `Shorts,短影片` 兩個必備標籤**
5. **上架前 checklist**：標題 ≤ 40 字、封面、字幕、`#Shorts` 在標題或描述、發布時段建議

### Step 11：自我檢查清單

跑完後逐項確認：
- [ ] 資料夾名結尾有 ` [<Agent>] (Short)` 後綴
- [ ] 影片時長 ≤ 120 秒（ffprobe 確認）
- [ ] 開頭 5 秒內出現 hook 字幕
- [ ] 7 個檔案齊全（含 `_直式9x16.mp4`）
- [ ] 直式版解析度 1080×1920（make_vertical.py 會自動驗證）
- [ ] cover.png 主色符合 `cover-style.md` 的配色規則
- [ ] 發布資訊.md 照範本結構、含 `#Shorts` 標籤
- [ ] handoff.md 已更新本支短片狀態

### Step 12：更新 handoff.md

紀錄：
- 短片標題
- 來源長片 video-id
- 時間碼組合
- 選用的 hook 策略（A/B/C 或 user-defined）
- 輸出路徑

---

## Override 模式：使用者直接給時間碼或描述

使用者可以在 step 2 之前直接指定，例如：
- 「用 00:00:05–00:00:15、00:01:20–00:02:00 這兩段組」→ 跳到 step 5
- 「我要剪『Claude 怎麼操作 + 結果展示』那兩段」→ 你 AI 從 SRT 找出對應時間碼，給使用者確認後跳 step 5

## 踩坑

- **時間碼必須對齊 `cut.mp4` 不是 `raw/`**：對原始檔的時間碼跟字幕對不上。
- **重新編碼 vs stream copy**：短片切點通常不在 keyframe，用 stream copy（`-c copy`）會出現黑畫面；本 Skill 一律走重新編碼。
- **音訊 fade in/out**：`clip_cut.py` 預設不加 fade；想要 0.05s 軟切點可在 step 5 加 `--audio-fade 0.05`。
- **段落數別超過 8 段**：太多碎片會讓觀感不連貫；2 分鐘 3–6 段最舒服。
- **不要切到一句話中間**：選時間碼時對齊字幕段落邊界，否則會「切到一半」。
- **YouTube Shorts 規則**：影片 ≤ 60 秒會自動進 Shorts feed，60–180 秒則是「短片」但不一定進 Shorts feed。本 Skill 預設 ≤ 120 秒比較通用。
- **9:16 直式是必產項**：一律用 `make_vertical.py` 模糊背景填充，**不要用 crop 裁切**——螢幕示範類影片裁掉左右會失去 UI 資訊。輸入用已燒字幕版，字幕自動跟著前景縮放，不需重燒。
- **直式版與 16:9 字卡共用**：結尾字卡在轉直式前已加好，直式版自帶字卡，不用另做直式字卡。

---

## 檔案結構

```
skills/short-video-workflow/
├── SKILL.md
└── scripts/
    ├── clip_cut.py        # ffmpeg 切片+組片+SRT 重編
    ├── add_end_card.py    # 結尾添加 3 秒「詳細影片請看留言」字卡
    ├── burn_subtitles.py  # 將 srt 字幕燒錄進 mp4 影片
    └── make_vertical.py   # 16:9 → 9:16 直式（模糊背景填充，Shorts 發布用）
```

## 與其他 Skill 的關係
- **依賴**：`smart-cut` + `audio-to-srt`（已產 cut.mp4 + srt）
- **共用**：`cover-image` SOP、`assets/style/cover-style.md`、`assets/persona/`
- **被呼叫**：`youtube-video-workflow` 的階段 2 會接手本 Skill 的完整流程
