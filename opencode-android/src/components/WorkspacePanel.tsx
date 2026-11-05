import React, { useEffect, useState } from 'react';
import {
  Archive,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Edit3,
  FileCode,
  FilePlus,
  Folder,
  FolderOpen,
  FolderPlus,
  GitCompare,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Square,
  Terminal as TerminalIcon,
  Trash2,
  X,
} from 'lucide-react';
import type { FileDiffItem, FileNode, TodoItem } from '../types/opencode';
import { PlatformBridge } from '../bridge/platformBridge';
import { t } from '../i18n/translations';

export type WorkspaceTab = 'review' | 'files' | 'terminal' | 'todos';

interface WorkspacePanelProps {
  locale: 'ru' | 'en';
  projectId: string;
  activeTab: WorkspaceTab;
  tree: FileNode[];
  sessionDiffs: FileDiffItem[];
  todos: TodoItem[];
  selectedFilePath: string | null;
  lastSnapshotId?: string;
  onSelectTab: (tab: WorkspaceTab) => void;
  onClose: () => void;
  onRefreshWorkspace: () => void;
  onSelectFile: (relPath: string | null) => void;
  onRevertLastSnapshot: () => void;
  onToggleTodo: (id: string) => void;
}

const TreeItem: React.FC<{
  node: FileNode;
  depth: number;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
  onDeletePath: (path: string) => void;
}> = ({ node, depth, selectedPath, onSelectFile, onDeletePath }) => {
  const [open, setOpen] = useState(depth < 1);

  if (node.type === 'directory') {
    return (
      <div>
        <div
          onClick={() => setOpen((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: `5px 8px 5px ${8 + depth * 14}px`,
            cursor: 'pointer',
            borderRadius: 6,
            color: 'var(--text-base)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {open ? (
              <FolderOpen size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
            ) : (
              <Folder size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
            )}
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>
              {node.name}
            </span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDeletePath(node.path);
            }}
            title="Удалить папку"
            style={{ color: 'var(--text-muted)', opacity: 0.65, padding: 2 }}
          >
            <Trash2 size={12} />
          </button>
        </div>
        {open &&
          node.children?.map((child) => (
            <TreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelectFile={onSelectFile}
              onDeletePath={onDeletePath}
            />
          ))}
      </div>
    );
  }

  const isSelected = selectedPath === node.path;
  return (
    <div
      onClick={() => onSelectFile(node.path)}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: `5px 8px 5px ${22 + depth * 14}px`,
        cursor: 'pointer',
        borderRadius: 6,
        background: isSelected ? 'var(--bg-elevated)' : 'transparent',
        color: isSelected ? 'var(--text-strong)' : 'var(--text-base)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <FileCode size={13} style={{ color: isSelected ? 'var(--primary)' : 'var(--text-muted)', flexShrink: 0 }} />
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {node.name}
        </span>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDeletePath(node.path);
        }}
        title="Удалить файл"
        style={{ color: 'var(--text-muted)', opacity: 0.65, padding: 2 }}
      >
        <Trash2 size={12} />
      </button>
    </div>
  );
};

