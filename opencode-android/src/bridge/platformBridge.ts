import type { DaemonStatus, FileDiffItem, FileNode, ProjectInfo } from '../types/opencode';

export interface AndroidNativeInterface {
  isNativeAndroid(): boolean;
  getDaemonUrl(): string;
  getDeviceInfo(): string;
  setDaemonTaskStatus(statusText: string, busy: boolean): void;
  setSystemBarsTheme(bgHex: string, isDark: boolean): void;
  copyToClipboard(text: string): void;
  notifyTaskComplete(title: string, body: string): void;
  openExternalUrl(url: string): void;
  shareProjectZip(projectId: string): string;
  vibrateTick(): void;
}

declare global {
  interface Window {
    OpenCodeAndroid?: AndroidNativeInterface;
    __onAndroidKeyboardInset?: (px: number) => void;
    __onAndroidBackPressed?: () => boolean;
  }
}

export function isAndroidApp(): boolean {
  try {
    return Boolean(window.OpenCodeAndroid?.isNativeAndroid?.());
  } catch {
    return false;
  }
}

export function getApiBase(): string {
  try {
    if (window.OpenCodeAndroid?.getDaemonUrl) {
      const daemonUrl = window.OpenCodeAndroid.getDaemonUrl();
      if (daemonUrl && location.protocol === 'file:') {
        return daemonUrl.replace(/\/$/, '');
      }
    }
  } catch {
    // fallback to relative origin
  }
  return '';
}

async function apiPost<T>(endpoint: string, body: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(`${getApiBase()}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || data?.ok === false) {
    throw new Error(data?.error || `HTTP ${res.status} on ${endpoint}`);
  }
  return data as T;
}

async function apiGet<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${getApiBase()}${endpoint}`);
  const data = await res.json();
  if (!res.ok || data?.ok === false) {
    throw new Error(data?.error || `HTTP ${res.status} on ${endpoint}`);
  }
  return data as T;
}

