#!/usr/bin/env python3
"""背景配樂離線渲染：headless Chrome 開網站，對每種氣氛用 OfflineAudioContext 渲染成 WAV，印 peak／RMS。
用法（在 site/ 底下）：python3 tools/bgm_render.py [--sec 20] [--out 目錄] [--url http://127.0.0.1:8000/]
不給 --url 就自己在隨機埠起一個暫時的靜態伺服器。合格標準：peak < 0.9、RMS > 0.01，不合格 exit 1。
"""
import argparse, base64, functools, json, os, sys, threading, wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.abspath(os.path.join(SITE, "..", "evidence", "2026-10-17", "bgm"))

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="")
ap.add_argument("--sec", type=float, default=20)
ap.add_argument("--sr", type=int, default=44100)
ap.add_argument("--out", default=DEFAULT_OUT)
ap.add_argument("--channel", default="chrome")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)

srv = None
url = a.url
if not url:
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=SITE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"

RENDER_JS = """
async ([mood, sec, sr]) => {
  const buf = await SandyBGM.renderOffline(mood, sec, sr, CONTENT.music);
  const L = buf.getChannelData(0), R = buf.numberOfChannels > 1 ? buf.getChannelData(1) : L;
  let peak = 0, sum = 0;
  const pcm = new Int16Array(L.length * 2);
  for (let i = 0; i < L.length; i++) {
    const l = L[i], r = R[i];
    peak = Math.max(peak, Math.abs(l), Math.abs(r)); sum += l * l + r * r;
    pcm[2 * i] = Math.max(-32768, Math.min(32767, Math.round(l * 32767)));
    pcm[2 * i + 1] = Math.max(-32768, Math.min(32767, Math.round(r * 32767)));
  }
  const bytes = new Uint8Array(pcm.buffer); let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return { peak, rms: Math.sqrt(sum / (L.length * 2)), b64: btoa(bin), info: SandyBGM.info(mood) };
}
"""

ok = True
rows = []
with sync_playwright() as p:
    br = p.chromium.launch(channel=a.channel, headless=True)
    page = br.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url, wait_until="networkidle")
    page.wait_for_function("() => window.SandyBGM && window.CONTENT")
    moods = page.evaluate("() => SandyBGM.moods")
    for m in moods:
        r = page.evaluate(RENDER_JS, [m, a.sec, a.sr])
        path = os.path.join(a.out, f"{m}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(a.sr)
            w.writeframes(base64.b64decode(r["b64"]))
        good = r["peak"] < 0.9 and r["rms"] > 0.01
        ok &= good
        rows.append({"mood": m, "peak": round(r["peak"], 4), "rms": round(r["rms"], 4), "ok": good, "wav": path, **r["info"]})
        print(f"{m:8s} peak={r['peak']:.4f} rms={r['rms']:.4f} {'OK' if good else 'FAIL'}  "
              f"{r['info']['bpm']} BPM, {r['info']['bars']} 小節, 循環 {r['info']['loopSec']} 秒  → {path}")
    br.close()
    if errors:
        ok = False
        print("page errors:", errors)
if srv: srv.shutdown()
with open(os.path.join(a.out, "bgm_render.json"), "w") as f:
    json.dump({"sec": a.sec, "sr": a.sr, "rows": rows, "ok": ok}, f, ensure_ascii=False, indent=1)
print("ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