export const WorkspacePanel: React.FC<WorkspacePanelProps> = ({
  locale,
  projectId,
  activeTab,
  tree,
  sessionDiffs,
  todos,
  selectedFilePath,
  lastSnapshotId,
  onSelectTab,
  onClose,
  onRefreshWorkspace,
  onSelectFile,
  onRevertLastSnapshot,
  onToggleTodo,
}) => {
  const [editorContent, setEditorContent] = useState('');
  const [editorDirty, setEditorDirty] = useState(false);
  const [editorStatus, setEditorStatus] = useState('');
  const [creatingType, setCreatingType] = useState<'file' | 'folder' | null>(null);
  const [newPathInput, setNewPathInput] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [renameInput, setRenameInput] = useState('');

  // Terminal state
  const [termCmd, setTermCmd] = useState('');
  const [termRunning, setTermRunning] = useState(false);
  const [termLogs, setTermLogs] = useState<Array<{ cmd: string; out: string; code: number }>>([
    {
      cmd: 'opencode --version',
      out: 'OpenCode Android Daemon v2.2.5 • POSIX /system/bin/sh ready.',
      code: 0,
    },
  ]);

  useEffect(() => {
    if (!selectedFilePath || !projectId) return;
    let cancelled = false;
    setEditorStatus('Загрузка…');
    PlatformBridge.readFile(projectId, selectedFilePath, 1, 5000)
      .then((res) => {
        if (cancelled) return;
        setEditorContent(res.content);
        setEditorDirty(false);
        setEditorStatus(`${res.totalLines} стр. • ${res.size} байт`);
        setRenameInput(selectedFilePath);
      })
      .catch((err) => {
        if (!cancelled) setEditorStatus(`Ошибка: ${err.message}`);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFilePath, projectId]);

  const handleSaveFile = async () => {
    if (!selectedFilePath) return;
    await PlatformBridge.writeFile(projectId, selectedFilePath, editorContent);
    setEditorDirty(false);
    setEditorStatus('Сохранено ✓');
    onRefreshWorkspace();
  };

  const handleCreateItem = async () => {
    const clean = newPathInput.trim().replace(/^\/+/, '');
    if (!clean || !creatingType) return;
    if (creatingType === 'file') {
      await PlatformBridge.writeFile(projectId, clean, '');
      onRefreshWorkspace();
      onSelectFile(clean);
    } else {
      await PlatformBridge.mkdir(projectId, clean);
      onRefreshWorkspace();
    }
    setNewPathInput('');
    setCreatingType(null);
  };

  const handleDeletePath = async (relPath: string) => {
    await PlatformBridge.deletePath(projectId, relPath);
    if (selectedFilePath === relPath) onSelectFile(null);
    onRefreshWorkspace();
  };

  const handleRenameSelected = async () => {
    if (!selectedFilePath || !renameInput.trim() || renameInput.trim() === selectedFilePath) {
      setRenaming(false);
      return;
    }
    const target = renameInput.trim().replace(/^\/+/, '');
    await PlatformBridge.renamePath(projectId, selectedFilePath, target);
    setRenaming(false);
    onRefreshWorkspace();
    onSelectFile(target);
  };

  const runTerminalCommand = async (cmdOverride?: string) => {
    const command = (cmdOverride ?? termCmd).trim();
    if (!command) return;
    if (command === 'clear') {
      setTermLogs([]);
      setTermCmd('');
      return;
    }
    setTermCmd('');
    setTermRunning(true);
    try {
      const res = await PlatformBridge.execShell(projectId, command, 45000);
      const output = [res.stdout, res.stderr].filter(Boolean).join('\n').trim() || `(exit ${res.exitCode})`;
      setTermLogs((prev) => [...prev, { cmd: command, out: output, code: res.exitCode }]);
      onRefreshWorkspace();
    } catch (err: any) {
      setTermLogs((prev) => [...prev, { cmd: command, out: err.message || String(err), code: 1 }]);
    } finally {
      setTermRunning(false);
    }
  };

  return (
    <section className="oc-workspace-panel">
      {/* Top Panel Tabs */}
      <div
        style={{
          height: 48,
          minHeight: 48,
          padding: '0 10px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          background: 'var(--bg-raised)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflowX: 'auto' }}>
          <button
            onClick={() => onSelectTab('review')}
            className={`oc-pill ${activeTab === 'review' ? 'active' : ''}`}
          >
            <GitCompare size={13} />
            <span>{t(locale, 'header.review')}</span>
            {sessionDiffs.length > 0 && (
              <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{sessionDiffs.length}</span>
            )}
          </button>
          <button
            onClick={() => onSelectTab('files')}
            className={`oc-pill ${activeTab === 'files' ? 'active' : ''}`}
          >
            <Folder size={13} />
            <span>{t(locale, 'header.files')}</span>
          </button>
          <button
            onClick={() => onSelectTab('terminal')}
            className={`oc-pill ${activeTab === 'terminal' ? 'active' : ''}`}
          >
            <TerminalIcon size={13} />
            <span>{t(locale, 'header.terminal')}</span>
          </button>
          <button
            onClick={() => onSelectTab('todos')}
            className={`oc-pill ${activeTab === 'todos' ? 'active' : ''}`}
          >
            <CheckSquare size={13} />
            <span>{t(locale, 'header.todos')}</span>
            {todos.length > 0 && <span>{todos.length}</span>}
          </button>
        </div>

        <button className="oc-icon-btn" onClick={onClose} title="Закрыть панель">
          <X size={16} />
        </button>
      </div>

      {/* TAB 1: REVIEW DIFFS */}
      {activeTab === 'review' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {lastSnapshotId && sessionDiffs.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Изменено файлов: {sessionDiffs.length}
              </span>
              <button className="oc-pill" onClick={onRevertLastSnapshot}>
                <RotateCcw size={12} /> Откатить все изменения
              </button>
            </div>
          )}

          {sessionDiffs.length === 0 ? (
            <div style={{ padding: 28, textAlign: 'center', color: 'var(--text-muted)' }}>
              {t(locale, 'panel.review.empty')}
            </div>
          ) : (
            sessionDiffs.map((d) => (
              <div key={d.path} className="oc-tool-card">
                <div
                  className="oc-tool-header"
                  onClick={() => {
                    onSelectFile(d.path);
                    onSelectTab('files');
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-strong)' }}>
                    {d.path}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>
                    <span style={{ color: 'var(--diff-add-fg)' }}>+{d.additions}</span>{' '}
                    <span style={{ color: 'var(--diff-del-fg)' }}>-{d.deletions}</span>
                  </span>
                </div>
                <div className="oc-tool-body">
                  {d.unifiedDiff.split('\n').map((line, i) => {
                    const cls = line.startsWith('+') && !line.startsWith('+++')
                      ? 'add'
                      : line.startsWith('-') && !line.startsWith('---')
                        ? 'del'
                        : line.startsWith('@@')
                          ? 'hunk'
                          : '';
                    return (
                      <div key={i} className={`oc-diff-line ${cls}`}>
                        {line}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* TAB 2: FILE EXPLORER & BUILT-IN CODE EDITOR */}
      {activeTab === 'files' && (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {/* File Toolbar */}
          <div
            style={{
              padding: '8px 10px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              flexWrap: 'wrap',
            }}
          >
            <button className="oc-pill" onClick={() => setCreatingType('file')}>
              <FilePlus size={13} /> {t(locale, 'panel.files.newFile')}
            </button>
            <button className="oc-pill" onClick={() => setCreatingType('folder')}>
              <FolderPlus size={13} /> {t(locale, 'panel.files.newFolder')}
            </button>
            <button className="oc-pill" onClick={() => PlatformBridge.exportProjectZip(projectId)}>
              <Archive size={13} /> {t(locale, 'panel.files.exportZip')}
            </button>
            <button className="oc-icon-btn" onClick={onRefreshWorkspace} style={{ marginLeft: 'auto', height: 28 }}>
              <RefreshCw size={13} />
            </button>
          </div>

          {creatingType && (
            <div
              style={{
                padding: '8px 10px',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                gap: 6,
                background: 'var(--bg-raised)',
              }}
            >
              <input
                autoFocus
                value={newPathInput}
                onChange={(e) => setNewPathInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateItem()}
                placeholder={creatingType === 'file' ? 'src/newFile.ts' : 'src/components'}
                style={{
                  flex: 1,
                  height: 30,
                  padding: '0 8px',
                  borderRadius: 6,
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-deep)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                }}
              />
              <button className="oc-send-btn" style={{ height: 30 }} onClick={handleCreateItem}>
                Создать
              </button>
              <button className="oc-pill" style={{ height: 30 }} onClick={() => setCreatingType(null)}>
                Отмена
              </button>
            </div>
          )}

          {/* File Tree + Code Editor Split */}
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div
              style={{
                maxHeight: selectedFilePath ? '36%' : '100%',
                overflowY: 'auto',
                padding: 6,
                borderBottom: selectedFilePath ? '1px solid var(--border)' : 'none',
              }}
            >
              {tree.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                  Папка проекта пуста. Создайте файл или попросите агента!
                </div>
              ) : (
                tree.map((node) => (
                  <TreeItem
                    key={node.path}
                    node={node}
                    depth={0}
                    selectedPath={selectedFilePath}
                    onSelectFile={onSelectFile}
                    onDeletePath={handleDeletePath}
                  />
                ))
              )}
            </div>

            {selectedFilePath && (
              <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: 'var(--bg-base)' }}>
                <div
                  style={{
                    padding: '6px 10px',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--bg-raised)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 6,
                  }}
                >
                  {renaming ? (
                    <div style={{ display: 'flex', gap: 4, flex: 1 }}>
                      <input
                        value={renameInput}
                        onChange={(e) => setRenameInput(e.target.value)}
                        style={{
                          flex: 1,
                          height: 26,
                          padding: '0 6px',
                          borderRadius: 5,
                          border: '1px solid var(--primary)',
                          background: 'var(--bg-deep)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: 11.5,
                        }}
                      />
                      <button className="oc-pill" style={{ height: 26 }} onClick={handleRenameSelected}>
                        OK
                      </button>
                    </div>
                  ) : (
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--text-strong)' }}>
                        {selectedFilePath} {editorDirty ? '●' : ''}
                      </div>
                      <div style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>{editorStatus}</div>
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <button
                      className="oc-icon-btn"
                      style={{ height: 28, width: 28 }}
                      onClick={() => setRenaming((v) => !v)}
                      title="Переименовать"
                    >
                      <Edit3 size={13} />
                    </button>
                    <button
                      className="oc-send-btn"
                      style={{ height: 28, padding: '0 10px' }}
                      disabled={!editorDirty}
                      onClick={handleSaveFile}
                    >
                      <Save size={12} /> {t(locale, 'panel.files.save')}
                    </button>
                    <button
                      className="oc-icon-btn"
                      style={{ height: 28, width: 28 }}
                      onClick={() => onSelectFile(null)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>

                <textarea
                  value={editorContent}
                  onChange={(e) => {
                    setEditorContent(e.target.value);
                    setEditorDirty(true);
                  }}
                  spellCheck={false}
                  style={{
                    flex: 1,
                    width: '100%',
                    border: 'none',
                    outline: 'none',
                    resize: 'none',
                    padding: 12,
                    background: 'var(--bg-deep)',
                    color: 'var(--text-strong)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12.5,
                    lineHeight: 1.55,
                  }}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: REAL ANDROID POSIX TERMINAL */}
      {activeTab === 'terminal' && (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: '#0a0a0c' }}>
          {/* Touch Quick-Command Row for Android */}
          <div
            style={{
              padding: '6px 8px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              gap: 5,
              overflowX: 'auto',
              background: 'var(--bg-raised)',
            }}
          >
            {['ls -la', 'pwd', 'uname -a', 'find . -maxdepth 2', 'df -h', 'clear'].map((quick) => (
              <button
                key={quick}
                onClick={() => runTerminalCommand(quick)}
                className="oc-pill"
                style={{ height: 24, fontFamily: 'var(--font-mono)', fontSize: 11 }}
              >
                {quick}
              </button>
            ))}
          </div>

          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: 12,
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            {termLogs.map((entry, idx) => (
              <div key={idx}>
                <div style={{ color: 'var(--primary)', fontWeight: 600 }}>$ {entry.cmd}</div>
                <pre
                  style={{
                    margin: '4px 0 0',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: entry.code === 0 ? '#d8d8e0' : 'var(--danger)',
                  }}
                >
                  {entry.out}
                </pre>
              </div>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void runTerminalCommand();
            }}
            style={{
              padding: 8,
              borderTop: '1px solid var(--border)',
              display: 'flex',
              gap: 6,
              background: 'var(--bg-raised)',
            }}
          >
            <input
              value={termCmd}
              onChange={(e) => setTermCmd(e.target.value)}
              placeholder={t(locale, 'panel.terminal.placeholder')}
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              style={{
                flex: 1,
                height: 36,
                padding: '0 10px',
                borderRadius: 8,
                border: '1px solid var(--border-strong)',
                background: 'var(--bg-deep)',
                fontFamily: 'var(--font-mono)',
                fontSize: 12.5,
              }}
            />
            <button type="submit" className="oc-send-btn" disabled={termRunning || !termCmd.trim()}>
              <Play size={13} /> {t(locale, 'panel.terminal.run')}
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: TODOS */}
      {activeTab === 'todos' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {todos.length === 0 ? (
            <div style={{ padding: 28, textAlign: 'center', color: 'var(--text-muted)' }}>
              Список задач пуст — агент автоматически наполняет его при многошаговой разработке (todowrite).
            </div>
          ) : (
            todos.map((item) => (
              <div
                key={item.id}
                onClick={() => onToggleTodo(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border)',
                  cursor: 'pointer',
                }}
              >
                {item.status === 'completed' ? (
                  <CheckSquare size={15} style={{ color: 'var(--success)', flexShrink: 0 }} />
                ) : (
                  <Square size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                )}
                <span
                  style={{
                    textDecoration: item.status === 'completed' ? 'line-through' : 'none',
                    color: item.status === 'completed' ? 'var(--text-muted)' : 'var(--text-strong)',
                  }}
                >
                  {item.content}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </section>
  );
};
