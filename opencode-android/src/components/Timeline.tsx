import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  Brain,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode2,
  FilePlus2,
  FolderSearch,
  GitBranch,
  HelpCircle,
  Loader2,
  RotateCcw,
  ShieldAlert,
  Terminal,
  Trash2,
  User,
} from 'lucide-react';
import type {
  PermissionRequest,
  QuestionRequest,
  SessionMessage,
  ToolCallPart,
} from '../types/opencode';
import { OpenCodeMark } from './Logo';
import { PlatformBridge } from '../bridge/platformBridge';
import { t } from '../i18n/translations';

interface TimelineProps {
  locale: 'ru' | 'en';
  messages: SessionMessage[];
  pendingPermission: PermissionRequest | null;
  pendingQuestion: QuestionRequest | null;
  onResolvePermission: (decision: 'approved_once' | 'approved_always' | 'rejected') => void;
  onResolveQuestion: (answer: string) => void;
  onRevertToSnapshot: (snapshotId: string) => void;
  onForkFromMessage: (msgId: string) => void;
  onQuickPrompt: (prompt: string, agent?: 'build' | 'plan') => void;
  onOpenFileInEditor: (relPath: string) => void;
}

function SimpleMarkdown({ text }: { text: string }) {
  if (!text) return null;
  const segments = text.split(/(```[\s\S]*?```)/g);
  return (
    <div className="oc-md">
      {segments.map((seg, idx) => {
        if (seg.startsWith('```') && seg.endsWith('```')) {
          const lines = seg.slice(3, -3).split('\n');
          const lang = lines[0]?.trim() || 'code';
          const code = lines.slice(1).join('\n');
          return (
            <div key={idx} style={{ position: 'relative', margin: '8px 0' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 10px',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderBottom: 'none',
                  borderTopLeftRadius: 8,
                  borderTopRightRadius: 8,
                  fontSize: 11,
                  color: 'var(--text-muted)',
                }}
              >
                <span>{lang}</span>
                <button
                  onClick={() => PlatformBridge.copyText(code)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--text-base)', fontSize: 11 }}
                >
                  <Copy size={11} /> Копировать
                </button>
              </div>
              <pre style={{ marginTop: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
                <code>{code}</code>
              </pre>
            </div>
          );
        }
        return seg
          .split('\n\n')
          .filter(Boolean)
          .map((para, pIdx) => (
            <p key={`${idx}-${pIdx}`} style={{ whiteSpace: 'pre-wrap' }}>
              {para}
            </p>
          ));
      })}
    </div>
  );
}

function ToolCallCard({
  part,
  onOpenFile,
}: {
  part: ToolCallPart;
  onOpenFile: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(Boolean(part.diff));

  const icon = (() => {
    switch (part.tool) {
      case 'bash':
        return <Terminal size={14} style={{ color: 'var(--accent)' }} />;
      case 'write':
        return <FilePlus2 size={14} style={{ color: 'var(--success)' }} />;
      case 'edit':
      case 'apply_patch':
        return <FileCode2 size={14} style={{ color: 'var(--primary)' }} />;
      case 'delete_file':
        return <Trash2 size={14} style={{ color: 'var(--danger)' }} />;
      case 'glob':
      case 'grep':
        return <FolderSearch size={14} style={{ color: 'var(--text-muted)' }} />;
      default:
        return <Bot size={14} style={{ color: 'var(--primary)' }} />;
    }
  })();

  const statusBadge = (() => {
    if (part.status === 'running' || part.status === 'awaiting_permission' || part.status === 'awaiting_answer') {
      return <Loader2 size={14} className="oc-spin" style={{ color: 'var(--warning)' }} />;
    }
    if (part.status === 'completed') {
      return <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />;
    }
    return <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />;
  })();

  const targetFile = String(part.input.filePath ?? part.input.path ?? '');

  return (
    <div className="oc-tool-card">
      <button className="oc-tool-header" onClick={() => setExpanded((v) => !v)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {icon}
          <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{part.title}</span>
          {part.subtitle && (
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11.5,
                color: 'var(--text-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {part.subtitle}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {part.diff && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              <span style={{ color: 'var(--diff-add-fg)' }}>+{part.diff.additions}</span>{' '}
              <span style={{ color: 'var(--diff-del-fg)' }}>-{part.diff.deletions}</span>
            </span>
          )}
          {statusBadge}
        </div>
      </button>

      {expanded && (
        <div className="oc-tool-body">
          {targetFile && part.tool !== 'delete_file' && (
            <div style={{ marginBottom: 6, display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => onOpenFile(targetFile)}
                className="oc-pill"
                style={{ height: 22, fontSize: 11 }}
              >
                Открыть {targetFile} в редакторе
              </button>
            </div>
          )}

          {part.subagentMessages && part.subagentMessages.length > 0 && (
            <div style={{ marginBottom: 8, color: 'var(--text-muted)' }}>
              {part.subagentMessages.map((m, i) => (
                <div key={i}>↳ {m}</div>
              ))}
            </div>
          )}

          {part.diff ? (
            <div>
              {part.diff.unifiedDiff.split('\n').map((line, idx) => {
                const cls = line.startsWith('+') && !line.startsWith('+++')
                  ? 'add'
                  : line.startsWith('-') && !line.startsWith('---')
                    ? 'del'
                    : line.startsWith('@@')
                      ? 'hunk'
                      : '';
                return (
                  <div key={idx} className={`oc-diff-line ${cls}`}>
                    {line}
                  </div>
                );
              })}
            </div>
          ) : (
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {part.error || part.output || JSON.stringify(part.input, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export const Timeline: React.FC<TimelineProps> = ({
  locale,
  messages,
  pendingPermission,
  pendingQuestion,
  onResolvePermission,
  onResolveQuestion,
  onRevertToSnapshot,
  onForkFromMessage,
  onQuickPrompt,
  onOpenFileInEditor,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [customAnswer, setCustomAnswer] = useState('');
  const [openThinkIds, setOpenThinkIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, messages[messages.length - 1]?.text, pendingPermission, pendingQuestion]);

  if (messages.length === 0) {
    return (
      <div className="oc-timeline">
        <div
          style={{
            maxWidth: 620,
            margin: '32px auto 0',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: 14,
              background: 'var(--bg-raised)',
              border: '1px solid var(--border-strong)',
              display: 'grid',
              placeItems: 'center',
            }}
          >
            <OpenCodeMark size={24} />
          </div>
          <h1 style={{ margin: 0, fontSize: 21, fontWeight: 650, color: 'var(--text-strong)' }}>
            {t(locale, 'timeline.emptyTitle')}
          </h1>
          <p style={{ margin: 0, color: 'var(--text-muted)', maxWidth: 480, fontSize: 13 }}>
            {t(locale, 'timeline.emptyDesc')}
          </p>

          {/* Starter Quick Actions */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 10,
              width: '100%',
              marginTop: 10,
              textAlign: 'left',
            }}
          >
            {[
              {
                title: 'Изучить файлы проекта',
                desc: 'Проверить структуру локальной рабочей папки',
                prompt: 'Покажи все файлы текущего проекта и прочитай README.md',
                agent: 'build' as const,
              },
              {
                title: 'Создать приложение',
                desc: 'Сгенерировать новый файл с фиксацией diff',
                prompt: 'Создай файл calculator.html с современным инженерным калькулятором',
                agent: 'build' as const,
              },
              {
                title: 'Проверить Android Shell',
                desc: 'Запустить системную команду в папке проекта',
                prompt: 'Выполни uname -a && pwd && ls -la',
                agent: 'build' as const,
              },
              {
                title: 'Архитектурный Plan-режим',
                desc: 'Безопасный анализ без изменения файлов',
                prompt: 'Проанализируй структуру проекта и составь план рефакторинга',
                agent: 'plan' as const,
              },
            ].map((card, i) => (
              <button
                key={i}
                onClick={() => onQuickPrompt(card.prompt, card.agent)}
                style={{
                  padding: '12px 14px',
                  borderRadius: 11,
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border)',
                  textAlign: 'left',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                }}
              >
                <span style={{ fontWeight: 600, color: 'var(--text-strong)', fontSize: 13 }}>{card.title}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>{card.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="oc-timeline">
      <div className="oc-timeline-inner">
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const thinkOpen = openThinkIds[msg.id] ?? false;

          return (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
                padding: isUser ? '11px 14px' : '4px 2px',
                borderRadius: isUser ? 12 : 0,
                background: isUser ? 'var(--bg-raised)' : 'transparent',
                border: isUser ? '1px solid var(--border)' : 'none',
              }}
            >
              {/* Message Meta Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, color: 'var(--text-muted)' }}>
                  {isUser ? <User size={13} /> : <OpenCodeMark size={12} />}
                  <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>
                    {isUser ? 'Вы' : 'OpenCode'}
                  </span>
                  <span
                    style={{
                      padding: '0 6px',
                      borderRadius: 4,
                      background: 'var(--bg-elevated)',
                      color: msg.agent === 'plan' ? 'var(--accent)' : 'var(--primary)',
                      fontSize: 10.5,
                      fontWeight: 600,
                    }}
                  >
                    {msg.agent}
                  </span>
                  {msg.modelId && !isUser && <span>• {msg.modelId}</span>}
                </div>

                {/* Per-message OpenCode actions: Revert workspace snapshot, Fork, Copy */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {isUser && msg.snapshotId && (
                    <button
                      onClick={() => onRevertToSnapshot(msg.snapshotId!)}
                      className="oc-pill"
                      style={{ height: 22, padding: '0 7px', fontSize: 10.5 }}
                      title={t(locale, 'timeline.revert')}
                    >
                      <RotateCcw size={11} />
                      <span>Откатить</span>
                    </button>
                  )}
                  <button
                    onClick={() => onForkFromMessage(msg.id)}
                    className="oc-icon-btn"
                    style={{ width: 24, height: 24, minWidth: 24, padding: 0 }}
                    title={t(locale, 'timeline.fork')}
                  >
                    <GitBranch size={12} />
                  </button>
                  {msg.text && (
                    <button
                      onClick={() => PlatformBridge.copyText(msg.text)}
                      className="oc-icon-btn"
                      style={{ width: 24, height: 24, minWidth: 24, padding: 0 }}
                      title={t(locale, 'timeline.copy')}
                    >
                      <Copy size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* Mentioned files / attachments */}
              {((msg.mentionedFiles && msg.mentionedFiles.length > 0) ||
                (msg.attachments && msg.attachments.length > 0)) && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {msg.mentionedFiles?.map((f) => (
                    <button
                      key={f}
                      onClick={() => onOpenFileInEditor(f)}
                      className="oc-pill"
                      style={{ height: 22, fontSize: 11, fontFamily: 'var(--font-mono)' }}
                    >
                      @{f}
                    </button>
                  ))}
                  {msg.attachments?.map((a) => (
                    <span key={a.id} className="oc-pill" style={{ height: 22, fontSize: 11 }}>
                      📎 {a.name}
                    </span>
                  ))}
                </div>
              )}

              {/* Thinking / Reasoning Collapsible */}
              {msg.thinking && (
                <div
                  style={{
                    border: '1px dashed var(--border-strong)',
                    borderRadius: 9,
                    background: 'var(--bg-deep)',
                    overflow: 'hidden',
                  }}
                >
                  <button
                    onClick={() => setOpenThinkIds((s) => ({ ...s, [msg.id]: !thinkOpen }))}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 7,
                      fontSize: 11.5,
                      color: 'var(--text-muted)',
                    }}
                  >
                    <Brain size={13} style={{ color: 'var(--accent)' }} />
                    <span>{t(locale, 'timeline.thinking')}</span>
                    {msg.thinkingDurationMs && (
                      <span>({(msg.thinkingDurationMs / 1000).toFixed(1)}s)</span>
                    )}
                    <span style={{ marginLeft: 'auto' }}>
                      {thinkOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    </span>
                  </button>
                  {thinkOpen && (
                    <div
                      style={{
                        padding: '8px 12px',
                        borderTop: '1px dashed var(--border)',
                        fontSize: 12,
                        color: 'var(--text-muted)',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {msg.thinking}
                    </div>
                  )}
                </div>
              )}

              {/* Tool Calls */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {msg.toolCalls.map((tc) => (
                    <ToolCallCard key={tc.id} part={tc} onOpenFile={onOpenFileInEditor} />
                  ))}
                </div>
              )}

              {/* Message Text */}
              {msg.text && <SimpleMarkdown text={msg.text} />}

              {msg.isStreaming && !msg.text && (!msg.toolCalls || msg.toolCalls.length === 0) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 12 }}>
                  <Loader2 size={14} className="oc-spin" />
                  <span>OpenCode генерирует ответ…</span>
                </div>
              )}

              {msg.error && (
                <div
                  style={{
                    padding: '9px 12px',
                    borderRadius: 8,
                    background: 'var(--diff-del-bg)',
                    color: 'var(--diff-del-fg)',
                    border: '1px solid var(--danger)',
                    fontSize: 12,
                  }}
                >
                  Ошибка: {msg.error}
                </div>
              )}
            </div>
          );
        })}

        {/* Interactive Permission Prompt Card */}
        {pendingPermission && (
          <div
            style={{
              padding: 14,
              borderRadius: 12,
              background: 'var(--bg-raised)',
              border: '1px solid var(--warning)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--warning)', fontWeight: 600 }}>
              <ShieldAlert size={17} />
              <span>{t(locale, 'permission.title')}: {pendingPermission.title}</span>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-base)' }}>{pendingPermission.description}</div>
            {pendingPermission.commandOrPath && (
              <pre
                style={{
                  margin: 0,
                  padding: '8px 10px',
                  borderRadius: 8,
                  background: 'var(--bg-deep)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                }}
              >
                {pendingPermission.commandOrPath}
              </pre>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button className="oc-send-btn" onClick={() => onResolvePermission('approved_once')}>
                <Check size={14} /> {t(locale, 'permission.allowOnce')}
              </button>
              <button className="oc-pill" style={{ height: 32 }} onClick={() => onResolvePermission('approved_always')}>
                {t(locale, 'permission.allowAlways')}
              </button>
              <button
                className="oc-pill"
                style={{ height: 32, color: 'var(--danger)', borderColor: 'var(--danger)' }}
                onClick={() => onResolvePermission('rejected')}
              >
                {t(locale, 'permission.reject')}
              </button>
            </div>
          </div>
        )}

        {/* Interactive Clarifying Question Card */}
        {pendingQuestion && (
          <div
            style={{
              padding: 14,
              borderRadius: 12,
              background: 'var(--bg-raised)',
              border: '1px solid var(--primary)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--primary)', fontWeight: 600 }}>
              <HelpCircle size={17} />
              <span>{pendingQuestion.question}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {pendingQuestion.options.map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => onResolveQuestion(opt.label)}
                  style={{
                    padding: '9px 12px',
                    borderRadius: 8,
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-strong)',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{opt.label}</div>
                  {opt.description && (
                    <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{opt.description}</div>
                  )}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={customAnswer}
                onChange={(e) => setCustomAnswer(e.target.value)}
                placeholder="Или введите свой вариант…"
                style={{
                  flex: 1,
                  height: 34,
                  padding: '0 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-deep)',
                }}
              />
              <button
                className="oc-send-btn"
                disabled={!customAnswer.trim()}
                onClick={() => {
                  onResolveQuestion(customAnswer.trim());
                  setCustomAnswer('');
                }}
              >
                Ответить
              </button>
            </div>
          </div>
        )}

        <div ref={bottomRef} style={{ height: 6 }} />
      </div>
    </div>
  );
};
