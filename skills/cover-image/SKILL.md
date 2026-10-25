---
name: cover-image
description: 用 OpenAI gpt-image-2 生成或修改圖片（封面、插圖、示意圖、社群圖）。當 agent 沒有內建生圖能力，卻需要「畫一張封面」「生一張圖」「改這張圖」「把背景換成 XX」時使用此技能，透過 OPENAI_API_KEY 呼叫本目錄的 draw.py。若你的 agent 本身就有內建生圖工具（例如 Codex 的 image 生圖、Antigravity 的 generate_image），優先用內建工具，不需要跑本技能。
---

# cover-image：gpt-image-2 生圖／改圖

## 什麼時候用本技能

| Agent | 生封面走哪條路 |
|-------|---------------|
| Claude Code | ✅ 跑本技能的 `draw.py` |
| OpenCode | ✅ 跑本技能的 `draw.py` |
| Codex | ❌ 用內建 image 生圖工具 |
| Antigravity | ❌ 用內建 `generate_image` |

一句話：**有內建生圖就用內建，沒有才跑 draw.py。**

## 前置需求

- 環境變數 `OPENAI_API_KEY`（或 `~/.openai.env`、專案根目錄 `.env` 內含此變數）
- OpenAI 組織已完成 **Individual 驗證**（gpt-image-2 的硬性要求）
- 已安裝 `openai` Python 套件

## 腳本位置

`skills/cover-image/draw.py`（專案內）。若你把本技能裝到全域技能目錄，就用該處的 `draw.py`。

**不要直接改這份。** 它是全域 `draw` 技能的逐位元副本，原始檔在 `agents/agent-setup-guide/skills/05-draw/draw.py`；
總控 `youtube-video-workflow/scripts/draw.py` 是第二份副本。要改就改上游、再整份覆蓋這兩份，
`check_sync.py` 會比對三份是否一致（上游不在這台時略過）。

## 使用方式

### 生新圖

```bash
python skills/cover-image/draw.py "要畫的內容" --name cover --outdir "output/<標題> [<Agent>]"
```

### 以人物基準照生封面（YouTube 封面固定走這條）

```bash
python skills/cover-image/draw.py "<prompt>" \
  --edit "assets/persona/<你的人物照>.png" \
  --size 1536x1024 --quality low \
  --name cover --outdir "output/<標題> [<Agent>]"
```

`--edit` 模式下 gpt-image-2 會延續輸入圖的五官、髮型、穿著，這是頻道人物識別能穩定的關鍵。純文字描述「一個戴眼鏡的人」每次臉都不一樣。

### 參數

- `prompt`（必填）：要畫什麼
- `--edit`：參考圖路徑（改圖／延續人物）
- `--size`：`1024x1024`（方，預設）／`1536x1024`（橫，封面用）／`1024x1536`（直）／`auto`
- `--quality`：`low`／`medium`／`high`／`auto`
- `--n`：1–8 張
- `--name`：輸出檔名前綴
- `--outdir`：輸出目錄

## quality 怎麼選

**預設一律 `low`**（省錢又快，99% 情境夠用）。

| 等級 | 約略成本 | 什麼時候用 |
|------|---------|-----------|
| `low` | NT$0.3 | YouTube 封面、簡報插圖、示意圖、社群圖 — 預設值 |
| `medium` | NT$1.3 | low 明顯不夠時 |
| `high` | NT$5.5 | 實體印刷、密集跨語言文字要零錯 |

`1536x1024` 約乘 1.5 倍；`--n>1` 乘張數。要升 medium／high **先問使用者**，不要自作主張。

## 封面 prompt 撰寫

依 `assets/style/cover-style.md` 的填空範本寫。要點：

- 只描述**位置、姿勢、場景、文字、配色**
- **不要**重新描述五官／髮型／外套顏色／眼鏡 — 交給 `--edit` 的基準照，重複描述會讓模型妥協走樣
- 每次都用原始人物基準照，**不要**拿上一張生成的封面當輸入（誤差會越滾越大）

## 輸出

PNG，檔名 `<name>_<YYYYMMDD_HHMMSS>.png`（多張加 `_1` `_2`）。封面用途跑完後刪掉時間戳版本，只留一份 `cover.png`。

## 錯誤處理

- `403 Organization must be verified` → 去 platform.openai.com/settings/organization/general 做 Individual 驗證
- `401 Invalid API key` → 檢查 `OPENAI_API_KEY` 或 `.env`
- `429 Rate limit` → 額度用完，去 Billing 儲值
