import React, { useState } from 'react';
import { Check, Cpu, FolderPlus, Github, Key, Palette, Radio, Shield, X } from 'lucide-react';
import type {
  AppSettings,
  ModelDef,
  ProviderConfig,
  ProviderId,
  RemoteServerConfig,
} from '../types/opencode';
import { BUILTIN_MODELS, OPENCODE_THEMES } from '../themes/presets';
import { RemoteOpenCodeClient } from '../engine/remoteOpenCode';

export const ModelPickerModal: React.FC<{
  selectedProvider: ProviderId;
  selectedModel: string;
  providers: ProviderConfig[];
  onSelect: (provider: ProviderId, modelId: string) => void;
  onOpenSettings: () => void;
  onClose: () => void;
}> = ({ selectedProvider, selectedModel, providers, onSelect, onOpenSettings, onClose }) => {
  const [filter, setFilter] = useState('');
  const [customModel, setCustomModel] = useState('');

  const models: ModelDef[] = BUILTIN_MODELS.filter(
    (m) =>
      m.name.toLowerCase().includes(filter.toLowerCase()) ||
      m.id.toLowerCase().includes(filter.toLowerCase()) ||
      m.providerName.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="oc-modal-backdrop" onClick={onClose}>
      <div className="oc-modal" onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, color: 'var(--text-strong)' }}>
            <Cpu size={16} style={{ color: 'var(--primary)' }} />
            <span>Выбор AI-модели</span>
          </div>
          <button className="oc-icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8 }}>
          <input
            autoFocus
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Поиск модели (Claude, GPT-4.1, Gemini, DeepSeek, Free…)"
            style={{
              flex: 1,
              height: 34,
              padding: '0 10px',
              borderRadius: 8,
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-deep)',
            }}
          />
          <button className="oc-pill" style={{ height: 34 }} onClick={onOpenSettings}>
            <Key size={13} /> Ключи API
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {models.map((m) => {
            const pCfg = providers.find((p) => p.id === m.provider);
            const hasKey = m.provider === 'demo' || m.provider === 'ollama' || Boolean(pCfg?.apiKey);
            const isSelected = m.id === selectedModel && m.provider === selectedProvider;

            return (
              <button
                key={`${m.provider}:${m.id}`}
                onClick={() => {
                  onSelect(m.provider, m.id);
                  onClose();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 10,
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                  border: isSelected ? '1px solid var(--primary)' : '1px solid transparent',
                  textAlign: 'left',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-strong)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>{m.name}</span>
                    {m.free && (
                      <span
                        style={{
                          fontSize: 10,
                          padding: '1px 5px',
                          borderRadius: 4,
                          background: 'var(--diff-add-bg)',
                          color: 'var(--diff-add-fg)',
                        }}
                      >
                        FREE
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {m.providerName} • {m.id}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, color: hasKey ? 'var(--success)' : 'var(--text-muted)' }}>
                    {hasKey ? 'Готов' : 'Нужен ключ'}
                  </span>
                  {isSelected && <Check size={15} style={{ color: 'var(--primary)' }} />}
                </div>
              </button>
            );
          })}
        </div>

        {/* Custom model ID input */}
        <div
          style={{
            padding: '10px 14px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            gap: 6,
            background: 'var(--bg-deep)',
          }}
        >
          <input
            value={customModel}
            onChange={(e) => setCustomModel(e.target.value)}
            placeholder="Или введите свой ID модели (например anthropic/claude-3.7-sonnet)"
            style={{
              flex: 1,
              height: 32,
              padding: '0 10px',
              borderRadius: 7,
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-raised)',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
            }}
          />
          <button
            className="oc-send-btn"
            style={{ height: 32 }}
            disabled={!customModel.trim()}
            onClick={() => {
              onSelect(selectedProvider === 'demo' ? 'openrouter' : selectedProvider, customModel.trim());
              onClose();
            }}
          >
            Выбрать
          </button>
        </div>
      </div>
    </div>
  );
};

