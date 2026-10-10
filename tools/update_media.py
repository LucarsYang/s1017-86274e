#!/usr/bin/env python3
"""掃 site/media/，產生 media/manifest.js（網站只認這份清單，缺檔不會出錯）。
順手處理：iPhone 的 .heic/.png 信照片轉成 .jpg、太大的照片縮到長邊 1600、
.mov 動畫轉 .mp4（需要 ffmpeg）。
用法（在 site/ 底下）：python3 tools/update_media.py
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
MEDIA = SITE / "media"
MEDIA.mkdir(exist_ok=True)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def img_long_side(p):
    r = run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(p)])
    nums = [int(x) for x in re.findall(r"pixel(?:Width|Height): (\d+)", r.stdout)]
    return max(nums) if nums else 0


# 1) 小花的信：heic/png → jpg，長邊 ≤1600（macOS 內建 sips）
for p in sorted(MEDIA.iterdir()):
    if not p.name.startswith("hua-letter-"):
        continue
    ext = p.suffix.lower()
    if ext in (".heic", ".heif", ".png") and shutil.which("sips"):
        out = p.with_suffix(".jpg")
        if not out.exists():
            run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(p), "--out", str(out)])
            print(f"轉檔 {p.name} → {out.name}")
        p = out
    if p.suffix.lower() in (".jpg", ".jpeg") and shutil.which("sips") and img_long_side(p) > 1600:
        run(["sips", "-Z", "1600", str(p)])
        print(f"縮圖 {p.name} → 長邊 1600")

# 2) 丞丞動畫：.mov → .mp4（H.264＋AAC、faststart，iPhone/Android 都能播）
mp4 = MEDIA / "cheng-animation.mp4"
if not mp4.exists():
    for ext in (".mov", ".MOV", ".m4v", ".MP4"):
        src = MEDIA / f"cheng-animation{ext}"
        if src.exists() and src != mp4:
            if shutil.which("ffmpeg"):
                r = run(["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                         "-movflags", "+faststart", str(mp4)])
                print(f"轉檔 {src.name} → {mp4.name}" if r.returncode == 0 else f"⚠️ {src.name} 轉檔失敗")
            else:
                print(f"⚠️ 找不到 ffmpeg，請自己把 {src.name} 轉成 cheng-animation.mp4")
            break

# 3) 產生清單（只列網站認得的檔）
ok = re.compile(r"^(cheng-animation\.mp4|sandy-birthday-recap\.mp4|hua-letter-\d+\.(jpe?g|png|webp|gif))$", re.I)
files = sorted(p.name for p in MEDIA.iterdir() if p.is_file() and ok.match(p.name))
(MEDIA / "manifest.js").write_text(
    "// 由 tools/update_media.py 自動產生，不用手改\nwindow.MEDIA_FILES = " + json.dumps(files, ensure_ascii=False) + ";\n",
    encoding="utf-8")
print("media/manifest.js 已更新：", ", ".join(files) if files else "（目前沒有檔案，禮物卡會顯示「今晚揭曉」）")
for name in ("cheng-animation.mp4", "hua-letter-1.jpg", "sandy-birthday-recap.mp4"):
    if not any(f.lower().startswith(name.split(".")[0].rstrip("1")) for f in files):
        print(f"  尚缺：{name}")
