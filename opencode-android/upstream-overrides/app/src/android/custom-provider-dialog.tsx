import { Button } from "@opencode/ui/button"
import { Badge } from "@opencode/ui/badge"
import { Dialog, DialogBody, DialogHeader, DialogTitleGroup } from "@opencode/ui/dialog"
import { useDialog } from "@opencode/ui/context/dialog"
import { Icon } from "@opencode/ui/icon"
import { Loader } from "@opencode/ui/loader"
import { createSignal, For, Show, type Component } from "solid-js"
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
}

const PRESETS = [
  { label: "Custom OpenAI URL", name: "", baseURL: "https://api.example.com/v1", protocol: "openai" as const },
  { label: "OpenRouter", name: "OpenRouter", baseURL: "https://openrouter.ai/api/v1", protocol: "openai" as const },
  { label: "DeepSeek", name: "DeepSeek", baseURL: "https://api.deepseek.com/v1", protocol: "openai" as const },
  { label: "Groq", name: "Groq", baseURL: "https://api.groq.com/openai/v1", protocol: "openai" as const },
  { label: "Together AI", name: "Together AI", baseURL: "https://api.together.xyz/v1", protocol: "openai" as const },
  { label: "Ollama / LAN", name: "Ollama LAN", baseURL: "http://127.0.0.1:11434/v1", protocol: "openai" as const },
  { label: "Anthropic Proxy", name: "Anthropic Custom", baseURL: "https://api.anthropic.com/v1", protocol: "anthropic" as const },
]

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
  const [baseURL, setBaseURL] = createSignal(props.initial?.baseURL ?? "")
  const [protocol, setProtocol] = createSignal<"openai" | "anthropic">(props.initial?.protocol ?? "openai")
  const [apiKey, setApiKey] = createSignal("")
  const [extraModels, setExtraModels] = createSignal("")
  const [discovering, setDiscovering] = createSignal(false)
  const [saving, setSaving] = createSignal(false)
  const [discovered, setDiscovered] = createSignal<DiscoveredPreviewModel[]>([])
  const [endpointUsed, setEndpointUsed] = createSignal<string | undefined>(undefined)
  const [statusMessage, setStatusMessage] = createSignal<string | undefined>(undefined)
  const [errorMessage, setErrorMessage] = createSignal<string | undefined>(undefined)

  const doFetch = () => platform.fetch ?? globalThis.fetch
  const apiUrl = (path: string) => {
    const base = sdk.url.endsWith("/") ? sdk.url.slice(0, -1) : sdk.url
    return `${base}${path}`
  }

  const probeModels = async () => {
    if (!baseURL().trim()) {
      setErrorMessage("Please enter an API Base URL first (e.g. https://openrouter.ai/api/v1)")
      return
    }
    setDiscovering(true)
    setErrorMessage(undefined)
    setStatusMessage(undefined)
    try {
      const res = await doFetch()(apiUrl("/api/android/discover-models"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          baseURL: baseURL().trim(),
          apiKey: apiKey().trim() || undefined,
          protocol: protocol(),
        }),
      })
      const json = await res.json()
      const list: DiscoveredPreviewModel[] = Array.isArray(json.models) ? json.models : []
      setDiscovered(list)
      setEndpointUsed(json.endpointUsed)
      if (list.length > 0) {
        setStatusMessage(`Auto-discovered ${list.length} models from ${json.endpointUsed ?? "/v1/models"}`)
      } else {
        setErrorMessage(
          json.error
            ? `${json.error}. You can still save with Fallback Model IDs below.`
            : "0 models returned by /v1/models. Enter Fallback Model IDs if your server hides /models.",
        )
      }
    } catch (err: any) {
      setErrorMessage(err?.message ? String(err.message) : "Failed to query /v1/models")
    } finally {
      setDiscovering(false)
    }
  }

  const saveProvider = async (e?: Event) => {
    e?.preventDefault()
    if (!name().trim() || !baseURL().trim()) {
      setErrorMessage("Provider Name and API Base URL are required.")
      return
    }
    setSaving(true)
    setErrorMessage(undefined)
    try {
      const res = await doFetch()(apiUrl("/api/android/custom-providers"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: props.initial?.id,
          name: name().trim(),
          baseURL: baseURL().trim(),
          protocol: protocol(),
          apiKey: apiKey().trim(),
          extraModels: extraModels().trim(),
        }),
      })
      const json = await res.json()
      if (!res.ok) {
        throw new Error(json?.message || `HTTP ${res.status}`)
      }

      const providerObj = json.provider
      const location = props.directory ? { directory: props.directory } : undefined
      data.location.integration.invalidate(location)
      data.location.provider.invalidate(location)
      data.location.model.invalidate(location)
      await Promise.all([
        data.location.integration.sync(location),
        data.location.provider.sync(location),
        data.location.model.sync(location),
      ]).catch(() => undefined)

      if (providerObj?.discoveredModels?.length) {
        global.models.show(
          providerObj.discoveredModels.map((m: { id: string }) => ({
            providerID: providerObj.id,
            modelID: m.id,
          })),
        )
      }

      const totalModels = providerObj?.discoveredModels?.length ?? 0
      showToast({
        variant: "success",
        icon: "circle-check",
        title: `Connected ${providerObj?.name ?? name().trim()}`,
        description:
          totalModels > 0
            ? `${totalModels} models automatically loaded & ready in model selector.`
            : json.warning || "Provider saved.",
      })

      props.onSaved?.(providerObj.id)
      dialog.close()
    } catch (err: any) {
      setErrorMessage(err?.message ? String(err.message) : "Failed to save custom provider")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      containerClass="!self-start !rounded-[12px] !bg-v2-background-bg-base !mt-[max(8px,calc((100dvh_-_600px)/2))] !w-[min(calc(100vw_-_16px),600px)] !max-h-[calc(100dvh_-_16px)]"
      class="[font-family:var(--v2-font-family-sans)]"
    >
      <DialogHeader closeLabel="Close">
        <DialogTitleGroup
          title="Add Custom Provider"
          description="Connect any OpenAI-compatible or Anthropic endpoint — models are automatically fetched from /v1/models."
        />
      </DialogHeader>
      <DialogBody class="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
        <form onSubmit={saveProvider} class="flex flex-col gap-3.5">
          <div class="flex flex-wrap gap-1.5 pb-1">
            <For each={PRESETS}>
              {(preset) => (
                <button
                  type="button"
                  class="rounded-md border border-v2-border-border-muted bg-v2-background-bg-surface px-2.5 py-1 text-[11.5px] font-[500] text-v2-text-text-muted hover:bg-v2-overlay-simple-overlay-hover hover:text-v2-text-text-base transition-colors"
                  onClick={() => {
                    if (preset.name && !name()) setName(preset.name)
                    else if (preset.name) setName(preset.name)
                    setBaseURL(preset.baseURL)
                    setProtocol(preset.protocol)
                  }}
                >
                  {preset.label}
                </button>
              )}
            </For>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label class="flex flex-col gap-1">
              <span class="text-[12px] font-[520] text-v2-text-text-base">Provider Name *</span>
              <input
                type="text"
                value={name()}
                onInput={(e) => setName(e.currentTarget.value)}
                placeholder="e.g. My vLLM / OpenRouter / DeepSeek"
                class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
                required
              />
            </label>

            <label class="flex flex-col gap-1">
              <span class="text-[12px] font-[520] text-v2-text-text-base">API Protocol</span>
              <select
                value={protocol()}
                onChange={(e) => setProtocol(e.currentTarget.value === "anthropic" ? "anthropic" : "openai")}
                class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-2.5 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              >
                <option value="openai">OpenAI-Compatible (/v1/chat/completions)</option>
                <option value="anthropic">Anthropic (/v1/messages)</option>
              </select>
            </label>
          </div>

          <label class="flex flex-col gap-1">
            <span class="text-[12px] font-[520] text-v2-text-text-base">API Base URL *</span>
            <div class="flex gap-2">
              <input
                type="url"
                value={baseURL()}
                onInput={(e) => setBaseURL(e.currentTarget.value)}
                placeholder="https://api.openai.com/v1 or http://192.168.1.10:11434/v1"
                class="h-9 min-w-0 flex-1 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
                required
              />
              <Button
                type="button"
                variant="neutral"
                size="normal"
                disabled={discovering()}
                onClick={() => void probeModels()}
              >
                <Show when={discovering()} fallback={<span>Fetch Models</span>}>
                  <span class="flex items-center gap-1.5">
                    <Loader class="size-3.5" />
                    <span>Fetching…</span>
                  </span>
                </Show>
              </Button>
            </div>
            <span class="text-[11px] text-v2-text-text-faint">
              Automatically queries GET /v1/models (and /models or /api/tags) on save or when clicking Fetch Models.
            </span>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-[12px] font-[520] text-v2-text-text-base">API Key (optional for local Ollama / LAN)</span>
            <input
              type="password"
              value={apiKey()}
              onInput={(e) => setApiKey(e.currentTarget.value)}
              placeholder="sk-..."
              autocomplete="off"
              class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
            />
          </label>

          <Show when={statusMessage()}>
            {(msg) => (
              <div class="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[12px] text-emerald-600 dark:text-emerald-400">
                <Icon name="circle-check" size="small" class="shrink-0" />
                <span class="min-w-0 flex-1">{msg()}</span>
              </div>
            )}
          </Show>

          <Show when={errorMessage()}>
            {(err) => (
              <div class="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-700 dark:text-amber-300">
                {err()}
              </div>
            )}
          </Show>

          <Show when={discovered().length > 0}>
            <div class="flex flex-col gap-1.5 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface p-2.5">
              <div class="flex items-center justify-between">
                <span class="text-[12px] font-[530] text-v2-text-text-base">
                  Auto-Discovered Models
                </span>
                <Badge>{discovered().length} models</Badge>
              </div>
              <div class="max-h-36 overflow-y-auto pr-1 text-[12px]">
                <For each={discovered().slice(0, 80)}>
                  {(m) => (
                    <div class="flex items-center justify-between border-b border-v2-border-border-muted/50 py-1 last:border-b-0">
                      <span class="truncate font-mono text-[11.5px] text-v2-text-text-base">{m.id}</span>
                      <span class="ml-2 shrink-0 text-[11px] text-v2-text-text-faint">
                        {Math.round((m.contextWindow || 128000) / 1024)}k ctx
                      </span>
                    </div>
                  )}
                </For>
              </div>
              <Show when={endpointUsed()}>
                {(ep) => <span class="truncate text-[10.5px] text-v2-text-text-faint">Source: {ep()}</span>}
              </Show>
            </div>
          </Show>

          <label class="flex flex-col gap-1">
            <span class="text-[12px] font-[520] text-v2-text-text-muted">
              Manual / Extra Model IDs (optional comma-separated fallback)
            </span>
            <input
              type="text"
              value={extraModels()}
              onInput={(e) => setExtraModels(e.currentTarget.value)}
              placeholder="Leave empty for automatic /v1/models discovery, or e.g. gpt-4.1, my-model"
              class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
            />
          </label>

          <div class="mt-1 flex items-center justify-end gap-2 border-t border-v2-border-border-muted pt-3">
            <Button type="button" variant="ghost-muted" onClick={() => dialog.close()}>
              Cancel
            </Button>
            <Button type="submit" variant="contrast" disabled={saving()}>
              <Show when={saving()} fallback={<span>Save & Auto-Load Models</span>}>
                <span class="flex items-center gap-1.5">
                  <Loader class="size-3.5" />
                  <span>Connecting…</span>
                </span>
              </Show>
            </Button>
          </div>
        </form>
      </DialogBody>
    </Dialog>
  )
}
