# media-youtube-publish — YouTube 上架素材自動化生產線

把原始影片素材丟進來，AI agent 接力產出：剪好的影片、SRT 字幕、純文字稿、封面圖、YouTube 描述、社群貼文、SEO 標籤。

**四種 agent 共用同一套流程**：Claude Code、Codex、OpenCode、Antigravity。差別只在封面怎麼生、輸出資料夾標籤叫什麼。

---

## 🚀 第一次用？

先看 **[`SETUP.md`](./SETUP.md)** — 安裝、API key、個人化清單、第一次試跑。

## 📂 工作流概覽

```
raw/<video-id>/source.mp4
    │
    ├─ smart-cut        → 去靜音（auto-editor，自動處理 VFR）
    ├─ audio-to-srt     → SRT + 純文字（本地 Whisper，Groq 備援）
    ├─ 🛑 疑慮術語確認  → 不確定的專有名詞列給你勘誤
    ├─ 🛑 10 個標題候選 → 等你挑一個
    │
    └─ 你挑完 ──→ output/<標題> [<Agent>]/
                     ├── <標題>.mp4
                     ├── <標題>.srt
                     ├── <標題>.txt
                     ├── cover.png      ← 人物基準照 + 頻道風格
                     └── 發布資訊.md    ← YouTube 說明欄 / 社群貼文 / 標籤

（可選）短片模式 → output/<短片標題> [<Agent>] (Short)/  含 9:16 直式版，共 7 檔
```

## 對 agent 的入口

| Agent | 讀哪一份 |
|-------|---------|
| **Codex** / **OpenCode** / **Antigravity** | [`AGENTS.md`](./AGENTS.md)（原生就讀這份） |
| **Claude Code** | [`CLAUDE.md`](./CLAUDE.md) → 橋接到 `AGENTS.md` |
| 交班 | 全部讀寫 `handoff.md`（**不進 git**，只走雲端硬碟同步；clone 下來的人自己建一份） |

**工作規範只有一份 `AGENTS.md`**；`CLAUDE.md` 只放 Claude Code 的差異（封面路線、輸出後綴）。

## Skills

| Skill | 用途 |
|-------|------|
| [`youtube-video-workflow`](./skills/youtube-video-workflow/SKILL.md) | **主要入口** — 一次跑完整條生產線，自帶全部腳本 |
| [`smart-cut`](./skills/smart-cut/SKILL.md) | 單步驟：去靜音剪口播 |
| [`audio-to-srt`](./skills/audio-to-srt/SKILL.md) | 單步驟：語音轉 SRT |
| [`video-editing-and-subtitles`](./skills/video-editing-and-subtitles/SKILL.md) | 只要影片＋字幕，不要行銷素材 |
| [`short-video-workflow`](./skills/short-video-workflow/SKILL.md) | 長片 → ≤2 分鐘 Shorts |
| [`cover-image`](./skills/cover-image/SKILL.md) | 封面生圖（agent 沒有內建生圖時才用） |

技能留在專案內使用（Agent 依 `AGENTS.md` 直接讀 `skills/<技能>/SKILL.md`），不裝到全域；只有 `skills/cover/` 用 `skill-sync` 裝到全域，給其他媒體專案做封面。

## 個人化資產

- [`assets/persona/`](./assets/persona/README.md) — 你的人物形象照（封面必用，不進 git）
- [`assets/style/`](./assets/style/README.md) — 你的頻道封面風格指南

---

## 對人的快速操作

1. 把影片丟進 `raw/<video-id>/`
2. 跟 agent 說：「使用 youtube-video-workflow 處理 `raw/<video-id>`」
3. agent 跑到「疑慮術語」與「標題候選」會**停下來等你**
4. 你拍板後，agent 繼續產封面與文案
5. 成品在 `output/<標題> [<Agent>]/`

完整細節見 [`SETUP.md`](./SETUP.md)。
