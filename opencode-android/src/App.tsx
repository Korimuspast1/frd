import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FolderTree,
  GitCompare,
  Menu,
  Plus,
  Settings,
  Terminal as TerminalIcon,
} from 'lucide-react';
import type {
  AgentId,
  AppSettings,
  AttachmentItem,
  DaemonStatus,
  EffortLevel,
  FileDiffItem,
  FileNode,
  PermissionRequest,
  ProjectInfo,
  ProviderConfig,
  ProviderId,
  QuestionRequest,
  RemoteServerConfig,
  SessionInfo,
  SessionMessage,
} from './types/opencode';
import {
  DEFAULT_PROVIDERS,
  OPENCODE_THEMES,
  resolveActiveModel,
} from './themes/presets';
import { PlatformBridge } from './bridge/platformBridge';
import { runOpenCodeAgentTurn } from './engine/agentLoop';
import { RemoteOpenCodeClient } from './engine/remoteOpenCode';
import { Sidebar } from './components/Sidebar';
import { Timeline } from './components/Timeline';
import { Composer } from './components/Composer';
import { WorkspacePanel, type WorkspaceTab } from './components/WorkspacePanel';
import {
  ModelPickerModal,
  NewProjectModal,
  RemoteServerModal,
  SettingsModal,
} from './components/Modals';

