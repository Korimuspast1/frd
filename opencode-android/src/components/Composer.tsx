import React, { useMemo, useRef, useState } from 'react';
import {
  ArrowUp,
  AtSign,
  Cpu,
  Paperclip,
  Slash,
  Sparkles,
  Square,
  X,
} from 'lucide-react';
import type { AgentId, AttachmentItem, EffortLevel, ModelDef } from '../types/opencode';
import { t } from '../i18n/translations';

interface ComposerProps {
  locale: 'ru' | 'en';
  agent: AgentId;
  activeModel: ModelDef;
  effort: EffortLevel;
  isStreaming: boolean;
  flatFiles: string[];
  onToggleAgent: () => void;
  onCycleEffort: () => void;
  onOpenModelPicker: () => void;
  onSend: (text: string, attachments: AttachmentItem[], mentionedFiles: string[]) => void;
  onStop: () => void;
  onSlashCommand: (cmd: string) => void;
}

const SLASH_COMMANDS = [
  { cmd: '/init', desc: 'Создать/обновить AGENTS.md для текущего проекта' },
  { cmd: '/review', desc: 'Открыть панель изменений (Diff Review)' },
  { cmd: '/files', desc: 'Открыть проводник и редактор файлов проекта' },
  { cmd: '/terminal', desc: 'Открыть встроенный Android Shell терминал' },
  { cmd: '/agent', desc: 'Переключить режим агента (build ↔ plan)' },
  { cmd: '/models', desc: 'Выбрать AI-модель и провайдера' },
  { cmd: '/undo', desc: 'Откатить файлы к предыдущему снимку сессии' },
  { cmd: '/compact', desc: 'Сжать историю диалога для экономии контекста' },
  { cmd: '/clear', desc: 'Начать чистую сессию в текущем проекте' },
];

