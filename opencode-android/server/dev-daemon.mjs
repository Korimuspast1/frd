#!/usr/bin/env node
/**
 * OpenCode Android v2.2.5 — Live Preview & Local Reference Server
 * Serves the literal compiled upstream `anomalyco/opencode` (`@opencode/app`) UI
 * backed by `OpenCodeV2Engine` (100% OpenCode v2.2.5 HTTP + SSE + Persistent PTY WebSocket).
 */

import http from "node:http"
import crypto from "node:crypto"
import fs from "node:fs"
import fsp from "node:fs/promises"
import path from "node:path"
import os from "node:os"
import { execFile, exec } from "node:child_process"
import { promisify } from "node:util"
import { fileURLToPath } from "node:url"
import { OpenCodeV2Engine } from "./opencode-v2-engine.mjs"

const execAsync = promisify(exec)
const execFileAsync = promisify(execFile)

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PORT = Number(process.env.PORT || 4096)
const HOST = process.env.HOST || "0.0.0.0"

const STATE_ROOT = process.env.OPENCODE_ANDROID_ROOT || "/tmp/opencode-android-runtime"
const WORKSPACES_ROOT = path.join(STATE_ROOT, "workspaces")
const KV_FILE = path.join(STATE_ROOT, "kv-store.json")

const STATIC_CANDIDATES = [
  process.env.OPENCODE_WEB_DIST,
  "/tmp/opencode-ref/packages/app/dist",
  path.resolve(__dirname, "../dist"),
].filter(Boolean)

function resolveStaticRoot() {
  for (const candidate of STATIC_CANDIDATES) {
    if (candidate && fs.existsSync(path.join(candidate, "index.html"))) {
      return candidate
    }
  }
  return path.resolve(__dirname, "../dist")
}

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".wasm": "application/wasm",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".aac": "audio/aac",
  ".mp3": "audio/mpeg",
}

fs.mkdirSync(WORKSPACES_ROOT, { recursive: true })

let kvCache = {}
try {
  if (fs.existsSync(KV_FILE)) {
    kvCache = JSON.parse(fs.readFileSync(KV_FILE, "utf8"))
  }
} catch {
  kvCache = {}
}
function saveKv() {
  try {
    fs.writeFileSync(KV_FILE, JSON.stringify(kvCache, null, 2), "utf8")
  } catch {
    // ignore
  }
}

async function ensureSampleWorkspace() {
  const sampleDir = path.join(WORKSPACES_ROOT, "opencode-demo-app")
  if (!fs.existsSync(sampleDir)) {
    fs.mkdirSync(path.join(sampleDir, "src"), { recursive: true })
    fs.writeFileSync(
      path.join(sampleDir, "README.md"),
      [
        "# OpenCode Android Local Project",
        "",
        "Welcome to **OpenCode v2.2.5** running with the literal upstream `anomalyco/opencode` UI!",
        "",
        "## Quick Start",
        "1. Click **Connect provider** or **Settings -> Providers -> + Custom Provider**.",
        "2. Enter any OpenAI-compatible or Anthropic-compatible Base URL & API key — `/v1/models` are discovered automatically.",
        "3. Ask the `build` or `plan` agent to inspect, create, edit, or refactor files, or open the Ghostty terminal.",
        "",
      ].join("\n"),
      "utf8",
    )
    fs.writeFileSync(
      path.join(sampleDir, "package.json"),
      JSON.stringify(
        {
          name: "opencode-demo-app",
          version: "1.0.0",
          type: "module",
          scripts: {
            start: "node src/index.js",
            test: "node --test",
          },
        },
        null,
        2,
      ) + "\n",
      "utf8",
    )
    fs.writeFileSync(
      path.join(sampleDir, "src/index.js"),
      [
        "export function greet(name = 'OpenCode Android') {",
        "  return `Hello from ${name} v2.2.5!`;",
        "}",
        "",
        "if (import.meta.url === `file://${process.argv[1]}`) {",
        "  console.log(greet());",
        "}",
        "",
      ].join("\n"),
      "utf8",
    )
    try {
      await execAsync(
        'git init -b main && git config user.email "dev@opencode.local" && git config user.name "OpenCode" && git add -A && git commit -m "Initial workspace"',
        { cwd: sampleDir },
      )
    } catch {
      // ignore git init errors
    }
  }
  return sampleDir
}

