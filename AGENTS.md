# media-youtube-publish（專案藍圖）

> 本檔為跨 Agent 通用的專案藍圖（AGENTS.md 開放標準）。任何 Agent 的每個 session 都應先讀本檔＋`handoff.md`。
> Codex、OpenCode、Antigravity 原生就讀本檔；Claude Code 有 `CLAUDE.md` 時只讀它，故由 `CLAUDE.md` 的 `@AGENTS.md` import 進來（`CLAUDE.md` 只有這一行）；Claude 專屬規範寫在本檔〈Claude Code 專屬〉一節。

## 專案簡介

一條 **YouTube 影片自動化生產線**。使用者把原始影片丟進 `raw/`，Agent 接力完成：智能剪口播（去靜音）→ 語音轉字幕（本地 Whisper，Groq 備援）→ 生 10 個標題候選 → 以選定標題建資料夾並平行產出封面、YouTube 描述、社群貼文、SEO 標籤 → 打包成 `output/<標題> [<Agent>]/` 的完整上架素材包。可選再從長片字幕抓亮點剪 ≤2 分鐘 Shorts。

四種 Agent（Claude Code／Codex／OpenCode／Antigravity）共用同一套流程與技能，差別只在「封面怎麼生」與「輸出資料夾標籤」。

## 關鍵時程

- 無固定截止日期，依素材到位節奏推進

## 目標與路線圖

- [x] 階段一：把模板專案改成自己的版本（移除原作者私人資料、三份 agent 專屬技能合併成一份通用技能）
- [x] 技能整併：七個技能收成 `youtube-long`、`youtube-shorts`、`audio-to-srt`、`cover`，腳本只留一份；`audio-to-srt`、`cover` 裝到全域
- [ ] 階段二：完成個人化（人物基準照、封面風格指南、字幕詞彙表〈頻道／人物〉佔位符、封面用 OFL 字型；Groq key 選填）
- [ ] 階段三：跑完第一支長片，驗證整條生產線
- [ ] 階段四：驗證短片（Shorts）流程

## 資料夾結構

```
media-youtube-publish/
├── AGENTS.md         # 本檔 — 跨 Agent 專案藍圖
├── CLAUDE.md         # Claude Code 橋接（@AGENTS.md + Claude 專屬）
├── handoff.md        # 交接檔（不進 git，只走雲端硬碟同步）
├── README.md         # 對人的快速說明
├── SETUP.md          # 安裝、API key、個人化清單
├── .env.example      # API key 範本（真正的 .env 不進 git）
├── raw/              # 原始影片素材（不進 git）
├── working/          # 中間產物：cut.mp4、_subtitles/、titles.md（不進 git）
├── output/           # 交付成品，一支影片一資料夾
├── projects/         # 需要長期管理的影片專案
├── assets/
│   ├── persona/      # 人物基準照（封面必用，不進 git）
│   └── style/        # 頻道封面風格指南
└── skills/
    ├── youtube-long/   # 長片生產線：去靜音 → 字幕 → 標題 → 封面 → 發布資訊（發布資訊範本正本在這）
    ├── youtube-shorts/ # 長片 → ≤2 分鐘 Shorts
    ├── audio-to-srt/   # 語音轉 SRT（全域，其他專案也用）
    └── cover/          # 底圖 → 封面（裁切＋疊字；全域，其他媒體專案也用）
```

---

## 專案專屬規則

### Agent 適配表（唯一需要分辨 Agent 的地方）

| Agent | 入口檔 | 封面底圖 | 輸出資料夾後綴 |
|-------|--------|---------|---------------|
| **Claude Code** | `CLAUDE.md` → 本檔 | 全域 `draw` 技能 | ` [Claude]` |
| **Codex** | 本檔 | 內建 image 生圖工具 | ` [Codex]` |
| **OpenCode** | 本檔 | 全域 `draw` 技能 | ` [OpenCode]` |
| **Antigravity** | 本檔 | 內建 `generate_image` | ` [Antigravity]` |

- 一句話：**有內建生圖就用內建，沒有就用全域 `draw` 技能**（它自己選 Codex CLI 代生或 API 路線）；疊字一律用 `cover`
- 其餘所有步驟四種 Agent 完全一樣——不要各自發明流程、不要為某個 Agent 另開一份技能
- 後綴用於 A/B 比較不同 Agent 的產出品質；**只有資料夾加後綴，裡面的檔案不加**

