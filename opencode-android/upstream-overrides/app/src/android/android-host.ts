import { OpenCodeV2Engine, type OpenCodeHostAdapter, type ProjectRecord } from "./opencode-v2-engine"

declare global {
  interface Window {
    OpenCodeNative?: {
      getDaemonUrl?: () => string
      getRuntimeInfo?: () => string
      invokeAsync?: (requestJson: string, callbackId: string) => void
    }
    __ocNativeCallbacks?: Record<string, { resolve: (val: any) => void; reject: (err: Error) => void }>
    __ocNativeResolve?: (callbackId: string, responseJson: string) => void
  }
}

export function isAndroidNativeWebView(): boolean {
  if (typeof window === "undefined") return false
  return Boolean(window.OpenCodeNative) || window.location.hostname === "opencode.local"
}

function setupNativeBridgeCallbacks() {
  if (typeof window === "undefined") return
  if (!window.__ocNativeCallbacks) {
    window.__ocNativeCallbacks = {}
  }
  if (!window.__ocNativeResolve) {
    window.__ocNativeResolve = (callbackId: string, responseJson: string) => {
      const cb = window.__ocNativeCallbacks?.[callbackId]
      if (!cb) return
      delete window.__ocNativeCallbacks![callbackId]
      try {
        const parsed = JSON.parse(responseJson)
        if (parsed && parsed.__error) {
          cb.reject(new Error(String(parsed.__error)))
        } else {
          cb.resolve(parsed)
        }
      } catch (err: any) {
        cb.reject(err instanceof Error ? err : new Error(String(err)))
      }
    }
  }
}