const defaultWorkspace = await ensureSampleWorkspace()

// ── Persistent registry of arbitrary device directories opened as projects ──
const PROJECT_REGISTRY = path.join(STATE_ROOT, "custom-projects.json")

async function readProjectRegistry() {
  try {
    const raw = await fsp.readFile(PROJECT_REGISTRY, "utf8")
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((p) => p && typeof p.directory === "string") : []
  } catch {
    return []
  }
}

async function writeProjectRegistry(entries) {
  await fsp.mkdir(STATE_ROOT, { recursive: true })
  await fsp.writeFile(PROJECT_REGISTRY, JSON.stringify(entries, null, 2) + "\n")
}

async function registerProjectDir(directory, name) {
  const resolved = path.resolve(
    String(directory).replace(/^\/sdcard\//, "/storage/emulated/0/").replace(/^~\/?/, `${os.homedir()}/`),
  )
  await fsp.mkdir(resolved, { recursive: true }).catch(() => undefined)
  const entries = await readProjectRegistry()
  const existing = entries.find((entry) => entry.directory === resolved)
  const now = Date.now()
  const record = {
    directory: resolved,
    name: name || existing?.name || path.basename(resolved) || "workspace",
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  }
  const next = [record, ...entries.filter((entry) => entry.directory !== resolved)]
  await writeProjectRegistry(next)
  return record
}

const IGNORED_DIRS = new Set([".git", "node_modules", ".next", "dist", "build", "__pycache__"])

async function walkDirectory(dir, baseDir, out = [], limit = 2000) {
  if (out.length >= limit) return out
  let entries = []
  try {
    entries = await fsp.readdir(dir, { withFileTypes: true })
  } catch {
    return out
  }
  for (const entry of entries) {
    if (out.length >= limit) break
    if (IGNORED_DIRS.has(entry.name)) continue
    const full = path.join(dir, entry.name)
    const rel = path.relative(baseDir, full).split(path.sep).join("/")
    if (entry.isDirectory()) {
      out.push({ path: rel, type: "directory" })
      await walkDirectory(full, baseDir, out, limit)
    } else if (entry.isFile()) {
      out.push({ path: rel, type: "file" })
    }
  }
  return out
}

/** @type {import('../src/engine/opencode-v2-engine').OpenCodeHostAdapter} */
const hostAdapter = {
  platform: "node",

  async getDefaultRoot() {
    return defaultWorkspace
  },

  async loadState(key) {
    const val = kvCache[key]
    return typeof val === "string" ? val : val != null ? JSON.stringify(val) : null
  },
  async saveState(key, value) {
    kvCache[key] = value
    saveKv()
  },

  async listProjects() {
    const entries = await fsp.readdir(WORKSPACES_ROOT, { withFileTypes: true }).catch(() => [])
    const out = []
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const full = path.join(WORKSPACES_ROOT, entry.name)
      const stat = await fsp.stat(full).catch(() => null)
      const now = Date.now()
      const createdAt = stat && Number.isFinite(stat.birthtimeMs) && stat.birthtimeMs > 0 ? Math.floor(stat.birthtimeMs) : now
      const updatedAt = stat && Number.isFinite(stat.mtimeMs) && stat.mtimeMs > 0 ? Math.floor(stat.mtimeMs) : now
      out.push({
        id: entry.name,
        name: entry.name,
        directory: full,
        createdAt,
        updatedAt,
      })
    }
    const registry = await readProjectRegistry()
    for (const entry of registry) {
      if (out.some((p) => p.directory === entry.directory)) continue
      out.push({
        id: `ext-${entry.name}`,
        name: entry.name,
        directory: entry.directory,
        createdAt: entry.createdAt,
        updatedAt: entry.updatedAt,
      })
    }
    return out.sort((a, b) => b.updatedAt - a.updatedAt)
  },

  async registerProject(directory, name) {
    const record = await registerProjectDir(directory, name)
    return { id: `ext-${record.name}`, name: record.name, directory: record.directory, createdAt: record.createdAt, updatedAt: record.updatedAt }
  },

  async environmentInfo() {
    return { platform: "node", home: os.homedir(), cwd: process.cwd(), tools: "bash sh curl wget git jq zip unzip tree node npm python3" }
  },

  async createProject(input) {
    const rawName = typeof input === "string" ? input : input?.name || `project-${Date.now()}`
    const template = typeof input === "object" && input?.template ? input.template : "blank"
    const clean = rawName.trim().replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || `project-${Date.now()}`
    const full = (typeof input === "object" && input?.directory) || path.join(WORKSPACES_ROOT, clean)
    await fsp.mkdir(full, { recursive: true })
    if (template === "node" || template === "node-ts") {
      await fsp.mkdir(path.join(full, "src"), { recursive: true })
      await fsp.writeFile(
        path.join(full, "package.json"),
        JSON.stringify({ name: clean, version: "0.1.0", type: "module", scripts: { start: "node src/index.js" } }, null, 2) + "\n",
      )
      await fsp.writeFile(path.join(full, "src/index.js"), `console.log("Hello from ${clean}!");\n`)
    } else if (template === "python") {
      await fsp.writeFile(path.join(full, "main.py"), `def main():\n    print("Hello from ${clean}!")\n\nif __name__ == "__main__":\n    main()\n`)
    } else if (template === "web" || template === "html") {
      await fsp.writeFile(
        path.join(full, "index.html"),
        `<!doctype html>\n<html><head><meta charset="utf-8"><title>${clean}</title></head><body><h1>${clean}</h1></body></html>\n`,
      )
    }
    if (!fs.existsSync(path.join(full, "README.md"))) {
      await fsp.writeFile(path.join(full, "README.md"), `# ${clean}\n\nCreated in OpenCode Android.\n`)
    }
    try {
      await execAsync(
        'git init -b main && git config user.email "dev@opencode.local" && git config user.name "OpenCode" && git add -A && git commit -m "Initial commit"',
        { cwd: full },
      )
    } catch {
      // ignore
    }
    const now = Date.now()
    return {
      id: clean,
      name: clean,
      directory: full,
      createdAt: now,
      updatedAt: now,
    }
  },

  async deleteProject(directory) {
    if (directory && directory.startsWith(WORKSPACES_ROOT)) {
      await fsp.rm(directory, { recursive: true, force: true })
    }
  },

  async fsList(directory, subPath = "") {
    const target = subPath ? path.resolve(directory, subPath) : directory
    const entries = await fsp.readdir(target, { withFileTypes: true }).catch(() => [])
    const nodes = []
    for (const entry of entries) {
      if (entry.name === ".git") continue
      const full = path.join(target, entry.name)
      const rel = path.relative(directory, full).split(path.sep).join("/")
      nodes.push({
        path: rel,
        type: entry.isDirectory() ? "directory" : "file",
      })
    }
    return nodes.sort((a, b) => (a.type === b.type ? a.path.localeCompare(b.path) : a.type === "directory" ? -1 : 1))
  },

  async fsFind(directory, query, type, limit = 100) {
    const all = await walkDirectory(directory, directory, [], 2500)
    const q = (query || "").toLowerCase()
    const matches = []
    for (const item of all) {
      if (type && item.type !== type) continue
      if (!q || item.path.toLowerCase().includes(q)) {
        matches.push(item)
        if (matches.length >= limit) break
      }
    }
    return matches
  },

  async fsRead(directory, relPath) {
    const full = path.isAbsolute(relPath) ? relPath : path.resolve(directory, relPath)
    if (!fs.existsSync(full) || fs.statSync(full).isDirectory()) {
      return { exists: false }
    }
    const buf = await fsp.readFile(full)
    const ext = path.extname(full).toLowerCase()
    const mime = MIME_TYPES[ext] || "text/plain; charset=utf-8"
    let hasNull = false
    const checkLen = Math.min(buf.length, 1024)
    for (let i = 0; i < checkLen; i++) {
      if (buf[i] === 0) {
        hasNull = true
        break
      }
    }
    return {
      exists: true,
      bytes: new Uint8Array(buf),
      text: hasNull ? undefined : buf.toString("utf8"),
      mime: hasNull && !MIME_TYPES[ext] ? "application/octet-stream" : mime,
    }
  },

  async fsWrite(directory, relPath, content) {
    const full = path.isAbsolute(relPath) ? relPath : path.resolve(directory, relPath)
    await fsp.mkdir(path.dirname(full), { recursive: true })
    if (typeof content === "string") {
      await fsp.writeFile(full, content, "utf8")
    } else {
      await fsp.writeFile(full, Buffer.from(content))
    }
    return { path: full }
  },

  async fsDelete(directory, relPath) {
    const full = path.isAbsolute(relPath) ? relPath : path.resolve(directory, relPath)
    if (!fs.existsSync(full)) return false
    await fsp.rm(full, { recursive: true, force: true })
    return true
  },

  async fsGrep(directory, pattern, _include, limit = 80) {
    const all = await walkDirectory(directory, directory, [], 1500)
    const hits = []
    let regex = null
    try {
      regex = new RegExp(pattern, "i")
    } catch {
      regex = null
    }
    for (const item of all) {
      if (item.type !== "file") continue
      const full = path.join(directory, item.path)
      const stat = await fsp.stat(full).catch(() => null)
      if (!stat || stat.size > 512 * 1024) continue
      const text = await fsp.readFile(full, "utf8").catch(() => null)
      if (!text) continue
      const lines = text.split("\n")
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        const matched = regex ? regex.test(line) : line.toLowerCase().includes(pattern.toLowerCase())
        if (matched) {
          hits.push({
            path: item.path,
            line: i + 1,
            text: line.slice(0, 300),
          })
          if (hits.length >= limit) return hits
        }
      }
    }
    return hits
  },

  async execShell(directory, command, timeoutMs = 120000) {
    const start = Date.now()
    return new Promise((resolve) => {
      exec(
        command,
        {
          cwd: directory && fs.existsSync(directory) ? directory : defaultWorkspace,
          timeout: timeoutMs,
          maxBuffer: 8 * 1024 * 1024,
          shell: process.env.OPENCODE_SHELL || "/bin/bash",
          env: { ...process.env, OPENCODE: "1", OPENCODE_PLATFORM: "web" },
        },
        (error, stdout, stderr) => {
          const code = error && typeof error.code === "number" ? error.code : error ? 1 : 0
          resolve({
            stdout: stdout || "",
            stderr: stderr || (error && !stderr ? String(error.message || "") : ""),
            exitCode: code,
            durationMs: Date.now() - start,
          })
        },
      )
    })
  },

  async httpFetch(url, init) {
    return globalThis.fetch(url, init)
  },
}