### Skills 用哪一個

| 使用者要的 | 用哪個 |
|-------|--------|
| 一次跑完整支長片 | `skills/youtube-long/`（**主要入口**） |
| 只想去靜音 | `youtube-long` 第 0–1 步 |
| 只要影片＋字幕，不要行銷素材 | `youtube-long` 第 0–2 步 |
| 只想轉 SRT（不剪片） | `skills/audio-to-srt/` |
| 長片跑完後加碼剪 Shorts | `skills/youtube-shorts/` |
| 只做封面疊字 | `skills/cover/` |

**腳本只放一份，技能之間直接引用**：`youtube-long` 用 `../audio-to-srt/scripts/` 轉字幕、用 `../cover/` 疊字，
`youtube-shorts` 用 `../youtube-long/references/` 的範本與行銷規格。四個技能永遠一起放在本專案，引用不會斷；
**不要再把別的技能的腳本複製一份進來**——副本會悄悄分岔。`preflight.py` 會檢查同層技能在不在。

**技能在專案內使用**：在本專案開 session 時，Agent 依上表直接讀 `skills/<技能>/SKILL.md`，四種 Agent 都適用。
代價是不會依對話自動觸發、也不能在別的資料夾用——做影片就在本專案做。
**不要為此另開或依賴外部 repo**——`agents/media-audio-srt` 是本 repo 字幕技能的前身，程式改良（dc4cb12）與個人化詞彙表都已併入，該專案待退役，不得反向依賴。

**`audio-to-srt` 與 `cover` 例外，用全域 `skill-sync` 裝到四個 Agent 的全域目錄**：其他專案也要轉字幕、做封面。
改了這兩個技能就要再跑一次同步；`youtube-long`、`youtube-shorts` 不要裝到全域（`skill-sync` 會把「來源有、但都沒裝」當成刻意不裝，不會自動補）。
別的專案用 `audio-to-srt` 時，詞彙表用參數換成該專案的，**不要改本 repo 的 `vocabulary.md`／`replacements.md`**（見該技能〈在其他專案使用〉）。

### 標準工作流

> 完整細節在 `skills/youtube-long/SKILL.md`，這裡只是骨架。

1. **收件**：素材在 `raw/<video-id>/`（video-id 是暫時的工作識別，例如 `20260822-agent-intro`）
2. **建工作空間**：`working/<video-id>/` 與 `working/<video-id>/_subtitles/`
3. **剪口播**：`smart_cut.py` → `<video-id>.cut.mp4`（先用 45 秒樣本試剪讓使用者確認節奏）
4. **轉字幕**：transcribe（預設本地，沒裝才走 Groq；輸出同格式）→ resegment → apply_vocab → find_dubious_terms → **🛑 確認疑慮術語** → finalize → **validate_srt【硬關卡】** → srt_to_txt
5. **生 10 個標題候選** → `working/<video-id>/titles.md` → **🛑 等使用者挑**
6. **選定後**：清洗標題成合法資料夾名（去掉 `？！：／＼?!:/\<>|"*`）→ 建 `output/<標題> [<Agent>]/`，平行產出封面與 `發布資訊.md`
7. **打包**：`<標題>.mp4`／`.srt`／`.txt`／`cover.png`／`發布資訊.md` 五件套
8. **（可選）短片**：接 `skills/youtube-shorts/`，輸出 `output/<短片標題> [<Agent>] (Short)/`，8 件套（含 9:16 直式版與 9:16 封面）
9. **更新 `handoff.md`**

`發布資訊.md` **照 `skills/youtube-long/references/發布資訊範本.md` 的結構寫**（YouTube／FB／IG／Threads 文案、AI 揭露、可直接貼進標籤欄的一行），口播的寫法照同資料夾的 `marketing-spec.md`。
範本是五個媒體專案共用的，**正本就是本 repo 這一份**：要改就改正本，再整份覆蓋到 media-short-film、media-3d-studio、media-music-video、media-video-specs 的 `templates/`；`skills/youtube-long/scripts/check_sync.py` 會逐一比對（`preflight.py` 順帶跑，不一致只 `[WARN]`）。其他專案的副本不准就地改。

### 三個不准跳過的 STOP 關卡