async function callNativeRpc<T = any>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  setupNativeBridgeCallbacks()

  // Try background LocalHttpDaemon first if running
  const daemonUrl = window.OpenCodeNative?.getDaemonUrl?.() || ""
  if (daemonUrl.startsWith("http://127.0.0.1:")) {
    try {
      const res = await globalThis.fetch(`${daemonUrl}/__native/rpc`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, payload }),
      })
      if (res.ok) {
        const json = await res.json()
        if (json && json.__error) throw new Error(String(json.__error))
        return json as T
      }
    } catch {
      // Automatic zero-socket fallback to @JavascriptInterface async executor
    }
  }

  if (window.OpenCodeNative?.invokeAsync) {
    return new Promise<T>((resolve, reject) => {
      const cbId = `cb_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
      window.__ocNativeCallbacks![cbId] = { resolve, reject }
      try {
        window.OpenCodeNative!.invokeAsync!(JSON.stringify({ action, payload }), cbId)
      } catch (err: any) {
        delete window.__ocNativeCallbacks![cbId]
        reject(err instanceof Error ? err : new Error(String(err)))
      }
    })
  }

  throw new Error("Android Native Bridge is not available")
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

function bytesToBase64(bytes: Uint8Array): string {
  let bin = ""
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(bin)
}

export function createAndroidHostAdapter(): OpenCodeHostAdapter {
  return {
    platform: "android",

    async getDefaultRoot(): Promise<string> {
      const res = await callNativeRpc<{ root: string }>("getDefaultRoot")
      return res.root
    },

    async listProjects(): Promise<ProjectRecord[]> {
      const res = await callNativeRpc<{ projects: ProjectRecord[] }>("listProjects")
      return res.projects ?? []
    },

    async createProject(input): Promise<ProjectRecord> {
      const res = await callNativeRpc<{ project: ProjectRecord }>("createProject", input)
      return res.project
    },

    async deleteProject(directory: string): Promise<void> {
      await callNativeRpc("deleteProject", { directory })
    },

    async fsList(directory: string, subPath?: string) {
      const res = await callNativeRpc<{ entries: Array<{ path: string; type: "file" | "directory" }> }>("fsList", {
        directory,
        subPath,
      })
      return res.entries ?? []
    },

    async fsFind(directory: string, query: string, type?: "file" | "directory", limit?: number) {
      const res = await callNativeRpc<{ entries: Array<{ path: string; type: "file" | "directory" }> }>("fsFind", {
        directory,
        query,
        type,
        limit: limit ?? 100,
      })
      return res.entries ?? []
    },

    async fsRead(directory: string, relPath: string) {
      const res = await callNativeRpc<{
        exists: boolean
        text?: string
        base64?: string
        mime?: string
      }>("fsRead", { directory, relPath })
      if (!res.exists) return { exists: false }
      const bytes = res.base64 !== undefined ? base64ToBytes(res.base64) : new TextEncoder().encode(res.text ?? "")
      return {
        exists: true,
        text: res.text,
        bytes,
        mime: res.mime ?? "text/plain; charset=utf-8",
      }
    },

    async fsWrite(directory: string, relPath: string, content: Uint8Array | string) {
      const payload: Record<string, unknown> = { directory, relPath }
      if (typeof content === "string") {
        payload.text = content
      } else {
        payload.base64 = bytesToBase64(content)
      }
      const res = await callNativeRpc<{ path: string }>("fsWrite", payload)
      return { path: res.path }
    },

    async fsDelete(directory: string, relPath: string) {
      const res = await callNativeRpc<{ deleted: boolean }>("fsDelete", { directory, relPath })
      return Boolean(res.deleted)
    },

    async fsGrep(directory: string, pattern: string, include?: string, limit?: number) {
      const res = await callNativeRpc<{ matches: Array<{ path: string; line: number; text: string }> }>("fsGrep", {
        directory,
        pattern,
        include,
        limit: limit ?? 80,
      })
      return res.matches ?? []
    },

    async execShell(directory: string, command: string, timeoutMs?: number) {
      return callNativeRpc<{ stdout: string; stderr: string; exitCode: number; durationMs: number }>("execShell", {
        directory,
        command,
        timeoutMs: timeoutMs ?? 30000,
      })
    },

    async httpFetch(url: string, init?: RequestInit): Promise<Response> {
      const method = (init?.method ?? "GET").toUpperCase()
      const headersObj: Record<string, string> = {}
      if (init?.headers) {
        const h = new Headers(init.headers)
        h.forEach((v, k) => {
          headersObj[k] = v
        })
      }
      const bodyStr = typeof init?.body === "string" ? init.body : undefined

      // 1. Stream directly through background Kotlin LocalHttpDaemon (CORS-free real SSE streaming!)
      const daemonUrl = window.OpenCodeNative?.getDaemonUrl?.() || ""
      if (daemonUrl.startsWith("http://127.0.0.1:")) {
        try {
          const proxyRes = await globalThis.fetch(`${daemonUrl}/__native/http-proxy`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              url,
              method,
              headers: headersObj,
              body: bodyStr,
            }),
            signal: init?.signal ?? undefined,
          })
          const upstreamStatus = Number(proxyRes.headers.get("x-upstream-status") || proxyRes.status || 200)
          const upstreamType = proxyRes.headers.get("x-upstream-content-type") || proxyRes.headers.get("content-type") || "application/json"
          return new Response(proxyRes.body, {
            status: upstreamStatus,
            headers: { "Content-Type": upstreamType },
          })
        } catch (err: any) {
          if (init?.signal?.aborted) throw err
        }
      }

      // 2. Fallback to @JavascriptInterface background HTTP execution (never touches main thread, zero sockets needed)
      const fallback = await callNativeRpc<{
        status: number
        contentType: string
        body: string
      }>("httpRequest", {
        url,
        method,
        headers: headersObj,
        body: bodyStr,
      })
      return new Response(fallback.body ?? "", {
        status: fallback.status || 200,
        headers: { "Content-Type": fallback.contentType || "application/json" },
      })
    },

    async loadState(key: string): Promise<string | null> {
      try {
        const res = await callNativeRpc<{ value: string | null }>("loadState", { key })
        if (res.value !== null && res.value !== undefined) return res.value
      } catch {}
      try {
        return localStorage.getItem(key)
      } catch {
        return null
      }
    },

    async saveState(key: string, value: string): Promise<void> {
      try {
        localStorage.setItem(key, value)
      } catch {}
      try {
        await callNativeRpc("saveState", { key, value })
      } catch {}
    },
  }
}

let singletonEngine: OpenCodeV2Engine | null = null

export function getInAppAndroidEngine(): OpenCodeV2Engine {
  if (!singletonEngine) {
    singletonEngine = new OpenCodeV2Engine(createAndroidHostAdapter())
  }
  return singletonEngine
}

/**
 * Installs an in-app WebSocket shim ONLY for `/api/experimental/persistent-pty/:ptyID/connect`
 * when running inside Android WebView (`http://opencode.local`), so Ghostty WASM Terminal works
 * interactively without needing a separate native WebSocket server!
 */
export function installAndroidPtyWebSocketBridge(engine: OpenCodeV2Engine) {
  if (typeof window === "undefined" || !isAndroidNativeWebView()) return
  const NativeWebSocket = window.WebSocket
  if ((NativeWebSocket as any).__ocPatched) return

  class BridgedWebSocket extends EventTarget {
    static readonly CONNECTING = 0
    static readonly OPEN = 1
    static readonly CLOSING = 2
    static readonly CLOSED = 3
    readonly CONNECTING = 0
    readonly OPEN = 1
    readonly CLOSING = 2
    readonly CLOSED = 3

    url: string
    readyState = 0
    binaryType: BinaryType = "blob"
    protocol = ""
    extensions = ""
    bufferedAmount = 0
    onopen: ((ev: Event) => any) | null = null
    onmessage: ((ev: MessageEvent) => any) | null = null
    onerror: ((ev: Event) => any) | null = null
    onclose: ((ev: CloseEvent) => any) | null = null

    private realSocket: WebSocket | null = null
    private ptyID: string | null = null

    constructor(url: string | URL, protocols?: string | string[]) {
      super()
      const urlObj = new URL(String(url), window.location.href)
      this.url = urlObj.href
      const match = /\/api\/experimental\/persistent-pty\/([^/]+)\/connect$/.exec(urlObj.pathname)

      if (match && (urlObj.hostname === "opencode.local" || urlObj.hostname === "127.0.0.1")) {
        this.ptyID = decodeURIComponent(match[1])
        queueMicrotask(() => {
          if (this.readyState !== 0) return
          this.readyState = 1
          const openEv = new Event("open")
          this.onopen?.(openEv)
          this.dispatchEvent(openEv)

          this.emitMessage(
            JSON.stringify({
              type: "attached",
              inputProtocol: 1,
              info: { size: { cols: 80, rows: 24 } },
              role: "controller",
            }),
          )
          const initialBytes = engine.getPtyReplayBytes(this.ptyID!)
          if (initialBytes.byteLength > 0) {
            this.emitBinary(initialBytes)
          }
          this.emitMessage(JSON.stringify({ type: "replay_complete" }))
        })
      } else {
        this.realSocket = protocols ? new NativeWebSocket(url, protocols) : new NativeWebSocket(url)
        this.realSocket.addEventListener("open", (e) => {
          this.readyState = 1
          this.onopen?.(e)
          this.dispatchEvent(new Event("open"))
        })
        this.realSocket.addEventListener("message", (e) => {
          const me = new MessageEvent("message", { data: e.data })
          this.onmessage?.(me)
          this.dispatchEvent(me)
        })
        this.realSocket.addEventListener("error", (e) => {
          this.onerror?.(e)
          this.dispatchEvent(new Event("error"))
        })
        this.realSocket.addEventListener("close", (e) => {
          this.readyState = 3
          const ce = new CloseEvent("close", { code: e.code, reason: e.reason, wasClean: e.wasClean })
          this.onclose?.(ce)
          this.dispatchEvent(ce)
        })
      }
    }

    private emitMessage(text: string) {
      if (this.readyState !== 1) return
      const ev = new MessageEvent("message", { data: text })
      this.onmessage?.(ev)
      this.dispatchEvent(ev)
    }

    private emitBinary(bytes: Uint8Array) {
      if (this.readyState !== 1) return
      const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
      const ev = new MessageEvent("message", { data: buf })
      this.onmessage?.(ev)
      this.dispatchEvent(ev)
    }

    send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
      if (this.realSocket) {
        if (this.realSocket.binaryType !== this.binaryType) {
          this.realSocket.binaryType = this.binaryType
        }
        this.realSocket.send(data as any)
        return
      }
      if (!this.ptyID || this.readyState !== 1) return
      let bytes: Uint8Array | null = null
      if (data instanceof Uint8Array) {
        bytes = data
      } else if (data instanceof ArrayBuffer) {
        bytes = new Uint8Array(data)
      } else if (ArrayBuffer.isView(data)) {
        bytes = new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
      }
      if (bytes && bytes.length >= 5 && bytes[0] === 1) {
        const text = new TextDecoder().decode(bytes.subarray(5))
        void engine.sendPtyInput(this.ptyID, text, (out) => this.emitBinary(out))
      } else if (typeof data === "string") {
        void engine.sendPtyInput(this.ptyID, data, (out) => this.emitBinary(out))
      }
    }

    close(code = 1000, reason = "") {
      if (this.realSocket) {
        this.realSocket.close(code, reason)
        return
      }
      if (this.readyState === 3) return
      this.readyState = 3
      const ev = new CloseEvent("close", { code, reason, wasClean: true })
      this.onclose?.(ev)
      this.dispatchEvent(ev)
    }
  }

  ;(BridgedWebSocket as any).__ocPatched = true
  window.WebSocket = BridgedWebSocket as any
}
