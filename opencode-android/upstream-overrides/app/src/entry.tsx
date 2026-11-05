// @refresh reload

import "@/runtime/polyfills"
import "@/android/mobile-adapt.css"
import { createEffect, type Component } from "solid-js"
import { render } from "solid-js/web"
import { useDialog } from "@opencode/ui/context/dialog"
import { AppBaseProviders, AppInterface } from "@/app"
import { loadInitialLocale } from "@/runtime/i18n/language"
import { PlatformProvider, type Platform } from "@/runtime/platform/platform"
import { createBrowserDraftStore } from "@/runtime/persistence/drafts"
import { isStandalone, PwaRoutePersistence, restorePwaRoute } from "@/runtime/platform/pwa"
import { KeyboardInsets } from "@/runtime/platform/keyboard"
import { authFromToken } from "@/runtime/server/api"
import pkg from "../package.json"
import { ServerConnection } from "@/runtime/server/registry"
import {
  getInAppAndroidEngine,
  installAndroidPtyWebSocketBridge,
  isAndroidNativeWebView,
} from "@/android/android-host"
import { DialogAndroidProjectPicker } from "@/android/project-picker-dialog"

type DirectoryPickerHandler = (opts?: { title?: string; multiple?: boolean }) => Promise<string | string[] | null>
let activeDirectoryPickerHandler: DirectoryPickerHandler | null = null

const AndroidDirectoryPickerHost: Component<{ serverUrl: string }> = (props) => {
  const dialog = useDialog()

  createEffect(() => {
    activeDirectoryPickerHandler = (opts) =>
      new Promise<string | null>((resolve) => {
        let settled = false
        const finish = (val: string | null) => {
          if (settled) return
          settled = true
          resolve(val)
        }
        void dialog.show(
          () => (
            <DialogAndroidProjectPicker
              title={opts?.title}
              serverUrl={props.serverUrl}
              onResolve={(picked) => finish(picked)}
            />
          ),
          () => finish(null),
        )
      })
  })

  return null
}

const root = document.getElementById("root")

const clearAuthToken = () => {
  const params = new URLSearchParams(location.search)
  if (!params.has("auth_token")) return
  params.delete("auth_token")
  history.replaceState(null, "", location.pathname + (params.size ? `?${params}` : "") + location.hash)
}

const nativeAndroid = isAndroidNativeWebView()
const serverOrigin = location.origin && location.origin !== "null" ? location.origin : "http://opencode.local"

const androidEngine = nativeAndroid ? getInAppAndroidEngine() : null
if (androidEngine) {
  installAndroidPtyWebSocketBridge(androidEngine)
}

const customFetch: typeof fetch | undefined = androidEngine
  ? async (input, init) => {
      const req = new Request(input, init)
      const u = new URL(req.url, serverOrigin)
      if (
        (u.hostname === "opencode.local" || u.hostname === "127.0.0.1" || u.hostname === "localhost") &&
        u.pathname.startsWith("/api/")
      ) {
        return androidEngine.handle(req)
      }
      return globalThis.fetch(input, init)
    }
  : undefined

const platform: Platform = {
  platform: "desktop",
  windowID: "main",
  version: import.meta.env.VITE_OPENCODE_VERSION ?? pkg.version,
  draftStore: createBrowserDraftStore(),
  fetch: customFetch,
  openDirectoryPickerDialog(opts) {
    if (activeDirectoryPickerHandler) {
      return activeDirectoryPickerHandler(opts)
    }
    return Promise.resolve(null)
  },
  openExternal(value) {
    if (!URL.canParse(value)) return
    const url = new URL(value)
    if (url.protocol !== "http:" && url.protocol !== "https:" && url.protocol !== "mailto:") return
    window.open(url.href, "_blank", "noopener,noreferrer")
  },
  async openBrowser(value) {
    if (!URL.canParse(value)) return false
    window.open(value, "_blank", "noopener,noreferrer")
    return true
  },
  restart: async () => window.location.reload(),
  async writeClipboardText(text) {
    await navigator.clipboard?.writeText(text).catch(() => undefined)
  },
  async notify(title, description, onClick) {
    if (!("Notification" in window)) return
    const permission =
      Notification.permission === "default"
        ? await Notification.requestPermission().catch(() => "denied")
        : Notification.permission
    if (permission !== "granted") return
    if (document.visibilityState === "visible" && document.hasFocus()) return
    const notification = new Notification(title, {
      body: description ?? "",
    })
    notification.onclick = () => {
      window.focus()
      onClick?.()
      notification.close()
    }
  },
}

if (root instanceof HTMLElement && root.dataset.opencodeMounted === undefined) {
  root.dataset.opencodeMounted = ""
  void loadInitialLocale().then((locale) => {
    const auth = authFromToken(new URLSearchParams(location.search).get("auth_token"))
    clearAuthToken()
    const standalone = isStandalone()
    root.dataset.standalone = String(standalone)
    if (standalone) restorePwaRoute()

    const server: ServerConnection.Http = {
      type: "http",
      authToken: !!auth,
      http: {
        url: serverOrigin,
        ...auth,
      },
    }

    render(
      () => (
        <PlatformProvider value={platform}>
          <AppBaseProviders locale={locale}>
            <AppInterface canonicalLocalServer={ServerConnection.key(server)} servers={[server]}>
              <AndroidDirectoryPickerHost serverUrl={serverOrigin} />
              <KeyboardInsets />
              {standalone && <PwaRoutePersistence />}
            </AppInterface>
          </AppBaseProviders>
        </PlatformProvider>
      ),
      root,
    )
  })
}
