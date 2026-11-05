package ai.opencode.android

import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Executes JavaScript inside the app's WebView (V8) runtime and returns captured console output.
 *
 * Used by the portable `node` CLI shim (`CliTools node script.js`) so JS/HTTP/JSON scripts written by
 * the agent actually run on-device even though Android cannot start a native `node` binary from
 * `/storage/emulated/0` (a `noexec` FUSE mount).
 *
 * The prelude installed before every script provides a practical Node.js-compatible surface built on
 * top of the app's native bridge: `fs`, `path`, `os`, `process`, `child_process`, `crypto`, `util`,
 * `events`, `fetch`, `Buffer`, plus ES-module syntax transpiled to CommonJS.
 */
class JsBridgeRunner(
    private val runtime: OpenCodeRuntime,
    private val getWebView: () -> WebView?,
) {

    private val main = Handler(Looper.getMainLooper())

    @Volatile
    private var installed = false

    fun install() {
        if (installed) return
        installed = true
    }

    fun evaluateBlocking(code: String, cwd: String, filename: String, timeoutMs: Long): JSONObject {
        val job = OpenCodeRuntime.JsJob(
            id = "js_" + System.currentTimeMillis() + "_" + (Math.random() * 1_000_000).toInt(),
            code = code,
            cwd = cwd,
            filename = filename,
        )
        runtime.submitJsJob(job)

        val view = getWebView()
        if (view != null) {
            evaluate(job, view)
        }

        val deadline = System.currentTimeMillis() + timeoutMs.coerceIn(1000, 900000)
        while (System.currentTimeMillis() < deadline) {
            if (job.completed) return toJson(job)
            if (!job.started) {
                val pendingView = getWebView()
                if (pendingView != null) evaluate(job, pendingView)
            }
            try {
                Thread.sleep(50)
            } catch (_: Throwable) {
                break
            }
        }
        return JSONObject()
            .put("ok", false)
            .put(
                "error",
                "JavaScript evaluation timed out — keep the OpenCode app window open and retry `node ${File(filename).name}`.",
            )
            .put("stdout", job.stdout)
            .put("stderr", job.stderr)
            .put("exitCode", 124)
    }

    private fun toJson(job: OpenCodeRuntime.JsJob): JSONObject = JSONObject()
        .put("ok", job.ok)
        .put("stdout", job.stdout)
        .put("stderr", job.stderr)
        .put("exitCode", job.exitCode)
        .put("error", job.error ?: JSONObject.NULL)

    private fun evaluate(job: OpenCodeRuntime.JsJob, view: WebView) {
        if (job.started) return
        job.started = true
        val startedAt = System.currentTimeMillis()
        val script = buildScript(job)
        val latch = CountDownLatch(1)
        var scriptReturned = false
        main.post {
            try {
                view.evaluateJavascript(script) { result ->
                    scriptReturned = true
                    if (!job.completed) {
                        val decoded = decodeJsString(result ?: "null")
                        if (decoded == "null" || decoded.isBlank()) {
                            runtime.finishJsJob(
                                job.id,
                                JSONObject().put("ok", false)
                                    .put("error", "JavaScript job produced no result")
                                    .put("exitCode", 1).toString(),
                            )
                        } else {
                            runtime.finishJsJob(job.id, decoded)
                        }
                    }
                    latch.countDown()
                }
            } catch (t: Throwable) {
                runtime.finishJsJob(
                    job.id,
                    JSONObject()
                        .put("ok", false)
                        .put("error", t.message ?: "WebView evaluation failed")
                        .put("exitCode", 1)
                        .toString(),
                )
            } finally {
                latch.countDown()
            }
        }
        try {
            latch.await(3, TimeUnit.SECONDS)
        } catch (_: Throwable) {
        }
        if (!scriptReturned && !job.completed && System.currentTimeMillis() - startedAt < 5000) {
            runtime.finishJsJob(
                job.id,
                JSONObject()
                    .put("ok", false)
                    .put("error", "WebView did not respond to the JavaScript job")
                    .put("exitCode", 1)
                    .toString(),
            )
        }
    }

    /** WebView returns a JSON-encoded string literal — unwrap one layer. */
    private fun decodeJsString(raw: String): String {
        val trimmed = raw.trim()
        if (trimmed.length >= 2 && trimmed.startsWith("\"") && trimmed.endsWith("\"")) {
            return try {
                JSONObject("{\"v\":$trimmed}").optString("v", trimmed.substring(1, trimmed.length - 1))
            } catch (_: Throwable) {
                trimmed.substring(1, trimmed.length - 1)
            }
        }
        return trimmed
    }

    private fun buildScript(job: OpenCodeRuntime.JsJob): String {
        val codeText = job.code
        val cwdLiteral = jsonQuote(job.cwd)
        val fileLiteral = jsonQuote(job.filename)
        val nodeRuntime = NODE_PRELUDE
            .replace("__OC_CWD__", cwdLiteral)
            .replace("__OC_FILENAME__", fileLiteral)
        return "(async function(){\n" + nodeRuntime + "\nreturn await __ocRun(" + jsonQuote(codeText) + ");\n})()"
    }

    private fun jsonQuote(value: String): String {
        val sb = StringBuilder("\"")
        for (ch in value) {
            when (ch) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                '\u2028' -> sb.append("\\u2028")
                '\u2029' -> sb.append("\\u2029")
                else -> if (ch.code < 0x20) sb.append(String.format("\\u%04x", ch.code)) else sb.append(ch)
            }
        }
        return sb.append('"').toString()
    }

    companion object {
        /**
         * Node.js-compatible runtime surface. Everything is synchronous where Node is synchronous,
         * backed by the local native daemon (`/__native/rpc`) which performs real file I/O and shell
         * execution in the Android app process.
         */
        private val NODE_PRELUDE: String = """
var __cwd = __OC_CWD__;
var __filename = __OC_FILENAME__;
var __dirname = (function (p) { var i = p.lastIndexOf('/'); return i > 0 ? p.slice(0, i) : '/'; })(__filename);
var __outBuf = [];
var __errBuf = [];
var __jobs = [];
function __writeOut(s) { __outBuf.push(String(s)); }
function __writeErr(s) { __errBuf.push(String(s)); }

function __daemonBase() {
  try {
    var url = (window.OpenCodeNative && window.OpenCodeNative.getDaemonUrl) ? window.OpenCodeNative.getDaemonUrl() : '';
    return url && url.indexOf('http') === 0 ? url : '';
  } catch (e) { return ''; }
}

function __ocRpcSync(action, payload) {
  var base = __daemonBase();
  if (!base) throw new Error('OpenCode native runtime is not available — open the app once, then retry');
  var xhr = new XMLHttpRequest();
  xhr.open('POST', base + '/__native/rpc', false);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(JSON.stringify({ action: action, payload: payload || {} }));
  var text = xhr.responseText || '{}';
  var parsed;
  try { parsed = JSON.parse(text); } catch (e) { throw new Error('native rpc parse error: ' + text.slice(0, 200)); }
  if (parsed && parsed.__error) throw new Error(String(parsed.__error));
  return parsed;
}

function __ocRpcAsync(action, payload) {
  return new Promise(function (resolve, reject) {
    var base = __daemonBase();
    if (!base) return reject(new Error('OpenCode native runtime is not available'));
    fetch(base + '/__native/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, payload: payload || {} }),
    }).then(function (r) { return r.text(); }).then(function (text) {
      var parsed;
      try { parsed = JSON.parse(text); } catch (e) { return reject(new Error('native rpc parse error')); }
      if (parsed && parsed.__error) return reject(new Error(String(parsed.__error)));
      resolve(parsed);
    }).catch(reject);
  });
}

function __normPath(p) {
  p = String(p === undefined || p === null ? '' : p);
  if (p === '') return __cwd;
  if (p.charAt(0) !== '/') p = __cwd + '/' + p;
  var parts = p.split('/');
  var stack = [];
  for (var i = 0; i < parts.length; i++) {
    var seg = parts[i];
    if (seg === '' || seg === '.') continue;
    if (seg === '..') { stack.pop(); continue; }
    stack.push(seg);
  }
  return '/' + stack.join('/');
}

function __relPath(p) {
  var abs = __normPath(p);
  return abs === __cwd ? '.' : abs;
}

/* ─── Buffer ─── */
function Buffer(arg, enc) {
  if (!(this instanceof Buffer)) return new Buffer(arg, enc);
  var bytes;
  if (typeof arg === 'string') {
    var s = enc === 'base64' ? atob(arg) : arg;
    bytes = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i) & 0xff;
  } else if (arg instanceof Uint8Array) {
    bytes = arg.slice();
  } else if (arg instanceof ArrayBuffer) {
    bytes = new Uint8Array(arg.slice(0));
  } else if (Array.isArray(arg)) {
    bytes = new Uint8Array(arg);
  } else if (typeof arg === 'number') {
    bytes = new Uint8Array(arg);
  } else {
    bytes = new Uint8Array(0);
  }
  this._bytes = bytes;
  this.length = bytes.length;
}
Buffer.prototype.toString = function (enc) {
  if (enc === 'base64') {
    var bin = '';
    for (var i = 0; i < this._bytes.length; i++) bin += String.fromCharCode(this._bytes[i]);
    return btoa(bin);
  }
  if (enc === 'hex') {
    var hex = '';
    for (var j = 0; j < this._bytes.length; j++) hex += ('0' + this._bytes[j].toString(16)).slice(-2);
    return hex;
  }
  var out = '';
  var chunk = 8192;
  for (var k = 0; k < this._bytes.length; k += chunk) {
    out += String.fromCharCode.apply(null, this._bytes.subarray(k, k + chunk));
  }
  return out;
};
Buffer.prototype.toJSON = function () { return { type: 'Buffer', data: Array.prototype.slice.call(this._bytes) }; };
Buffer.from = function (v, enc) { return new Buffer(v, enc); };
Buffer.alloc = function (n, fill) {
  var b = new Buffer(n);
  if (fill !== undefined) b._bytes.fill(typeof fill === 'string' ? fill.charCodeAt(0) : fill);
  return b;
};
Buffer.concat = function (list) {
  var total = 0;
  for (var i = 0; i < list.length; i++) total += list[i].length;
  var out = new Uint8Array(total);
  var offset = 0;
  for (var j = 0; j < list.length; j++) { out.set(list[j]._bytes, offset); offset += list[j].length; }
  return new Buffer(out);
};
Buffer.isBuffer = function (v) { return v instanceof Buffer; };
Buffer.byteLength = function (s) { return new Buffer(String(s)).length; };

/* ─── path ─── */
var path = {
  sep: '/',
  delimiter: ':',
  join: function () {
    var parts = Array.prototype.slice.call(arguments).filter(function (p) { return p !== '' && p !== undefined && p !== null; });
    return parts.join('/').replace(/\/{2,}/g, '/');
  },
  resolve: function () {
    var parts = Array.prototype.slice.call(arguments);
    var p = '';
    for (var i = 0; i < parts.length; i++) {
      if (parts[i] && String(parts[i]).charAt(0) === '/') { p = String(parts[i]); }
      else if (parts[i]) { p = p ? p + '/' + String(parts[i]) : String(parts[i]); }
    }
    return __normPath(p);
  },
  dirname: function (p) { var s = String(p).replace(/\/+${'$'}/, ''); var i = s.lastIndexOf('/'); return i < 0 ? '.' : (i === 0 ? '/' : s.slice(0, i)); },
  basename: function (p, ext) {
    var b = String(p).replace(/\/+${'$'}/, '').split('/').pop();
    if (ext && b.slice(-ext.length) === ext) return b.slice(0, -ext.length);
    return b;
  },
  extname: function (p) { var b = path.basename(p); var i = b.lastIndexOf('.'); return i <= 0 ? '' : b.slice(i); },
  relative: function (from, to) {
    var f = __normPath(from).split('/').filter(Boolean);
    var t = __normPath(to).split('/').filter(Boolean);
    var i = 0;
    while (i < f.length && i < t.length && f[i] === t[i]) i++;
    var up = [];
    for (var j = i; j < f.length; j++) up.push('..');
    return up.concat(t.slice(i)).join('/') || '.';
  },
  isAbsolute: function (p) { return String(p).charAt(0) === '/'; },
  normalize: function (p) { return __normPath(p); },
  parse: function (p) {
    var b = path.basename(p); var e = path.extname(p);
    return { root: '/', dir: path.dirname(p), base: b, ext: e, name: b.slice(0, b.length - e.length) };
  },
};
path.posix = path;

/* ─── fs ─── */
function __fsRead(p) {
  var res = __ocRpcSync('fsRead', { directory: __cwd, relPath: __relPath(p) });
  return res;
}
function __fsWrite(p, content, mode) {
  var payload = { directory: __cwd, relPath: __relPath(p) };
  if (content instanceof Buffer || content instanceof Uint8Array) payload.base64 = new Buffer(content).toString('base64');
  else payload.text = String(content);
  if (mode && mode !== 'utf8' && mode !== 'utf-8' && payload.text !== undefined) payload.base64 = new Buffer(payload.text).toString('base64');
  var res = __ocRpcSync('fsWrite', payload);
  return res.path || __normPath(p);
}
var fs = {
  readFileSync: function (p, enc) {
    var res = __fsRead(p);
    if (!res.exists) {
      var e = new Error("ENOENT: no such file or directory, open '" + p + "'");
      e.code = 'ENOENT';
      throw e;
    }
    if (enc === 'base64') return res.base64 || '';
    var bytes = new Buffer(res.base64 || '', 'base64');
    if (enc) return bytes.toString(enc);
    return bytes;
  },
  writeFileSync: function (p, content, enc) { __fsWrite(p, content, typeof enc === 'object' ? enc && enc.encoding : enc); },
  appendFileSync: function (p, content, enc) {
    var existing = '';
    try { existing = fs.readFileSync(p, 'utf8'); } catch (e) { existing = ''; }
    fs.writeFileSync(p, existing + (typeof content === 'string' ? content : new Buffer(content).toString()), enc);
  },
  existsSync: function (p) { try { return __fsRead(p).exists === true; } catch (e) { return false; } },
  mkdirSync: function (p, opts) {
    var recursive = opts && opts.recursive;
    var target = __normPath(p);
    __ocRpcSync('mkdir', { directory: __cwd, relPath: __relPath(p) });
    return recursive ? target : undefined;
  },
  readdirSync: function (p, opts) {
    var res = __ocRpcSync('fsList', { directory: __cwd, subPath: __relPath(p || '.') });
    var entries = res.entries || [];
    var withFileTypes = opts && opts.withFileTypes;
    return entries.map(function (e) {
      var name = e.path.split('/').pop();
      return withFileTypes ? { name: name, isDirectory: function () { return e.type === 'directory'; }, isFile: function () { return e.type === 'file'; } } : name;
    });
  },
  statSync: function (p) {
    var res = __fsRead(p);
    if (!res.exists) { var e = new Error("ENOENT: no such file or directory, stat '" + p + "'"); e.code = 'ENOENT'; throw e; }
    var isDir = false;
    try { var listing = __ocRpcSync('fsList', { directory: __cwd, subPath: __relPath(p) }); isDir = (listing.entries || []).length > 0 || /\/${'$'}/.test(String(p)); } catch (e) {}
    var size = res.base64 ? Math.floor((res.base64.length * 3) / 4) : 0;
    return { size: size, isDirectory: function () { return isDir; }, isFile: function () { return !isDir; }, mtimeMs: Date.now(), mtime: new Date() };
  },
  lstatSync: function (p) { return fs.statSync(p); },
  unlinkSync: function (p) { __ocRpcSync('fsDelete', { directory: __cwd, relPath: __relPath(p) }); },
  rmSync: function (p, opts) { __ocRpcSync('fsDelete', { directory: __cwd, relPath: __relPath(p) }); },
  rmdirSync: function (p) { __ocRpcSync('fsDelete', { directory: __cwd, relPath: __relPath(p) }); },
  copyFileSync: function (from, to) { fs.writeFileSync(to, fs.readFileSync(from)); },
  renameSync: function (from, to) { var data = fs.readFileSync(from); fs.writeFileSync(to, data); try { fs.unlinkSync(from); } catch (e) {} },
  readJSON: function (p) { return JSON.parse(fs.readFileSync(p, 'utf8')); },
  promises: {
    readFile: function (p, enc) { return Promise.resolve().then(function () { return fs.readFileSync(p, enc); }); },
    writeFile: function (p, c, enc) { return Promise.resolve().then(function () { return fs.writeFileSync(p, c, enc); }); },
    readdir: function (p, o) { return Promise.resolve().then(function () { return fs.readdirSync(p, o); }); },
    mkdir: function (p, o) { return Promise.resolve().then(function () { return fs.mkdirSync(p, o); }); },
    stat: function (p) { return Promise.resolve().then(function () { return fs.statSync(p); }); },
    unlink: function (p) { return Promise.resolve().then(function () { return fs.unlinkSync(p); }); },
    rm: function (p, o) { return Promise.resolve().then(function () { return fs.rmSync(p, o); }); },
    copyFile: function (a, b) { return Promise.resolve().then(function () { return fs.copyFileSync(a, b); }); },
    appendFile: function (p, c, e) { return Promise.resolve().then(function () { return fs.appendFileSync(p, c, e); }); },
  },
};
Object.defineProperty(fs, 'constants', { value: { F_OK: 0, R_OK: 4, W_OK: 2, X_OK: 1 }, enumerable: false });

/* ─── os / util / events / crypto ─── */
var os = {
  platform: function () { return 'android'; },
  arch: function () { return 'arm64'; },
  type: function () { return 'Linux'; },
  release: function () { return 'android'; },
  homedir: function () { return __ocRpcSync('environmentInfo', {}).home || '/data'; },
  tmpdir: function () { return '/data/local/tmp'; },
  cpus: function () { return [{ model: 'Android', speed: 2000 }]; },
  totalmem: function () { return 4 * 1024 * 1024 * 1024; },
  freemem: function () { return 1024 * 1024 * 1024; },
  hostname: function () { return 'android'; },
  EOL: '\n',
};
var util = {
  format: function () { return Array.prototype.slice.call(arguments).map(function (a) { return typeof a === 'string' ? a : util.inspect(a); }).join(' '); },
  inspect: function (v) { try { return JSON.stringify(v, null, 2); } catch (e) { return String(v); } },
  promisify: function (fn) { return function () { var args = Array.prototype.slice.call(arguments); return new Promise(function (res, rej) { args.push(function (e, v) { e ? rej(e) : res(v); }); fn.apply(null, args); }); }; },
  isDeepStrictEqual: function (a, b) { return JSON.stringify(a) === JSON.stringify(b); },
};
function EventEmitter() { this._events = {}; }
EventEmitter.prototype.on = function (name, fn) { (this._events[name] = this._events[name] || []).push(fn); return this; };
EventEmitter.prototype.addListener = EventEmitter.prototype.on;
EventEmitter.prototype.once = function (name, fn) { var self = this; function w() { self.off(name, w); fn.apply(null, arguments); } return this.on(name, w); };
EventEmitter.prototype.off = function (name, fn) { this._events[name] = (this._events[name] || []).filter(function (f) { return f !== fn; }); return this; };
EventEmitter.prototype.removeListener = EventEmitter.prototype.off;
EventEmitter.prototype.emit = function (name) { var args = Array.prototype.slice.call(arguments, 1); (this._events[name] || []).forEach(function (fn) { fn.apply(null, args); }); return true; };
var crypto = {
  randomUUID: function () {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) { var r = (Math.random() * 16) | 0; return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16); });
  },
  randomBytes: function (n) { var b = new Buffer(n); (window.crypto || {}).getRandomValues && window.crypto.getRandomValues(b._bytes); return b; },
};

/* ─── process ─── */
var argvFull = [__filename].concat(window.__ocArgv || []);
var process = {
  platform: 'android',
  arch: 'arm64',
  version: 'v22.11.0',
  versions: { node: '22.11.0' },
  env: Object.assign({}, window.__ocEnv || {}),
  argv: argvFull,
  argv0: 'node',
  execPath: '/system/bin/node',
  pid: 1,
  exitCode: 0,
  cwd: function () { return __cwd; },
  chdir: function (p) { __cwd = __normPath(p); },
  hrtime: function (prev) {
    var ms = performance.now();
    var s = Math.floor(ms / 1000); var ns = Math.floor((ms % 1000) * 1e6);
    if (prev) return [s - prev[0], ns - prev[1]];
    return [s, ns];
  },
  uptime: function () { return performance.now() / 1000; },
  memoryUsage: function () { return { rss: 50 * 1024 * 1024, heapTotal: 20 * 1024 * 1024, heapUsed: 10 * 1024 * 1024 }; },
  exit: function (code) { var e = new Error('process.exit'); e.__ocExit = code || 0; throw e; },
  abort: function () { var e = new Error('process.abort'); e.__ocExit = 134; throw e; },
  on: function () { return process; },
  once: function () { return process; },
  nextTick: function (fn) { Promise.resolve().then(fn); },
  stdout: {
    write: function (s) { if (window.__ocStdoutCollector) window.__ocStdoutCollector(s); else __writeOut(s); return true; },
    isTTY: false,
    columns: 100,
  },
  stderr: {
    write: function (s) { if (window.__ocStderrCollector) window.__ocStderrCollector(s); else __writeErr(s); return true; },
    isTTY: false,
  },
};

/* ─── child_process ─── */
function __runShell(command, opts) {
  var dir = opts && opts.cwd ? __normPath(opts.cwd) : __cwd;
  var res = __ocRpcSync('execShell', { directory: dir, command: String(command), timeoutMs: (opts && opts.timeout) || 120000 });
  return { stdout: res.stdout || '', stderr: res.stderr || '', status: res.exitCode || 0, signal: null };
}
var child_process = {
  execSync: function (command, opts) {
    var r = __runShell(command, opts);
    if (opts && opts.encoding === 'buffer') return new Buffer(r.stdout);
    if (r.status !== 0 && !(opts && opts.ignoreErrors)) {
      var e = new Error('Command failed: ' + command + '\n' + (r.stderr || ''));
      e.status = r.status; e.stdout = r.stdout; e.stderr = r.stderr;
      throw e;
    }
    return r.stdout;
  },
  execFileSync: function (file, args, opts) { return child_process.execSync([file].concat(args || []).join(' '), opts); },
  spawnSync: function (file, args, opts) {
    var r = __runShell([file].concat(args || []).join(' '), opts);
    return { stdout: new Buffer(r.stdout), stderr: new Buffer(r.stderr), status: r.status, pid: 1 };
  },
  exec: function (command, opts, cb) {
    if (typeof opts === 'function') { cb = opts; opts = {}; }
    __ocRpcAsync('execShell', { directory: opts && opts.cwd ? __normPath(opts.cwd) : __cwd, command: String(command), timeoutMs: (opts && opts.timeout) || 120000 })
      .then(function (r) {
        var err = (r.exitCode || 0) !== 0 ? Object.assign(new Error('Command failed: ' + command), { code: r.exitCode, stdout: r.stdout, stderr: r.stderr }) : null;
        cb && cb(err, r.stdout, r.stderr);
      })
      .catch(function (e) { cb && cb(e, '', String(e)); });
    return { pid: 1, kill: function () {} };
  },
  execFile: function (file, args, opts, cb) {
    if (typeof args === 'function') { cb = args; args = []; opts = {}; }
    if (typeof opts === 'function') { cb = opts; opts = {}; }
    child_process.exec([file].concat(args || []).join(' '), opts, cb);
    return { pid: 1, kill: function () {} };
  },
  spawn: function (file, args) {
    var r = __runShell([file].concat(args || []).join(' '));
    var listeners = {};
    var stdout = new EventEmitter(); stdout.setEncoding = function () {}; stdout.pause = function () {}; stdout.resume = function () {};
    var stderr = new EventEmitter(); stderr.setEncoding = function () {}; stderr.pause = function () {}; stderr.resume = function () {};
    var proc = new EventEmitter();
    proc.stdout = stdout; proc.stderr = stderr; proc.pid = 1; proc.kill = function () {};
    setTimeout(function () {
      if (r.stdout) { stdout.emit('data', r.stdout); listeners.data && listeners.data(r.stdout); }
      if (r.stderr) { stderr.emit('data', r.stderr); }
      proc.emit('close', r.status);
      proc.emit('exit', r.status);
    }, 0);
    return proc;
  },
};

/* ─── fetch (through the native daemon so CORS never blocks CLI scripts) ─── */
function __makeResponse(res) {
  var text = res.body || '';
  var headersObj = {};
  return {
    ok: res.status >= 200 && res.status < 300,
    status: res.status,
    statusText: '',
    headers: { get: function (k) { return k && k.toLowerCase() === 'content-type' ? (res.contentType || 'application/json') : null; }, has: function (k) { return String(k).toLowerCase() === 'content-type'; } },
    text: function () { return Promise.resolve(text); },
    json: function () { return Promise.resolve(JSON.parse(text)); },
    arrayBuffer: function () { return Promise.resolve(new Buffer(text).buffer || new Buffer(text)._bytes.buffer); },
    clone: function () { return __makeResponse(res); },
    bodyUsed: false,
  };
}
function __fetch(url, init) {
  init = init || {};
  var headers = {};
  var h = init.headers || {};
  if (h.forEach) h.forEach(function (v, k) { headers[k] = v; });
  else Object.keys(h).forEach(function (k) { headers[k] = h[k]; });
  return __ocRpcAsync('httpRequest', {
    url: String(url),
    method: (init.method || 'GET').toUpperCase(),
    headers: headers,
    body: typeof init.body === 'string' ? init.body : (init.body === undefined || init.body === null ? null : String(init.body)),
  }).then(__makeResponse);
}

/* ─── require ─── */
var __moduleCache = {};
function __resolveLocal(name) {
  var base = name.charAt(0) === '/' ? name : path.join(__dirname, name);
  var candidates = [base, base + '.js', base + '.mjs', base + '.cjs', base + '/index.js'];
  for (var i = 0; i < candidates.length; i++) {
    try { if (fs.existsSync(candidates[i])) return candidates[i]; } catch (e) {}
  }
  return null;
}
function require(name) {
  var clean = String(name).replace(/^node:/, '');
  if (clean === 'fs') return fs;
  if (clean === 'path') return path;
  if (clean === 'os') return os;
  if (clean === 'util') return util;
  if (clean === 'crypto') return crypto;
  if (clean === 'process') return process;
  if (clean === 'events') return { EventEmitter: EventEmitter };
  if (clean === 'child_process') return child_process;
  if (clean === 'buffer') return { Buffer: Buffer };
  if (clean === 'url') return { URL: URL, URLSearchParams: URLSearchParams };
  if (clean === 'assert') return { ok: function (v, m) { if (!v) throw new Error(m || 'Assertion failed'); }, equal: function (a, b, m) { if (a != b) throw new Error(m || 'Assertion failed'); }, strictEqual: function (a, b, m) { if (a !== b) throw new Error(m || 'Assertion failed'); } };
  if (clean === 'querystring') return { stringify: function (o) { return new URLSearchParams(o).toString(); }, parse: function (s) { var out = {}; new URLSearchParams(s).forEach(function (v, k) { out[k] = v; }); return out; } };
  var resolved = __resolveLocal(name);
  if (resolved) {
    if (__moduleCache[resolved]) return __moduleCache[resolved].exports;
    var src = fs.readFileSync(resolved, 'utf8');
    var mod = { exports: {} };
    __moduleCache[resolved] = mod;
    var fn = new Function('exports', 'require', 'module', '__filename', '__dirname', 'console', 'process', 'Buffer', src + '\n;return module.exports;');
    fn(mod.exports, require, mod, resolved, path.dirname(resolved), window.__ocConsole, process, Buffer);
    return __moduleCache[resolved].exports;
  }
  throw new Error("Cannot find module '" + name + "' (portable OpenCode runtime provides fs, path, os, util, crypto, process, events, child_process, buffer, url, assert, querystring and local files)");
}
var module = { exports: {} };
var exports = module.exports;

var console = window.__ocConsole;

function __transpile(code) {
  var out = String(code);
  out = out.replace(/^import\s+([\s\S]*?)\s+from\s+(['"])([^'"]+)\2;?/gm, function (m, what, q, from) {
    var spec = JSON.stringify(from);
    if (/^\*\s+as\s+/.test(what)) return 'var ' + what.replace(/^\*\s+as\s+/, '') + ' = require(' + spec + ');';
    if (what.charAt(0) === '{') return 'var ' + what + ' = require(' + spec + ');';
    var parts = what.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    if (parts.length === 1) return 'var ' + parts[0] + ' = require(' + spec + ');';
    var defaultName = parts[0];
    var rest = parts.slice(1).join(', ');
    return 'var __m = require(' + spec + '); var ' + defaultName + ' = (__m && __m.default) ? __m.default : __m;' + (rest ? ' var ' + rest + ' = __m;' : '');
  });
  out = out.replace(/^import\s+(['"])([^'"]+)\1;?/gm, function (m, q, target) { return 'require(' + q + target + q + ');'; });
  out = out.replace(/^export\s+default\s+/gm, 'module.exports.default = module.exports = ');
  out = out.replace(/^export\s+(const|let|var|function|class)\s+/gm, function (m, kw) { return kw + ' '; });
  out = out.replace(/^export\s*\{([^}]*)\};?/gm, function (m, names) {
    return names.split(',').map(function (n) { n = n.trim(); if (!n) return ''; var as = n.split(/\s+as\s+/); return 'module.exports.' + (as[1] || as[0]) + ' = ' + as[0] + ';'; }).join('\n');
  });
  return out;
}

async function __ocRun(codeText) {
  var __exit = 0;
  var collectedFiles = [];
  var AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  try {
    var body = __transpile(codeText);
    var fn = new AsyncFunction('exports', 'require', 'module', '__filename', '__dirname', 'console', 'process', 'Buffer', 'fetch', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval', body + '\n;');
    await fn(module.exports, require, module, __filename, __dirname, console, process, Buffer, __fetch, setTimeout, setInterval, clearTimeout, clearInterval);
    await new Promise(function (r) { setTimeout(r, 0); });
    return JSON.stringify({ ok: true, stdout: __outBuf.join('\n') + (__outBuf.length ? '\n' : ''), stderr: __errBuf.join('\n') + (__errBuf.length ? '\n' : ''), exitCode: 0, error: '' });
  } catch (e) {
    if (e && typeof e === 'object' && '__ocExit' in e) {
      return JSON.stringify({ ok: true, stdout: __outBuf.join('\n'), stderr: __errBuf.join('\n'), exitCode: e.__ocExit || 0, error: '' });
    }
    var message = (e && (e.stack || e.message)) || String(e);
    return JSON.stringify({ ok: false, stdout: __outBuf.join('\n'), stderr: __errBuf.join('\n') + (__errBuf.length ? '\n' : '') + String(message), exitCode: (e && e.status) || 1, error: String((e && e.message) || e) });
  }
}

/* expose collectors used by the injected entry bootstrap */
window.__ocConsole = {
  log: function () { __outBuf.push(Array.prototype.map.call(arguments, function (a) { return typeof a === 'string' ? a : (function () { try { return JSON.stringify(a); } catch (e) { return String(a); } })(); }).join(' ')); },
  info: function () { window.__ocConsole.log.apply(null, arguments); },
  debug: function () { window.__ocConsole.log.apply(null, arguments); },
  warn: function () { __errBuf.push(Array.prototype.map.call(arguments, function (a) { return typeof a === 'string' ? a : String(a); }).join(' ')); },
  error: function () { window.__ocConsole.warn.apply(null, arguments); },
  table: function (v) { window.__ocConsole.log(v); },
  dir: function (v) { window.__ocConsole.log(v); },
  trace: function () { window.__ocConsole.warn(Array.prototype.join.call(arguments, ' ')); },
};
var console = window.__ocConsole;
        """.trimIndent()
    }
}
