# Sandy 生日作戰檔案（10/17 用）

全螢幕直式的互動網站，7 章、點畫面往下。程式不用動；要改的只有 `content.js`（台詞、檔名）和 `media/`（補檔）。

## 補檔三步（丞丞動畫、小花的信、回顧影片）

1. **丟檔**：把檔案放進 `site/media/`，檔名照這樣取：
   - 丞丞動畫：`cheng-animation.mp4`（`.mov` 也可以，第 2 步會自動轉 mp4，需要 ffmpeg）
   - 小花的信：`hua-letter-1.jpg`、`hua-letter-2.jpg`…（可多張，照數字排序；iPhone 的 `.heic`／`.png` 也可以，第 2 步會轉 jpg、縮到長邊 1600）
   - 回顧影片：`sandy-birthday-recap.mp4`（由 `tools/build_video.*` 產生）
2. **跑一行指令**（在 `site/` 底下）：
   ```
   python3 tools/update_media.py
   ```
   它會更新 `media/manifest.js`（網站只認這份清單），並印出還缺哪些檔。
3. **重新整理**網頁。缺的檔，禮物卡會顯示「🎁 今晚揭曉」，不會出錯。

## 本機預覽

```
cd ~/Documents/workspace/sandy-birthday-2026/site
python3 tools/serve.py          # 手機同 Wi-Fi 可開畫面上印的網址；只給這台 Mac 看就加 --local
```
- Mac 上用 Chrome 開 `http://127.0.0.1:8000/`，按 ⌥⌘I →切成手機尺寸（iPhone 16 Pro 是 402×874）最像實際畫面；大螢幕會顯示成置中的直式長條。
- 也可以用 `python3 -m http.server`，但它不支援影片分段讀取，**iPhone Safari 會播不了影片**；用 `tools/serve.py` 就沒問題。
- 開始畫面先點一下（同時解鎖聲音）。右上角「跳過」會跳到本章下一個互動或下一章，現場太吵、卡住都能往下。

## 正式播放前要知道的（需要 HTTPS 的功能）

| 功能 | HTTPS（正式網址） | http（區網預覽） |
|---|---|---|
| 吹蠟燭 | 允許麥克風就偵測吹氣；拒絕也能按住蛋糕 2 秒 | 自動改成「按住蛋糕 2 秒」 |
| 保存回顧影片 | iPhone 跳出分享選單 →選「儲存影片」存進相簿 | 改成下載檔案（iPhone 存到「檔案」App），不行時開新頁「長按影片 →儲存」 |

部署方式（GitHub Pages／Cloudflare／NAS）還沒決定；這個資料夾直接整包放上任何靜態網站空間就能跑，不需要外部 CDN 或字型，離線也能開。
生日快樂歌是網頁合成的聲音：iPhone 靜音開關打開時可能沒聲音（程式有設 iOS 17 起的 `audioSession = playback` 想避開，未實機驗證），播之前請把靜音關掉、音量調大。

## 檔案

| 檔 | 用途 |
|---|---|
| `index.html`、`style.css`、`app.js` | 網站本體（版面、互動） |
| `content.js` | 劇本、檔名、畫面文字（改台詞改這裡） |
| `assets/` | WebP 背景、立繪、貼圖（`tools/build_assets.sh` 從 `../assets/` 重產） |
| `media/` | 補檔位＋`manifest.js` |
| `save.html` | 保存影片的最後備案頁（長按影片儲存） |
| `tools/update_media.py` | 補檔後更新清單 |
| `tools/serve.py` | 本機／區網預覽（支援影片） |
| `tools/e2e.py` | headless Chrome 從頭點到尾的自動測試 |