const engine = new OpenCodeV2Engine(hostAdapter)

// Minimal RFC 6455 WebSocket helper for Persistent PTY (/api/experimental/persistent-pty/:ptyID/connect)
function encodeWsFrame(payload, opcode = 0x01) {
  const data = typeof payload === "string" ? Buffer.from(payload, "utf8") : Buffer.from(payload)
  const len = data.length
  let header
  if (len < 126) {
    header = Buffer.alloc(2)
    header[0] = 0x80 | opcode
    header[1] = len
  } else if (len < 65536) {
    header = Buffer.alloc(4)
    header[0] = 0x80 | opcode
    header[1] = 126
    header.writeUInt16BE(len, 2)
  } else {
    header = Buffer.alloc(10)
    header[0] = 0x80 | opcode
    header[1] = 127
    header.writeBigUInt64BE(BigInt(len), 2)
  }
  return Buffer.concat([header, data])
}

function attachPtyWebSocket(req, socket, head, ptyID) {
  const key = req.headers["sec-websocket-key"]
  if (!key) {
    socket.destroy()
    return
  }
  const accept = crypto
    .createHash("sha1")
    .update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    .digest("base64")

  socket.write(
    [
      "HTTP/1.1 101 Switching Protocols",
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Accept: ${accept}`,
      "\r\n",
    ].join("\r\n"),
  )

  const sendText = (obj) => {
    if (!socket.destroyed) socket.write(encodeWsFrame(JSON.stringify(obj), 0x01))
  }
  const sendBinary = (bytes) => {
    if (!socket.destroyed) socket.write(encodeWsFrame(bytes, 0x02))
  }

  sendText({
    type: "attached",
    inputProtocol: 1,
    info: { size: { cols: 100, rows: 30 } },
    role: "controller",
  })
  const replay = engine.getPtyReplayBytes(ptyID)
  if (replay.byteLength > 0) {
    sendBinary(replay)
  }
  sendText({ type: "replay_complete" })

  const unsub = engine.subscribePtyOutput(ptyID, (bytes) => sendBinary(bytes))

  let buffer = head && head.length ? Buffer.from(head) : Buffer.alloc(0)
  let lineBuffer = ""

  const handleIncomingFrame = (opcode, payload) => {
    if (opcode === 0x08) {
      socket.end(encodeWsFrame(Buffer.alloc(0), 0x08))
      return
    }
    if (opcode === 0x09) {
      socket.write(encodeWsFrame(payload, 0x0a))
      return
    }
    if (opcode === 0x02 && payload.length >= 5) {
      const hasData = payload[0] === 1
      if (!hasData) return
      const text = payload.subarray(5).toString("utf8")
      for (const ch of text) {
        if (ch === "\r" || ch === "\n") {
          sendBinary(Buffer.from("\r\n", "utf8"))
          const cmd = lineBuffer.trim()
          lineBuffer = ""
          void engine.writePtyInput(ptyID, cmd + "\n")
        } else if (ch === "\u007f" || ch === "\b") {
          if (lineBuffer.length > 0) {
            lineBuffer = lineBuffer.slice(0, -1)
            sendBinary(Buffer.from("\b \b", "utf8"))
          }
        } else if (ch === "\u0003") {
          lineBuffer = ""
          sendBinary(Buffer.from("^C\r\n$ ", "utf8"))
        } else {
          lineBuffer += ch
          sendBinary(Buffer.from(ch, "utf8"))
        }
      }
    } else if (opcode === 0x01) {
      const str = payload.toString("utf8")
      try {
        const parsed = JSON.parse(str)
        if (parsed?.type === "ping") sendText({ type: "pong" })
      } catch {
        void engine.writePtyInput(ptyID, str)
      }
    }
  }

  const parseFrames = () => {
    while (buffer.length >= 2) {
      const byte0 = buffer[0]
      const byte1 = buffer[1]
      const opcode = byte0 & 0x0f
      const masked = (byte1 & 0x80) !== 0
      let len = byte1 & 0x7f
      let offset = 2
      if (len === 126) {
        if (buffer.length < 4) return
        len = buffer.readUInt16BE(2)
        offset = 4
      } else if (len === 127) {
        if (buffer.length < 10) return
        len = Number(buffer.readBigUInt64BE(2))
        offset = 10
      }
      const maskLen = masked ? 4 : 0
      if (buffer.length < offset + maskLen + len) return
      const mask = masked ? buffer.subarray(offset, offset + 4) : null
      offset += maskLen
      const payload = Buffer.from(buffer.subarray(offset, offset + len))
      if (mask) {
        for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i & 3]
      }
      buffer = buffer.subarray(offset + len)
      handleIncomingFrame(opcode, payload)
    }
  }

  if (buffer.length > 0) parseFrames()
  socket.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk])
    parseFrames()
  })
  socket.on("close", () => unsub())
  socket.on("error", () => unsub())
}

const server = http.createServer(async (req, res) => {
  try {
    const reqUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`)

    // CORS & iframe-friendly headers for Live Preview
    res.setHeader("Access-Control-Allow-Origin", "*")
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
    res.setHeader("Access-Control-Allow-Headers", "*")
    if (req.method === "OPTIONS") {
      res.writeHead(204)
      res.end()
      return
    }

    if (reqUrl.pathname.startsWith("/api/")) {
      const chunks = []
      for await (const chunk of req) chunks.push(chunk)
      const bodyBuf = chunks.length > 0 ? Buffer.concat(chunks) : undefined

      const headers = new Headers()
      for (const [k, v] of Object.entries(req.headers)) {
        if (Array.isArray(v)) headers.set(k, v.join(", "))
        else if (typeof v === "string") headers.set(k, v)
      }

      const webReq = new Request(reqUrl.toString(), {
        method: req.method || "GET",
        headers,
        body: req.method === "GET" || req.method === "HEAD" ? undefined : bodyBuf,
      })

      const webRes = await engine.handle(webReq)
      res.statusCode = webRes.status
      webRes.headers.forEach((value, key) => {
        res.setHeader(key, value)
      })

      if (!webRes.body) {
        res.end()
        return
      }

      const reader = webRes.body.getReader()
      req.on("close", () => {
        void reader.cancel().catch(() => undefined)
      })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (res.writableEnded) break
        res.write(Buffer.from(value))
      }
      if (!res.writableEnded) res.end()
      return
    }

    // Serve compiled upstream @opencode/app static assets
    const staticRoot = resolveStaticRoot()
    let relPath = decodeURIComponent(reqUrl.pathname)
    if (relPath === "/") relPath = "/index.html"
    const candidate = path.resolve(staticRoot, "." + relPath)

    if (candidate.startsWith(staticRoot) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      const ext = path.extname(candidate).toLowerCase()
      res.setHeader("Content-Type", MIME_TYPES[ext] || "application/octet-stream")
      if (relPath.startsWith("/_assets/")) {
        res.setHeader("Cache-Control", "public, max-age=31536000, immutable")
      } else {
        res.setHeader("Cache-Control", "no-cache")
      }
      fs.createReadStream(candidate).pipe(res)
      return
    }

    // SPA fallback -> index.html
    const indexHtml = path.join(staticRoot, "index.html")
    if (fs.existsSync(indexHtml)) {
      res.setHeader("Content-Type", "text/html; charset=utf-8")
      res.setHeader("Cache-Control", "no-cache")
      fs.createReadStream(indexHtml).pipe(res)
      return
    }

    res.statusCode = 404
    res.end("OpenCode web bundle not found. Run npm run build:web first.")
  } catch (err) {
    if (!res.headersSent) res.statusCode = 500
    res.end(JSON.stringify({ error: err instanceof Error ? err.message : String(err) }))
  }
})

server.on("upgrade", (req, socket, head) => {
  try {
    const reqUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`)
    const m = reqUrl.pathname.match(/^\/api\/experimental\/persistent-pty\/([^/]+)\/connect$/)
    if (m) {
      attachPtyWebSocket(req, socket, head, decodeURIComponent(m[1]))
      return
    }
    socket.destroy()
  } catch {
    socket.destroy()
  }
})

server.listen(PORT, HOST, () => {
  console.log(`[OpenCode Android v2.2.5] Upstream Desktop/Mobile Server listening on http://${HOST}:${PORT}`)
  console.log(`[OpenCode Android v2.2.5] Static root: ${resolveStaticRoot()}`)
  console.log(`[OpenCode Android v2.2.5] Default workspace: ${defaultWorkspace}`)
})
