import React from 'react';
import {
  Activity,
  Download,
  FolderGit2,
  FolderPlus,
  MessageSquare,
  Plus,
  Radio,
  Settings,
  Trash2,
  X,
} from 'lucide-react';
import type { DaemonStatus, ProjectInfo, RemoteServerConfig, SessionInfo } from '../types/opencode';
import { OpenCodeWordmark } from './Logo';
import { t } from '../i18n/translations';
import { isAndroidApp } from '../bridge/platformBridge';

interface SidebarProps {
  open: boolean;
  locale: 'ru' | 'en';
  projects: ProjectInfo[];
  activeProjectId: string;
  sessions: SessionInfo[];
  activeSessionId: string;
  daemon: DaemonStatus;
  remoteConfig: RemoteServerConfig;
  apkAvailable: boolean;
  onClose: () => void;
  onSelectProject: (id: string) => void;
  onDeleteProject: (id: string) => void;
  onOpenNewProject: () => void;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onOpenSettings: () => void;
  onOpenRemoteModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  open,
  locale,
  projects,
  activeProjectId,
  sessions,
  activeSessionId,
  daemon,
  remoteConfig,
  apkAvailable,
  onClose,
  onSelectProject,
  onDeleteProject,
  onOpenNewProject,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onOpenSettings,
  onOpenRemoteModal,
}) => {
  const projectSessions = sessions
    .filter((s) => s.projectId === activeProjectId)
    .sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <>
      <div className={`oc-sidebar-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`oc-sidebar ${open ? 'open' : ''}`}>
        {/* Brand Top Bar */}
        <div
          style={{
            height: 48,
            padding: '0 14px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <OpenCodeWordmark height={18} />
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '1px 5px',
                borderRadius: 4,
                background: 'var(--bg-elevated)',
                color: 'var(--primary)',
                letterSpacing: '0.04em',
              }}
            >
              ANDROID
            </span>
          </div>
          <button className="oc-icon-btn" onClick={onClose} title="Закрыть панель" style={{ width: 30, height: 30 }}>
            <X size={16} />
          </button>
        </div>

        {/* Projects Section */}
        <div style={{ padding: '12px 10px 6px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 4px 6px',
              fontSize: 11,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--text-muted)',
            }}
          >
            <span>{t(locale, 'sidebar.projects')}</span>
            <button
              onClick={onOpenNewProject}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                color: 'var(--primary)',
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              <FolderPlus size={13} />
              <span>+</span>
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 165, overflowY: 'auto' }}>
            {projects.map((p) => {
              const isSelected = p.id === activeProjectId;
              return (
                <div
                  key={p.id}
                  onClick={() => onSelectProject(p.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    padding: '7px 9px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                    color: isSelected ? 'var(--text-strong)' : 'var(--text-base)',
                    border: isSelected ? '1px solid var(--border-strong)' : '1px solid transparent',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <FolderGit2 size={15} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: isSelected ? 600 : 400 }}>
                      {p.name}
                    </span>
                  </div>
                  {projects.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteProject(p.id);
                      }}
                      title="Удалить локальный проект"
                      style={{ color: 'var(--text-muted)', padding: 2, opacity: 0.7 }}
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Sessions Section */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
            padding: '8px 10px',
            borderTop: '1px solid var(--border)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 4px 8px',
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--text-muted)',
              }}
            >
              {t(locale, 'sidebar.sessions')}
            </span>
            <button
              onClick={() => {
                onNewSession();
                if (window.innerWidth < 860) onClose();
              }}
              className="oc-pill"
              style={{ height: 24, padding: '0 8px', fontSize: 11 }}
            >
              <Plus size={12} />
              <span>{t(locale, 'sidebar.newSession')}</span>
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
            {projectSessions.map((s) => {
              const active = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  onClick={() => {
                    onSelectSession(s.id);
                    if (window.innerWidth < 860) onClose();
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 6,
                    padding: '8px 9px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: active ? 'var(--bg-raised)' : 'transparent',
                    borderLeft: active ? '2px solid var(--primary)' : '2px solid transparent',
                    color: active ? 'var(--text-strong)' : 'var(--text-base)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <MessageSquare size={14} style={{ color: active ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12.5 }}>
                        {s.title}
                      </div>
                      <div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>
                        {s.agent} • {s.messages.length} сообщ.
                      </div>
                    </div>
                  </div>
                  {projectSessions.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(s.id);
                      }}
                      style={{ color: 'var(--text-muted)', padding: 2, opacity: 0.65 }}
                      title="Удалить сессию"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer: Android Foreground Daemon + PC Remote + APK Download + Settings */}
        <div
          style={{
            padding: 10,
            borderTop: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            background: 'var(--bg-deep)',
          }}
        >
          {/* Background Daemon Status Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 10px',
              borderRadius: 8,
              background: 'var(--bg-raised)',
              border: '1px solid var(--border)',
              fontSize: 11.5,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: daemon.running ? (daemon.busy ? 'var(--warning)' : 'var(--success)') : 'var(--danger)',
                boxShadow: daemon.running ? '0 0 8px var(--success)' : 'none',
                flexShrink: 0,
              }}
            />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 600, color: 'var(--text-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {daemon.busy ? t(locale, 'sidebar.daemonBusy') : t(locale, 'sidebar.daemonActive')}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {daemon.currentTask || daemon.daemonUrl}
              </div>
            </div>
            <Activity size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
          </div>

          {!isAndroidApp() && apkAvailable && (
            <a
              href="/download/OpenCode-Android-v2.2.5.apk"
              download="OpenCode-Android-v2.2.5.apk"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 7,
                padding: '8px 10px',
                borderRadius: 8,
                background: 'var(--primary)',
                color: 'var(--primary-fg)',
                fontWeight: 600,
                fontSize: 12,
                textDecoration: 'none',
              }}
            >
              <Download size={14} />
              <span>{t(locale, 'sidebar.downloadApk')}</span>
            </a>
          )}

          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={onOpenRemoteModal}
              className="oc-pill"
              style={{
                flex: 1,
                justifyContent: 'center',
                height: 32,
                borderColor: remoteConfig.enabled && remoteConfig.connected ? 'var(--success)' : undefined,
              }}
            >
              <Radio size={13} style={{ color: remoteConfig.enabled && remoteConfig.connected ? 'var(--success)' : 'var(--text-muted)' }} />
              <span>{remoteConfig.enabled ? 'ПК активен' : t(locale, 'sidebar.connectPc')}</span>
            </button>
            <button
              onClick={onOpenSettings}
              className="oc-pill"
              style={{ flex: 1, justifyContent: 'center', height: 32 }}
            >
              <Settings size={13} />
              <span>{t(locale, 'sidebar.settings')}</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};
