import { Button } from "@opencode/ui/button"
import { Badge } from "@opencode/ui/badge"
import { Dialog, DialogBody, DialogFooter, DialogHeader, DialogTitleGroup } from "@opencode/ui/dialog"
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
  { id: "empty", label: "Пустой проект" },
  { id: "typescript", label: "Node.js / TypeScript" },
  { id: "python", label: "Python (бот / скрипт)" },
  { id: "web", label: "Web (HTML/CSS/JS)" },
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
  const [customPath, setCustomPath] = createSignal("/storage/emulated/0/")
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
      setError("Введите название папки проекта (например tg-bot)")
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
      setError(err?.message ? String(err.message) : "Ошибка создания проекта")
    } finally {
      setCreating(false)
    }
  }

  const openOrCreateExternalFolder = async () => {
    const target = customPath().trim()
    if (!target) return
    setCreating(true)
    setError(undefined)
    try {
      const folderName = target.replace(/\/+$/, "").split("/").pop() || "external-project"
      const res = await doFetch()(apiUrl("/api/android/projects"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: folderName, template: "empty", directory: target }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json?.message || `HTTP ${res.status}`)
      await refetch()
      choose(json.canonical)
    } catch (err: any) {
      setError(err?.message ? String(err.message) : "Не удалось открыть папку")
    } finally {
      setCreating(false)
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
          title={props.title || "Проекты и рабочие папки"}
          description="Откройте рабочую среду, создайте новый проект или укажите любую папку на телефоне (/storage/emulated/0/...)."
        />
      </DialogHeader>
      <DialogBody class="px-4 pb-3">
        <div class="flex flex-col gap-3.5">
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <span class="text-[12px] font-[530] text-v2-text-text-base">Рабочие среды</span>
              <Badge>{projects()?.length ?? 0}</Badge>
            </div>
            <div class="flex max-h-44 flex-col gap-1.5 overflow-y-auto">
              <For each={projects() ?? []}>
                {(proj) => (
                  <button
                    type="button"
                    onClick={() => choose(proj.canonical)}
                    class="flex items-center justify-between gap-3 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface px-3 py-2 text-start hover:bg-v2-overlay-simple-overlay-hover transition-colors"
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
                    <span class="shrink-0 text-[12px] font-[500] text-v2-text-text-muted">Открыть →</span>
                  </button>
                )}
              </For>
            </div>
          </div>

          <form
            onSubmit={createNewProject}
            class="flex flex-col gap-2.5 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface/60 p-3"
          >
            <span class="text-[12.5px] font-[540] text-v2-text-text-base">Создать локальный проект</span>
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <input
                type="text"
                value={newName()}
                onInput={(e) => setNewName(e.currentTarget.value)}
                placeholder="Имя проекта (напр. tg-bot)"
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
            <div class="flex justify-end">
              <Button type="submit" variant="contrast" icon="plus" disabled={creating()}>
                {creating() ? "Создание…" : "Создать и открыть"}
              </Button>
            </div>
          </form>

          <div class="flex flex-col gap-1.5 rounded-lg border border-v2-border-border-muted bg-v2-background-bg-surface/60 p-3">
            <span class="text-[12px] font-[530] text-v2-text-text-base">
              Открыть / создать любую папку в памяти телефона
            </span>
            <div class="flex items-center gap-1.5">
              <input
                type="text"
                value={customPath()}
                onInput={(e) => setCustomPath(e.currentTarget.value)}
                placeholder="/storage/emulated/0/gg"
                class="h-9 min-w-0 flex-1 rounded-md border border-v2-border-border-base bg-v2-background-bg-base px-2.5 font-mono text-[12px] text-v2-text-text-base outline-none"
              />
              <Button
                type="button"
                variant="neutral"
                disabled={!customPath().trim() || creating()}
                onClick={() => void openOrCreateExternalFolder()}
              >
                Открыть
              </Button>
            </div>
          </div>

          <Show when={error()}>
            {(err) => <span class="text-[12px] text-red-500">{err()}</span>}
          </Show>
        </div>
      </DialogBody>
      <DialogFooter>
        <Button type="button" variant="ghost-muted" onClick={() => { props.onResolve(null); dialog.close() }}>
          Закрыть
        </Button>
      </DialogFooter>
    </Dialog>
  )
}
