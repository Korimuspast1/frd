#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальный сервер + веб-интерфейс для снапшотов тестовых серверов Telegram.
Источник данных: https://github.com/glebxdlolreal/testserverchangesall

Запуск:
    python3 server.py                      # http://0.0.0.0:8000
    SNAPSHOT_ROOT=/path/to/repo PORT=8000 python3 server.py

Что умеет:
  * "/"                         — главная: 5 поддоменов (a-, b-, i-, l-, y-) + JSON-снапшоты MTProto
  * "/{sub}/"                   — список файлов поддомена
  * "/{sub}/botfather.html"     — страница снапшота, отрендеренная локально
                                  (абсолютные пути /css, /js, /img переписываются на /{sub}/...)
  * "/raw/{sub}/{file}"         — исходный файл без перезаписи
  * "/json/{method}.json"       — просмотр JSON-снапшотов методов
  * "/history/{sub}/{file}"     — история изменений файла (git log)
  * POST "/api/pull"            — git pull: обновить снапшоты из GitHub
"""

import html
import json
import mimetypes
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs

ROOT = os.environ.get("SNAPSHOT_ROOT", "/home/user/testserverchangesall")
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "0.0.0.0")
SUBS = ["a-", "b-", "i-", "l-", "y-"]

SUB_TITLES = {
    "a-": "Поддомен a- — веб-ресурсы тестового сервера",
    "b-": "Поддомен b- — веб-ресурсы тестового сервера",
    "i-": "Поддомен i- — веб-ресурсы тестового сервера",
    "l-": "Поддомен l- — веб-ресурсы тестового сервера",
    "y-": "Поддомен y- — веб-ресурсы тестового сервера",
}

EXTRA_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}

# что Telegran-страницы тянут по абсолютным путям от корня домена
ASSET_PREFIXES = ("css/", "js/", "img/", "file/", "fonts/", "font/", "svg/", "static/", "assets/")

PAGES = (".html",)

# 1x1 прозрачный GIF — для /img/*, которых в снапшоте нет
PIXEL = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c0000000001000100"
    "000002024401003b"
)

CSS = """
:root{--bg:#0e1116;--bg2:#161b22;--bg3:#1c2230;--line:#2a3140;--fg:#e6edf3;--dim:#8b949e;
--acc:#4c9aff;--acc2:#2ea043;--warn:#d29922}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 60px}
header.top{border-bottom:1px solid var(--line);background:linear-gradient(180deg,#161b22,#0e1116);padding:26px 0 22px;margin-bottom:26px}
header.top h1{margin:0 0 6px;font-size:24px;letter-spacing:.2px}
header.top p{margin:0;color:var(--dim);font-size:14px}
header.top .repo{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
h2{font-size:18px;margin:32px 0 14px;display:flex;align-items:center;gap:10px}
h2 .tag{font-size:12px;color:var(--dim);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.card{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:16px;transition:.15s}
.card:hover{border-color:var(--acc);transform:translateY(-2px);text-decoration:none}
.card .sub{font-family:ui-monospace,monospace;font-size:20px;color:var(--acc);font-weight:600}
.card .meta{color:var(--dim);font-size:13px;margin-top:6px}
table.files{width:100%;border-collapse:collapse;font-size:14px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;overflow:hidden}
table.files th{text-align:left;background:var(--bg3);color:var(--dim);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.5px;padding:10px 14px}
table.files td{padding:9px 14px;border-top:1px solid var(--line)}
table.files tr:hover td{background:#1a2130}
table.files td.name{font-family:ui-monospace,monospace}
table.files td.size{color:var(--dim);white-space:nowrap;text-align:right}
table.files td.date{color:var(--dim);white-space:nowrap;font-size:13px}
.pages{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
.pill{background:var(--bg3);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-family:ui-monospace,monospace;font-size:13px}
.pill:hover{border-color:var(--acc);text-decoration:none}
.pill.hot{border-color:#2ea04355;background:#12261a}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.bar .sp{flex:1}
button,.btn{background:var(--bg3);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 14px;font-size:13px;cursor:pointer;font-family:inherit}
button:hover,.btn:hover{border-color:var(--acc);text-decoration:none}
pre{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:16px;overflow:auto;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;max-height:70vh}
pre.json{margin:0;border-radius:0;border:none;max-height:none}
code.k{color:#79c0ff}code.s{color:#a5d6ff}code.n{color:#f2cc60}code.b{color:#d2a8ff}
.hist li{margin-bottom:10px;font-size:13px}
.hist .sha{font-family:ui-monospace,monospace;color:var(--dim)}
.hist .when{color:var(--dim);margin-left:8px}
.note{color:var(--dim);font-size:13px;background:#1a1f27;border-left:3px solid var(--warn);padding:10px 14px;border-radius:0 8px 8px 0}
footer{color:var(--dim);font-size:13px;border-top:1px solid var(--line);margin-top:40px;padding-top:16px}
#snap-bar{position:fixed;top:0;left:0;right:0;z-index:2147483647;height:38px;display:flex;align-items:center;gap:12px;
padding:0 12px;background:#11161f;border-bottom:1px solid #2a3140;color:#e6edf3;font:13px/1 -apple-system,"Segoe UI",Roboto,sans-serif}
#snap-bar a{color:#4c9aff}
#snap-bar .sb-sp{flex:1}
#snap-bar button{background:#222a38;color:#e6edf3;border:1px solid #2a3140;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
.mini{font-size:12px;color:var(--dim)}
"""

JS = """
(function(){
  var b=document.getElementById('snap-bar'); if(!b) return;
  document.body.style.paddingTop='38px';
  var h=document.getElementById('sb-hide');
  if(h){ h.onclick=function(){ b.remove(); document.body.style.paddingTop=''; }; }
})();
"""

BAR_TPL = """
<div id="snap-bar">
  <a href="/">← все снапшоты</a>
  <a href="/{sub}/">{sub}</a>
  <span style="color:#8b949e">{page}</span>
  <span class="sb-sp"></span>
  <a href="/history/{sub}/{page}">история</a>
  <a href="/raw/{sub}/{page}">исходник</a>
  <button id="sb-hide">скрыть панель</button>
</div>
"""


# --------------------------------------------------------------------------- utils
def esc(s):
    return html.escape(str(s))


def fsize(n):
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024.0


def sub_path(sub, name=""):
    return os.path.join(ROOT, sub, name)


def in_root(path):
    real = os.path.realpath(path)
    return real == ROOT or real.startswith(os.path.realpath(ROOT) + os.sep)


def content_type(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in EXTRA_TYPES:
        return EXTRA_TYPES[ext]
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def git(*args, timeout=20):
    try:
        p = subprocess.run(
            ["git", "-C", ROOT] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
        if p.returncode != 0:
            return None
        return p.stdout
    except Exception:
        return None


def is_shallow():
    return os.path.exists(os.path.join(ROOT, ".git", "shallow"))


HIST = {}  # relpath -> {"count": n, "last": {sha,date,msg}}


def build_history_index():
    """Один проход по всей истории: для каждого файла — дата последней правки и число правок."""
    HIST.clear()
    if is_shallow():
        return 0
    out = git("-c", "core.quotePath=false", "log", "--format=@@@%H %ad %s",
              "--date=short", "--name-only", timeout=120)
    if not out:
        return 0
    cur = None
    for line in out.split("\n"):
        if line.startswith("@@@"):
            parts = line[3:].split(" ", 2)
            cur = {"sha": parts[0][:8], "date": parts[1] if len(parts) > 1 else "",
                   "msg": parts[2] if len(parts) > 2 else ""}
        elif line.strip():
            e = HIST.setdefault(line.strip(), {"count": 0, "last": None})
            e["count"] += 1
            if e["last"] is None:
                e["last"] = cur
    return len(HIST)


def git_info(relpath):
    """Последний коммит, затронувший файл, и сколько всего коммитов."""
    e = HIST.get(relpath)
    if not e:
        return None, None
    return e["last"], e["count"]


def list_files(sub):
    d = sub_path(sub)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            st = os.stat(p)
            out.append({"name": name, "size": st.st_size, "mtime": st.st_mtime})
    return out


def repo_stat():
    files = 0
    size = 0
    for sub in SUBS:
        for f in list_files(sub):
            files += 1
            size += f["size"]
    n_json = len([f for f in os.listdir(ROOT) if f.endswith(".json")]) if os.path.isdir(ROOT) else 0
    return files, size, n_json


# ------------------------------------------------------------------- rewriting
ATTR_RE = re.compile(r'((?:href|src|action|data-[a-z-]+)=")(/[^"]*)(")')
CSSURL_RE = re.compile(r"(url\()(['\"]?)(/[^)'\"]*)")


def rewrite_html(text, sub):
    """Переписать абсолютные пути Telegram-страниц на локальные /{sub}/..."""

    def attr(m):
        pre, url, post = m.group(1), m.group(2), m.group(3)
        if url.startswith("//"):
            return m.group(0)
        path = url.split("?")[0].split("#")[0]
        if any(path.startswith("/" + p) for p in ASSET_PREFIXES):
            return pre + "/" + sub + url + post
        if path == "/":
            return pre + "/" + sub + "/" + post
        # ссылки на другие страницы того же сервера: /botfather -> /{sub}/botfather.html
        if "/" not in path[1:] and "." not in os.path.basename(path):
            if os.path.isfile(sub_path(sub, path[1:] + ".html")):
                return pre + "/" + sub + path + ".html" + post
        return m.group(0)

    text = ATTR_RE.sub(attr, text)
    # встроенные <style>
    def css(m):
        url = m.group(3)
        if any(url.startswith("/" + p) for p in ASSET_PREFIXES):
            return m.group(1) + m.group(2) + "/" + sub + url
        return m.group(0)

    text = CSSURL_RE.sub(css, text)
    return text


def rewrite_css(text, sub):
    def css(m):
        url = m.group(3)
        if any(url.startswith("/" + p) for p in ASSET_PREFIXES):
            return m.group(1) + m.group(2) + "/" + sub + url
        return m.group(0)

    return CSSURL_RE.sub(css, text)


def inject_bar(text, sub, page):
    bar = BAR_TPL.format(sub=esc(sub), page=esc(page))
    low = text.lower()
    idx = low.find("<body")
    if idx != -1:
        end = text.find(">", idx)
        if end != -1:
            return text[: end + 1] + bar + text[end + 1 :]
    return bar + text


# ------------------------------------------------------------------- rendering
def page(title, body, sub=None):
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body>
<header class="top"><div class="wrap">
<h1>Снапшоты тестовых серверов Telegram</h1>
<p class="repo">репозиторий <a href="https://github.com/glebxdlolreal/testserverchangesall">glebxdlolreal/testserverchangesall</a> ·
локальный просмотрщик на <code>{esc(ROOT)}</code></p>
</div></header>
<div class="wrap">{body}
<footer>Данные — слепки веб-ресурсов тестовых поддоменов Telegram (<code>a-</code>, <code>b-</code>, <code>i-</code>, <code>l-</code>, <code>y-</code>)
и ответов MTProto-методов. Запросы к самим серверам Telegram из этой песочницы недоступны, поэтому интерактивные формы работать не будут.</footer>
</div></body></html>"""


def render_home():
    files, size, n_json = repo_stat()
    head = git("log", "-1", "--format=%h %ad", "--date=short")
    head = (head or "").strip()
    cards = []
    for sub in SUBS:
        fl = list_files(sub)
        npages = len([f for f in fl if f["name"].endswith(".html")])
        hot = [f["name"] for f in fl if f["name"].endswith(".html")][:4]
        cards.append(f"""<a class="card" href="/{sub}/">
<div class="sub">{sub}</div>
<div class="meta">{len(fl)} файлов · {npages} страниц · {fsize(sum(f['size'] for f in fl))}</div>
<div class="meta" style="margin-top:8px">{esc(', '.join(hot))}</div></a>""")

    jsons = []
    if os.path.isdir(ROOT):
        for name in sorted(os.listdir(ROOT)):
            p = os.path.join(ROOT, name)
            if os.path.isfile(p) and name.endswith(".json"):
                jsons.append(
                    f'<a class="pill" href="/json/{esc(name)}">{esc(name)}</a>'
                )

    body = f"""
<div class="bar">
  <strong>{files}</strong>&nbsp;<span class="mini">файлов в поддоменах · {fsize(size)} · {n_json} JSON-методов</span>
  <span class="sp"></span>
  <span class="mini">HEAD: {esc(head) or '—'}{' (shallow clone)' if is_shallow() else ''}</span>
  <form method="post" action="/api/pull" style="display:inline">
    <button type="submit">↻ обновить из GitHub</button>
  </form>
</div>
<p class="note">Это архив слепков, а не приложение: «интерфейс» — это сами сохранённые страницы
(BotFather, oauth, stickers, contest, demo и др.). Откройте поддомен и выберите страницу — она
отрендерится локально: css/js подхватываются из снапшота, картинки <code>/img/*</code> в архив не
попадают, поэтому вместо них прозрачная заглушка.</p>
<h2>Поддомены тестового сервера <span class="tag">веб-ресурсы</span></h2>
<div class="grid">{''.join(cards)}</div>
<h2>Снапшоты ответов MTProto <span class="tag">{n_json} методов</span></h2>
<div class="pages">{''.join(jsons) or '<span class="mini">нет</span>'}</div>
"""
    return page("Снапшоты тестовых серверов Telegram", body)


def render_sub(sub):
    files = list_files(sub)
    pages = [f for f in files if f["name"].endswith(PAGES)]
    others = [f for f in files if not f["name"].endswith(PAGES)]
    pills = "".join(
        f'<a class="pill hot" href="/{sub}/{esc(f["name"])}">{esc(f["name"])}</a>' for f in pages
    )
    rows = []
    for f in others:
        last, total = git_info(f"{sub}/{f['name']}")
        date = last["date"] if last else datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d")
        commits = f' <span class="mini">({total} правок)</span>' if total else ""
        rows.append(
            f'<tr><td class="name"><a href="/raw/{sub}/{esc(f["name"])}">{esc(f["name"])}</a>'
            f'<a class="mini" href="/history/{sub}/{esc(f["name"])}" style="margin-left:8px">история</a>{commits}</td>'
            f'<td class="size">{fsize(f["size"])}</td><td class="date">{esc(date)}</td></tr>'
        )
    body = f"""
<div class="bar"><a class="btn" href="/">← назад</a><strong>{esc(sub)}</strong>
<span class="mini">{esc(SUB_TITLES.get(sub, ''))}</span><span class="sp"></span>
<span class="mini">{len(files)} файлов · {fsize(sum(f['size'] for f in files))}</span></div>
<h2>Страницы <span class="tag">открыть в этом окне</span></h2>
<div class="pages">{pills or '<span class="mini">нет html</span>'}</div>
<h2>Ресурсы <span class="tag">css / js / карты</span></h2>
<table class="files"><tr><th>Файл</th><th style="text-align:right">Размер</th><th>Изменён</th></tr>
{''.join(rows)}</table>
"""
    return page(f"{sub} — снапшоты", body, sub)


def render_json(name):
    path = os.path.join(ROOT, name)
    if not in_root(path) or not os.path.isfile(path):
        return None
    raw = open(path, encoding="utf-8", errors="replace").read()
    try:
        pretty = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except Exception:
        pretty = raw
    pretty = esc(pretty)
    pretty = re.sub(r'&quot;([^&]*?)&quot;(\s*:)', r'<code class="k">&quot;\1&quot;</code>\2', pretty)
    body = f"""
<div class="bar"><a class="btn" href="/">← назад</a><strong>{esc(name)}</strong><span class="sp"></span>
<a class="btn" href="/raw/_root_/{esc(name)}">скачать JSON</a></div>
<pre class="json">{pretty}</pre>
"""
    return page(name, body)


def render_history(relpath):
    if is_shallow():
        body = f"""
<div class="bar"><a class="btn" href="/">← назад</a><strong>{esc(relpath)}</strong></div>
<p class="note">История недоступна: репозиторий клонирован с <code>--depth 1</code>.
Выполните <code>git -C {esc(ROOT)} fetch --unshallow</code> и перезапустите сервер.</p>"""
        return page("История " + relpath, body)
    out = git("log", "--format=%H%x1f%ad%x1f%an%x1f%s", "--date=iso", "--", relpath)
    if out is None:
        return None
    items = []
    for line in [l for l in out.strip().split("\n") if l]:
        sha, date, author, msg = (line.split("\x1f") + ["", "", "", ""])[:4]
        items.append(
            f'<li><span class="sha">{esc(sha[:10])}</span> {esc(msg)}'
            f'<span class="when">{esc(date[:16])} · {esc(author)}</span></li>'
        )
    body = f"""
<div class="bar"><a class="btn" href="/">← назад</a>
<a class="btn" href="/{esc(relpath.split('/')[0])}/">{esc(relpath.split('/')[0])}</a>
<strong>{esc(relpath)}</strong></div>
<h2>История изменений <span class="tag">{len(items)} коммитов</span></h2>
<ul class="hist">{''.join(items) or '<li class="mini">нет данных</li>'}</ul>
"""
    return page("История " + relpath, body)


# ------------------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    server_version = "TGSnapshotViewer/1.0"

    def log_message(self, fmt, *args):
        if "/img/" in (self.path or ""):
            return
        super().log_message(fmt, *args)

    # -- helpers
    def send(self, data, ctype="text/html; charset=utf-8", code=200, extra=None):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_file(self, path, ctype=None, rewrite=None, sub=None):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            return self.send(self.notfound(path), code=404)
        name = os.path.basename(path)
        ct = ctype or content_type(name)
        if rewrite and ct.startswith("text/"):
            text = data.decode("utf-8", errors="replace")
            text = rewrite(text)
            if sub is not None:
                text = inject_bar(text, sub, name)
            data = text.encode("utf-8")
        return self.send(data, ct)

    def notfound(self, what=""):
        return page("404", f"""<div class="bar"><a class="btn" href="/">← на главную</a></div>
<p class="note">Не найдено: <code>{esc(what)}</code></p>""")

    def redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.end_headers()

    # -- routes
    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/pull":
            out = git("pull", "--ff-only", timeout=180)
            msg = (out or "ошибка git pull").strip().split("\n")[-1][:200]
            n = build_history_index()
            if (self.headers.get("Accept") or "").find("json") >= 0:
                return self.send(
                    json.dumps({"ok": out is not None, "output": msg, "files": n},
                               ensure_ascii=False),
                    "application/json; charset=utf-8",
                )
            body = f"""
<div class="bar"><a class="btn" href="/">← на главную</a></div>
<h2>Обновление из GitHub</h2>
<p class="note">{'<b>Ок:</b> ' if out is not None else '<b>Ошибка:</b> '}{esc(msg)}</p>
<p>Проиндексировано файлов в истории: <b>{n}</b></p>
<p><a class="btn" href="/">вернуться к снапшотам</a></p>"""
            return self.send(page("git pull", body))
        self.send(self.notfound(path), code=404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            return self.send(render_home())
        if path == "/favicon.ico":
            return self.send(PIXEL, "image/gif")
        if path == "/assets/app.css":
            return self.send(CSS, "text/css; charset=utf-8")
        if path == "/assets/app.js":
            return self.send(JS, "text/javascript; charset=utf-8")

        parts = [p for p in path.split("/") if p]

        # /raw/{sub}/{file}  и /raw/_root_/{file}
        if parts and parts[0] == "raw":
            if len(parts) < 3:
                return self.send(self.notfound(path), code=404)
            sub, name = parts[1], "/".join(parts[2:])
            base = ROOT if sub == "_root_" else sub_path(sub)
            if sub != "_root_" and sub not in SUBS:
                return self.send(self.notfound(path), code=404)
            return self.send_file(os.path.join(base, name))

        # /json/{method}.json
        if parts and parts[0] == "json":
            name = "/".join(parts[1:])
            if not name.endswith(".json") or "/" in name:
                return self.send(self.notfound(path), code=404)
            out = render_json(name)
            return self.send(out if out else self.notfound(path), code=200 if out else 404)

        # /history/{sub}/{file}
        if parts and parts[0] == "history":
            rel = "/".join(parts[1:])
            if len(parts) < 3:
                return self.send(self.notfound(path), code=404)
            out = render_history(rel)
            return self.send(out if out else self.notfound(path), code=200 if out else 404)

        # /{sub}/...
        if parts and parts[0] in SUBS:
            sub = parts[0]
            rest = parts[1:]
            if not rest:
                return self.send(render_sub(sub))
            rel = "/".join(rest)
            # /{sub}/css/foo.css -> плоский файл foo.css внутри папки поддомена
            first = rest[0]
            if len(rest) > 1 and any(first + "/" == p for p in ASSET_PREFIXES):
                name = rest[-1].split("?")[0]
                p = sub_path(sub, name)
                if os.path.isfile(p):
                    return self.send_file(p, rewrite=(lambda t: rewrite_css(t, sub)))
                if first == "img":
                    return self.send(PIXEL, "image/gif")
                return self.send(self.notfound(path), code=404)
            # страница или файл
            p = sub_path(sub, rel)
            if os.path.isfile(p):
                if rel.endswith(".html") and "raw" not in query:
                    return self.send_file(
                        p, rewrite=(lambda t: rewrite_html(t, sub)), sub=sub
                    )
                return self.send_file(p)
            # /{sub}/botfather -> botfather.html
            alt = sub_path(sub, rel + ".html")
            if os.path.isfile(alt):
                return self.send_file(alt, rewrite=(lambda t: rewrite_html(t, sub)), sub=sub)
            return self.send(self.notfound(path), code=404)

        return self.send(self.notfound(path), code=404)


def main():
    if not os.path.isdir(ROOT):
        raise SystemExit(f"Нет каталога со снапшотами: {ROOT}")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    t0 = time.time()
    n = build_history_index()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] индекс истории: {n} файлов за {time.time()-t0:.1f} c")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] снапшоты: {ROOT}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] интерфейс: http://{HOST}:{PORT}/  (Ctrl+C — стоп)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
