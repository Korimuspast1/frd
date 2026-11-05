import { Button } from "@opencode/ui/button"
import { Badge } from "@opencode/ui/badge"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitleGroup } from "@opencode/ui/dialog"
import { useDialog } from "@opencode/ui/context/dialog"
import { Icon } from "@opencode/ui/icon"
import { Loader } from "@opencode/ui/loader"
import { createEffect, createMemo, createSignal, For, onCleanup, Show, type Component } from "solid-js"
import { usePlatform } from "@/runtime/platform/platform"
import { useServerSDK } from "@/runtime/server/client"
import { useData } from "@/runtime/server/current"
import { useGlobal } from "@/runtime/server/runtime"
import { showToast } from "@/shell/notifications/toast"

interface DiscoveredPreviewModel {
  id: string
  name: string
  contextWindow: number
  maxOutput: number
  vision?: boolean
  reasoning?: boolean
  tools?: boolean
}

const PRESETS = [
  { label: "OpenRouter", name: "OpenRouter", baseURL: "https://openrouter.ai/api/v1", protocol: "openai" as const },
  { label: "DeepSeek", name: "DeepSeek", baseURL: "https://api.deepseek.com/v1", protocol: "openai" as const },
  { label: "Gemini URL", name: "Gemini Custom", baseURL: "https://generativelanguage.googleapis.com/v1beta/openai", protocol: "openai" as const },
  { label: "Groq", name: "Groq", baseURL: "https://api.groq.com/openai/v1", protocol: "openai" as const },
  { label: "Together", name: "Together AI", baseURL: "https://api.together.xyz/v1", protocol: "openai" as const },
  { label: "Ollama", name: "Ollama LAN", baseURL: "http://127.0.0.1:11434/v1", protocol: "openai" as const },
  { label: "Anthropic", name: "Anthropic Custom", baseURL: "https://api.anthropic.com/v1", protocol: "anthropic" as const },
]

function inferProviderNameFromUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim()
  if (!trimmed) return ""
  try {
    const withProto = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`
    const host = new URL(withProto).hostname.toLowerCase()
    if (host.includes("openrouter")) return "OpenRouter"
    if (host.includes("deepseek")) return "DeepSeek"
    if (host.includes("generativelanguage.googleapis")) return "Google Gemini"
    if (host.includes("groq")) return "Groq"
    if (host.includes("together")) return "Together AI"
    if (host.includes("fireworks")) return "Fireworks AI"
    if (host.includes("mistral")) return "Mistral"
    if (host.includes("anthropic")) return "Anthropic Custom"
    if (host.includes("openai")) return "OpenAI Custom"
    if (host === "127.0.0.1" || host === "localhost") return "Local Provider"
    return host.replace(/^api\./, "")
  } catch {
    return ""
  }
}

export const DialogCustomProvider: Component<{
  directory?: string
  initial?: {
    id?: string
    name?: string
    baseURL?: string
    protocol?: "openai" | "anthropic"
  }
  onSaved?: (providerID: string) => void
}> = (props) => {
  const dialog = useDialog()
  const platform = usePlatform()
  const sdk = useServerSDK()
  const data = useData()
  const global = useGlobal()

  const [name, setName] = createSignal(props.initial?.name ?? "")
  const [nameTouched, setNameTouched] = createSignal(Boolean(props.initial?.name))
  const [baseURL, setBaseURL] = createSignal(props.initial?.baseURL ?? "")
  const [protocol, setProtocol] = createSignal<"openai" | "anthropic">(props.initial?.protocol ?? "openai")
  const [apiKey, setApiKey] = createSignal("")
  const [showKey, setShowKey] = createSignal(false)
  const [extraModels, setExtraModels] = createSignal("")
  const [modelFilter, setModelFilter] = createSignal("")
  const [discovering, setDiscovering] = createSignal(false)
  const [saving, setSaving] = createSignal(false)
  const [discovered, setDiscovered] = createSignal<DiscoveredPreviewModel[]>([])
  const [uncheckedIds, setUncheckedIds] = createSignal<Set<string>>(new Set())
  const [endpointUsed, setEndpointUsed] = createSignal<string | undefined>(undefined)
  const [statusMessage, setStatusMessage] = createSignal<string | undefined>(undefined)
  const [errorMessage, setErrorMessage] = createSignal<string | undefined>(undefined)

  let probeReqCounter = 0

  const doFetch = () => platform.fetch ?? globalThis.fetch
  const apiUrl = (path: string) => {
    const base = sdk.url.endsWith("/") ? sdk.url.slice(0, -1) : sdk.url
    return `${base}${path}`
  }

  const looksQueryableUrl = (raw: string) => {
    const t = raw.trim()
    if (t.length < 6) return false
    return t.includes(".") || t.includes("localhost") || t.includes("127.0.0.1") || /:\d+/.test(t)
  }

  const probeModels = async (silentIfAuthNeeded = false) => {
    const cleanUrl = baseURL().trim()
    if (!cleanUrl) {
      if (!silentIfAuthNeeded) {
        setErrorMessage("Введите Base URL провайдера (например https://openrouter.ai/api/v1)")
      }
      return
    }
    const reqId = ++probeReqCounter
    setDiscovering(true)
    if (!silentIfAuthNeeded) {
      setErrorMessage(undefined)
    }

    try {
      const res = await doFetch()(apiUrl("/api/android/discover-models"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          baseURL: cleanUrl,
          apiKey: apiKey().trim() || undefined,
          protocol: protocol(),
        }),
      })
      if (reqId !== probeReqCounter) return
      const json = await res.json()
      const list: DiscoveredPreviewModel[] = Array.isArray(json.models) ? json.models : []
      if (list.length > 0) {
        setDiscovered(list)
        setUncheckedIds(new Set())
        setEndpointUsed(json.endpointUsed)
        setErrorMessage(undefined)
        setStatusMessage(`Автоматически подхвачено моделей: ${list.length}`)
      } else {
        const errStr = String(json.error ?? "")
        if (silentIfAuthNeeded && !apiKey().trim() && /401|403|unauthorized|key/i.test(errStr)) {
          setStatusMessage(undefined)
          setErrorMessage("Введите API Key — модели подхватятся автоматически.")
        } else {
          setStatusMessage(undefined)
          setErrorMessage(
            errStr
              ? `Не удалось получить /v1/models (${errStr}). Проверьте Base URL / API Key или укажите ID моделей вручную ниже.`
              : "Эндпоинт /v1/models вернул 0 моделей. Проверьте API Key или укажите ID моделей ниже.",
          )
        }
      }
    } catch (err: any) {
      if (reqId !== probeReqCounter) return
      if (!silentIfAuthNeeded) {
        setErrorMessage(err?.message ? String(err.message) : "Ошибка запроса к /v1/models")
      }
    } finally {
      if (reqId === probeReqCounter) {
        setDiscovering(false)
      }
    }
  }

  // Automatic debounced model discovery whenever Base URL, API Key, or Protocol changes
  createEffect(() => {
    const u = baseURL().trim()
    const k = apiKey().trim()
    const p = protocol()
    void k
    void p

    if (!looksQueryableUrl(u)) return

    const timer = setTimeout(() => {
      void probeModels(true)
    }, 450)

    onCleanup(() => clearTimeout(timer))
  })

  const filteredModels = createMemo(() => {
    const q = modelFilter().trim().toLowerCase()
    const all = discovered()
    if (!q) return all
    return all.filter((m) => `${m.id} ${m.name}`.toLowerCase().includes(q))
  })

  const selectedDiscoveredModels = () => {
    const unchecked = uncheckedIds()
    return discovered().filter((m) => !unchecked.has(m.id))
  }

  const toggleModelCheck = (id: string) => {
    setUncheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const saveProvider = async (e?: Event) => {
    e?.preventDefault()
    const cleanUrl = baseURL().trim()
    if (!cleanUrl) {
      setErrorMessage("Укажите API Base URL провайдера.")
      return
    }
    const finalName = name().trim() || inferProviderNameFromUrl(cleanUrl) || "Custom Provider"
    setSaving(true)
    setErrorMessage(undefined)

    try {
      const chosenModels = selectedDiscoveredModels()
      const res = await doFetch()(apiUrl("/api/android/custom-providers"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: props.initial?.id,
          name: finalName,
          baseURL: cleanUrl,
          protocol: protocol(),
          apiKey: apiKey().trim(),
          extraModels: extraModels().trim(),
          ...(chosenModels.length > 0 ? { discoveredModels: chosenModels } : {}),
        }),
      })
      const json = await res.json()
      if (!res.ok) {
        throw new Error(json?.message || `HTTP ${res.status}`)
      }

      const providerObj = json.provider
      const defaultLoc = data.location.default()
      const activeLoc = props.directory ? { directory: props.directory } : undefined

      data.location.integration.invalidate(defaultLoc)
      data.location.provider.invalidate(defaultLoc)
      data.location.model.invalidate(defaultLoc)
      if (activeLoc) {
        data.location.integration.invalidate(activeLoc)
        data.location.provider.invalidate(activeLoc)
        data.location.model.invalidate(activeLoc)
      }

      await Promise.all([
        data.location.integration.sync(defaultLoc),
        data.location.provider.sync(defaultLoc),
        data.location.model.sync(defaultLoc),
        ...(activeLoc
          ? [
              data.location.integration.sync(activeLoc),
              data.location.provider.sync(activeLoc),
              data.location.model.sync(activeLoc),
            ]
          : []),
      ]).catch(() => undefined)

      if (providerObj?.discoveredModels?.length) {
        const modelKeys = providerObj.discoveredModels.map((m: { id: string }) => ({
          providerID: providerObj.id,
          modelID: m.id,
        }))
        global.models.show(modelKeys)
        const firstKey = modelKeys[0]
        if (firstKey) {
          const existingRecent = global.models.store.recent.filter(
            (r) => !(r.providerID === firstKey.providerID && r.modelID === firstKey.modelID),
          )
          global.models.set("recent", [firstKey, ...existingRecent].slice(0, 5))
        }
      }

      const totalModels = providerObj?.discoveredModels?.length ?? 0
      showToast({
        variant: "success",
        icon: "circle-check",
        title: `Подключён ${providerObj?.name ?? finalName}`,
        description:
          totalModels > 0
            ? `Автоматически подхвачено моделей: ${totalModels}. Доступны в выборе модели!`
            : json.warning || "Провайдер сохранён.",
      })

      props.onSaved?.(providerObj.id)
      dialog.close()
    } catch (err: any) {
      setErrorMessage(err?.message ? String(err.message) : "Не удалось сохранить провайдера")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      fit
      containerClass="oc-mobile-full-dialog"
      class="[font-family:var(--v2-font-family-sans)]"
    >
      <DialogHeader closeLabel="Close">
        <DialogTitleGroup
          title="Кастомный провайдер (API Key + Авто-модели)"
          description="Введите Base URL и API Key — модели подхватятся автоматически."
        />
      </DialogHeader>

      <DialogBody class="px-4 pb-3">
        <form id="oc-custom-provider-form" onSubmit={saveProvider} class="flex flex-col gap-2.5">
          {/* Compact single-row scrollable presets */}
          <div class="flex items-center gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <For each={PRESETS}>
              {(preset) => (
                <button
                  type="button"
                  class="shrink-0 rounded-md border border-v2-border-border-muted bg-v2-background-bg-surface px-2.5 py-1 text-[11.5px] font-[500] text-v2-text-text-muted hover:bg-v2-overlay-simple-overlay-hover hover:text-v2-text-text-base transition-colors"
                  onClick={() => {
                    setName(preset.name)
                    setNameTouched(true)
                    setBaseURL(preset.baseURL)
                    setProtocol(preset.protocol)
                  }}
                >
                  {preset.label}
                </button>
              )}
            </For>
          </div>

          <label class="flex flex-col gap-1">
            <span class="text-[12px] font-[530] text-v2-text-text-base">1. API Base URL *</span>
            <div class="flex gap-1.5">
              <input
                type="text"
                inputMode="url"
                autocapitalize="off"
                autocorrect="off"
                spellcheck={false}
                value={baseURL()}
                onInput={(e) => {
                  const v = e.currentTarget.value
                  setBaseURL(v)
                  if (!nameTouched()) {
                    const inferred = inferProviderNameFromUrl(v)
                    if (inferred) setName(inferred)
                  }
                }}
                placeholder="https://openrouter.ai/api/v1"
                class="h-9 min-w-0 flex-1 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
                required
              />
              <Button
                type="button"
                variant="neutral"
                size="normal"
                disabled={discovering()}
                onClick={() => void probeModels(false)}
              >
                <Show when={discovering()} fallback={<span>Найти</span>}>
                  <Loader class="size-3.5" />
                </Show>
              </Button>
            </div>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[12px] font-[530] text-v2-text-text-base">2. API Key (ключ провайдера)</span>
            <div class="flex gap-1.5">
              <input
                type={showKey() ? "text" : "password"}
                autocapitalize="off"
                autocorrect="off"
                spellcheck={false}
                value={apiKey()}
                onInput={(e) => setApiKey(e.currentTarget.value)}
                placeholder="sk-... / AIza... (вставьте ключ)"
                autocomplete="off"
                class="h-9 min-w-0 flex-1 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 font-mono text-[12.5px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              />
              <Button
                type="button"
                variant="ghost-muted"
                size="normal"
                onClick={() => setShowKey((v) => !v)}
              >
                {showKey() ? "Скрыть" : "Показать"}
              </Button>
            </div>
          </label>

          <div class="grid grid-cols-2 gap-2">
            <label class="flex flex-col gap-1">
              <span class="text-[11.5px] font-[520] text-v2-text-text-base">Название</span>
              <input
                type="text"
                value={name()}
                onInput={(e) => {
                  setName(e.currentTarget.value)
                  setNameTouched(true)
                }}
                placeholder="Авто из URL"
                class="h-8.5 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-2.5 text-[12.5px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              />
            </label>

            <label class="flex flex-col gap-1">
              <span class="text-[11.5px] font-[520] text-v2-text-text-base">Протокол</span>
              <select
                value={protocol()}
                onChange={(e) => setProtocol(e.currentTarget.value === "anthropic" ? "anthropic" : "openai")}
                class="h-8.5 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-2 text-[12.5px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              >
                <option value="openai">OpenAI (/v1)</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </label>
          </div>

          <Show when={discovering()}>
            <div class="flex items-center gap-2 rounded-md border border-v2-border-border-muted bg-v2-background-bg-surface px-3 py-2 text-[12px] text-v2-text-text-muted">
              <Loader class="size-3.5 shrink-0" />
              <span>Автоматический подхват моделей с /v1/models…</span>
            </div>
          </Show>

          <Show when={!discovering() && statusMessage()}>
            {(msg) => (
              <div class="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[12px] text-emerald-600 dark:text-emerald-400">
                <Icon name="circle-check" size="small" class="shrink-0" />
                <span class="min-w-0 flex-1">{msg()}</span>
              </div>
            )}
          </Show>

          <Show when={!discovering() && errorMessage()}>
            {(err) => (
              <div class="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-700 dark:text-amber-300">
                {err()}
              </div>
            )}
          </Show>

          <Show when={discovered().length > 0}>
            <div class="flex flex-col gap-1.5 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface p-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="text-[12px] font-[530] text-v2-text-text-base">
                  Модели ({selectedDiscoveredModels().length}/{discovered().length})
                </span>
                <div class="flex items-center gap-1.5">
                  <button
                    type="button"
                    class="text-[11px] text-v2-text-text-muted underline hover:text-v2-text-text-base"
                    onClick={() =>
                      setUncheckedIds(
                        uncheckedIds().size === 0 ? new Set(discovered().map((m) => m.id)) : new Set<string>(),
                      )
                    }
                  >
                    {uncheckedIds().size === 0 ? "Снять все" : "Выбрать все"}
                  </button>
                  <Badge>{discovered().length}</Badge>
                </div>
              </div>

              <Show when={discovered().length > 5}>
                <input
                  type="search"
                  value={modelFilter()}
                  onInput={(e) => setModelFilter(e.currentTarget.value)}
                  placeholder="Поиск по моделям..."
                  class="h-8 rounded-md border border-v2-border-border-base bg-v2-background-bg-base px-2.5 text-[12px] text-v2-text-text-base outline-none"
                />
              </Show>

              <div class="max-h-36 overflow-y-auto pr-1 text-[12px]">
                <For each={filteredModels().slice(0, 250)}>
                  {(m) => {
                    const checked = () => !uncheckedIds().has(m.id)
                    return (
                      <label class="flex cursor-pointer items-center justify-between gap-2 border-b border-v2-border-border-muted/50 py-1.5 last:border-b-0">
                        <span class="flex min-w-0 items-center gap-2">
                          <input
                            type="checkbox"
                            checked={checked()}
                            onChange={() => toggleModelCheck(m.id)}
                            class="size-3.5 shrink-0 accent-emerald-500"
                          />
                          <span class="truncate font-mono text-[11.5px] text-v2-text-text-base">{m.id}</span>
                        </span>
                        <span class="shrink-0 text-[11px] text-v2-text-text-faint">
                          {Math.round((m.contextWindow || 128000) / 1024)}k
                        </span>
                      </label>
                    )
                  }}
                </For>
              </div>
            </div>
          </Show>

          <label class="flex flex-col gap-1">
            <span class="text-[11.5px] font-[500] text-v2-text-text-muted">
              Свои ID моделей через запятую (необязательно)
            </span>
            <input
              type="text"
              value={extraModels()}
              onInput={(e) => setExtraModels(e.currentTarget.value)}
              placeholder="Оставьте пустым для автоподхвата /v1/models"
              class="h-8.5 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-2.5 text-[12px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
            />
          </label>
        </form>
      </DialogBody>

      <DialogFooter>
        <Button type="button" variant="ghost-muted" onClick={() => dialog.close()}>
          Отмена
        </Button>
        <Button type="submit" form="oc-custom-provider-form" variant="contrast" disabled={saving()}>
          <Show when={saving()} fallback={<span>Сохранить и подключить</span>}>
            <span class="flex items-center gap-1.5">
              <Loader class="size-3.5" />
              <span>Подключение…</span>
            </span>
          </Show>
        </Button>
      </DialogFooter>
    </Dialog>
  )
}
