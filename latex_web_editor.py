# -*- coding: utf-8 -*-
"""开题报告 · 本地网页版 LaTeX 编辑器（只用标准库）
   启动：python latex_web_editor.py
   打开：http://127.0.0.1:8766/
   功能：左侧编辑 开题报告.tex，点「保存并编译」→ 右侧实时看 PDF
"""
import http.server
import io
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
TEXNAME = "开题报告模板.tex"
PDFNAME = "开题报告模板.pdf"
XELATEX = r"C:\texlive\2026\bin\windows\xelatex.exe"
PORT = 8766

_lock = threading.Lock()

PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>开题报告 · LaTeX 编辑器</title>
<style>
 html,body{margin:0;height:100%;font-family:"Microsoft YaHei",system-ui,sans-serif}
 header{display:flex;align-items:center;gap:12px;padding:8px 14px;background:#1f2937;color:#fff;flex-wrap:wrap}
 header h1{font-size:15px;margin:0;font-weight:600}
 button{padding:6px 14px;border:0;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer;font-size:14px}
 button:hover{background:#1d4ed8}
 button.ghost{background:#374151}
 #status{font-size:13px;color:#d1d5db}
 #log{font-size:12px;color:#fca5a5;max-height:120px;overflow:auto;white-space:pre-wrap;width:100%}
 main{display:flex;height:calc(100% - 52px)}
 #src{width:50%;height:100%;border:0;border-right:1px solid #ddd;padding:10px;
      font-family:Consolas,monospace;font-size:13px;line-height:1.5;resize:none;box-sizing:border-box}
 #pv{width:50%;height:100%;border:0;background:#525659}
</style></head>
<body>
<header>
  <h1>开题报告 · LaTeX 编辑器</h1>
  <button id="btn">保存并编译</button>
  <button class="ghost" id="reload">刷新 PDF</button>
  <a href="/pdf" target="_blank" style="color:#93c5fd;font-size:13px">在新窗口打开 PDF</a>
  <span id="status">就绪</span>
  <div id="log"></div>
</header>
<main>
  <textarea id="src" spellcheck="false"></textarea>
  <iframe id="pv" src="/pdf"></iframe>
</main>
<script>
var src = document.getElementById('src'), st = document.getElementById('status'),
    lg = document.getElementById('log'), pv = document.getElementById('pv');
fetch('/source').then(function(r){return r.text();}).then(function(t){src.value = t;});
function showPDF(){ pv.src = '/pdf?t=' + Date.now(); }
document.getElementById('reload').onclick = showPDF;
document.getElementById('btn').onclick = function(){
  st.textContent = '正在编译…'; lg.textContent = '';
  fetch('/compile', {method:'POST', body: src.value})
    .then(function(r){return r.json();})
    .then(function(j){
      st.textContent = j.ok ? ('编译成功（' + j.seconds + ' 秒）') : '编译有错误，见下方';
      st.style.color = j.ok ? '#86efac' : '#fca5a5';
      lg.textContent = j.ok ? '' : j.log;
      if (j.ok) showPDF();
    })
    .catch(function(e){ st.textContent = '请求失败：' + e; });
};
document.addEventListener('keydown', function(e){
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); document.getElementById('btn').click(); }
});
</script>
</body></html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, ctype, body, nocache=True):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if nocache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif path == "/source":
            p = os.path.join(ROOT, TEXNAME)
            txt = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
            self._send(200, "text/plain; charset=utf-8", txt)
        elif path == "/pdf":
            p = os.path.join(ROOT, PDFNAME)
            if os.path.exists(p):
                self._send(200, "application/pdf", open(p, "rb").read())
            else:
                self._send(404, "text/plain; charset=utf-8", "尚未生成 PDF")
        else:
            self._send(404, "text/plain; charset=utf-8", "not found")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8", "replace")
        if self.path == "/save":
            with _lock:
                io.open(os.path.join(ROOT, TEXNAME), "w", encoding="utf-8").write(body)
            self._send(200, "application/json", json.dumps({"ok": True}))
        elif self.path == "/compile":
            res = compile_tex(body)
            self._send(200, "application/json", json.dumps(res, ensure_ascii=False))
        else:
            self._send(404, "text/plain", "not found")


def compile_tex(source: str):
    import time
    t0 = time.time()
    tex = os.path.join(ROOT, TEXNAME)
    logf = os.path.join(ROOT, "_compile.log")
    with _lock:
        io.open(tex, "w", encoding="utf-8").write(source)
        ok = True
        for _ in range(2):
            with open(logf, "wb") as fh:
                rc = subprocess.call([XELATEX, "-interaction=nonstopmode", TEXNAME],
                                     cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
            if rc != 0:
                ok = False
    log = io.open(logf, encoding="utf-8", errors="replace").read() if os.path.exists(logf) else ""
    # 提取错误行，便于阅读
    errs = [l for l in log.split("\n") if l.startswith("!")]
    pdf = os.path.join(ROOT, PDFNAME)
    good = ok and os.path.exists(pdf)
    return {"ok": good, "seconds": round(time.time() - t0, 1),
            "log": "\n".join(errs[:12]) or log[-1500:]}


def main():
    os.chdir(ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("编辑器已启动: http://127.0.0.1:%d/" % PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()