export const PlatformBridge = {
  isAndroid: isAndroidApp,

  async getDaemonStatus(): Promise<DaemonStatus> {
    try {
      const health = await apiGet<DaemonStatus & { ok: boolean }>('/api/health');
      return health;
    } catch {
      return {
        running: false,
        platform: isAndroidApp() ? 'android' : 'web',
        daemonUrl: getApiBase() || location.origin,
        foregroundService: isAndroidApp(),
        busy: false,
        currentTask: 'Offline',
      };
    }
  },

  async setDaemonTask(statusText: string, busy: boolean): Promise<void> {
    try {
      window.OpenCodeAndroid?.setDaemonTaskStatus?.(statusText, busy);
    } catch {
      // ignore
    }
    try {
      await apiPost('/api/daemon/status', { statusText, busy });
    } catch {
      // ignore
    }
  },

  syncSystemTheme(bgHex: string, isDark: boolean): void {
    try {
      window.OpenCodeAndroid?.setSystemBarsTheme?.(bgHex, isDark);
    } catch {
      // ignore
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', bgHex);
  },

  notify(title: string, body: string): void {
    try {
      if (window.OpenCodeAndroid?.notifyTaskComplete) {
        window.OpenCodeAndroid.notifyTaskComplete(title, body);
        return;
      }
      if ('Notification' in window && Notification.permission === 'granted' && document.hidden) {
        new Notification(title, { body });
      }
    } catch {
      // ignore
    }
  },

  copyText(text: string): void {
    try {
      if (window.OpenCodeAndroid?.copyToClipboard) {
        window.OpenCodeAndroid.copyToClipboard(text);
        return;
      }
    } catch {
      // fallback
    }
    void navigator.clipboard?.writeText(text);
  },

  openExternal(url: string): void {
    try {
      if (window.OpenCodeAndroid?.openExternalUrl) {
        window.OpenCodeAndroid.openExternalUrl(url);
        return;
      }
    } catch {
      // fallback
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  },

  vibrate(): void {
    try {
      window.OpenCodeAndroid?.vibrateTick?.();
    } catch {
      // ignore
    }
  },

  // Projects
  async listProjects(): Promise<ProjectInfo[]> {
    const res = await apiGet<{ projects: ProjectInfo[] }>('/api/projects');
    return res.projects;
  },

  async createProject(name: string, template: string): Promise<ProjectInfo> {
    const res = await apiPost<{ project: ProjectInfo }>('/api/projects/create', { name, template });
    return res.project;
  },

  async cloneGithubRepo(repoUrl: string, name?: string): Promise<ProjectInfo> {
    const res = await apiPost<{ project: ProjectInfo }>('/api/projects/clone', { repoUrl, name });
    return res.project;
  },

  async deleteProject(projectId: string): Promise<void> {
    await apiPost('/api/projects/delete', { projectId });
  },

  exportProjectZip(projectId: string): void {
    try {
      if (window.OpenCodeAndroid?.shareProjectZip) {
        const res = window.OpenCodeAndroid.shareProjectZip(projectId);
        if (res === 'ok') return;
      }
    } catch {
      // fallback to download link
    }
    const url = `${getApiBase()}/api/projects/export-zip?projectId=${encodeURIComponent(projectId)}`;
    window.open(url, '_blank');
  },

  // File System Operations
  async listTree(projectId: string): Promise<{ tree: FileNode[]; flatFiles: string[] }> {
    return apiPost('/api/fs/tree', { projectId });
  },

  async readFile(
    projectId: string,
    relPath: string,
    offset?: number,
    limit?: number,
  ): Promise<{ content: string; totalLines: number; numbered: string; size: number; isBinary?: boolean }> {
    return apiPost('/api/fs/read', { projectId, path: relPath, offset, limit });
  },

  async writeFile(
    projectId: string,
    relPath: string,
    content: string,
  ): Promise<{ diff: FileDiffItem }> {
    return apiPost('/api/fs/write', { projectId, path: relPath, content });
  },

  async editFile(
    projectId: string,
    relPath: string,
    oldString: string,
    newString: string,
    replaceAll = false,
  ): Promise<{ diff: FileDiffItem; replacements: number }> {
    return apiPost('/api/fs/edit', { projectId, path: relPath, oldString, newString, replaceAll });
  },

  async applyPatch(
    projectId: string,
    patchText: string,
  ): Promise<{ diffs: FileDiffItem[]; summary: string }> {
    return apiPost('/api/fs/patch', { projectId, patchText });
  },

  async deletePath(
    projectId: string,
    relPath: string,
  ): Promise<{ diff?: FileDiffItem; deletedCount: number }> {
    return apiPost('/api/fs/delete', { projectId, path: relPath });
  },

  async mkdir(projectId: string, relPath: string): Promise<void> {
    await apiPost('/api/fs/mkdir', { projectId, path: relPath });
  },

  async renamePath(projectId: string, oldPath: string, newPath: string): Promise<void> {
    await apiPost('/api/fs/rename', { projectId, oldPath, newPath });
  },

  async globFiles(projectId: string, pattern: string): Promise<{ matches: string[] }> {
    return apiPost('/api/fs/glob', { projectId, pattern });
  },

  async grepFiles(
    projectId: string,
    pattern: string,
    include?: string,
  ): Promise<{ matches: Array<{ path: string; line: number; text: string }> }> {
    return apiPost('/api/fs/grep', { projectId, pattern, include });
  },

  // Snapshots & Diffs (1:1 OpenCode session review & revert)
  async createSnapshot(projectId: string): Promise<{ snapshotId: string }> {
    return apiPost('/api/snapshots/create', { projectId });
  },

  async diffSnapshot(projectId: string, snapshotId: string): Promise<{ diffs: FileDiffItem[] }> {
    return apiPost('/api/snapshots/diff', { projectId, snapshotId });
  },

  async revertSnapshot(projectId: string, snapshotId: string): Promise<{ restoredFiles: number }> {
    return apiPost('/api/snapshots/revert', { projectId, snapshotId });
  },

  // Real Shell Execution
  async execShell(
    projectId: string,
    command: string,
    timeoutMs = 45000,
  ): Promise<{ stdout: string; stderr: string; exitCode: number; durationMs: number; cwd: string }> {
    return apiPost('/api/shell/exec', { projectId, command, timeoutMs });
  },

  // CORS-Free WebFetch & Streaming Proxy (runs through ForegroundService on Android!)
  async proxyFetchText(url: string): Promise<{ status: number; content: string; contentType: string }> {
    return apiPost('/api/proxy/fetch', { url });
  },

  async proxyStream(
    targetUrl: string,
    method: string,
    headers: Record<string, string>,
    body: unknown,
    signal?: AbortSignal,
  ): Promise<Response> {
    return fetch(`${getApiBase()}/api/proxy/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: targetUrl, method, headers, body }),
      signal,
    });
  },
};
