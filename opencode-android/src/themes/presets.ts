import type { ModelDef, ProviderConfig, ProviderId } from '../types/opencode';

export interface ThemePalette {
  id: string;
  name: string;
  dark: {
    bgDeep: string;
    bgBase: string;
    bgRaised: string;
    bgElevated: string;
    bgHover: string;
    border: string;
    borderStrong: string;
    textStrong: string;
    textBase: string;
    textMuted: string;
    primary: string;
    primaryFg: string;
    accent: string;
    success: string;
    warning: string;
    danger: string;
    diffAddBg: string;
    diffAddFg: string;
    diffDelBg: string;
    diffDelFg: string;
  };
  light: {
    bgDeep: string;
    bgBase: string;
    bgRaised: string;
    bgElevated: string;
    bgHover: string;
    border: string;
    borderStrong: string;
    textStrong: string;
    textBase: string;
    textMuted: string;
    primary: string;
    primaryFg: string;
    accent: string;
    success: string;
    warning: string;
    danger: string;
    diffAddBg: string;
    diffAddFg: string;
    diffDelBg: string;
    diffDelFg: string;
  };
}

export const OPENCODE_THEMES: ThemePalette[] = [
  {
    id: 'oc-2',
    name: 'OpenCode (OC-2)',
    dark: {
      bgDeep: '#0d0b0b',
      bgBase: '#131010',
      bgRaised: '#1b1717',
      bgElevated: '#231e1e',
      bgHover: '#2c2626',
      border: '#2d2727',
      borderStrong: '#3e3636',
      textStrong: '#f5f2f0',
      textBase: '#cbc5c2',
      textMuted: '#877f7c',
      primary: '#dcde8d',
      primaryFg: '#161610',
      accent: '#fab283',
      success: '#49c970',
      warning: '#f6c251',
      danger: '#fc533a',
      diffAddBg: 'rgba(73, 201, 112, 0.14)',
      diffAddFg: '#7ce89b',
      diffDelBg: 'rgba(252, 83, 58, 0.14)',
      diffDelFg: '#ff8a78',
    },
    light: {
      bgDeep: '#efefef',
      bgBase: '#f8f8f8',
      bgRaised: '#ffffff',
      bgElevated: '#f2f2f2',
      bgHover: '#eaeaea',
      border: '#dbdbdb',
      borderStrong: '#c4c4c4',
      textStrong: '#171717',
      textBase: '#424242',
      textMuted: '#787878',
      primary: '#171311',
      primaryFg: '#f8f8f8',
      accent: '#034cff',
      success: '#128a36',
      warning: '#b88214',
      danger: '#d92e3c',
      diffAddBg: 'rgba(18, 201, 5, 0.12)',
      diffAddFg: '#0e6f28',
      diffDelBg: 'rgba(252, 83, 58, 0.12)',
      diffDelFg: '#b82419',
    },
  },
  {
    id: 'amoled',
    name: 'AMOLED Pitch',
    dark: {
      bgDeep: '#000000',
      bgBase: '#050505',
      bgRaised: '#0e0e11',
      bgElevated: '#16161b',
      bgHover: '#1f1f26',
      border: '#22222a',
      borderStrong: '#343442',
      textStrong: '#ffffff',
      textBase: '#d4d4dc',
      textMuted: '#7e7e8f',
      primary: '#b388ff',
      primaryFg: '#0a0612',
      accent: '#18ffff',
      success: '#00e676',
      warning: '#ffea00',
      danger: '#ff1744',
      diffAddBg: 'rgba(0, 230, 118, 0.14)',
      diffAddFg: '#69f0ae',
      diffDelBg: 'rgba(255, 23, 68, 0.15)',
      diffDelFg: '#ff6e89',
    },
    light: {
      bgDeep: '#eaeaea',
      bgBase: '#f5f5f7',
      bgRaised: '#ffffff',
      bgElevated: '#ededf2',
      bgHover: '#e2e2ea',
      border: '#d5d5e0',
      borderStrong: '#b8b8c8',
      textStrong: '#0a0a0a',
      textBase: '#33333d',
      textMuted: '#6e6e80',
      primary: '#6200ff',
      primaryFg: '#ffffff',
      accent: '#0091ea',
      success: '#00a152',
      warning: '#c68400',
      danger: '#d50000',
      diffAddBg: 'rgba(0, 200, 83, 0.12)',
      diffAddFg: '#00701a',
      diffDelBg: 'rgba(213, 0, 0, 0.11)',
      diffDelFg: '#9b0000',
    },
  },
  {
    id: 'tokyonight',
    name: 'Tokyo Night',
    dark: {
      bgDeep: '#13141c',
      bgBase: '#1a1b26',
      bgRaised: '#24283b',
      bgElevated: '#292e42',
      bgHover: '#323850',
      border: '#2f3549',
      borderStrong: '#414868',
      textStrong: '#c0caf5',
      textBase: '#a9b1d6',
      textMuted: '#565f89',
      primary: '#7aa2f7',
      primaryFg: '#13141c',
      accent: '#bb9af7',
      success: '#9ece6a',
      warning: '#e0af68',
      danger: '#f7768e',
      diffAddBg: 'rgba(158, 206, 106, 0.14)',
      diffAddFg: '#9ece6a',
      diffDelBg: 'rgba(247, 118, 142, 0.14)',
      diffDelFg: '#f7768e',
    },
    light: {
      bgDeep: '#d5d6db',
      bgBase: '#e1e2e7',
      bgRaised: '#edf0f5',
      bgElevated: '#d9dce3',
      bgHover: '#cfd3dc',
      border: '#c4c8d4',
      borderStrong: '#9aa5ce',
      textStrong: '#343b58',
      textBase: '#4c505e',
      textMuted: '#787c99',
      primary: '#2e7de9',
      primaryFg: '#ffffff',
      accent: '#7847bd',
      success: '#485e30',
      warning: '#8f5e15',
      danger: '#c64343',
      diffAddBg: 'rgba(72, 94, 48, 0.12)',
      diffAddFg: '#385f0d',
      diffDelBg: 'rgba(198, 67, 67, 0.12)',
      diffDelFg: '#8c2323',
    },
  },
  {
    id: 'catppuccin',
    name: 'Catppuccin Mocha',
    dark: {
      bgDeep: '#11111b',
      bgBase: '#1e1e2e',
      bgRaised: '#262639',
      bgElevated: '#313244',
      bgHover: '#3b3d54',
      border: '#313244',
      borderStrong: '#45475a',
      textStrong: '#cdd6f4',
      textBase: '#bac2de',
      textMuted: '#6c7086',
      primary: '#cba6f7',
      primaryFg: '#11111b',
      accent: '#89b4fa',
      success: '#a6e3a1',
      warning: '#f9e2af',
      danger: '#f38ba8',
      diffAddBg: 'rgba(166, 227, 161, 0.14)',
      diffAddFg: '#a6e3a1',
      diffDelBg: 'rgba(243, 139, 168, 0.14)',
      diffDelFg: '#f38ba8',
    },
    light: {
      bgDeep: '#dce0e8',
      bgBase: '#eff1f5',
      bgRaised: '#ffffff',
      bgElevated: '#e6e9ef',
      bgHover: '#ccd0da',
      border: '#ccd0da',
      borderStrong: '#bcc0cc',
      textStrong: '#4c4f69',
      textBase: '#5c5f77',
      textMuted: '#8c8fa1',
      primary: '#8839ef',
      primaryFg: '#ffffff',
      accent: '#1e66f5',
      success: '#40a02b',
      warning: '#df8e1d',
      danger: '#d20f39',
      diffAddBg: 'rgba(64, 160, 43, 0.12)',
      diffAddFg: '#2e7d20',
      diffDelBg: 'rgba(210, 15, 57, 0.12)',
      diffDelFg: '#a50c2d',
    },
  },
  {
    id: 'cursor',
    name: 'Cursor Graphite',
    dark: {
      bgDeep: '#0c0c0d',
      bgBase: '#141416',
      bgRaised: '#1c1c1f',
      bgElevated: '#242429',
      bgHover: '#2d2d33',
      border: '#29292e',
      borderStrong: '#3b3b42',
      textStrong: '#f2f2f3',
      textBase: '#c5c5cb',
      textMuted: '#7a7a85',
      primary: '#569cd6',
      primaryFg: '#0c0c0d',
      accent: '#4ec9b0',
      success: '#4ec9b0',
      warning: '#dcdcaa',
      danger: '#f44747',
      diffAddBg: 'rgba(78, 201, 176, 0.14)',
      diffAddFg: '#6ee7cf',
      diffDelBg: 'rgba(244, 71, 71, 0.15)',
      diffDelFg: '#ff8080',
    },
    light: {
      bgDeep: '#ececef',
      bgBase: '#f6f6f8',
      bgRaised: '#ffffff',
      bgElevated: '#ededf0',
      bgHover: '#e2e2e7',
      border: '#d8d8de',
      borderStrong: '#bdbdc7',
      textStrong: '#18181b',
      textBase: '#3f3f46',
      textMuted: '#71717a',
      primary: '#0066b8',
      primaryFg: '#ffffff',
      accent: '#098658',
      success: '#098658',
      warning: '#9e6a03',
      danger: '#cd3131',
      diffAddBg: 'rgba(9, 134, 88, 0.12)',
      diffAddFg: '#076844',
      diffDelBg: 'rgba(205, 49, 49, 0.12)',
      diffDelFg: '#a12020',
    },
  },
  {
    id: 'aura',
    name: 'Aura Violet',
    dark: {
      bgDeep: '#100f15',
      bgBase: '#15141b',
      bgRaised: '#1d1b26',
      bgElevated: '#262333',
      bgHover: '#302c40',
      border: '#2c283b',
      borderStrong: '#403a57',
      textStrong: '#edecee',
      textBase: '#c9c6d3',
      textMuted: '#7d7891',
      primary: '#a277ff',
      primaryFg: '#120e1c',
      accent: '#61ffca',
      success: '#61ffca',
      warning: '#ffca85',
      danger: '#ff6767',
      diffAddBg: 'rgba(97, 255, 202, 0.14)',
      diffAddFg: '#61ffca',
      diffDelBg: 'rgba(255, 103, 103, 0.14)',
      diffDelFg: '#ff8585',
    },
    light: {
      bgDeep: '#ebe4fa',
      bgBase: '#f5f0ff',
      bgRaised: '#ffffff',
      bgElevated: '#eee6ff',
      bgHover: '#e3d8fc',
      border: '#d6c8f5',
      borderStrong: '#bca6eb',
      textStrong: '#2d2640',
      textBase: '#493f66',
      textMuted: '#7d7399',
      primary: '#7b5ae0',
      primaryFg: '#ffffff',
      accent: '#2b8a57',
      success: '#2b8a57',
      warning: '#a96a22',
      danger: '#d94f4f',
      diffAddBg: 'rgba(43, 138, 87, 0.12)',
      diffAddFg: '#1f6e43',
      diffDelBg: 'rgba(217, 79, 79, 0.12)',
      diffDelFg: '#a83232',
    },
  },
];