export const Composer: React.FC<ComposerProps> = ({
  locale,
  agent,
  activeModel,
  effort,
  isStreaming,
  flatFiles,
  onToggleAgent,
  onCycleEffort,
  onOpenModelPicker,
  onSend,
  onStop,
  onSlashCommand,
}) => {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [mentionedFiles, setMentionedFiles] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Detect active /slash or @file autocomplete token
  const slashQuery = useMemo(() => {
    if (!text.startsWith('/') || text.includes(' ')) return null;
    return text.toLowerCase();
  }, [text]);

  const mentionQuery = useMemo(() => {
    const match = text.match(/(?:^|\s)@([a-zA-Z0-9_./-]*)$/);
    return match ? match[1].toLowerCase() : null;
  }, [text]);

  const filteredSlash = useMemo(() => {
    if (slashQuery === null) return [];
    return SLASH_COMMANDS.filter((c) => c.cmd.startsWith(slashQuery));
  }, [slashQuery]);

  const filteredFiles = useMemo(() => {
    if (mentionQuery === null) return [];
    return flatFiles.filter((f) => f.toLowerCase().includes(mentionQuery)).slice(0, 8);
  }, [mentionQuery, flatFiles]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;

    if (trimmed.startsWith('/') && !trimmed.includes(' ')) {
      setText('');
      onSlashCommand(trimmed.toLowerCase());
      return;
    }

    onSend(trimmed, attachments, mentionedFiles);
    setText('');
    setAttachments([]);
    setMentionedFiles([]);
  };

  const handleFilePicked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    for (const f of files) {
      const isText =
        f.type.startsWith('text/') ||
        /\.(ts|tsx|js|jsx|json|md|py|kt|java|xml|html|css|sh|yml|yaml|toml|txt|gradle)$/i.test(f.name);
      let textContent: string | undefined;
      if (isText && f.size < 512 * 1024) {
        textContent = await f.text();
      }
      setAttachments((prev) => [
        ...prev,
        {
          id: `att_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
          name: f.name,
          mimeType: f.type || 'application/octet-stream',
          size: f.size,
          textContent,
        },
      ]);
    }
    e.target.value = '';
  };

  return (
    <div className="oc-composer-region">
      <div className="oc-composer-card">
        {/* Slash Commands Popup */}
        {filteredSlash.length > 0 && (
          <div
            style={{
              position: 'absolute',
              left: 8,
              right: 8,
              bottom: 'calc(100% + 6px)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              borderRadius: 11,
              padding: 6,
              boxShadow: '0 14px 36px rgba(0,0,0,0.45)',
              zIndex: 30,
              maxHeight: 240,
              overflowY: 'auto',
            }}
          >
            {filteredSlash.map((item) => (
              <button
                key={item.cmd}
                onClick={() => {
                  setText('');
                  onSlashCommand(item.cmd);
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                  padding: '8px 10px',
                  borderRadius: 7,
                  textAlign: 'left',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--primary)' }}>
                  {item.cmd}
                </span>
                <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{item.desc}</span>
              </button>
            ))}
          </div>
        )}

        {/* @File Mention Popup */}
        {filteredFiles.length > 0 && (
          <div
            style={{
              position: 'absolute',
              left: 8,
              right: 8,
              bottom: 'calc(100% + 6px)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              borderRadius: 11,
              padding: 6,
              boxShadow: '0 14px 36px rgba(0,0,0,0.45)',
              zIndex: 30,
              maxHeight: 220,
              overflowY: 'auto',
            }}
          >
            {filteredFiles.map((file) => (
              <button
                key={file}
                onClick={() => {
                  setMentionedFiles((prev) => (prev.includes(file) ? prev : [...prev, file]));
                  setText((prev) => prev.replace(/(?:^|\s)@[a-zA-Z0-9_./-]*$/, ' '));
                  textareaRef.current?.focus();
                }}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 10px',
                  borderRadius: 7,
                  textAlign: 'left',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                }}
              >
                <AtSign size={13} style={{ color: 'var(--primary)' }} />
                <span>{file}</span>
              </button>
            ))}
          </div>
        )}

        {/* Attached files & @mentions chips */}
        {(mentionedFiles.length > 0 || attachments.length > 0) && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, paddingBottom: 6 }}>
            {mentionedFiles.map((f) => (
              <span key={f} className="oc-pill" style={{ height: 24, fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                @{f}
                <button
                  onClick={() => setMentionedFiles((prev) => prev.filter((x) => x !== f))}
                  style={{ color: 'var(--text-muted)', display: 'inline-flex' }}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
            {attachments.map((att) => (
              <span key={att.id} className="oc-pill" style={{ height: 24, fontSize: 11 }}>
                📎 {att.name}
                <button
                  onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== att.id))}
                  style={{ color: 'var(--text-muted)', display: 'inline-flex' }}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}

        <textarea
          ref={textareaRef}
          className="oc-composer-textarea"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Tab' && !e.shiftKey) {
              e.preventDefault();
              onToggleAgent();
              return;
            }
            if (e.key === 'Enter' && !e.shiftKey && window.innerWidth > 768) {
              e.preventDefault();
              if (!isStreaming) handleSubmit();
            }
          }}
          placeholder={
            agent === 'plan'
              ? t(locale, 'composer.placeholder.plan')
              : t(locale, 'composer.placeholder.build')
          }
        />

        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={handleFilePicked}
        />

        {/* Bottom Composer Pill Controls */}
        <div className="oc-composer-toolbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {/* Agent switcher: build <-> plan (Tab) */}
            <button
              type="button"
              onClick={onToggleAgent}
              className={`oc-agent-chip ${agent === 'plan' ? 'plan' : 'build'}`}
              title={agent === 'plan' ? t(locale, 'agent.plan.desc') : t(locale, 'agent.build.desc')}
            >
              <span>{agent}</span>
            </button>

            {/* Model selector */}
            <button
              type="button"
              onClick={onOpenModelPicker}
              className="oc-pill"
              style={{ height: 30, maxWidth: 195 }}
            >
              <Cpu size={13} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {activeModel.name}
              </span>
            </button>

            {/* Effort / Thinking toggle */}
            <button
              type="button"
              onClick={onCycleEffort}
              className="oc-pill"
              style={{ height: 30, padding: '0 8px' }}
              title="Уровень размышления (Effort)"
            >
              <Sparkles size={12} style={{ color: 'var(--accent)' }} />
              <span>{effort}</span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <button
              type="button"
              className="oc-icon-btn"
              onClick={() => setText((prev) => (prev.startsWith('/') ? prev : '/' + prev))}
              title="Слэш-команды (/)"
              style={{ width: 32, height: 32 }}
            >
              <Slash size={15} />
            </button>
            <button
              type="button"
              className="oc-icon-btn"
              onClick={() => {
                setText((prev) => (prev.endsWith(' ') || !prev ? prev + '@' : prev + ' @'));
                textareaRef.current?.focus();
              }}
              title="Упомянуть файл проекта (@)"
              style={{ width: 32, height: 32 }}
            >
              <AtSign size={15} />
            </button>
            <button
              type="button"
              className="oc-icon-btn"
              onClick={() => fileInputRef.current?.click()}
              title={t(locale, 'composer.attach')}
              style={{ width: 32, height: 32 }}
            >
              <Paperclip size={15} />
            </button>

            {isStreaming ? (
              <button type="button" className="oc-send-btn stop" onClick={onStop}>
                <Square size={13} fill="currentColor" />
                <span>{t(locale, 'composer.stop')}</span>
              </button>
            ) : (
              <button
                type="button"
                className="oc-send-btn"
                disabled={!text.trim() && attachments.length === 0}
                onClick={handleSubmit}
              >
                <ArrowUp size={15} />
                <span>{t(locale, 'composer.send')}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