const STORAGE_SETTINGS = 'opencode_android_settings_v2';
const STORAGE_PROVIDERS = 'opencode_android_providers_v2';
const STORAGE_SESSIONS = 'opencode_android_sessions_v2';
const STORAGE_REMOTE = 'opencode_android_remote_v2';

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export const App: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>(() =>
    loadJson<AppSettings>(STORAGE_SETTINGS, {
      locale: 'ru',
      themeId: 'oc-2',
      colorMode: 'dark',
      selectedProvider: 'demo',
      selectedModel: 'opencode-local-agent',
      effort: 'medium',
      permissionPolicy: 'auto',
      backgroundKeepAlive: true,
      notificationsEnabled: true,
      terminalFontSize: 12,
      editorWordWrap: true,
      showThinking: true,
      autoCompactContext: true,
    }),
  );

  const [providers, setProviders] = useState<ProviderConfig[]>(() =>
    loadJson<ProviderConfig[]>(STORAGE_PROVIDERS, DEFAULT_PROVIDERS),
  );

  const [remoteConfig, setRemoteConfig] = useState<RemoteServerConfig>(() =>
    loadJson<RemoteServerConfig>(STORAGE_REMOTE, { enabled: false, url: '' }),
  );

  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string>('');
  const [tree, setTree] = useState<FileNode[]>([]);
  const [flatFiles, setFlatFiles] = useState<string[]>([]);
  const [sessionDiffs, setSessionDiffs] = useState<FileDiffItem[]>([]);
  const [baselineSnapshotId, setBaselineSnapshotId] = useState<string | undefined>();

  const [sessions, setSessions] = useState<SessionInfo[]>(() =>
    loadJson<SessionInfo[]>(STORAGE_SESSIONS, []),
  );
  const [activeSessionId, setActiveSessionId] = useState<string>('');

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(() => window.innerWidth >= 1120);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('files');
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  const [modal, setModal] = useState<'models' | 'settings' | 'newProject' | 'remote' | null>(null);
  const [daemon, setDaemon] = useState<DaemonStatus>({
    running: true,
    platform: PlatformBridge.isAndroid() ? 'android' : 'web',
    daemonUrl: '127.0.0.1',
    foregroundService: PlatformBridge.isAndroid(),
    busy: false,
    currentTask: 'OpenCode готов',
  });
  const [apkAvailable, setApkAvailable] = useState(false);

  const [pendingPermission, setPendingPermission] = useState<PermissionRequest | null>(null);
  const permissionResolverRef = useRef<
    ((decision: 'approved_once' | 'approved_always' | 'rejected') => void) | null
  >(null);

  const [pendingQuestion, setPendingQuestion] = useState<QuestionRequest | null>(null);
  const questionResolverRef = useRef<((ans: string) => void) | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const alwaysAllowedToolsRef = useRef<Set<string>>(new Set());

  // Persist state
  useEffect(() => {
    localStorage.setItem(STORAGE_SETTINGS, JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    localStorage.setItem(STORAGE_PROVIDERS, JSON.stringify(providers));
  }, [providers]);

  useEffect(() => {
    localStorage.setItem(STORAGE_SESSIONS, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem(STORAGE_REMOTE, JSON.stringify(remoteConfig));
  }, [remoteConfig]);

  // Apply OpenCode Theme CSS variables & sync Android System Bars!
  useEffect(() => {
    const theme = OPENCODE_THEMES.find((t) => t.id === settings.themeId) ?? OPENCODE_THEMES[0];
    const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true;
    const isDark = settings.colorMode === 'system' ? prefersDark : settings.colorMode === 'dark';
    const p = isDark ? theme.dark : theme.light;
    const root = document.documentElement;

    root.style.setProperty('--bg-deep', p.bgDeep);
    root.style.setProperty('--bg-base', p.bgBase);
    root.style.setProperty('--bg-raised', p.bgRaised);
    root.style.setProperty('--bg-elevated', p.bgElevated);
    root.style.setProperty('--bg-hover', p.bgHover);
    root.style.setProperty('--border', p.border);
    root.style.setProperty('--border-strong', p.borderStrong);
    root.style.setProperty('--text-strong', p.textStrong);
    root.style.setProperty('--text-base', p.textBase);
    root.style.setProperty('--text-muted', p.textMuted);
    root.style.setProperty('--primary', p.primary);
    root.style.setProperty('--primary-fg', p.primaryFg);
    root.style.setProperty('--accent', p.accent);
    root.style.setProperty('--success', p.success);
    root.style.setProperty('--warning', p.warning);
    root.style.setProperty('--danger', p.danger);
    root.style.setProperty('--diff-add-bg', p.diffAddBg);
    root.style.setProperty('--diff-add-fg', p.diffAddFg);
    root.style.setProperty('--diff-del-bg', p.diffDelBg);
    root.style.setProperty('--diff-del-fg', p.diffDelFg);

    PlatformBridge.syncSystemTheme(p.bgBase, isDark);
  }, [settings.themeId, settings.colorMode]);

  // Register Android Native Keyboard Inset & Hardware Back Gesture handlers!
  useEffect(() => {
    window.__onAndroidKeyboardInset = (px: number) => {
      document.documentElement.style.setProperty('--kb-inset', `${Math.max(0, px)}px`);
    };
    window.__onAndroidBackPressed = () => {
      if (modal) {
        setModal(null);
        return true;
      }
      if (sidebarOpen) {
        setSidebarOpen(false);
        return true;
      }
      if (workspaceOpen && window.innerWidth < 960) {
        setWorkspaceOpen(false);
        return true;
      }
      return false;
    };
  }, [modal, sidebarOpen, workspaceOpen]);

  // Load projects & daemon health on mount
  useEffect(() => {
    const init = async () => {
      const status = await PlatformBridge.getDaemonStatus();
      setDaemon(status);
      const list = await PlatformBridge.listProjects();
      setProjects(list);
      if (list.length > 0) {
        setActiveProjectId((prev) => (list.some((x) => x.id === prev) ? prev : list[0].id));
      }
      if (!PlatformBridge.isAndroid()) {
        fetch('/download/OpenCode-Android-v2.2.5.apk', { method: 'HEAD' })
          .then((r) => setApkAvailable(r.ok))
          .catch(() => {});
      }
    };
    void init();
    const timer = setInterval(async () => {
      const st = await PlatformBridge.getDaemonStatus();
      setDaemon(st);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const refreshWorkspace = useCallback(async () => {
    if (!activeProjectId) return;
    try {
      const res = await PlatformBridge.listTree(activeProjectId);
      setTree(res.tree);
      setFlatFiles(res.flatFiles);
      if (baselineSnapshotId) {
        const d = await PlatformBridge.diffSnapshot(activeProjectId, baselineSnapshotId);
        setSessionDiffs(d.diffs);
      }
    } catch {
      // ignore
    }
  }, [activeProjectId, baselineSnapshotId]);

  // Ensure an active session exists for the selected project & capture baseline snapshot
  useEffect(() => {
    if (!activeProjectId) return;
    void PlatformBridge.createSnapshot(activeProjectId).then((snap) => {
      setBaselineSnapshotId(snap.snapshotId);
      setSessionDiffs([]);
      void PlatformBridge.listTree(activeProjectId).then((res) => {
        setTree(res.tree);
        setFlatFiles(res.flatFiles);
      });
    });

    setSessions((prev) => {
      const forProj = prev.filter((s) => s.projectId === activeProjectId);
      if (forProj.length > 0) {
        setActiveSessionId((cur) => (forProj.some((x) => x.id === cur) ? cur : forProj[0].id));
        return prev;
      }
      const fresh: SessionInfo = {
        id: `ses_${Date.now()}`,
        projectId: activeProjectId,
        title: 'Новая сессия',
        agent: 'build',
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messages: [],
        todos: [],
      };
      setActiveSessionId(fresh.id);
      return [fresh, ...prev];
    });
  }, [activeProjectId]);

  const activeProject = useMemo(
    () => projects.find((p) => p.id === activeProjectId) ?? projects[0],
    [projects, activeProjectId],
  );

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId),
    [sessions, activeSessionId],
  );

  const { model: activeModel } = useMemo(
    () => resolveActiveModel(settings.selectedProvider, settings.selectedModel, providers),
    [settings.selectedProvider, settings.selectedModel, providers],
  );

  const isStreaming = Boolean(
    activeSession?.messages.some((m) => m.isStreaming),
  );

  const updateSession = useCallback((sessionId: string, updater: (s: SessionInfo) => SessionInfo) => {
    setSessions((prev) => prev.map((s) => (s.id === sessionId ? updater(s) : s)));
  }, []);

  const handleNewSession = () => {
    if (!activeProjectId) return;
    const fresh: SessionInfo = {
      id: `ses_${Date.now()}`,
      projectId: activeProjectId,
      title: 'Новая сессия',
      agent: 'build',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
      todos: [],
    };
    setSessions((prev) => [fresh, ...prev]);
    setActiveSessionId(fresh.id);
  };

  const handleRevertSnapshot = async (snapshotId: string) => {
    if (!activeProjectId) return;
    await PlatformBridge.revertSnapshot(activeProjectId, snapshotId);
    await refreshWorkspace();
  };

  const handleSend = async (
    promptText: string,
    attachments: AttachmentItem[],
    mentionedFiles: string[],
    overrideAgent?: AgentId,
  ) => {
    if (!activeProject || !activeSession) return;
    PlatformBridge.vibrate();

    const targetAgent = overrideAgent ?? activeSession.agent;
    const snap = await PlatformBridge.createSnapshot(activeProject.id);
    if (!baselineSnapshotId) setBaselineSnapshotId(snap.snapshotId);

    const userMsg: SessionMessage = {
      id: `msg_u_${Date.now()}`,
      role: 'user',
      createdAt: Date.now(),
      agent: targetAgent,
      text: promptText,
      attachments,
      mentionedFiles,
      snapshotId: snap.snapshotId,
    };

    const assistantMsgId = `msg_a_${Date.now() + 1}`;
    const assistantMsg: SessionMessage = {
      id: assistantMsgId,
      role: 'assistant',
      createdAt: Date.now() + 1,
      agent: targetAgent,
      modelId: remoteConfig.enabled ? `remote (${remoteConfig.url})` : activeModel.name,
      providerId: settings.selectedProvider,
      text: '',
      toolCalls: [],
      isStreaming: true,
    };

    const priorMessages = activeSession.messages;
    const currentSessionId = activeSession.id;

    updateSession(currentSessionId, (s) => ({
      ...s,
      agent: targetAgent,
      title: s.messages.length === 0 ? promptText.slice(0, 44) : s.title,
      updatedAt: Date.now(),
      messages: [...s.messages, userMsg, assistantMsg],
    }));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Remote PC `opencode serve` mode if enabled!
    if (remoteConfig.enabled && remoteConfig.url) {
      try {
        const res = await RemoteOpenCodeClient.sendRemotePrompt({
          cfg: remoteConfig,
          remoteSessionId: activeSession.remoteSessionId,
          agent: targetAgent,
          prompt: promptText,
        });
        updateSession(currentSessionId, (s) => ({
          ...s,
          remoteSessionId: res.remoteSessionId,
          messages: s.messages.map((m) =>
            m.id === assistantMsgId ? { ...m, text: res.replyText, isStreaming: false } : m,
          ),
        }));
      } catch (err: any) {
        updateSession(currentSessionId, (s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.id === assistantMsgId ? { ...m, error: err.message || String(err), isStreaming: false } : m,
          ),
        }));
      }
      return;
    }

    // Autonomous Local Android OpenCode Agent Turn!
    try {
      await runOpenCodeAgentTurn({
        sessionId: currentSessionId,
        project: activeProject,
        agent: targetAgent,
        prompt: promptText,
        attachments,
        mentionedFiles,
        priorMessages,
        todos: activeSession.todos,
        settings,
        providers,
        alwaysAllowedTools: alwaysAllowedToolsRef.current,
        signal: controller.signal,
        onUpdateAssistantMessage: (updater) => {
          updateSession(currentSessionId, (s) => ({
            ...s,
            updatedAt: Date.now(),
            messages: s.messages.map((m) => (m.id === assistantMsgId ? updater(m) : m)),
          }));
        },
        onUpdateTodos: (todos) => {
          updateSession(currentSessionId, (s) => ({ ...s, todos }));
        },
        onRequestPermission: (req) =>
          new Promise((resolve) => {
            permissionResolverRef.current = resolve;
            setPendingPermission(req);
          }),
        onRequestQuestion: (req) =>
          new Promise((resolve) => {
            questionResolverRef.current = resolve;
            setPendingQuestion(req);
          }),
        onWorkspaceChanged: () => {
          void refreshWorkspace();
        },
      });
    } catch (err: any) {
      if (!controller.signal.aborted) {
        updateSession(currentSessionId, (s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.id === assistantMsgId
              ? { ...m, error: err.message || String(err), isStreaming: false }
              : m,
          ),
        }));
      }
    } finally {
      await refreshWorkspace();
    }
  };

  const handleSlashCommand = async (cmd: string) => {
    switch (cmd) {
      case '/review':
        setWorkspaceTab('review');
        setWorkspaceOpen(true);
        break;
      case '/files':
        setWorkspaceTab('files');
        setWorkspaceOpen(true);
        break;
      case '/terminal':
        setWorkspaceTab('terminal');
        setWorkspaceOpen(true);
        break;
      case '/models':
        setModal('models');
        break;
      case '/agent':
        if (activeSession) {
          updateSession(activeSession.id, (s) => ({
            ...s,
            agent: s.agent === 'build' ? 'plan' : 'build',
          }));
        }
        break;
      case '/clear':
        handleNewSession();
        break;
      case '/undo': {
        const lastUserSnap = [...(activeSession?.messages ?? [])]
          .reverse()
          .find((m) => m.snapshotId)?.snapshotId;
        if (lastUserSnap) await handleRevertSnapshot(lastUserSnap);
        break;
      }
      case '/compact':
        if (activeSession && activeSession.messages.length > 4) {
          updateSession(activeSession.id, (s) => ({
            ...s,
            messages: s.messages.slice(-6),
          }));
        }
        break;
      case '/init':
        void handleSend(
          'Проанализируй структуру проекта и создай подробный файл AGENTS.md с правилами сборки и архитектурой.',
          [],
          [],
          'build',
        );
        break;
    }
  };

  const totalAdditions = sessionDiffs.reduce((acc, d) => acc + d.additions, 0);
  const totalDeletions = sessionDiffs.reduce((acc, d) => acc + d.deletions, 0);

  return (
    <div className="oc-app">
      <Sidebar
        open={sidebarOpen}
        locale={settings.locale}
        projects={projects}
        activeProjectId={activeProjectId}
        sessions={sessions}
        activeSessionId={activeSessionId}
        daemon={daemon}
        remoteConfig={remoteConfig}
        apkAvailable={apkAvailable}
        onClose={() => setSidebarOpen(false)}
        onSelectProject={(id) => setActiveProjectId(id)}
        onDeleteProject={async (id) => {
          await PlatformBridge.deleteProject(id);
          const next = await PlatformBridge.listProjects();
          setProjects(next);
          if (next.length > 0 && activeProjectId === id) setActiveProjectId(next[0].id);
        }}
        onOpenNewProject={() => setModal('newProject')}
        onSelectSession={(id) => setActiveSessionId(id)}
        onNewSession={handleNewSession}
        onDeleteSession={(id) => {
          setSessions((prev) => {
            const rem = prev.filter((s) => s.id !== id);
            if (activeSessionId === id && rem.length > 0) setActiveSessionId(rem[0].id);
            return rem;
          });
        }}
        onOpenSettings={() => setModal('settings')}
        onOpenRemoteModal={() => setModal('remote')}
      />

      {/* Main Column */}
      <main className="oc-main">
        {/* Session Identity Top Header */}
        <header className="oc-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <button className="oc-icon-btn" onClick={() => setSidebarOpen((v) => !v)} title="Проекты и сессии">
              <Menu size={18} />
            </button>
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontWeight: 600,
                  color: 'var(--text-strong)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>{activeProject?.name ?? 'OpenCode'}</span>
                <span style={{ color: 'var(--text-muted)' }}>/</span>
                <span style={{ color: 'var(--text-base)', fontWeight: 450 }}>
                  {activeSession?.title ?? 'Сессия'}
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            {sessionDiffs.length > 0 && (
              <button
                className="oc-pill"
                onClick={() => {
                  setWorkspaceTab('review');
                  setWorkspaceOpen(true);
                }}
              >
                <GitCompare size={13} />
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--diff-add-fg)' }}>+{totalAdditions}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--diff-del-fg)' }}>-{totalDeletions}</span>
              </button>
            )}

            <button
              className={`oc-icon-btn ${workspaceOpen && workspaceTab === 'files' ? 'active' : ''}`}
              onClick={() => {
                if (workspaceOpen && workspaceTab === 'files') setWorkspaceOpen(false);
                else {
                  setWorkspaceTab('files');
                  setWorkspaceOpen(true);
                }
              }}
              title="Файлы проекта и редактор кода"
            >
              <FolderTree size={16} />
            </button>

            <button
              className={`oc-icon-btn ${workspaceOpen && workspaceTab === 'terminal' ? 'active' : ''}`}
              onClick={() => {
                if (workspaceOpen && workspaceTab === 'terminal') setWorkspaceOpen(false);
                else {
                  setWorkspaceTab('terminal');
                  setWorkspaceOpen(true);
                }
              }}
              title="Терминал Android Shell"
            >
              <TerminalIcon size={16} />
            </button>

            <button className="oc-icon-btn" onClick={handleNewSession} title="Новая сессия">
              <Plus size={17} />
            </button>

            <button className="oc-icon-btn" onClick={() => setModal('settings')} title="Настройки и API ключи">
              <Settings size={16} />
            </button>
          </div>
        </header>

        {/* Body Split: Chat Timeline + Docked/Drawer Workspace */}
        <div className="oc-body-split">
          <div className="oc-chat-pane">
            <Timeline
              locale={settings.locale}
              messages={activeSession?.messages ?? []}
              pendingPermission={pendingPermission}
              pendingQuestion={pendingQuestion}
              onResolvePermission={(decision) => {
                setPendingPermission(null);
                permissionResolverRef.current?.(decision);
              }}
              onResolveQuestion={(answer) => {
                setPendingQuestion(null);
                questionResolverRef.current?.(answer);
              }}
              onRevertToSnapshot={handleRevertSnapshot}
              onForkFromMessage={(msgId) => {
                if (!activeSession) return;
                const idx = activeSession.messages.findIndex((m) => m.id === msgId);
                if (idx < 0) return;
                const forked: SessionInfo = {
                  ...activeSession,
                  id: `ses_fork_${Date.now()}`,
                  title: `${activeSession.title} (ветка)`,
                  createdAt: Date.now(),
                  updatedAt: Date.now(),
                  messages: activeSession.messages.slice(0, idx + 1),
                };
                setSessions((prev) => [forked, ...prev]);
                setActiveSessionId(forked.id);
              }}
              onQuickPrompt={(p, ag) => void handleSend(p, [], [], ag)}
              onOpenFileInEditor={(relPath) => {
                setSelectedFilePath(relPath);
                setWorkspaceTab('files');
                setWorkspaceOpen(true);
              }}
            />

            <Composer
              locale={settings.locale}
              agent={activeSession?.agent ?? 'build'}
              activeModel={activeModel}
              effort={settings.effort}
              isStreaming={isStreaming}
              flatFiles={flatFiles}
              onToggleAgent={() => {
                if (!activeSession) return;
                updateSession(activeSession.id, (s) => ({
                  ...s,
                  agent: s.agent === 'build' ? 'plan' : 'build',
                }));
              }}
              onCycleEffort={() => {
                const order: EffortLevel[] = ['low', 'medium', 'high'];
                const next = order[(order.indexOf(settings.effort) + 1) % order.length];
                setSettings((s) => ({ ...s, effort: next }));
              }}
              onOpenModelPicker={() => setModal('models')}
              onSend={(t, att, men) => void handleSend(t, att, men)}
              onStop={() => {
                abortControllerRef.current?.abort();
                if (activeSession) {
                  updateSession(activeSession.id, (s) => ({
                    ...s,
                    messages: s.messages.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
                  }));
                }
              }}
              onSlashCommand={(cmd) => void handleSlashCommand(cmd)}
            />
          </div>

          {workspaceOpen && activeProject && (
            <WorkspacePanel
              locale={settings.locale}
              projectId={activeProject.id}
              activeTab={workspaceTab}
              tree={tree}
              sessionDiffs={sessionDiffs}
              todos={activeSession?.todos ?? []}
              selectedFilePath={selectedFilePath}
              lastSnapshotId={baselineSnapshotId}
              onSelectTab={setWorkspaceTab}
              onClose={() => setWorkspaceOpen(false)}
              onRefreshWorkspace={() => void refreshWorkspace()}
              onSelectFile={setSelectedFilePath}
              onRevertLastSnapshot={() => baselineSnapshotId && void handleRevertSnapshot(baselineSnapshotId)}
              onToggleTodo={(todoId) => {
                if (!activeSession) return;
                updateSession(activeSession.id, (s) => ({
                  ...s,
                  todos: s.todos.map((t) =>
                    t.id === todoId
                      ? { ...t, status: t.status === 'completed' ? 'pending' : 'completed' }
                      : t,
                  ),
                }));
              }}
            />
          )}
        </div>
      </main>

      {/* Modals */}
      {modal === 'models' && (
        <ModelPickerModal
          selectedProvider={settings.selectedProvider}
          selectedModel={settings.selectedModel}
          providers={providers}
          onSelect={(provider, modelId) =>
            setSettings((s) => ({ ...s, selectedProvider: provider, selectedModel: modelId }))
          }
          onOpenSettings={() => setModal('settings')}
          onClose={() => setModal(null)}
        />
      )}

      {modal === 'settings' && (
        <SettingsModal
          settings={settings}
          providers={providers}
          onUpdateSettings={(patch) => setSettings((s) => ({ ...s, ...patch }))}
          onUpdateProvider={(id, patch) => {
            setProviders((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
            // Auto-switch away from demo if user enters a real API key!
            if (patch.apiKey && settings.selectedProvider === 'demo') {
              const firstModel =
                id === 'anthropic'
                  ? 'claude-sonnet-4-5'
                  : id === 'openai'
                    ? 'gpt-4.1'
                    : id === 'google'
                      ? 'gemini-2.5-pro'
                      : id === 'deepseek'
                        ? 'deepseek-chat'
                        : id === 'groq'
                          ? 'llama-3.3-70b-versatile'
                          : id === 'xai'
                            ? 'grok-3'
                            : 'deepseek/deepseek-chat-v3-0324:free';
              setSettings((s) => ({ ...s, selectedProvider: id, selectedModel: firstModel }));
            }
          }}
          onClose={() => setModal(null)}
        />
      )}

      {modal === 'newProject' && (
        <NewProjectModal
          onCreate={async (name, template) => {
            const p = await PlatformBridge.createProject(name, template);
            const list = await PlatformBridge.listProjects();
            setProjects(list);
            setActiveProjectId(p.id);
          }}
          onCloneGithub={async (repoUrl, name) => {
            const p = await PlatformBridge.cloneGithubRepo(repoUrl, name);
            const list = await PlatformBridge.listProjects();
            setProjects(list);
            setActiveProjectId(p.id);
          }}
          onClose={() => setModal(null)}
        />
      )}

      {modal === 'remote' && (
        <RemoteServerModal
          config={remoteConfig}
          onSave={(cfg) => setRemoteConfig(cfg)}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
};