export const DEFAULT_PROVIDERS: ProviderConfig[] = [
  {
    id: 'openrouter',
    name: 'OpenRouter',
    apiKey: '',
    baseUrl: 'https://openrouter.ai/api/v1',
    enabled: true,
  },
  {
    id: 'anthropic',
    name: 'Anthropic (Claude)',
    apiKey: '',
    baseUrl: 'https://api.anthropic.com/v1',
    enabled: true,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1',
    enabled: true,
  },
  {
    id: 'google',
    name: 'Google Gemini',
    apiKey: '',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    enabled: true,
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    apiKey: '',
    baseUrl: 'https://api.deepseek.com/v1',
    enabled: true,
  },
  {
    id: 'groq',
    name: 'Groq',
    apiKey: '',
    baseUrl: 'https://api.groq.com/openai/v1',
    enabled: true,
  },
  {
    id: 'xai',
    name: 'xAI (Grok)',
    apiKey: '',
    baseUrl: 'https://api.x.ai/v1',
    enabled: true,
  },
  {
    id: 'ollama',
    name: 'Ollama / Custom Local',
    apiKey: 'ollama',
    baseUrl: 'http://127.0.0.1:11434/v1',
    enabled: false,
  },
  {
    id: 'demo',
    name: 'OpenCode Local Sandbox (Offline)',
    apiKey: 'builtin',
    baseUrl: 'local://builtin',
    enabled: true,
  },
];

