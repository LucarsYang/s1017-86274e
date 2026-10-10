#!/usr/bin/env python3
"""本機預覽伺服器（支援影片 Range 請求，iPhone Safari 才播得了影片）。
用法（在 site/ 底下）：python3 tools/serve.py [port] [--local]，預設 8000；--local 只開給這台 Mac。
同一個 Wi-Fi 的手機可以開 http://<這台 Mac 的 IP>:8000/ 試看
（http 下麥克風與分享檔案不能用，會自動改「按住蛋糕」與「下載」；正式用要 HTTPS）。
"""
import os, re, socket, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else size - 1
        if m and not m.group(1) and m.group(2):          # bytes=-N（最後 N bytes）
            start, end = max(0, size - int(m.group(2))), size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416); return None
        f = open(path, "rb"); f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remain = end - start + 1
        return f

    def copyfile(self, src, dst):
        n = getattr(self, "_remain", None)
        if n is None:
            return super().copyfile(src, dst)
        while n > 0:
            buf = src.read(min(65536, n))
            if not buf: break
            dst.write(buf); n -= len(buf)
        self._remain = None


H.extensions_map.update({".webp": "image/webp", ".mp4": "video/mp4", ".js": "text/javascript"})
args = [x for x in sys.argv[1:] if not x.startswith("--")]
host = "127.0.0.1" if "--local" in sys.argv else "0.0.0.0"   # --local：只給這台 Mac 看
port = int(args[0]) if args else 8000
try:
    ip = socket.gethostbyname(socket.gethostname())
except Exception:
    ip = "<Mac 的 IP>"
print(f"本機：http://127.0.0.1:{port}/　手機（同 Wi-Fi）：http://{ip}:{port}/　按 Ctrl+C 停止")
ThreadingHTTPServer((host, port), H).serve_forever()
