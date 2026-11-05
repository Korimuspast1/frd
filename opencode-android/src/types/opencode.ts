export type AgentId = 'build' | 'plan' | 'general';

export type EffortLevel = 'low' | 'medium' | 'high';

export type ProviderId =
  | 'openrouter'
  | 'anthropic'
  | 'openai'
  | 'google'
  | 'deepseek'
  | 'groq'
  | 'xai'
  | 'ollama'
  | 'demo';

export interface ModelDef {
  id: string;
  name: string;
  provider: ProviderId;
  providerName: string;
  contextWindow: number;
  supportsThinking?: boolean;
  supportsImages?: boolean;
  free?: boolean;
}

export interface ProviderConfig {
  id: ProviderId;
  name: string;
  apiKey: string;
  baseUrl: string;
  enabled: boolean;
  customModels?: string[];
}

export interface ProjectInfo {
  id: string;
  name: string;
  path: string;
  template?: string;
  createdAt: number;
  updatedAt: number;
  fileCount?: number;
}

export interface FileNode {
  name: string;
  path: string; // relative path inside project
  type: 'file' | 'directory';
  size?: number;
  mtime?: number;
  children?: FileNode[];
}

export interface FileDiffItem {
  path: string;
  status: 'added' | 'modified' | 'deleted';
  oldContent: string;
  newContent: string;
  additions: number;
  deletions: number;
  unifiedDiff: string;
}

export interface TodoItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority?: 'high' | 'medium' | 'low';
}

export type ToolName =
  | 'read'
  | 'write'
  | 'edit'
  | 'apply_patch'
  | 'delete_file'
  | 'glob'
  | 'grep'
  | 'bash'
  | 'todowrite'
  | 'todoread'
  | 'webfetch'
  | 'question'
  | 'task';

export type ToolStatus = 'pending' | 'awaiting_permission' | 'awaiting_answer' | 'running' | 'completed' | 'error' | 'rejected';

export interface ToolCallPart {
  id: string;
  tool: ToolName;
  status: ToolStatus;
  input: Record<string, unknown>;
  title: string;
  subtitle?: string;
  output?: string;
  error?: string;
  diff?: FileDiffItem;
  startedAt: number;
  finishedAt?: number;
  subagentMessages?: string[];
}

export interface PermissionRequest {
  id: string;
  sessionId: string;
  toolCallId: string;
  tool: ToolName;
  title: string;
  description: string;
  commandOrPath: string;
  diffPreview?: string;
  status: 'pending' | 'approved_once' | 'approved_always' | 'rejected';
}

export interface QuestionOption {
  id: string;
  label: string;
  description?: string;
}

export interface QuestionRequest {
  id: string;
  sessionId: string;
  toolCallId: string;
  question: string;
  options: QuestionOption[];
  allowCustom?: boolean;
  answer?: string;
  status: 'pending' | 'answered' | 'skipped';
}

export interface AttachmentItem {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  dataUrl?: string;
  textContent?: string;
  projectRelPath?: string;
}

export interface SessionMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  createdAt: number;
  agent: AgentId;
  modelId?: string;
  providerId?: ProviderId;
  text: string;
  thinking?: string;
  thinkingDurationMs?: number;
  toolCalls?: ToolCallPart[];
  attachments?: AttachmentItem[];
  mentionedFiles?: string[];
  snapshotId?: string; // Pre-turn workspace snapshot ID for 1-click Revert
  tokens?: {
    input: number;
    output: number;
  };
  error?: string;
  isStreaming?: boolean;
}

export interface SessionInfo {
  id: string;
  projectId: string;
  title: string;
  agent: AgentId;
  createdAt: number;
  updatedAt: number;
  messages: SessionMessage[];
  todos: TodoItem[];
  revertedSnapshotId?: string;
  parentSessionId?: string;
  remoteSessionId?: string;
}

export interface RemoteServerConfig {
  enabled: boolean;
  url: string;
  password?: string;
  pairingToken?: string;
  connected?: boolean;
  version?: string;
  lastError?: string;
}

export interface DaemonStatus {
  running: boolean;
  platform: 'android' | 'web';
  daemonUrl: string;
  foregroundService: boolean;
  busy: boolean;
  currentTask: string;
  pid?: number;
  deviceModel?: string;
  androidVersion?: string;
  workspacesRoot?: string;
}

export type PermissionPolicy = 'auto' | 'ask_bash_and_delete' | 'ask_all_writes';

export interface AppSettings {
  locale: 'ru' | 'en';
  themeId: string;
  colorMode: 'dark' | 'light' | 'system';
  selectedProvider: ProviderId;
  selectedModel: string;
  effort: EffortLevel;
  permissionPolicy: PermissionPolicy;
  backgroundKeepAlive: boolean;
  notificationsEnabled: boolean;
  terminalFontSize: number;
  editorWordWrap: boolean;
  showThinking: boolean;
  autoCompactContext: boolean;
}