export const BUILTIN_MODELS: ModelDef[] = [
  // Anthropic
  {
    id: 'claude-sonnet-4-5',
    name: 'Claude Sonnet 4.5',
    provider: 'anthropic',
    providerName: 'Anthropic',
    contextWindow: 200000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'claude-opus-4-5',
    name: 'Claude Opus 4.5',
    provider: 'anthropic',
    providerName: 'Anthropic',
    contextWindow: 200000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'claude-3-7-sonnet-latest',
    name: 'Claude 3.7 Sonnet',
    provider: 'anthropic',
    providerName: 'Anthropic',
    contextWindow: 200000,
    supportsThinking: true,
    supportsImages: true,
  },
  // OpenAI
  {
    id: 'gpt-4.1',
    name: 'GPT-4.1',
    provider: 'openai',
    providerName: 'OpenAI',
    contextWindow: 1000000,
    supportsImages: true,
  },
  {
    id: 'o4-mini',
    name: 'o4-mini (Reasoning)',
    provider: 'openai',
    providerName: 'OpenAI',
    contextWindow: 200000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'openai',
    providerName: 'OpenAI',
    contextWindow: 128000,
    supportsImages: true,
  },
  // Google Gemini
  {
    id: 'gemini-2.5-pro',
    name: 'Gemini 2.5 Pro',
    provider: 'google',
    providerName: 'Google',
    contextWindow: 1000000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'gemini-2.5-flash',
    name: 'Gemini 2.5 Flash',
    provider: 'google',
    providerName: 'Google',
    contextWindow: 1000000,
    supportsThinking: true,
    supportsImages: true,
  },
  // OpenRouter
  {
    id: 'anthropic/claude-sonnet-4',
    name: 'Claude Sonnet 4 (OpenRouter)',
    provider: 'openrouter',
    providerName: 'OpenRouter',
    contextWindow: 200000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'google/gemini-2.5-pro',
    name: 'Gemini 2.5 Pro (OpenRouter)',
    provider: 'openrouter',
    providerName: 'OpenRouter',
    contextWindow: 1000000,
    supportsThinking: true,
    supportsImages: true,
  },
  {
    id: 'deepseek/deepseek-chat-v3-0324:free',
    name: 'DeepSeek V3 (Free • OpenRouter)',
    provider: 'openrouter',
    providerName: 'OpenRouter',
    contextWindow: 128000,
    free: true,
  },
  {
    id: 'qwen/qwen3-coder:free',
    name: 'Qwen3 Coder (Free • OpenRouter)',
    provider: 'openrouter',
    providerName: 'OpenRouter',
    contextWindow: 128000,
    free: true,
  },
  // DeepSeek
  {
    id: 'deepseek-chat',
    name: 'DeepSeek V3 Chat',
    provider: 'deepseek',
    providerName: 'DeepSeek',
    contextWindow: 128000,
  },
  {
    id: 'deepseek-reasoner',
    name: 'DeepSeek R1 Reasoner',
    provider: 'deepseek',
    providerName: 'DeepSeek',
    contextWindow: 128000,
    supportsThinking: true,
  },
  // Groq
  {
    id: 'llama-3.3-70b-versatile',
    name: 'Llama 3.3 70B Versatile',
    provider: 'groq',
    providerName: 'Groq',
    contextWindow: 128000,
  },
  // xAI
  {
    id: 'grok-3',
    name: 'Grok 3',
    provider: 'xai',
    providerName: 'xAI',
    contextWindow: 131072,
  },
  // Ollama / Local
  {
    id: 'qwen2.5-coder:7b',
    name: 'Qwen 2.5 Coder 7B (Local)',
    provider: 'ollama',
    providerName: 'Ollama',
    contextWindow: 32768,
  },
  // Built-in Offline Local Agent
  {
    id: 'opencode-local-agent',
    name: 'OpenCode Local Agent (Автономный тест без ключа)',
    provider: 'demo',
    providerName: 'Local Android',
    contextWindow: 128000,
    supportsThinking: true,
    free: true,
  },
];

export function resolveActiveModel(
  providerId: ProviderId,
  modelId: string,
  providers: ProviderConfig[],
): { provider: ProviderConfig; model: ModelDef } {
  const foundModel = BUILTIN_MODELS.find((m) => m.id === modelId && m.provider === providerId)
    ?? BUILTIN_MODELS.find((m) => m.id === modelId)
    ?? {
      id: modelId,
      name: modelId,
      provider: providerId,
      providerName: providerId,
      contextWindow: 128000,
    };

  const provider =
    providers.find((p) => p.id === foundModel.provider) ??
    providers[0] ??
    DEFAULT_PROVIDERS[DEFAULT_PROVIDERS.length - 1];

  return { provider, model: foundModel };
}
