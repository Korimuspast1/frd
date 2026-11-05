import { Button } from "@opencode/ui/button"
import { Badge } from "@opencode/ui/badge"
import { Dialog, DialogBody, DialogHeader, DialogTitleGroup } from "@opencode/ui/dialog"
import { useDialog } from "@opencode/ui/context/dialog"
import { Icon } from "@opencode/ui/icon"
import { createResource, createSignal, For, Show, type Component } from "solid-js"
import { usePlatform } from "@/runtime/platform/platform"

interface ProjectEntry {
  id: string
  canonical: string
  name?: string
}

const TEMPLATES = [
  { id: "empty", label: "Empty Workspace" },
  { id: "typescript", label: "TypeScript + Node" },
  { id: "python", label: "Python Project" },
  { id: "web", label: "Web App (HTML/CSS/JS)" },
  { id: "kotlin", label: "Kotlin / Android" },
]

export const DialogAndroidProjectPicker: Component<{
  title?: string
  serverUrl: string
  onResolve: (selectedPath: string | null) => void
}> = (props) => {
  const dialog = useDialog()
  const platform = usePlatform()
  const [newName, setNewName] = createSignal("")
  const [template, setTemplate] = createSignal("typescript")
  const [customPath, setCustomPath] = createSignal("")
  const [creating, setCreating] = createSignal(false)
  const [error, setError] = createSignal<string | undefined>(undefined)

  const doFetch = () => platform.fetch ?? globalThis.fetch
  const apiUrl = (path: string) => {
    const base = props.serverUrl.endsWith("/") ? props.serverUrl.slice(0, -1) : props.serverUrl
    return `${base}${path}`
  }

  const [projects, { refetch }] = createResource<ProjectEntry[]>(
    async () => {
      const res = await doFetch()(apiUrl("/api/project"))
      if (!res.ok) return []
      return res.json()
    },
    { initialValue: [] },
  )

  const choose = (dir: string) => {
    props.onResolve(dir)
    dialog.close()
  }

  const createNewProject = async (e: Event) => {
    e.preventDefault()
    const trimmed = newName().trim()
    if (!trimmed) {
      setError("Enter a project folder name (e.g. my-app)")
      return
    }
    setCreating(true)
    setError(undefined)
    try {
      const res = await doFetch()(apiUrl("/api/android/projects"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, template: template() }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json?.message || `HTTP ${res.status}`)
      await refetch()
      choose(json.canonical)
    } catch (err: any) {
      setError(err?.message ? String(err.message) : "Failed to create local project")
    } finally {
      setCreating(false)
    }
  }

  return (
    <Dialog
      containerClass="!self-start !rounded-[12px] !bg-v2-background-bg-base !mt-[max(8px,calc((100dvh_-_560px)/2))] !w-[min(calc(100vw_-_16px),560px)] !max-h-[calc(100dvh_-_16px)]"
      class="[font-family:var(--v2-font-family-sans)]"
    >
      <DialogHeader closeLabel="Close">
        <DialogTitleGroup
          title={props.title || "Open or Create Local Project"}
          description="Select an existing local workspace on your device or create a new project folder."
        />
      </DialogHeader>
      <DialogBody class="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
        <div class="flex flex-col gap-4">
          <div class="flex flex-col gap-2">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-[530] text-v2-text-text-base">Local Workspaces</span>
              <Badge>{projects()?.length ?? 0}</Badge>
            </div>
            <div class="flex max-h-48 flex-col gap-1.5 overflow-y-auto">
              <For each={projects() ?? []}>
                {(proj) => (
                  <button
                    type="button"
                    onClick={() => choose(proj.canonical)}
                    class="flex items-center justify-between gap-3 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface px-3 py-2.5 text-start hover:bg-v2-overlay-simple-overlay-hover transition-colors"
                  >
                    <div class="flex min-w-0 items-center gap-2.5">
                      <Icon name="folder" size="small" class="shrink-0 text-v2-icon-icon-muted" />
                      <div class="min-w-0">
                        <div class="truncate text-[13px] font-[520] text-v2-text-text-base">
                          {proj.name || proj.canonical.split("/").pop()}
                        </div>
                        <div class="truncate font-mono text-[11px] text-v2-text-text-faint">{proj.canonical}</div>
                      </div>
                    </div>
                    <span class="shrink-0 text-[12px] font-[500] text-v2-text-text-muted">Open →</span>
                  </button>
                )}
              </For>
            </div>
          </div>

          <form
            onSubmit={createNewProject}
            class="flex flex-col gap-3 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface/60 p-3.5"
          >
            <span class="text-[12.5px] font-[540] text-v2-text-text-base">Create New Local Project</span>
            <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              <input
                type="text"
                value={newName()}
                onInput={(e) => setNewName(e.currentTarget.value)}
                placeholder="Project name (e.g. mobile-api)"
                class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-base px-3 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              />
              <select
                value={template()}
                onChange={(e) => setTemplate(e.currentTarget.value)}
                class="h-9 rounded-md border border-v2-border-border-base bg-v2-background-bg-base px-2.5 text-[13px] text-v2-text-text-base outline-none focus:border-v2-border-border-strong"
              >
                <For each={TEMPLATES}>{(tpl) => <option value={tpl.id}>{tpl.label}</option>}</For>
              </select>
            </div>
            <Show when={error()}>
              {(err) => <span class="text-[12px] text-red-500">{err()}</span>}
            </Show>
            <div class="flex justify-end">
              <Button type="submit" variant="contrast" icon="plus" disabled={creating()}>
                {creating() ? "Creating…" : "Create & Open Project"}
              </Button>
            </div>
          </form>

          <div class="flex items-center gap-2 pt-1">
            <input
              type="text"
              value={customPath()}
              onInput={(e) => setCustomPath(e.currentTarget.value)}
              placeholder="Or open exact local path (/data/user/0/...)"
              class="h-8.5 min-w-0 flex-1 rounded-md border border-v2-border-border-base bg-v2-background-bg-surface px-3 font-mono text-[12px] text-v2-text-text-base outline-none"
            />
            <Button
              type="button"
              variant="neutral"
              disabled={!customPath().trim()}
              onClick={() => choose(customPath().trim())}
            >
              Open Path
            </Button>
          </div>
        </div>
      </DialogBody>
    </Dialog>
  )
}