export const SettingsModal: React.FC<{
  settings: AppSettings;
  providers: ProviderConfig[];
  onUpdateSettings: (patch: Partial<AppSettings>) => void;
  onUpdateProvider: (id: ProviderId, patch: Partial<ProviderConfig>) => void;
  onClose: () => void;
}> = ({ settings, providers, onUpdateSettings, onUpdateProvider, onClose }) => {
  const [tab, setTab] = useState<'providers' | 'appearance' | 'daemon'>('providers');

  return (
    <div className="oc-modal-backdrop" onClick={onClose}>
      <div className="oc-modal" onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontWeight: 650, fontSize: 14.5, color: 'var(--text-strong)' }}>
            Настройки OpenCode Android
          </span>
          <button className="oc-icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 6 }}>
          <button className={`oc-pill ${tab === 'providers' ? 'active' : ''}`} onClick={() => setTab('providers')}>
            <Key size={13} /> AI Провайдеры
          </button>
          <button className={`oc-pill ${tab === 'appearance' ? 'active' : ''}`} onClick={() => setTab('appearance')}>
            <Palette size={13} /> Темы (OC-2)
          </button>
          <button className={`oc-pill ${tab === 'daemon' ? 'active' : ''}`} onClick={() => setTab('daemon')}>
            <Shield size={13} /> Фоновый сервис и права
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {tab === 'providers' &&
            providers
              .filter((p) => p.id !== 'demo')
              .map((p) => (
                <div
                  key={p.id}
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: 'var(--bg-deep)',
                    border: '1px solid var(--border)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{p.name}</span>
                    <span style={{ fontSize: 11, color: p.apiKey ? 'var(--success)' : 'var(--text-muted)' }}>
                      {p.apiKey ? 'Ключ настроен ✓' : 'Не задан'}
                    </span>
                  </div>
                  <input
                    type="password"
                    value={p.apiKey}
                    onChange={(e) => onUpdateProvider(p.id, { apiKey: e.target.value })}
                    placeholder={`API Key для ${p.name}…`}
                    style={{
                      height: 34,
                      padding: '0 10px',
                      borderRadius: 7,
                      border: '1px solid var(--border-strong)',
                      background: 'var(--bg-raised)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 12,
                    }}
                  />
                  <input
                    type="text"
                    value={p.baseUrl}
                    onChange={(e) => onUpdateProvider(p.id, { baseUrl: e.target.value })}
                    placeholder="Base URL"
                    style={{
                      height: 30,
                      padding: '0 10px',
                      borderRadius: 7,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-raised)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11.5,
                      color: 'var(--text-muted)',
                    }}
                  />
                </div>
              ))}

          {tab === 'appearance' && (
            <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Режим яркости</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {(['dark', 'light', 'system'] as const).map((m) => (
                    <button
                      key={m}
                      className={`oc-pill ${settings.colorMode === m ? 'active' : ''}`}
                      onClick={() => onUpdateSettings({ colorMode: m })}
                    >
                      {m === 'dark' ? 'Тёмная' : m === 'light' ? 'Светлая' : 'Авто'}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Язык интерфейса</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className={`oc-pill ${settings.locale === 'ru' ? 'active' : ''}`}
                    onClick={() => onUpdateSettings({ locale: 'ru' })}
                  >
                    Русский
                  </button>
                  <button
                    className={`oc-pill ${settings.locale === 'en' ? 'active' : ''}`}
                    onClick={() => onUpdateSettings({ locale: 'en' })}
                  >
                    English
                  </button>
                </div>
              </div>

              <div style={{ fontWeight: 600, marginTop: 4, color: 'var(--text-strong)' }}>
                Фирменные темы OpenCode Desktop:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 }}>
                {OPENCODE_THEMES.map((th) => (
                  <button
                    key={th.id}
                    onClick={() => onUpdateSettings({ themeId: th.id })}
                    style={{
                      padding: 10,
                      borderRadius: 10,
                      background: th.dark.bgRaised,
                      color: th.dark.textStrong,
                      border:
                        settings.themeId === th.id
                          ? `2px solid ${th.dark.primary}`
                          : `1px solid ${th.dark.borderStrong}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span style={{ fontWeight: 600, fontSize: 12.5 }}>{th.name}</span>
                    <span
                      style={{
                        width: 14,
                        height: 14,
                        borderRadius: '50%',
                        background: th.dark.primary,
                      }}
                    />
                  </button>
                ))}
              </div>
            </>
          )}

          {tab === 'daemon' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: 'var(--bg-deep)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--text-strong)', marginBottom: 4 }}>
                  Android Foreground Service + WakeLock
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Как на ПК, OpenCode запускает локальный демон в фоновом сервисе Android (`OpenCodeDaemonService`), удерживая сессию, чтение/запись файлов, терминал и потоковые запросы активными даже при сворачивании приложения.
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Политика разрешений для агента Build:</span>
                {[
                  { id: 'auto', label: 'Полный автомат (как Build на ПК — без лишних окон)' },
                  { id: 'ask_bash_and_delete', label: 'Спрашивать перед Shell-командами и удалением файлов' },
                  { id: 'ask_all_writes', label: 'Спрашивать перед любым изменением файлов и Shell' },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => onUpdateSettings({ permissionPolicy: opt.id as AppSettings['permissionPolicy'] })}
                    style={{
                      padding: '9px 12px',
                      borderRadius: 8,
                      textAlign: 'left',
                      background: settings.permissionPolicy === opt.id ? 'var(--bg-elevated)' : 'var(--bg-deep)',
                      border:
                        settings.permissionPolicy === opt.id
                          ? '1px solid var(--primary)'
                          : '1px solid var(--border)',
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const NewProjectModal: React.FC<{
  onCreate: (name: string, template: string) => Promise<void>;
  onCloneGithub: (repoUrl: string, name?: string) => Promise<void>;
  onClose: () => void;
}> = ({ onCreate, onCloneGithub, onClose }) => {
  const [mode, setMode] = useState<'template' | 'github'>('template');
  const [name, setName] = useState('');
  const [template, setTemplate] = useState('typescript');
  const [repoUrl, setRepoUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (mode === 'template') {
        await onCreate(name.trim() || `project-${Date.now().toString().slice(-4)}`, template);
      } else {
        await onCloneGithub(repoUrl.trim(), name.trim() || undefined);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="oc-modal-backdrop" onClick={onClose}>
      <div className="oc-modal" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontWeight: 650, color: 'var(--text-strong)' }}>Новый локальный проект</span>
          <button className="oc-icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: '10px 14px 0', display: 'flex', gap: 6 }}>
          <button className={`oc-pill ${mode === 'template' ? 'active' : ''}`} onClick={() => setMode('template')}>
            <FolderPlus size={13} /> Локальный шаблон
          </button>
          <button className={`oc-pill ${mode === 'github' ? 'active' : ''}`} onClick={() => setMode('github')}>
            <Github size={13} /> Клонировать с GitHub
          </button>
        </div>

        <form onSubmit={submit} style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {mode === 'github' && (
            <div>
              <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-muted)' }}>
                URL репозитория GitHub (без необходимости в git!)
              </label>
              <input
                required
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                style={{
                  width: '100%',
                  height: 36,
                  padding: '0 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-deep)',
                  fontFamily: 'var(--font-mono)',
                }}
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-muted)' }}>
              Имя папки проекта
            </label>
            <input
              required={mode === 'template'}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-awesome-app"
              style={{
                width: '100%',
                height: 36,
                padding: '0 10px',
                borderRadius: 8,
                border: '1px solid var(--border-strong)',
                background: 'var(--bg-deep)',
                fontFamily: 'var(--font-mono)',
              }}
            />
          </div>

          {mode === 'template' && (
            <div>
              <label style={{ display: 'block', fontSize: 12, marginBottom: 4, color: 'var(--text-muted)' }}>
                Стартовый шаблон
              </label>
              <select
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                style={{
                  width: '100%',
                  height: 36,
                  padding: '0 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-deep)',
                }}
              >
                <option value="typescript">Web / TypeScript проект</option>
                <option value="python">Python скрипт + модули</option>
                <option value="android">Kotlin / Android модуль</option>
                <option value="empty">Пустая папка</option>
              </select>
            </div>
          )}

          {error && <div style={{ color: 'var(--danger)', fontSize: 12 }}>{error}</div>}

          <button type="submit" className="oc-send-btn" style={{ height: 38 }} disabled={busy}>
            {busy ? 'Создание проекта…' : mode === 'github' ? 'Клонировать на устройство' : 'Создать локальный проект'}
          </button>
        </form>
      </div>
    </div>
  );
};

export const RemoteServerModal: React.FC<{
  config: RemoteServerConfig;
  onSave: (cfg: RemoteServerConfig) => void;
  onClose: () => void;
}> = ({ config, onSave, onClose }) => {
  const [url, setUrl] = useState(config.url || '');
  const [password, setPassword] = useState(config.password || '');
  const [pairingInput, setPairingInput] = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const handleConnect = async () => {
    setBusy(true);
    setStatusMsg('Проверка соединения с ПК…');
    try {
      let nextCfg: RemoteServerConfig = {
        ...config,
        url: url.trim(),
        password: password.trim() || undefined,
      };
      if (pairingInput.trim()) {
        const redeemed = await RemoteOpenCodeClient.redeemPairingInput(pairingInput.trim());
        if (redeemed) {
          nextCfg = {
            ...nextCfg,
            url: redeemed.url,
            pairingToken: redeemed.token,
          };
          setUrl(redeemed.url);
        }
      }
      const probe = await RemoteOpenCodeClient.probeServer(nextCfg);
      if (!probe.ok) {
        setStatusMsg(probe.error || 'Ошибка подключения');
      } else {
        onSave({ ...nextCfg, enabled: true, connected: true, version: probe.version });
        setStatusMsg(`Подключено! (${probe.version})`);
        setTimeout(onClose, 500);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="oc-modal-backdrop" onClick={onClose}>
      <div className="oc-modal" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 650, color: 'var(--text-strong)' }}>
            <Radio size={15} style={{ color: 'var(--primary)' }} />
            <span>Подключение к ПК (opencode serve)</span>
          </div>
          <button className="oc-icon-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            По умолчанию OpenCode Android работает **полностью автономно** на самом телефоне. При желании вы можете также подключиться к серверу `opencode serve` на вашем ПК или VPS.
          </div>

          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://192.168.1.15:4096"
            style={{
              height: 36,
              padding: '0 10px',
              borderRadius: 8,
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-deep)',
              fontFamily: 'var(--font-mono)',
            }}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="OPENCODE_SERVER_PASSWORD (необязательно)"
            style={{
              height: 36,
              padding: '0 10px',
              borderRadius: 8,
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-deep)',
            }}
          />
          <input
            value={pairingInput}
            onChange={(e) => setPairingInput(e.target.value)}
            placeholder="Или ссылка сопряжения http://.../auth/connect/..."
            style={{
              height: 36,
              padding: '0 10px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--bg-deep)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11.5,
            }}
          />

          {statusMsg && <div style={{ fontSize: 12, color: 'var(--primary)' }}>{statusMsg}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <button className="oc-send-btn" style={{ flex: 1, height: 36 }} disabled={busy} onClick={handleConnect}>
              Подключить к ПК
            </button>
            {config.enabled && (
              <button
                className="oc-pill"
                style={{ height: 36 }}
                onClick={() => {
                  onSave({ ...config, enabled: false, connected: false });
                  onClose();
                }}
              >
                Вернуться в локальный режим
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
