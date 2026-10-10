#!/usr/bin/env python3
"""headless Chrome 從頭點到尾（驗收 A1～A3、A5、A6 用）。
用法：python3 tools/e2e.py --url http://127.0.0.1:8765/ --w 402 --h 874 --out ../evidence --tag a1 [--shots all|sample]
       [--stub-share] [--expect-media]
輸出：JSON 結果到 stdout（每句是否出現、版面檢查、console error、下載驗證）。
"""
import argparse, json, re, sys, time
from playwright.sync_api import sync_playwright

IOS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--w", type=int, default=402)
ap.add_argument("--h", type=int, default=874)
ap.add_argument("--dpr", type=float, default=3)
ap.add_argument("--out", required=True)
ap.add_argument("--tag", required=True)
ap.add_argument("--shots", default="all")           # all＝每章每個互動都截；sample＝抽 4 章
ap.add_argument("--share", default="native")       # native＝瀏覽器原樣；stub＝模擬 iOS Web Share（驗證路徑 1）；off＝不支援分享（驗證路徑 2 下載）；nodl＝分享、download 都不支援（路徑 3）
ap.add_argument("--expect-media", action="store_true")
ap.add_argument("--channel", default="chrome")
ap.add_argument("--engine", default="chromium")   # chromium（Chrome）或 webkit（Safari 引擎抽查，只支援 --via-skip）
ap.add_argument("--json", default="")             # 結果另存檔（關瀏覽器前就寫好）
ap.add_argument("--via-skip", action="store_true")  # 只按「跳過」一路跳到派對（驗證跳過不卡關）
ap.add_argument("--mic", default="pending")         # pending＝不回應權限；deny＝拒絕；none＝瀏覽器不支援
a = ap.parse_args()

SAMPLE = {0, 3, 5, 6}
res = {"size": f"{a.w}x{a.h}@{a.dpr}", "lines": [], "layout_issues": [], "console": [], "page_errors": [],
       "bad_responses": [], "shots": [], "bytes_non_video": 0, "checks": {}}

LAYOUT_JS = r"""
() => {
  const W = innerWidth, H = innerHeight, issues = [];
  const r = el => el.getBoundingClientRect();
  const vis = el => { const b = r(el); const cs = getComputedStyle(el); return b.width > 0 && b.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  const inter = (p, q) => !(p.right <= q.left || q.right <= p.left || p.bottom <= q.top || q.bottom <= p.top);
  const dlgs = [...document.querySelectorAll('#stage .dlg')].filter(vis);
  const btns = [...document.querySelectorAll('#stage .opt, #stage .pad button, #stage .cake, #stage video, #stage .env, #stage .letters img, #stage .bulb')].filter(vis);
  for (const d of dlgs) for (const b of btns) if (inter(r(d), r(b))) issues.push('對話框蓋到互動元件 ' + b.className + ' ' + (b.textContent||'').slice(0,12));
  const sel = '#stage .dlg, #stage .act, .chip, .loc, #skip, #save a, .hb, .flags, .polaroid';
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    const b = r(el);
    if (b.left < -1 || b.right > W + 1 || b.top < -1 || b.bottom > H + 1) issues.push('超出畫面 ' + el.className + ' ' + JSON.stringify([Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]));
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX !== 'auto') issues.push('文字橫向被裁 ' + el.className);
    if (el.scrollHeight > el.clientHeight + 2 && /dlg|act/.test(el.className)) issues.push('文字直向被裁 ' + el.className);
  }
  const act = document.querySelector('#stage .act');
  if (act && vis(act)) for (const d of dlgs) { if (inter(r(act), r(d)) && !act.contains(d)) issues.push('對話框和互動卡重疊'); }
  return issues;
}
"""

def norm(s):
    s = re.sub(r"<br\s*/?>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", "", s)

def dump():
    res["all_lines_ok"] = all(e.get("ok") for e in res["lines"])
    res["line_count"] = len(res["lines"])
    if a.json:
        with open(a.json, "w") as f: json.dump(res, f, ensure_ascii=False, indent=1)