- 🛑 **疑慮術語確認**——不確定的人名、產品名、縮寫、數字，列出段號問使用者，不准自己猜
- 🛑 **標題確認**——10 個候選給使用者挑，不准自己選
- 🛑 **短片三候選確認**——A 痛點型／B 好奇型／C 承諾型，等使用者選編號

### 製作硬規則

- **先剪片再轉字幕**，順序顛倒時間碼必錯位
- `validate_srt.py` 不通過（段數不一致／時間碼對不上）→ **中止交付並回報**，不得硬出
- 清字只改文字，**不動時間碼、不增刪段落**
- 短片切點一律對齊字幕段落邊界，**不准切到一句話中間**
- **每次生封面都重新讀原始人物基準照**，不得從上一張封面或衍生圖延續人物（誤差會越滾越大）
- 詞彙機械替換一律改 `skills/audio-to-srt/references/replacements.md`，**不准把規則寫回程式碼**
- **中文替換規則不准寫可能出現在正常語句裡的字串**（中文沒有詞邊界可言）；需要看語境的修正留給清字階段。
  不得已的例外要在 `replacements.md` 就地標警語說明何時該停用
- 英文替換若是「正確詞裡含有待替換字串」（`Cloudflare`、`Google Cloud`），加進 `replacements.md` 的〈保護詞〉，
  光靠詞邊界救不了
- `replacements.md` 的**規則順序有意義**：先 GPT-Codex 變體 → 再 Claude 生態 → 最後 `Cloud→Claude`。
  新增規則務必確認插入位置，順序錯了複合詞會被短規則先吃掉
- `vocabulary.md` 有 **Whisper prompt 長度上限**（約 224 token，腳本抓 200 字），超出的從尾端截掉、
  **只印警告不報錯**。重要的詞放前面；**加新詞前先決定拿掉哪一個**；`A / B` 這種寫法會被拆成兩個詞條、佔兩個名額
- 靜音修正只認**跨越段落邊界**的靜音，段內換氣必須忽略（否則字幕會在人還在講的時候消失）；
  `end` 只能縮短不能延長——word-level 時間碼才是文字何時被說出的依據

### 封面規範

1. 讀 `assets/style/cover-style.md`（頻道風格指南）
2. 讀 `assets/style/reference-thumbnails.png`（若有）
3. **重新讀** `assets/persona/` 內的人物基準照
4. 依 `cover-style.md` 的主題配色規則決定主色
5. 依適配表選生圖路線：
   - **內建生圖（Codex／Antigravity）**：把人物基準照當 reference image 傳給內建工具。若內建工具不支援參考圖，只能用 prompt 約束人物特徵，並**明確回報這個限制**，不要宣稱像本人
   - **沒有內建生圖（Claude Code／OpenCode）**：全域 `draw` 技能，`--edit <人物照>`
6. 底圖不寫字，最後用 `skills/cover/` 疊字（`--corner` 選不擋臉的角）

優先序：**人物基準照 > 風格指南 > 個別影片的 prompt 變化**。
`cover-style.md` 與人物照都是個人資料、不進 git（已在 `.gitignore`）；repo 只放範本 `cover-style.example.md`，
**不准改範本來放個人設定**。新電腦 clone 下來沒有 `cover-style.md` 時，照 `SETUP.md` 從範本複製。

### 相容性

- **第三方套件採登記制**：要防的是「漏裝的 pip 套件在流程跑到一半才爆」，所以開工前由 `preflight.py` 一次檢查。
  用第三方套件必須同時做到三件事，缺一不可：
  1. 登記進 `preflight.py`——只影響某一步的加進 `OPTIONAL_PACKAGES`（沒裝只 `[WARN]`），整條線都要的寫成專屬檢查（沒裝 `[ERR]`）
  2. 腳本一開始就確認套件在不在，沒裝立刻停下並印出安裝指令，不准做到一半才 import 失敗
  3. 寫進 `SETUP.md`〈系統前置〉表格
  標準庫做得到、難度差不多的仍優先用標準庫（每多一個套件，每台電腦、每個 Python 都要多裝一次）。
  目前登記的：auto-editor、faster-whisper／openai-whisper（專屬檢查）、pillow（`OPTIONAL_PACKAGES`）。封面生圖走全域 `draw` 技能，它的套件由它自己管