def main(p):
    br = p.webkit.launch(headless=True) if a.engine == "webkit" else p.chromium.launch(channel=a.channel, headless=True)
    ctx = br.new_context(viewport={"width": a.w, "height": a.h}, device_scale_factor=a.dpr, is_mobile=True,
                         has_touch=True, user_agent=IOS_UA, accept_downloads=True)
    if a.share == "off":
        ctx.add_init_script("delete Navigator.prototype.canShare; delete Navigator.prototype.share;")
    if a.share == "nodl":
        ctx.add_init_script("delete Navigator.prototype.canShare; delete Navigator.prototype.share; delete HTMLAnchorElement.prototype.download;")
    if a.share == "stub":
        ctx.add_init_script("""
          window.__shared = null;
          navigator.canShare = (d) => !!(d && d.files && d.files.length);
          navigator.share = (d) => { window.__shared = d.files.map(f => ({name:f.name, type:f.type, size:f.size})); return Promise.resolve(); };
        """)
    if a.mic == "deny":
        ctx.add_init_script("navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('denied', 'NotAllowedError'));")
    if a.mic == "none":
        ctx.add_init_script("Object.defineProperty(navigator, 'mediaDevices', {value: undefined});")
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)))
    def on_resp(r):
        if r.status >= 400: res["bad_responses"].append(f"{r.status} {r.url}")
        if not r.url.endswith(".mp4") and r.request.resource_type != "media":
            try: res["bytes_non_video"] += len(r.body())
            except Exception: pass
    page.on("response", on_resp)

    def shot(name):
        path = f"{a.out}/site-{a.tag}-{name}.png"
        page.screenshot(path=path)
        res["shots"].append(path)

    def state():
        return page.evaluate("() => ({ci: __sandy.ci, li: __sandy.li, busy: __sandy.busy, solved: __sandy.solved})")

    def wait_change(prev, timeout=6):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = state()
            if (s["ci"], s["li"]) != (prev["ci"], prev["li"]) and not s["busy"]:
                return s
            time.sleep(0.05)
        return state()

    def tap(x=None, y=None):
        page.touchscreen.tap(a.w / 2 if x is None else x, a.h - 70 if y is None else y)

    def tap_el(sel):
        b = page.locator(sel).first.bounding_box()
        page.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)

    def layout(label):
        for i in page.evaluate(LAYOUT_JS):
            res["layout_issues"].append(f"{label}: {i}")

    page.goto(a.url, wait_until="networkidle")
    page.wait_for_function("() => window.__sandy")
    scenes = page.evaluate("() => CONTENT.scenes")
    want_shot = lambda ci: a.shots == "all" or ci in SAMPLE
    shot("00-start") if a.shots == "all" else None
    tap(a.w / 2, a.h / 2)
    time.sleep(0.8)

    guard = 0
    if a.via_skip:
        path = []
        while guard < 60:
            guard += 1
            s = state(); path.append((s["ci"], s["li"], page.evaluate("() => { const l = __sandy.line(); return l.act || (l.quiz ? 'quiz' : l.w); }")))
            if path[-1][2] == "party": break
            if path[-1][2] == "candle":
                time.sleep(0.8)
                res["checks"]["candle_text"] = page.inner_text("#stage .act .main")
                shot("candle")
            time.sleep(0.7); tap_el("#skip"); wait_change(s)
        res["checks"]["skip_path"] = path
        time.sleep(3.8)
        res["checks"]["save_visible_after_skip"] = page.is_visible("#save a")
        shot("party-after-skip")
        guard = 999
    while guard < 200:
        guard += 1
        s = state(); ci, li = s["ci"], s["li"]
        l = scenes[ci]["lines"][li]
        time.sleep(0.75)   # 等彈出動畫
        text = page.inner_text("#stage")
        entry = {"ci": ci, "li": li}
        label = f"c{ci}-l{li:02d}"
        if "act" in l:
            entry["type"] = l["act"]
            entry["ok"] = page.locator("#stage .act").count() == 1
        elif "quiz" in l:
            entry["type"] = "quiz"; entry["ok"] = norm(l["q"]) in norm(text)
        else:
            entry["type"] = l["w"]; entry["ok"] = norm(l["t"]) in norm(text)
            if l.get("s"): entry["sticker"] = page.locator("#stage img.react").count() == 1
        if li == 0 and want_shot(ci): shot(f"{label}-first")
        if "act" not in l: layout(label)

        act = l.get("act")
        if act == "password":
            layout(label)
            if want_shot(ci): shot(f"{label}-password")
            for k in "1234": tap_el(f'#stage .pad button[data-k="{k}"]'); time.sleep(0.12)
            time.sleep(0.5)
            entry["wrong_hint"] = norm(l["wrong"]["t"]) in norm(page.inner_text("#stage"))
            layout(label + "-wrong")
            if want_shot(ci): shot(f"{label}-password-wrong")
            time.sleep(0.6)
            for k in "1017": tap_el(f'#stage .pad button[data-k="{k}"]'); time.sleep(0.12)
            time.sleep(0.4)
            if want_shot(ci): shot(f"{label}-password-ok")
            s2 = wait_change(s)
            entry["passed"] = s2["ci"] == ci + 1
        elif act == "bulbOff":
            tap_el("#stage .bulb"); time.sleep(1.4)
            entry["after_text"] = norm(l["after"]) in norm(page.inner_text("#stage"))
            layout(label)
            if want_shot(ci): shot(f"{label}-bulb")
            tap(); wait_change(s)
        elif act in ("bulbOn", "vote", "target", "search", "progress"):
            time.sleep({"search": 2.6, "progress": 2.8 if l.get("to") == 100 else 1.4, "vote": 1.4}.get(act, 0.6))
            if act == "search": entry["result"] = "明水然" in page.inner_text("#stage")
            if act == "progress": entry["pct"] = page.inner_text("#stage .pct")
            if act == "vote": entry["votes"] = page.inner_text("#stage .yes")
            layout(label)
            if want_shot(ci): shot(f"{label}-{act}")
            tap(); wait_change(s)
        elif act in ("giftVideo", "giftLetter"):
            if act == "giftVideo":
                has_v = page.locator("#stage video").count() == 1
                entry["video"] = has_v
                entry["placeholder"] = "今晚揭曉" in page.inner_text("#stage")
                if has_v:
                    page.wait_for_function("() => document.querySelector('#stage video').readyState >= 1", timeout=8000)
                    entry["video_duration"] = page.evaluate("() => document.querySelector('#stage video').duration")
            else:
                entry["placeholder"] = "今晚揭曉" in page.inner_text("#stage")
                if page.locator("#stage .env").count():
                    tap_el("#stage .env"); time.sleep(0.8)
                    entry["letters"] = page.evaluate("() => [...document.querySelectorAll('#stage .letters img')].map(i => i.naturalWidth)")
                    layout(label + "-open")
                    if want_shot(ci): shot(f"{label}-letter-open")
                    tap_el("#stage .letters img"); time.sleep(0.5)
                    entry["lightbox"] = page.is_visible("#lightbox img")
                    if want_shot(ci): shot(f"{label}-letter-lightbox")
                    page.click("#lightbox .close"); time.sleep(0.3)
            layout(label)
            if want_shot(ci): shot(f"{label}-{act}")
            tap(); wait_change(s)
        elif act == "candle":
            time.sleep(0.8)
            entry["mode_text"] = page.inner_text("#stage .act .main")
            entry["mic_text"] = page.inner_text("#stage .act .mic")
            layout(label)
            if want_shot(ci): shot(f"{label}-candle")
            b = page.locator("#stage .cake").bounding_box()
            cdp = ctx.new_cdp_session(page)
            pt = [{"x": b["x"] + b["width"] / 2, "y": b["y"] + b["height"] / 2}]
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt})
            time.sleep(1.0)
            entry["ring_mid"] = page.evaluate("() => getComputedStyle(document.querySelector('#stage .cake circle')).strokeDashoffset")
            if want_shot(ci): shot(f"{label}-candle-holding")
            time.sleep(1.3)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            s2 = wait_change(s)
            entry["passed"] = s2["li"] == li + 1
        elif "quiz" in l:
            wrong = next(i for i, o in enumerate(l["opts"]) if not o[1])
            right = next(i for i, o in enumerate(l["opts"]) if o[1])
            tap(); time.sleep(0.3)
            entry["blocked_before_answer"] = (state()["li"] == li)
            tap_el(f'#stage .opt[data-o="{wrong}"]'); time.sleep(0.9)
            entry["wrong_reply"] = norm(l["opts"][wrong][3]) in norm(page.inner_text("#stage"))
            layout(label + "-wrong")
            if want_shot(ci): shot(f"{label}-quiz-wrong")
            tap(); time.sleep(0.3)
            entry["blocked_after_wrong"] = (state()["li"] == li)
            tap_el(f'#stage .opt[data-o="{right}"]'); time.sleep(0.9)
            entry["right_reply"] = norm(l["opts"][right][3]) in norm(page.inner_text("#stage"))
            layout(label + "-right")
            if want_shot(ci): shot(f"{label}-quiz-right")
            tap(); wait_change(s)
        elif l.get("w") == "party":
            time.sleep(0.6)
            if want_shot(ci): shot(f"{label}-party-0s")
            time.sleep(3.2)
            entry["save_visible"] = page.is_visible("#save a")
            entry["skip_hidden"] = not page.is_visible("#skip")
            layout(label + "-save")
            shot(f"{label}-party-save")
            time.sleep(3)
            if want_shot(ci): shot(f"{label}-party-carousel")
            res["lines"].append(entry)
            break
        else:
            if want_shot(ci) and (l.get("s") or li in (0,)) and a.shots == "all": shot(f"{label}-line")
            tap(); s2 = wait_change(s)
        res["lines"].append(entry)

    # ── A5：保存按鈕 ──
    sv = page.evaluate("""() => { const a = document.querySelector('#saveLink');
        return { href: a.getAttribute('href'), abs: a.href, download: a.getAttribute('download'), type: a.getAttribute('type'),
                 text: a.textContent, hint: document.querySelector('#saveHint').textContent } }""")
    res["checks"]["save_link"] = sv
    head = None if not a.expect_media else page.evaluate("""async (u) => { const r = await fetch(u, {method:'HEAD'}); return {status:r.status, type:r.headers.get('content-type'), len:r.headers.get('content-length')}; }""", sv["abs"])
    res["checks"]["save_head"] = head
    if a.expect_media:
        if a.share == "stub":
            page.wait_for_function("() => !document.querySelector('#saveLink').classList.contains('busy')", timeout=8000)
            time.sleep(0.5)
            tap_el("#saveLink"); time.sleep(0.8)
            res["checks"]["share_called_with"] = page.evaluate("() => window.__shared")
        elif a.share == "nodl":
            with ctx.expect_page(timeout=10000) as np:
                tap_el("#saveLink")
            newp = np.value; newp.wait_for_load_state()
            newp.wait_for_function("() => document.querySelector('video').readyState >= 1", timeout=8000)
            res["checks"]["save_page"] = {"url": newp.url, "video_src": newp.evaluate("() => document.querySelector('video').currentSrc"),
                                          "duration": newp.evaluate("() => document.querySelector('video').duration"),
                                          "text": newp.inner_text("p")}
            newp.screenshot(path=f"{a.out}/site-{a.tag}-save-page.png"); res["shots"].append(f"{a.out}/site-{a.tag}-save-page.png")
        elif a.share == "off":
            res["checks"]["canShare_present"] = page.evaluate("() => 'canShare' in navigator")
            with page.expect_download(timeout=10000) as dl:
                tap_el("#saveLink")
            d = dl.value
            res["checks"]["download"] = {"suggested": d.suggested_filename, "url": d.url, "size": __import__('os').path.getsize(d.path())}
    res["checks"]["final_state"] = state()
    # 橫放提示
    if a.shots == "all":
        page.set_viewport_size({"width": a.h, "height": a.w}); time.sleep(0.4)
        res["checks"]["rotate_visible"] = page.is_visible("#rotate")
        shot("zz-landscape")
    dump()
    br.close()

with sync_playwright() as pw:
    try:
        main(pw)
    except Exception as ex:
        res["exception"] = repr(ex)[:500]
dump()
print(json.dumps(res, ensure_ascii=False, indent=1))