- 維持 **Python 3.9+ 相容**（別「順手現代化」成 `Path | None` 這類 3.10 語法）
- 目標平台以 **Windows** 為主：直接呼叫 `whisper` CLI 時一律加 `PYTHONUTF8=1` 與 `-X utf8`，否則 cp950 寫不了繁中；
  腳本寫檔一律明確指定 `encoding="utf-8"`
- 中文檔名上傳 Groq 會壞編碼，`transcribe_groq.py` 內部一律改用 `audio.<ext>` 上傳

### 安全與隱私

- API key 只從環境變數或使用者家目錄讀（`GROQ_API_KEY`／`~/.groq_api_key`、`OPENAI_API_KEY`／`~/.openai.env`），**不准寫進 repo、不准印在對話裡**
- 字幕**預設走本地** `transcribe_local.py`；改走 Groq 會把音訊上傳到第三方服務，內容可能敏感時**先問使用者**
- 大檔案不進 git（影片、音訊）；人物基準照屬個人隱私，已列入 `.gitignore`
- **本 repo 為公開**：新增檔案前確認沒有金鑰、個資或未公開素材

## 同步層級（本專案初始化至第 3 層級）

| 層級 | 平台 | 位置 | 讀取時機 |
|------|------|------|---------|
| L1 | 本地（GDrive） | `AGENTS.md`＋`handoff.md`（不進 git，只走雲端硬碟）＋`CLAUDE.md`（橋接） | 每個 session |
| L2 | GitHub | [changyiwu/media-youtube-publish](https://github.com/changyiwu/media-youtube-publish)（公開） | 指定時 |
| L3 | Obsidian | `media-youtube-publish/專案工作流程.md` | 有需要時 |

## 三個檔案的職責（依「時效性」分家，不是依「詳細程度」）

| 檔案 | 時效 | 寫入方式 | 放什麼 |
|------|------|---------|--------|
| `handoff.md` | **只對下一個 session 有效**，過期即丟 | 每次收工**整份重寫** | 做到哪、下一步、**這次**的暫時 workaround |
| `AGENTS.md`（本檔） | **長期有效**，每個 session 都適用 | 只有規則本身變了才改 | 目標、路線圖、常設規則、結構 |
| Obsidian（L3）／`git log` | **歷史**：發生過什麼、為什麼 | 只增不刪 | 決策紀錄、踩坑完整版、逐次進度 |

驗收標準：**`handoff.md` 整份刪掉，不應損失任何長期資訊**——會的話代表該升級進本檔卻沒升級。

**本檔不要出現的東西**（會無限膨脹，且開工每次都要重讀）：

- ❌ `## 最近進度`／逐次工作紀錄 → 寫 Obsidian「🗓️ 最近更動紀錄」
- ❌ 決策記錄、取捨理由、踩坑經過的完整版 → Obsidian「決策紀錄」「🕳️ 踩坑筆記」
- ✅ 只留「結論式的規則」：踩過的坑收斂成一條**祈使句**寫進〈製作硬規則〉或〈工作約定〉，理由留在 Obsidian

## 工作約定

- 任何 Agent、任何電腦：**開工先讀 `handoff.md`，收工必更新 `handoff.md`**
- `handoff.md` **不進 git**（含真實電腦名與本機絕對路徑），已列入 `.gitignore`，跨電腦靠雲端硬碟同步——不要把它加回版控
- 修改共用檔案前先讀最新內容，避免覆蓋其他 Agent 的變更
- **不要假設另一個 Agent 知道你做了什麼**，交接寫得像給陌生人看
- 所有回應、文件與 commit 訊息使用繁體中文
- 修改前先確認計畫，優先保留原有資料結構
- **產出一律放 `output/`**：本專案產生的檔案或資料夾預設放專案根目錄的 `output/`（一支影片一個資料夾），不另開 `outputs/`、`exports/`、`generated/`、`out/` 之類的資料夾；整個 `output/` 都在 `.gitignore`，不進 git（腳本會自己建資料夾）。

## Claude Code 專屬

- **封面底圖走全域 `draw` 技能**：Claude Code 沒有內建生圖，`draw` 會優先找已登入的 Codex CLI 代生，
  沒有才走 API（需要 `OPENAI_API_KEY`，環境變數或 `~/.openai.env`）。輸出資料夾後綴 ` [Claude]`。
- **中括號路徑**：PowerShell 會把 `output/<標題> [Claude]/` 的中括號當萬用字元，
  檔案操作要用 `-LiteralPath` 或單引號；Bash 直接雙引號即可。
