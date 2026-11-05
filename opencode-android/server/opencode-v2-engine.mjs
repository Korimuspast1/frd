// src/engine/opencode-v2-engine.ts
var ID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
var lastTs = 0;
var idCounter = 0;
function makeSortableId(prefix, descending = false, timestamp = Date.now()) {
  if (timestamp !== lastTs) {
    lastTs = timestamp;
    idCounter = 0;
  }
  idCounter++;
  const current = BigInt(timestamp) * 0x1000n + BigInt(idCounter);
  const value = descending ? ~current : current;
  const timeHex = Array.from({ length: 6 }, (_, idx) => Number(value >> BigInt(40 - 8 * idx) & 0xffn).toString(16).padStart(2, "0")).join("");
  const rnd = new Uint8Array(14);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(rnd);
  } else {
    for (let i = 0;i < rnd.length; i++)
      rnd[i] = Math.floor(Math.random() * 256);
  }
  const tail = Array.from(rnd, (b) => ID_CHARS[b % 62]).join("");
  return `${prefix}${timeHex}${tail}`;
}
var BUILTIN_PRESETS = [
  {
    id: "anthropic",
    name: "Anthropic",
    baseURL: "https://api.anthropic.com/v1",
    protocol: "anthropic",
    envNames: ["ANTHROPIC_API_KEY"],
    defaultModels: [
      { id: "claude-sonnet-4-5", name: "Claude Sonnet 4.5", contextWindow: 200000, maxOutput: 64000, vision: true, reasoning: true, tools: true, inputCost: 3, outputCost: 15 },
      { id: "claude-opus-4-5", name: "Claude Opus 4.5", contextWindow: 200000, maxOutput: 64000, vision: true, reasoning: true, tools: true, inputCost: 15, outputCost: 75 },
      { id: "claude-3-7-sonnet-latest", name: "Claude 3.7 Sonnet", contextWindow: 200000, maxOutput: 64000, vision: true, reasoning: true, tools: true, inputCost: 3, outputCost: 15 },
      { id: "claude-3-5-haiku-latest", name: "Claude 3.5 Haiku", contextWindow: 200000, maxOutput: 8192, vision: true, tools: true, inputCost: 0.8, outputCost: 4 }
    ]
  },
  {
    id: "openai",
    name: "OpenAI",
    baseURL: "https://api.openai.com/v1",
    protocol: "openai",
    envNames: ["OPENAI_API_KEY"],
    defaultModels: [
      { id: "gpt-4.1", name: "GPT-4.1", contextWindow: 1047576, maxOutput: 32768, vision: true, tools: true, inputCost: 2, outputCost: 8 },
      { id: "gpt-4.1-mini", name: "GPT-4.1 Mini", contextWindow: 1047576, maxOutput: 32768, vision: true, tools: true, inputCost: 0.4, outputCost: 1.6 },
      { id: "o4-mini", name: "o4-mini", contextWindow: 200000, maxOutput: 1e5, vision: true, reasoning: true, tools: true, inputCost: 1.1, outputCost: 4.4 },
      { id: "gpt-4o", name: "GPT-4o", contextWindow: 128000, maxOutput: 16384, vision: true, tools: true, inputCost: 2.5, outputCost: 10 }
    ]
  },
  {
    id: "google",
    name: "Google Gemini",
    baseURL: "https://generativelanguage.googleapis.com/v1beta/openai",
    protocol: "openai",
    envNames: ["GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"],
    defaultModels: [
      { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", contextWindow: 1048576, maxOutput: 65536, vision: true, reasoning: true, tools: true, inputCost: 1.25, outputCost: 10 },
      { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", contextWindow: 1048576, maxOutput: 65536, vision: true, reasoning: true, tools: true, inputCost: 0.15, outputCost: 0.6 }
    ]
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    baseURL: "https://openrouter.ai/api/v1",
    protocol: "openai",
    envNames: ["OPENROUTER_API_KEY"],
    defaultModels: [
      { id: "anthropic/claude-sonnet-4", name: "Claude Sonnet 4 (OpenRouter)", contextWindow: 200000, maxOutput: 64000, vision: true, reasoning: true, tools: true },
      { id: "openai/gpt-4.1", name: "GPT-4.1 (OpenRouter)", contextWindow: 1e6, maxOutput: 32768, vision: true, tools: true },
      { id: "google/gemini-2.5-pro", name: "Gemini 2.5 Pro (OpenRouter)", contextWindow: 1e6, maxOutput: 65536, vision: true, reasoning: true, tools: true },
      { id: "deepseek/deepseek-chat-v3-0324:free", name: "DeepSeek V3 (Free)", contextWindow: 131072, maxOutput: 16384, tools: true },
      { id: "qwen/qwen3-coder:free", name: "Qwen3 Coder (Free)", contextWindow: 131072, maxOutput: 16384, tools: true }
    ]
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    baseURL: "https://api.deepseek.com/v1",
    protocol: "openai",
    envNames: ["DEEPSEEK_API_KEY"],
    defaultModels: [
      { id: "deepseek-chat", name: "DeepSeek V3", contextWindow: 128000, maxOutput: 8192, tools: true, inputCost: 0.27, outputCost: 1.1 },
      { id: "deepseek-reasoner", name: "DeepSeek R1", contextWindow: 128000, maxOutput: 8192, reasoning: true, tools: true, inputCost: 0.55, outputCost: 2.19 }
    ]
  },
  {
    id: "groq",
    name: "Groq",
    baseURL: "https://api.groq.com/openai/v1",
    protocol: "openai",
    envNames: ["GROQ_API_KEY"],
    defaultModels: [
      { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B Versatile", contextWindow: 128000, maxOutput: 32768, tools: true },
      { id: "qwen-qwq-32b", name: "Qwen QwQ 32B", contextWindow: 128000, maxOutput: 16384, reasoning: true, tools: true }
    ]
  },
  {
    id: "xai",
    name: "xAI (Grok)",
    baseURL: "https://api.x.ai/v1",
    protocol: "openai",
    envNames: ["XAI_API_KEY"],
    defaultModels: [
      { id: "grok-3", name: "Grok 3", contextWindow: 131072, maxOutput: 32768, tools: true },
      { id: "grok-3-mini", name: "Grok 3 Mini", contextWindow: 131072, maxOutput: 32768, reasoning: true, tools: true }
    ]
  },
  {
    id: "mistral",
    name: "Mistral",
    baseURL: "https://api.mistral.ai/v1",
    protocol: "openai",
    envNames: ["MISTRAL_API_KEY"],
    defaultModels: [
      { id: "codestral-latest", name: "Codestral", contextWindow: 256000, maxOutput: 32768, tools: true },
      { id: "mistral-large-latest", name: "Mistral Large", contextWindow: 128000, maxOutput: 32768, tools: true }
    ]
  },
  {
    id: "ollama",
    name: "Ollama / Local LAN",
    baseURL: "http://127.0.0.1:11434/v1",
    protocol: "openai",
    envNames: [],
    keyOptional: true,
    defaultModels: []
  }
];
function slugifyProviderId(input) {
  const cleaned = input.trim().toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return cleaned || `custom-${Date.now().toString(36)}`;
}
function normalizeBaseUrl(raw, protocol) {
  let u = raw.trim().replace(/\/+$/, "");
  if (!u)
    return protocol === "anthropic" ? "https://api.anthropic.com/v1" : "https://api.openai.com/v1";
  if (!/^https?:\/\//i.test(u))
    u = `https://${u}`;
  u = u.replace(/\/chat\/completions$/i, "").replace(/\/messages$/i, "").replace(/\/models$/i, "");
  return u;
}
function resolveWorkdir(baseDir, raw) {
  const value = String(raw ?? "").trim();
  if (!value)
    return baseDir;
  let p = value;
  if (p === "~")
    p = baseDir;
  else if (p.startsWith("~/"))
    p = `${baseDir}/${p.slice(2)}`;
  p = p.replace(/^\/sdcard\//, "/storage/emulated/0/").replace(/^sdcard\//, "/storage/emulated/0/");
  if (!p.startsWith("/"))
    p = `${baseDir.replace(/\/$/, "")}/${p}`;
  const segments = [];
  for (const seg of p.split("/")) {
    if (!seg || seg === ".")
      continue;
    if (seg === "..")
      segments.pop();
    else
      segments.push(seg);
  }
  return `/${segments.join("/")}`;
}
function htmlToText(html) {
  return html.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<noscript[\s\S]*?<\/noscript>/gi, " ").replace(/<!--[\s\S]*?-->/g, " ").replace(/<br\s*\/?>/gi, `
`).replace(/<\/(p|div|li|h[1-6]|tr|section|article)>/gi, `
`).replace(/<li[^>]*>/gi, "- ").replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, `

`).trim();
}
function normalizeForMatch(input) {
  return input.replace(/\r\n/g, `
`).replace(/[ \t]+$/gm, "");
}
function findFuzzyMatch(haystack, needle) {
  const exact = haystack.indexOf(needle);
  if (exact >= 0)
    return { start: exact, end: exact + needle.length, text: needle };
  const normalizedHay = normalizeForMatch(haystack);
  const normalizedNeedle = normalizeForMatch(needle).trim();
  if (!normalizedNeedle)
    return null;
  const direct = normalizedHay.indexOf(normalizedNeedle);
  if (direct >= 0) {
    return { start: direct, end: direct + normalizedNeedle.length, text: haystack.slice(direct, direct + normalizedNeedle.length) };
  }
  const hayLines = haystack.split(`
`);
  const needleLines = normalizedNeedle.split(`
`).map((l) => l.trim()).filter((l) => l.length > 0);
  if (needleLines.length === 0)
    return null;
  for (let i = 0;i <= hayLines.length - needleLines.length; i++) {
    let ok = true;
    for (let j = 0;j < needleLines.length; j++) {
      const hay = hayLines[i + j].trim();
      const need = needleLines[j];
      if (hay !== need) {
        ok = false;
        break;
      }
    }
    if (ok) {
      const before = hayLines.slice(0, i);
      const matched = hayLines.slice(i, i + needleLines.length);
      const start = before.reduce((acc, line) => acc + line.length + 1, 0);
      return { start, end: start + matched.join(`
`).length, text: matched.join(`
`) };
    }
  }
  return null;
}
function computeUnifiedDiff(relPath, before, after) {
  const oldLines = before !== undefined ? before.split(`
`) : [];
  const newLines = after !== undefined ? after.split(`
`) : [];
  const status = before === undefined ? "added" : after === undefined ? "deleted" : "modified";
  let additions = 0;
  let deletions = 0;
  const body = [];
  if (status === "added") {
    for (const line of newLines) {
      additions++;
      body.push(`+${line}`);
    }
  } else if (status === "deleted") {
    for (const line of oldLines) {
      deletions++;
      body.push(`-${line}`);
    }
  } else {
    let prefix = 0;
    while (prefix < oldLines.length && prefix < newLines.length && oldLines[prefix] === newLines[prefix]) {
      prefix++;
    }
    let oldEnd = oldLines.length - 1;
    let newEnd = newLines.length - 1;
    while (oldEnd >= prefix && newEnd >= prefix && oldLines[oldEnd] === newLines[newEnd]) {
      oldEnd--;
      newEnd--;
    }
    const ctxStart = Math.max(0, prefix - 3);
    const ctxAfter = Math.min(oldLines.length - 1, oldEnd + 3);
    for (let i = ctxStart;i < prefix; i++)
      body.push(` ${oldLines[i]}`);
    for (let i = prefix;i <= oldEnd; i++) {
      deletions++;
      body.push(`-${oldLines[i]}`);
    }
    for (let i = prefix;i <= newEnd; i++) {
      additions++;
      body.push(`+${newLines[i]}`);
    }
    for (let i = oldEnd + 1;i <= ctxAfter; i++)
      body.push(` ${oldLines[i]}`);
  }
  const header = [
    `--- ${status === "added" ? "/dev/null" : `a/${relPath}`}`,
    `+++ ${status === "deleted" ? "/dev/null" : `b/${relPath}`}`,
    `@@ -${oldLines.length ? 1 : 0},${oldLines.length} +${newLines.length ? 1 : 0},${newLines.length} @@`
  ];
  return {
    file: relPath,
    patch: [...header, ...body].join(`
`),
    additions,
    deletions,
    status
  };
}
async function discoverModelsFromEndpoint(host, options) {
  const base = normalizeBaseUrl(options.baseURL, options.protocol);
  const candidatesSet = new Set;
  if (base.endsWith("/v1") || base.endsWith("/openai") || /\/v\d+[a-z]*$/i.test(base)) {
    candidatesSet.add(`${base}/models`);
    const root = base.replace(/\/v1$/i, "");
    if (root !== base) {
      candidatesSet.add(`${root}/models`);
      candidatesSet.add(`${root}/api/v1/models`);
      candidatesSet.add(`${root}/api/tags`);
    }
  } else {
    candidatesSet.add(`${base}/v1/models`);
    candidatesSet.add(`${base}/models`);
    candidatesSet.add(`${base}/api/v1/models`);
    candidatesSet.add(`${base}/api/models`);
    candidatesSet.add(`${base}/api/tags`);
  }
  if (base.includes("generativelanguage.googleapis.com") && options.apiKey) {
    candidatesSet.add(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(options.apiKey.trim())}`);
  }
  const candidates = Array.from(candidatesSet);
  const headers = {
    Accept: "application/json",
    ...options.headers ?? {}
  };
  const trimmedKey = options.apiKey?.trim() ?? "";
  if (trimmedKey) {
    if (!headers["Authorization"] && !headers["authorization"]) {
      headers["Authorization"] = `Bearer ${trimmedKey}`;
    }
    if (options.protocol === "anthropic" || base.includes("anthropic")) {
      headers["x-api-key"] = trimmedKey;
      headers["anthropic-version"] = headers["anthropic-version"] ?? "2023-06-01";
    }
  }
  let lastError = "";
  for (const url of candidates) {
    try {
      const controller = new AbortController;
      const timer = setTimeout(() => controller.abort(), 12000);
      let res;
      try {
        res = await host.httpFetch(url, { method: "GET", headers, signal: controller.signal });
        if ((res.status === 401 || res.status === 403) && trimmedKey && !headers["x-api-key"]) {
          res = await host.httpFetch(url, {
            method: "GET",
            headers: { ...headers, "x-api-key": trimmedKey, "anthropic-version": "2023-06-01" },
            signal: controller.signal
          });
        }
      } finally {
        clearTimeout(timer);
      }
      if (!res.ok) {
        lastError = `HTTP ${res.status} from ${url}`;
        continue;
      }
      const rawText = await res.text();
      let json;
      try {
        json = JSON.parse(rawText);
      } catch {
        lastError = `Non-JSON response from ${url}`;
        continue;
      }
      const items = Array.isArray(json) ? json : Array.isArray(json?.data) ? json.data : Array.isArray(json?.models) ? json.models : Array.isArray(json?.result?.data) ? json.result.data : Array.isArray(json?.result?.models) ? json.result.models : Array.isArray(json?.result) ? json.result : [];
      const parsed = [];
      const seen = new Set;
      for (const item of items) {
        if (typeof item === "string") {
          const id = item.trim();
          if (!id || seen.has(id))
            continue;
          seen.add(id);
          parsed.push({ id, name: id, contextWindow: 128000, maxOutput: 16384, tools: true });
          continue;
        }
        if (!item || typeof item !== "object")
          continue;
        let rawId = String(item.id ?? item.model ?? item.name ?? "").trim();
        if (!rawId)
          continue;
        if (url.includes("generativelanguage.googleapis.com/v1beta/models") && rawId.startsWith("models/")) {
          rawId = rawId.slice("models/".length);
        }
        if (/^(text-embedding|embedding-|whisper-|tts-|omni-moderation|dall-e|babbage|davinci)/i.test(rawId)) {
          continue;
        }
        if (seen.has(rawId))
          continue;
        seen.add(rawId);
        const contextWindow = Number(item.context_length ?? item.max_model_len ?? item.context_window ?? item.inputTokenLimit ?? item.top_provider?.context_length ?? 128000) || 128000;
        const maxOutput = Number(item.max_completion_tokens ?? item.max_output_tokens ?? item.outputTokenLimit ?? item.top_provider?.max_completion_tokens ?? Math.min(32768, Math.max(4096, Math.floor(contextWindow / 4)))) || 16384;
        const modalities = Array.isArray(item.architecture?.input_modalities) ? item.architecture.input_modalities : [];
        const vision = modalities.includes("image") || /vision|vl|gpt-4o|gpt-4\.1|claude-3|claude-sonnet|claude-opus|gemini/i.test(rawId);
        const reasoning = Boolean(item.supported_parameters?.includes?.("reasoning")) || /reasoner|r1|qwq|o1|o3|o4|thinking/i.test(rawId);
        const inputCost = item.pricing?.prompt ? Number(item.pricing.prompt) * 1e6 : undefined;
        const outputCost = item.pricing?.completion ? Number(item.pricing.completion) * 1e6 : undefined;
        parsed.push({
          id: rawId,
          name: String(item.display_name ?? item.displayName ?? item.name ?? rawId),
          contextWindow,
          maxOutput,
          vision,
          reasoning,
          tools: true,
          ...Number.isFinite(inputCost) ? { inputCost } : {},
          ...Number.isFinite(outputCost) ? { outputCost } : {}
        });
      }
      if (parsed.length > 0) {
        return { models: parsed, endpointUsed: url };
      }
      lastError = `0 models listed at ${url}`;
    } catch (err) {
      lastError = err?.message ? String(err.message) : `Connection error to ${url}`;
    }
  }
  return { models: [], error: lastError || "Could not reach /v1/models endpoint" };
}
var CUSTOM_PROVIDER_FORM_FIELDS = [
  {
    key: "providerName",
    type: "string",
    title: "Provider Name",
    description: "Display name in OpenCode (e.g. My Proxy, DeepSeek, Ollama LAN, Together AI)",
    placeholder: "My Custom Provider",
    required: true
  },
  {
    key: "baseURL",
    type: "string",
    title: "API Base URL",
    description: "Endpoint root — OpenCode automatically queries /v1/models to pick up all available models",
    placeholder: "https://api.openai.com/v1",
    required: true
  },
  {
    key: "protocol",
    type: "string",
    title: "API Protocol",
    description: "Choose OpenAI-compatible (/chat/completions) or Anthropic (/v1/messages)",
    default: "openai",
    options: [
      { value: "openai", label: "OpenAI-Compatible (/v1/chat/completions + /v1/models)" },
      { value: "anthropic", label: "Anthropic-Compatible (/v1/messages + /v1/models)" }
    ],
    required: true
  },
  {
    key: "extraModels",
    type: "string",
    title: "Fallback Model IDs (optional)",
    description: "Leave blank to auto-detect via /v1/models, or comma-separate IDs if endpoint disables /models",
    placeholder: "gpt-4.1, qwen3-coder",
    required: false
  }
];

class OpenCodeV2Engine {
  host;
  state = {
    credentials: [],
    customProviders: {},
    builtinOverrides: {},
    sessions: {},
    config: { shell: "/bin/sh", default_agent: "build" }
  };
  initialized = false;
  initPromise = null;
  subscribers = new Set;
  runningAbortControllers = new Map;
  shells = new Map;
  ptys = new Map;
  constructor(host) {
    this.host = host;
  }
  async ensureReady() {
    if (this.initialized)
      return;
    if (this.initPromise)
      return this.initPromise;
    this.initPromise = (async () => {
      try {
        const raw = await this.host.loadState("opencode_v2_state");
        if (raw) {
          const parsed = JSON.parse(raw);
          this.state = {
            credentials: Array.isArray(parsed.credentials) ? parsed.credentials : [],
            customProviders: parsed.customProviders && typeof parsed.customProviders === "object" ? parsed.customProviders : {},
            builtinOverrides: parsed.builtinOverrides && typeof parsed.builtinOverrides === "object" ? parsed.builtinOverrides : {},
            sessions: parsed.sessions && typeof parsed.sessions === "object" ? parsed.sessions : {},
            config: parsed.config && typeof parsed.config === "object" ? parsed.config : { shell: "/bin/sh", default_agent: "build" }
          };
        }
      } catch {}
      await this.host.listProjects().catch(() => []);
      this.initialized = true;
    })();
    return this.initPromise;
  }
  async persist() {
    try {
      await this.host.saveState("opencode_v2_state", JSON.stringify(this.state));
    } catch {}
  }
  emitEvent(event) {
    const payload = {
      id: makeSortableId("evt_"),
      created: Date.now(),
      type: event.type,
      data: event.data
    };
    if (event.location)
      payload.location = event.location;
    if (event.durable)
      payload.durable = event.durable;
    const frame = `data: ${JSON.stringify(payload)}

`;
    for (const sub of Array.from(this.subscribers)) {
      if (sub.types && !sub.types.has(event.type))
        continue;
      try {
        sub.push(frame);
      } catch {
        this.subscribers.delete(sub);
      }
    }
  }
  emitCatalogUpdated(directory) {
    const loc = directory ? { directory } : undefined;
    this.emitEvent({ type: "credential.updated", data: {}, location: loc });
    this.emitEvent({ type: "integration.updated", data: {}, location: loc });
    this.emitEvent({ type: "provider.updated", data: {}, location: loc });
    this.emitEvent({ type: "model.updated", data: {}, location: loc });
  }
  async resolveLocation(requestedDir) {
    const projects = await this.host.listProjects();
    const defaultRoot = projects[0]?.directory ?? await this.host.getDefaultRoot();
    const dir = requestedDir && requestedDir.trim() || defaultRoot;
    const match = projects.find((p) => dir === p.directory || dir.startsWith(p.directory + "/"));
    if (match) {
      return {
        directory: dir,
        project: {
          id: match.id,
          directory: match.directory,
          canonical: match.directory
        }
      };
    }
    const cleanName = dir.split("/").filter(Boolean).pop() || "workspace";
    const synthId = `prj_${slugifyProviderId(cleanName)}`;
    return {
      directory: dir,
      project: {
        id: synthId,
        directory: dir,
        canonical: dir
      }
    };
  }
  extractQueryLocation(url) {
    return url.searchParams.get("location[directory]") ?? url.searchParams.get("directory") ?? undefined;
  }
  buildIntegrationsList() {
    const list = [];
    const customConnections = this.state.credentials.filter((c) => c.integrationID === "custom-provider").sort((a, b) => Number(b.active) - Number(a.active)).map((c) => ({
      type: "credential",
      id: c.id,
      label: c.label,
      method: c.value.type === "external" ? "external" : "key"
    }));
    list.push({
      id: "custom-provider",
      name: "Custom Provider (API Key + Auto Models)",
      metadata: { custom: true },
      methods: [
        {
          type: "key",
          label: "Connect with Base URL + API Key (auto-fetches /v1/models)",
          form: CUSTOM_PROVIDER_FORM_FIELDS
        }
      ],
      connections: customConnections
    });
    for (const cp of Object.values(this.state.customProviders)) {
      const creds = this.state.credentials.filter((c) => c.integrationID === cp.id).sort((a, b) => Number(b.active) - Number(a.active)).map((c) => ({
        type: "credential",
        id: c.id,
        label: c.label,
        method: c.value.type === "external" ? "external" : "key"
      }));
      list.push({
        id: cp.id,
        name: cp.name,
        metadata: {
          custom: true,
          baseURL: cp.baseURL,
          protocol: cp.protocol,
          modelCount: cp.discoveredModels.length
        },
        methods: [
          {
            type: "key",
            label: "Update API Key & Re-sync /v1/models",
            form: [
              {
                key: "baseURL",
                type: "string",
                title: "API Base URL",
                default: cp.baseURL,
                placeholder: cp.baseURL,
                required: true
              },
              {
                key: "protocol",
                type: "string",
                title: "Protocol",
                default: cp.protocol,
                options: [
                  { value: "openai", label: "OpenAI-Compatible" },
                  { value: "anthropic", label: "Anthropic-Compatible" }
                ],
                required: true
              }
            ]
          }
        ],
        connections: creds
      });
    }
    for (const preset of BUILTIN_PRESETS) {
      const override = this.state.builtinOverrides[preset.id];
      const creds = this.state.credentials.filter((c) => c.integrationID === preset.id).sort((a, b) => Number(b.active) - Number(a.active)).map((c) => ({
        type: "credential",
        id: c.id,
        label: c.label,
        method: c.value.type === "external" ? "external" : "key"
      }));
      const methods = [
        {
          type: "key",
          label: "Enter API Key (auto-discovers available models)",
          form: [
            {
              key: "baseURL",
              type: "string",
              title: "API Base URL (optional override)",
              description: `Default: ${override?.baseURL ?? preset.baseURL}`,
              default: override?.baseURL ?? preset.baseURL,
              placeholder: preset.baseURL,
              required: false
            }
          ]
        }
      ];
      if (preset.keyOptional) {
        methods.unshift({
          id: "local-endpoint",
          type: "external",
          label: "Connect Local / LAN Endpoint (No API Key)",
          form: [
            {
              key: "baseURL",
              type: "string",
              title: "Ollama / Local Server URL",
              description: "e.g. http://127.0.0.1:11434/v1 or http://192.168.1.10:11434/v1",
              default: override?.baseURL ?? preset.baseURL,
              placeholder: "http://127.0.0.1:11434/v1",
              required: true
            }
          ]
        });
      }
      if (preset.envNames.length > 0) {
        methods.push({ type: "env", names: preset.envNames });
      }
      list.push({
        id: preset.id,
        name: preset.name,
        methods,
        connections: creds
      });
    }
    return list;
  }
  buildProvidersAndModels() {
    const providers = [];
    const models = [];
    const pushModel = (providerID, pkg, m, _index) => {
      models.push({
        id: m.id,
        modelID: m.id,
        providerID,
        type: "chat",
        name: m.name || m.id,
        family: m.id,
        package: pkg,
        ...m.reasoning ? { compatibility: { reasoningField: "reasoning_content" } } : {},
        capabilities: {
          tools: m.tools !== false,
          input: m.vision ? ["text", "image"] : ["text"],
          output: ["text"],
          temperature: true
        },
        variants: [],
        time: { released: 0 },
        cost: [
          {
            input: m.inputCost ?? 0,
            output: m.outputCost ?? 0,
            cache: { read: 0, write: 0 }
          }
        ],
        status: "active",
        enabled: true,
        limit: {
          context: m.contextWindow || 128000,
          output: m.maxOutput || 16384
        }
      });
    };
    for (const cp of Object.values(this.state.customProviders)) {
      const hasCred = this.state.credentials.some((c) => c.integrationID === cp.id || c.integrationID === "custom-provider");
      if (!hasCred && cp.apiKey === "" && cp.discoveredModels.length === 0)
        continue;
      const pkg = cp.protocol === "anthropic" ? "@ai-sdk/anthropic" : "@ai-sdk/openai-compatible";
      providers.push({
        id: cp.id,
        integrationID: cp.id,
        name: cp.name,
        activation: "enabled",
        package: pkg,
        settings: {
          baseURL: cp.baseURL,
          protocol: cp.protocol,
          custom: true
        }
      });
      const modelList = cp.discoveredModels.length > 0 ? cp.discoveredModels : (cp.extraModels ?? []).map((id) => ({
        id,
        name: id,
        contextWindow: 128000,
        maxOutput: 16384,
        tools: true
      }));
      modelList.forEach((m, idx) => pushModel(cp.id, pkg, m, idx));
    }
    for (const preset of BUILTIN_PRESETS) {
      const activeCred = this.state.credentials.find((c) => c.integrationID === preset.id && c.active) ?? this.state.credentials.find((c) => c.integrationID === preset.id);
      if (!activeCred)
        continue;
      const override = this.state.builtinOverrides[preset.id];
      const pkg = preset.protocol === "anthropic" ? "@ai-sdk/anthropic" : "@ai-sdk/openai-compatible";
      providers.push({
        id: preset.id,
        integrationID: preset.id,
        name: preset.name,
        activation: "enabled",
        package: pkg,
        settings: {
          baseURL: override?.baseURL ?? preset.baseURL,
          protocol: preset.protocol
        }
      });
      const merged = new Map;
      for (const dm of override?.discoveredModels ?? []) {
        merged.set(dm.id, dm);
      }
      for (const pm of preset.defaultModels) {
        if (!merged.has(pm.id))
          merged.set(pm.id, pm);
      }
      Array.from(merged.values()).forEach((m, idx) => pushModel(preset.id, pkg, m, idx));
    }
    return { providers, models };
  }
  async upsertCustomProvider(input) {
    const protocol = input.protocol === "anthropic" ? "anthropic" : "openai";
    const name = input.name.trim() || "Custom Provider";
    const id = input.id?.trim() ? slugifyProviderId(input.id) : slugifyProviderId(name);
    const baseURL = normalizeBaseUrl(input.baseURL, protocol);
    const existing = this.state.customProviders[id];
    const apiKey = input.apiKey !== undefined ? input.apiKey.trim() : existing?.apiKey ?? "";
    const extraList = Array.isArray(input.extraModels) ? input.extraModels.map((s) => s.trim()).filter(Boolean) : typeof input.extraModels === "string" ? input.extraModels.split(/[,\n]+/).map((s) => s.trim()).filter(Boolean) : existing?.extraModels ?? [];
    const preDiscovered = Array.isArray(input.discoveredModels) ? input.discoveredModels.filter((m) => m && typeof m.id === "string" && m.id.trim()) : [];
    const discovery = preDiscovered.length > 0 ? { models: preDiscovered, endpointUsed: "auto-discovered" } : await discoverModelsFromEndpoint(this.host, {
      baseURL,
      apiKey,
      protocol,
      headers: input.headers ?? existing?.headers
    });
    const mergedModels = new Map;
    for (const m of discovery.models)
      mergedModels.set(m.id, m);
    for (const extraId of extraList) {
      if (!mergedModels.has(extraId)) {
        mergedModels.set(extraId, {
          id: extraId,
          name: extraId,
          contextWindow: 128000,
          maxOutput: 16384,
          tools: true
        });
      }
    }
    if (mergedModels.size === 0 && existing?.discoveredModels?.length) {
      for (const prev of existing.discoveredModels)
        mergedModels.set(prev.id, prev);
    }
    const record = {
      id,
      name,
      baseURL,
      protocol,
      apiKey,
      headers: input.headers ?? existing?.headers,
      extraModels: extraList,
      discoveredModels: Array.from(mergedModels.values()),
      lastSyncedAt: Date.now(),
      lastError: discovery.models.length === 0 ? discovery.error : undefined
    };
    this.state.customProviders[id] = record;
    this.state.credentials = this.state.credentials.filter((c) => c.integrationID !== id);
    this.state.credentials.push({
      id: makeSortableId("cred_"),
      integrationID: id,
      label: `${name} (${new URL(baseURL).host})`,
      active: true,
      value: apiKey ? { type: "key", key: apiKey, metadata: { baseURL, protocol } } : { type: "external", methodID: "keyless-local", metadata: { baseURL, protocol } }
    });
    if (input.integrationAlias === "custom-provider") {
      this.state.credentials = this.state.credentials.filter((c) => c.integrationID !== "custom-provider");
      this.state.credentials.push({
        id: makeSortableId("cred_"),
        integrationID: "custom-provider",
        label: `${name} (${record.discoveredModels.length} models)`,
        active: true,
        value: apiKey ? { type: "key", key: apiKey, metadata: { targetProviderID: id, baseURL, protocol } } : { type: "external", methodID: "keyless-local", metadata: { targetProviderID: id, baseURL, protocol } }
      });
    }
    await this.persist();
    this.emitCatalogUpdated();
    return {
      provider: record,
      modelsDiscovered: discovery.models.length,
      endpointUsed: discovery.endpointUsed,
      warning: discovery.models.length === 0 ? discovery.error : undefined
    };
  }
  resolveProviderConnection(providerID) {
    const cp = this.state.customProviders[providerID];
    if (cp) {
      const cred = this.state.credentials.find((c) => c.integrationID === providerID && c.active) ?? this.state.credentials.find((c) => c.integrationID === providerID);
      const key = cred?.value.type === "key" ? cred.value.key : cp.apiKey;
      return {
        providerID,
        baseURL: cp.baseURL,
        protocol: cp.protocol,
        apiKey: key ?? "",
        headers: cp.headers ?? {}
      };
    }
    const preset = BUILTIN_PRESETS.find((p) => p.id === providerID);
    if (preset) {
      const cred = this.state.credentials.find((c) => c.integrationID === providerID && c.active) ?? this.state.credentials.find((c) => c.integrationID === providerID);
      if (!cred)
        return null;
      const override = this.state.builtinOverrides[providerID];
      return {
        providerID,
        baseURL: override?.baseURL ?? preset.baseURL,
        protocol: preset.protocol,
        apiKey: cred.value.type === "key" ? cred.value.key : "",
        headers: {}
      };
    }
    return null;
  }
  getAgentDefinitions() {
    const defaultPerms = [
      { action: "*", resource: "*", effect: "allow" },
      { action: "read", resource: "*.env", effect: "allow" }
    ];
    return [
      {
        id: "build",
        name: "build",
        description: "Default OpenCode agent with full file read/write/edit/delete and local shell execution.",
        request: { settings: {}, headers: {}, body: {} },
        mode: "primary",
        hidden: false,
        color: "#f97316",
        permissions: defaultPerms
      },
      {
        id: "plan",
        name: "plan",
        description: "Read-only planning & architecture agent. Inspects files and searches code without modifying files.",
        request: { settings: {}, headers: {}, body: {} },
        mode: "primary",
        hidden: false,
        color: "#3b82f6",
        permissions: defaultPerms
      },
      {
        id: "general",
        name: "general",
        description: "General-purpose subagent for focused research and multi-step coding tasks.",
        request: { settings: {}, headers: {}, body: {} },
        mode: "subagent",
        hidden: true,
        permissions: defaultPerms
      }
    ];
  }
  toPublicSession(s) {
    return {
      id: s.id,
      ...s.parentID ? { parentID: s.parentID } : {},
      projectID: s.projectID,
      ...s.agent ? { agent: s.agent } : {},
      ...s.model ? { model: s.model } : {},
      cost: s.cost,
      tokens: s.tokens,
      ...s.outcome ? { outcome: s.outcome } : {},
      time: s.time,
      ...s.title ? { title: s.title } : {},
      location: { directory: s.location.directory }
    };
  }
  nextSessionDurable(s, version = 1) {
    s.seq = (s.seq || 0) + 1;
    return {
      aggregateID: s.id,
      seq: s.seq,
      version
    };
  }
  getToolDefinitions(agentId) {
    const readOnly = agentId === "plan";
    const tools = [
      {
        name: "read",
        description: "Read the contents of a file in the project workspace with line numbers.",
        parameters: {
          type: "object",
          properties: {
            filePath: { type: "string", description: "Relative or absolute path to the file" },
            offset: { type: "integer", description: "1-based starting line number (optional)" },
            limit: { type: "integer", description: "Max lines to read (optional, default 250)" }
          },
          required: ["filePath"]
        }
      },
      {
        name: "list",
        description: "List files and directories at a given path in the workspace.",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string", description: "Directory path relative to workspace root (optional)" }
          }
        }
      },
      {
        name: "glob",
        description: "Find files by substring or glob-like query across the workspace.",
        parameters: {
          type: "object",
          properties: {
            pattern: { type: "string", description: "Filename or path pattern to match" }
          },
          required: ["pattern"]
        }
      },
      {
        name: "grep",
        description: "Search file contents using a regular expression across the workspace.",
        parameters: {
          type: "object",
          properties: {
            pattern: { type: "string", description: "Regex or text pattern to search for" },
            include: { type: "string", description: "Optional filename filter (e.g. .ts, .kt, .py)" }
          },
          required: ["pattern"]
        }
      }
    ];
    if (readOnly) {
      tools.push({
        name: "webfetch",
        description: "Fetch a URL over the network (GET by default) and return the response body as text/markdown.",
        parameters: {
          type: "object",
          properties: {
            url: { type: "string", description: "Absolute http(s) URL" },
            method: { type: "string", description: "HTTP method (default GET)" },
            maxLength: { type: "integer", description: "Max characters to return (default 60000)" }
          },
          required: ["url"]
        }
      }, {
        name: "todoread",
        description: "Read the current session task list.",
        parameters: { type: "object", properties: {} }
      });
    }
    if (!readOnly) {
      tools.push({
        name: "write",
        description: "Create a new file or overwrite an existing file in the local project workspace.",
        parameters: {
          type: "object",
          properties: {
            filePath: { type: "string", description: "Relative path inside workspace" },
            content: { type: "string", description: "Complete file content to write" }
          },
          required: ["filePath", "content"]
        }
      }, {
        name: "edit",
        description: "Edit an existing file by replacing oldString with newString.",
        parameters: {
          type: "object",
          properties: {
            filePath: { type: "string", description: "Relative path inside workspace" },
            oldString: { type: "string", description: "Exact text to find (whitespace-tolerant)" },
            newString: { type: "string", description: "Replacement text" },
            replaceAll: { type: "boolean", description: "Replace every occurrence" }
          },
          required: ["filePath", "oldString", "newString"]
        }
      }, {
        name: "delete_file",
        description: "Delete a file or directory inside the local project workspace.",
        parameters: {
          type: "object",
          properties: {
            filePath: { type: "string", description: "Relative path inside workspace to delete" }
          },
          required: ["filePath"]
        }
      }, {
        name: "bash",
        description: "Execute a shell command on the device and return stdout/stderr. Runs in the workspace by default; pass `workdir` to target any directory (/storage/emulated/0/..., /sdcard/..., internal workspaces). A portable toolchain (bash, curl, wget, git, jq, zip, unzip, tree, node, npm, python3) is on PATH.",
        parameters: {
          type: "object",
          properties: {
            command: { type: "string", description: "Shell command to execute" },
            workdir: {
              type: "string",
              description: "Directory to run the command in (absolute path or relative to the workspace)"
            },
            timeout: {
              type: "integer",
              description: "Timeout in milliseconds (default 120000, max 600000)"
            },
            description: { type: "string", description: "Short summary of what this command does" }
          },
          required: ["command"]
        }
      }, {
        name: "todowrite",
        description: "Create or update the session task list. Use it to plan multi-step work and mark progress (pending / in_progress / completed / cancelled).",
        parameters: {
          type: "object",
          properties: {
            todos: {
              type: "array",
              description: "The complete todo list (replaces the previous one)",
              items: {
                type: "object",
                properties: {
                  content: { type: "string", description: "Task description" },
                  status: {
                    type: "string",
                    description: "pending | in_progress | completed | cancelled"
                  }
                },
                required: ["content", "status"]
              }
            }
          },
          required: ["todos"]
        }
      }, {
        name: "webfetch",
        description: "Fetch a URL over the network (GET by default) and return the response body as text/markdown. Useful for reading documentation or APIs.",
        parameters: {
          type: "object",
          properties: {
            url: { type: "string", description: "Absolute http(s) URL" },
            method: { type: "string", description: "HTTP method (default GET)" },
            headers: {
              type: "object",
              description: "Extra request headers",
              additionalProperties: { type: "string" }
            },
            body: { type: "string", description: "Optional request body" },
            bodyText: { type: "string", description: "Optional request body (alias)" },
            maxLength: { type: "integer", description: "Max characters to return (default 60000)" }
          },
          required: ["url"]
        }
      }, {
        name: "todoread",
        description: "Read the current session task list.",
        parameters: { type: "object", properties: {} }
      });
    }
    return tools;
  }
  async executeAgentTool(session, name, args) {
    const dir = session.location.directory;
    const cleanRel = (raw) => {
      const trimmed = String(raw || "").trim();
      if (trimmed.startsWith(dir + "/"))
        return trimmed.slice(dir.length + 1);
      if (trimmed.startsWith("/storage/") || trimmed.startsWith("/sdcard/") || trimmed.startsWith("/mnt/")) {
        return trimmed;
      }
      return trimmed.replace(/^\/+/, "");
    };
    if (name === "read") {
      const rel = cleanRel(args.filePath ?? args.path ?? "");
      const res = await this.host.fsRead(dir, rel);
      if (!res.exists || res.text === undefined) {
        throw new Error(`File not found: ${rel}`);
      }
      const allLines = res.text.split(`
`);
      const start = Math.max(1, Number(args.offset ?? 1));
      const limit = Math.max(1, Math.min(1000, Number(args.limit ?? 250)));
      const slice = allLines.slice(start - 1, start - 1 + limit);
      const numbered = slice.map((l, idx) => `${String(start + idx).padStart(4, " ")} | ${l}`).join(`
`);
      return {
        output: `File: ${rel} (${allLines.length} lines)
${numbered}`,
        metadata: { filePath: rel, totalLines: allLines.length }
      };
    }
    if (name === "list") {
      const sub = args.path ? cleanRel(args.path) : undefined;
      const entries = await this.host.fsList(dir, sub);
      const formatted = entries.map((e) => `${e.type === "directory" ? "[DIR] " : "      "}${e.path}`).join(`
`);
      return { output: formatted || "(empty directory)", metadata: { count: entries.length } };
    }
    if (name === "glob") {
      const pattern = String(args.pattern ?? args.query ?? "").replace(/^\*\*\/|\*+/g, "");
      const matches = await this.host.fsFind(dir, pattern, "file", 100);
      return {
        output: matches.length ? matches.map((m) => m.path).join(`
`) : "No matching files found.",
        metadata: { count: matches.length }
      };
    }
    if (name === "grep") {
      const pattern = String(args.pattern ?? "");
      const matches = await this.host.fsGrep(dir, pattern, args.include ? String(args.include) : undefined, 80);
      return {
        output: matches.length ? matches.map((m) => `${m.path}:${m.line}: ${m.text}`).join(`
`) : `No matches found for /${pattern}/`,
        metadata: { count: matches.length }
      };
    }
    if (name === "write") {
      const rel = cleanRel(args.filePath ?? args.path ?? "");
      if (!rel)
        throw new Error("filePath is required");
      const prev = await this.host.fsRead(dir, rel);
      const content = String(args.content ?? "");
      await this.host.fsWrite(dir, rel, content);
      const diff = computeUnifiedDiff(rel, prev.exists ? prev.text : undefined, content);
      session.diffs = [...session.diffs.filter((d) => d.file !== rel), diff];
      this.emitEvent({
        type: "filesystem.changed",
        data: { file: rel, event: prev.exists ? "change" : "add" },
        location: { directory: dir }
      });
      return {
        output: `Wrote ${rel} (+${diff.additions} / -${diff.deletions} lines)`,
        metadata: { filePath: rel, diff: diff.patch, additions: diff.additions, deletions: diff.deletions }
      };
    }
    if (name === "edit") {
      const rel = cleanRel(args.filePath ?? args.path ?? "");
      const oldStr = String(args.oldString ?? "");
      const newStr = String(args.newString ?? "");
      const prev = await this.host.fsRead(dir, rel);
      if (!prev.exists || prev.text === undefined) {
        throw new Error(`File not found: ${rel}`);
      }
      const match = findFuzzyMatch(prev.text, oldStr);
      if (!match) {
        const hints = oldStr.split(`
`).map((l) => l.trim()).filter(Boolean).slice(0, 3);
        throw new Error(`oldString not found in ${rel}. Read the file first to get exact lines (looked for: ${hints.join(" / ") || "(empty)"}).`);
      }
      const occurrences = prev.text.split(oldStr).length - 1;
      if (occurrences > 1 && args.replaceAll !== true) {
        throw new Error(`oldString matches ${occurrences} locations in ${rel}. Add more surrounding context to make it unique, or pass replaceAll: true.`);
      }
      const updated = prev.text.slice(0, match.start) + newStr + prev.text.slice(match.end);
      await this.host.fsWrite(dir, rel, updated);
      const diff = computeUnifiedDiff(rel, prev.text, updated);
      session.diffs = [...session.diffs.filter((d) => d.file !== rel), diff];
      this.emitEvent({
        type: "filesystem.changed",
        data: { file: rel, event: "change" },
        location: { directory: dir }
      });
      return {
        output: `Edited ${rel} (+${diff.additions} / -${diff.deletions} lines)
${diff.patch}`,
        metadata: { filePath: rel, diff: diff.patch, additions: diff.additions, deletions: diff.deletions }
      };
    }
    if (name === "delete_file") {
      const rel = cleanRel(args.filePath ?? args.path ?? "");
      const prev = await this.host.fsRead(dir, rel);
      const ok = await this.host.fsDelete(dir, rel);
      if (!ok)
        throw new Error(`Failed to delete ${rel}`);
      const diff = computeUnifiedDiff(rel, prev.exists ? prev.text ?? "" : "", undefined);
      session.diffs = [...session.diffs.filter((d) => d.file !== rel), diff];
      this.emitEvent({
        type: "filesystem.changed",
        data: { file: rel, event: "unlink" },
        location: { directory: dir }
      });
      return {
        output: `Deleted ${rel}`,
        metadata: { filePath: rel }
      };
    }
    if (name === "bash") {
      const command = String(args.command ?? "");
      const targetDir = args.workdir ? resolveWorkdir(dir, String(args.workdir)) : dir;
      const timeout = Math.min(600000, Math.max(1000, Number(args.timeout ?? args.timeoutMs ?? 120000)));
      const res = await this.host.execShell(targetDir, command, timeout);
      const combined = [res.stdout, res.stderr ? `[stderr]
${res.stderr}` : ""].filter(Boolean).join(`
`).trim();
      session.time.updated = Date.now();
      await this.persist();
      return {
        output: `Exit code: ${res.exitCode} (${res.durationMs}ms) in ${targetDir}
${combined || "(no output)"}`,
        metadata: { exitCode: res.exitCode, durationMs: res.durationMs, command, workdir: targetDir }
      };
    }
    if (name === "todowrite") {
      const incoming = Array.isArray(args.todos) ? args.todos : [];
      const todos = incoming.map((t, idx) => ({
        id: String(t?.id ?? `todo_${idx + 1}`),
        content: String(t?.content ?? t?.text ?? ""),
        status: ["pending", "in_progress", "completed", "cancelled"].includes(String(t?.status)) ? String(t.status) : "pending"
      }));
      session.todos = todos;
      await this.persist();
      return {
        output: todos.length === 0 ? "Todo list cleared." : `Todo list updated:
` + todos.map((t) => `- [${t.status === "completed" ? "x" : t.status === "in_progress" ? "~" : " "}] ${t.content}`).join(`
`),
        metadata: { count: todos.length }
      };
    }
    if (name === "todoread") {
      const todos = session.todos ?? [];
      return {
        output: todos.length === 0 ? "(no todos)" : todos.map((t) => `- [${t.status}] ${t.content}`).join(`
`),
        metadata: { count: todos.length }
      };
    }
    if (name === "webfetch") {
      const url = String(args.url ?? "");
      if (!/^https?:\/\//i.test(url))
        throw new Error("webfetch requires an absolute http(s) URL");
      const maxLength = Math.min(400000, Math.max(1000, Number(args.maxLength ?? 60000)));
      const headers = {
        "User-Agent": "OpenCode/2.2.5 (android)",
        Accept: "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
        ...args.headers && typeof args.headers === "object" ? args.headers : {}
      };
      const res = await this.host.httpFetch(url, {
        method: String(args.method ?? "GET").toUpperCase(),
        headers,
        body: args.body !== undefined || args.bodyText !== undefined ? String(args.body ?? args.bodyText ?? "") : undefined
      });
      const contentType = res.headers.get("content-type") ?? "text/plain";
      const raw = await res.text();
      const text = contentType.includes("html") ? htmlToText(raw) : raw;
      const clipped = text.length > maxLength ? `${text.slice(0, maxLength)}
… [truncated ${text.length - maxLength} chars]` : text;
      return {
        output: `HTTP ${res.status} ${contentType}
${clipped}`,
        metadata: { url, status: res.status, contentType, bytes: raw.length }
      };
    }
    throw new Error(`Unknown tool: ${name}`);
  }
  async streamOpenAiStep(options) {
    const base = normalizeBaseUrl(options.conn.baseURL, "openai");
    const endpoint = base.endsWith("/chat/completions") ? base : `${base}/chat/completions`;
    const headers = {
      "Content-Type": "application/json",
      Accept: "text/event-stream, application/json",
      ...options.conn.headers
    };
    if (options.conn.apiKey) {
      headers["Authorization"] = `Bearer ${options.conn.apiKey}`;
    }
    const body = {
      model: options.modelID,
      stream: true,
      messages: [{ role: "system", content: options.systemPrompt }, ...options.history]
    };
    if (options.tools.length > 0) {
      body.tools = options.tools.map((t) => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters
        }
      }));
    }
    const doOpenAiFetch = async (reqBody) => {
      let lastErr = null;
      for (let attempt = 0;attempt < 3; attempt++) {
        if (options.signal.aborted)
          break;
        try {
          const r = await this.host.httpFetch(endpoint, {
            method: "POST",
            headers,
            body: JSON.stringify(reqBody),
            signal: options.signal
          });
          if ((r.status === 502 || r.status === 503 || r.status === 504) && attempt < 2) {
            const peek = await r.clone().text().catch(() => "");
            if (/unexpected end of stream|reset|eof|broken pipe|timeout/i.test(peek) || r.status >= 502) {
              await new Promise((res) => setTimeout(res, 300 * (attempt + 1)));
              continue;
            }
          }
          return r;
        } catch (err) {
          lastErr = err;
          if (options.signal.aborted || attempt === 2)
            throw err;
          await new Promise((res) => setTimeout(res, 300 * (attempt + 1)));
        }
      }
      throw lastErr ?? new Error("Connection failed");
    };
    let res = await doOpenAiFetch(body);
    if (!res.ok && res.status === 400 && body.tools) {
      const errBody = await res.text().catch(() => "");
      if (/tool|function/i.test(errBody)) {
        delete body.tools;
        res = await doOpenAiFetch(body);
      } else {
        throw new Error(`Provider returned HTTP ${res.status}: ${errBody.slice(0, 400)}`);
      }
    }
    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      throw new Error(`Provider HTTP ${res.status}: ${errBody.slice(0, 400)}`);
    }
    const ctype = res.headers.get("content-type") ?? "";
    if (!ctype.includes("event-stream") && !res.body) {
      const json = await res.json();
      const msg = json?.choices?.[0]?.message ?? {};
      const text = String(msg.content ?? "");
      const reasoning = String(msg.reasoning_content ?? msg.reasoning ?? "");
      if (reasoning)
        options.onReasoningDelta(reasoning);
      if (text)
        options.onTextDelta(text);
      const tcs = Array.isArray(msg.tool_calls) ? msg.tool_calls.map((tc, idx) => {
        const id = String(tc.id ?? `call_${idx}_${Date.now()}`);
        const name = String(tc.function?.name ?? "read");
        const args = typeof tc.function?.arguments === "string" ? tc.function.arguments : JSON.stringify(tc.function?.arguments ?? {});
        options.onToolStart(id, name);
        options.onToolDelta(id, args);
        return { id, name, arguments: args };
      }) : [];
      return {
        text,
        reasoning,
        toolCalls: tcs,
        usage: {
          input: Number(json?.usage?.prompt_tokens ?? 0),
          output: Number(json?.usage?.completion_tokens ?? 0),
          reasoning: Number(json?.usage?.completion_tokens_details?.reasoning_tokens ?? 0)
        },
        finishReason: tcs.length > 0 ? "tool-calls" : "stop"
      };
    }
    if (ctype.includes("application/json")) {
      const json = await res.json();
      const msg = json?.choices?.[0]?.message ?? {};
      const text = String(msg.content ?? "");
      const reasoning = String(msg.reasoning_content ?? msg.reasoning ?? "");
      if (reasoning)
        options.onReasoningDelta(reasoning);
      if (text)
        options.onTextDelta(text);
      const tcs = Array.isArray(msg.tool_calls) ? msg.tool_calls.map((tc, idx) => {
        const id = String(tc.id ?? `call_${idx}_${Date.now()}`);
        const name = String(tc.function?.name ?? "read");
        const args = typeof tc.function?.arguments === "string" ? tc.function.arguments : JSON.stringify(tc.function?.arguments ?? {});
        options.onToolStart(id, name);
        options.onToolDelta(id, args);
        return { id, name, arguments: args };
      }) : [];
      return {
        text,
        reasoning,
        toolCalls: tcs,
        usage: {
          input: Number(json?.usage?.prompt_tokens ?? 0),
          output: Number(json?.usage?.completion_tokens ?? 0),
          reasoning: Number(json?.usage?.completion_tokens_details?.reasoning_tokens ?? 0)
        },
        finishReason: tcs.length > 0 ? "tool-calls" : "stop"
      };
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder;
    let buffer = "";
    let text = "";
    let reasoning = "";
    let finishReason = "stop";
    const usage = { input: 0, output: 0, reasoning: 0 };
    const toolMap = new Map;
    let sawDone = false;
    while (true) {
      let done = false;
      let value;
      try {
        const chunkRead = await reader.read();
        done = chunkRead.done;
        value = chunkRead.value;
      } catch (readErr) {
        if (sawDone || text.length > 0 || toolMap.size > 0)
          break;
        throw readErr;
      }
      if (done)
        break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(`
`);
      buffer = lines.pop() ?? "";
      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line.startsWith("data:"))
          continue;
        const payload = line.slice(5).trim();
        if (!payload)
          continue;
        if (payload === "[DONE]") {
          sawDone = true;
          continue;
        }
        let chunk;
        try {
          chunk = JSON.parse(payload);
        } catch {
          continue;
        }
        if (chunk.usage) {
          usage.input = Number(chunk.usage.prompt_tokens ?? usage.input);
          usage.output = Number(chunk.usage.completion_tokens ?? usage.output);
          usage.reasoning = Number(chunk.usage.completion_tokens_details?.reasoning_tokens ?? usage.reasoning);
        }
        const choice = chunk.choices?.[0];
        if (!choice)
          continue;
        if (choice.finish_reason)
          finishReason = choice.finish_reason;
        const delta = choice.delta ?? {};
        const rDelta = delta.reasoning_content ?? delta.reasoning;
        if (typeof rDelta === "string" && rDelta.length > 0) {
          reasoning += rDelta;
          options.onReasoningDelta(rDelta);
        }
        if (typeof delta.content === "string" && delta.content.length > 0) {
          text += delta.content;
          options.onTextDelta(delta.content);
        }
        if (Array.isArray(delta.tool_calls)) {
          for (const tc of delta.tool_calls) {
            const idx = Number(tc.index ?? 0);
            let entry = toolMap.get(idx);
            if (!entry) {
              entry = {
                id: String(tc.id || `call_${idx}_${Date.now()}`),
                name: String(tc.function?.name || ""),
                arguments: "",
                started: false
              };
              toolMap.set(idx, entry);
            }
            if (tc.id)
              entry.id = String(tc.id);
            if (tc.function?.name)
              entry.name = String(tc.function.name);
            if (!entry.started && entry.name) {
              entry.started = true;
              options.onToolStart(entry.id, entry.name);
            }
            if (typeof tc.function?.arguments === "string" && tc.function.arguments.length > 0) {
              entry.arguments += tc.function.arguments;
              if (entry.started)
                options.onToolDelta(entry.id, tc.function.arguments);
            }
          }
        }
      }
    }
    const toolCalls = Array.from(toolMap.values()).filter((t) => t.name);
    return {
      text,
      reasoning,
      toolCalls,
      usage,
      finishReason: toolCalls.length > 0 ? "tool-calls" : finishReason === "tool_calls" ? "tool-calls" : "stop"
    };
  }
  async streamAnthropicStep(options) {
    const base = normalizeBaseUrl(options.conn.baseURL, "anthropic");
    const endpoint = base.endsWith("/messages") ? base : `${base}/messages`;
    const anthropicMsgs = [];
    for (const m of options.history) {
      if (m.role === "user") {
        anthropicMsgs.push({ role: "user", content: m.content });
      } else if (m.role === "assistant") {
        const blocks = [];
        if (m.content)
          blocks.push({ type: "text", text: m.content });
        if (Array.isArray(m.tool_calls)) {
          for (const tc of m.tool_calls) {
            let parsedInput = {};
            try {
              parsedInput = JSON.parse(tc.function.arguments || "{}");
            } catch {}
            blocks.push({
              type: "tool_use",
              id: tc.id,
              name: tc.function.name,
              input: parsedInput
            });
          }
        }
        if (blocks.length > 0)
          anthropicMsgs.push({ role: "assistant", content: blocks });
      } else if (m.role === "tool") {
        const prev = anthropicMsgs[anthropicMsgs.length - 1];
        const toolResultBlock = {
          type: "tool_result",
          tool_use_id: m.tool_call_id,
          content: String(m.content ?? "")
        };
        if (prev && prev.role === "user" && Array.isArray(prev.content)) {
          prev.content.push(toolResultBlock);
        } else {
          anthropicMsgs.push({ role: "user", content: [toolResultBlock] });
        }
      }
    }
    const headers = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "anthropic-version": "2023-06-01",
      ...options.conn.headers
    };
    if (options.conn.apiKey) {
      headers["x-api-key"] = options.conn.apiKey;
    }
    const body = {
      model: options.modelID,
      max_tokens: 8192,
      system: options.systemPrompt,
      stream: true,
      messages: anthropicMsgs,
      tools: options.tools.map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.parameters
      }))
    };
    const res = await this.host.httpFetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: options.signal
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Anthropic HTTP ${res.status}: ${errText.slice(0, 400)}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder;
    let buffer = "";
    let text = "";
    let reasoning = "";
    const usage = { input: 0, output: 0, reasoning: 0 };
    const toolBlocks = new Map;
    while (true) {
      const { done, value } = await reader.read();
      if (done)
        break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(`
`);
      buffer = lines.pop() ?? "";
      for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line.startsWith("data:"))
          continue;
        const payload = line.slice(5).trim();
        if (!payload)
          continue;
        let ev;
        try {
          ev = JSON.parse(payload);
        } catch {
          continue;
        }
        if (ev.type === "message_start" && ev.message?.usage) {
          usage.input = Number(ev.message.usage.input_tokens ?? 0);
        } else if (ev.type === "message_delta" && ev.usage) {
          usage.output = Number(ev.usage.output_tokens ?? usage.output);
        } else if (ev.type === "content_block_start" && ev.content_block?.type === "tool_use") {
          const idx = Number(ev.index ?? 0);
          const id = String(ev.content_block.id);
          const name = String(ev.content_block.name);
          toolBlocks.set(idx, { id, name, arguments: "" });
          options.onToolStart(id, name);
        } else if (ev.type === "content_block_delta") {
          const idx = Number(ev.index ?? 0);
          const d = ev.delta ?? {};
          if (d.type === "text_delta" && d.text) {
            text += d.text;
            options.onTextDelta(d.text);
          } else if (d.type === "thinking_delta" && d.thinking) {
            reasoning += d.thinking;
            options.onReasoningDelta(d.thinking);
          } else if (d.type === "input_json_delta" && d.partial_json) {
            const tb = toolBlocks.get(idx);
            if (tb) {
              tb.arguments += d.partial_json;
              options.onToolDelta(tb.id, d.partial_json);
            }
          }
        }
      }
    }
    const toolCalls = Array.from(toolBlocks.values());
    return {
      text,
      reasoning,
      toolCalls,
      usage,
      finishReason: toolCalls.length > 0 ? "tool-calls" : "stop"
    };
  }
  async runSessionLoop(session, userMsgId) {
    if (this.runningAbortControllers.has(session.id))
      return;
    const abortController = new AbortController;
    this.runningAbortControllers.set(session.id, abortController);
    const loc = { directory: session.location.directory };
    session.time.busy = Date.now();
    session.time.updated = Date.now();
    this.emitEvent({
      type: "session.inbox.delivered",
      data: { sessionID: session.id, inboxID: userMsgId },
      location: loc,
      durable: this.nextSessionDurable(session)
    });
    this.emitEvent({
      type: "session.execution.started",
      data: { sessionID: session.id },
      location: loc,
      durable: this.nextSessionDurable(session)
    });
    try {
      const { providers, models } = this.buildProvidersAndModels();
      let activeModel = session.model;
      if (!activeModel || !providers.some((p) => p.id === activeModel.providerID)) {
        const first = models[0];
        if (first) {
          activeModel = { providerID: first.providerID, id: first.id };
          session.model = activeModel;
        }
      }
      const conn = activeModel ? this.resolveProviderConnection(activeModel.providerID) : null;
      if (!activeModel || !conn) {
        const msgId = makeSortableId("msg_");
        const now = Date.now();
        const guideText = `### Connect a Provider or Add Your Own Custom Provider

` + `No AI provider is connected yet. Open **Settings → Providers** (or click **Connect provider** in the model picker) to:

` + "1. **Add a Custom Provider**: Enter any OpenAI-compatible or Anthropic-compatible **Base URL** + **API Key** (or local LAN Ollama URL) — OpenCode automatically queries `GET /v1/models` and picks up all available models.\n" + "2. **Connect a Built-in Provider**: Anthropic, OpenAI, Google Gemini, OpenRouter, DeepSeek, Groq, xAI, Mistral, or Ollama.";
        this.emitEvent({
          type: "session.step.started",
          data: {
            sessionID: session.id,
            assistantMessageID: msgId,
            agent: session.agent || "build",
            model: { providerID: "custom-provider", id: "unconfigured" },
            started: now
          },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        this.emitEvent({
          type: "session.text.started",
          data: { sessionID: session.id, assistantMessageID: msgId, ordinal: 0 },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        this.emitEvent({
          type: "session.text.delta",
          data: { sessionID: session.id, assistantMessageID: msgId, ordinal: 0, delta: guideText },
          location: loc
        });
        this.emitEvent({
          type: "session.text.ended",
          data: { sessionID: session.id, assistantMessageID: msgId, ordinal: 0, text: guideText },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        this.emitEvent({
          type: "session.step.streamed",
          data: { sessionID: session.id, assistantMessageID: msgId },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        this.emitEvent({
          type: "session.step.ended",
          data: {
            sessionID: session.id,
            assistantMessageID: msgId,
            finish: "stop",
            cost: 0,
            tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } }
          },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        session.messages.push({
          id: msgId,
          type: "assistant",
          agent: session.agent || "build",
          model: { providerID: "custom-provider", id: "unconfigured" },
          content: [{ type: "text", text: guideText }],
          finish: "stop",
          cost: 0,
          tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
          time: { created: now, streamed: Date.now(), completed: Date.now() }
        });
        session.messages.push({
          id: makeSortableId("msg_"),
          type: "idle",
          outcome: "succeeded",
          time: { created: Date.now() }
        });
        session.outcome = "succeeded";
        session.time.idle = Date.now();
        session.time.busy = undefined;
        session.time.updated = Date.now();
        this.emitEvent({
          type: "session.execution.succeeded",
          data: { sessionID: session.id },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        await this.persist();
        return;
      }
      const llmHistory = [];
      for (const m of session.messages) {
        if (m.type === "user") {
          llmHistory.push({ role: "user", content: m.text });
        } else if (m.type === "assistant") {
          const textParts = (m.content ?? []).filter((c) => c.type === "text").map((c) => c.text).join(`
`);
          const toolParts = (m.content ?? []).filter((c) => c.type === "tool");
          if (toolParts.length > 0) {
            llmHistory.push({
              role: "assistant",
              content: textParts || "",
              tool_calls: toolParts.map((tp) => ({
                id: tp.id,
                type: "function",
                function: {
                  name: tp.name,
                  arguments: JSON.stringify(tp.state?.input ?? {})
                }
              }))
            });
            for (const tp of toolParts) {
              const outText = tp.state?.status === "completed" ? (tp.state.content ?? []).map((c) => c.text ?? "").join(`
`) : `Error: ${tp.state?.error?.message ?? "Tool failed"}`;
              llmHistory.push({
                role: "tool",
                tool_call_id: tp.id,
                content: outText
              });
            }
          } else if (textParts) {
            llmHistory.push({ role: "assistant", content: textParts });
          }
        }
      }
      const agentMode = session.agent || "build";
      const systemPrompt = [
        `You are OpenCode (v2.2.5), an autonomous software engineering agent running locally in workspace: ${session.location.directory}.`,
        agentMode === "plan" ? "Active agent: PLAN (read-only). Inspect files, search code, and produce a clear implementation plan without modifying files." : "Active agent: BUILD (full access). Use read, list, glob, grep, write, edit, delete_file, and bash tools to inspect, build, edit, and verify code directly in the local workspace.",
        "Always read existing files before editing them, keep changes clean and accurate, and summarize what you accomplished concisely.",
        "The workspace can be ANY device directory (/storage/emulated/0/..., /sdcard/..., internal app storage). The bash tool accepts a `workdir` argument to run commands anywhere on the device, and PATH already contains a portable toolchain: bash, sh, curl, wget, git, jq, zip, unzip, tree, node, npm, python3, plus sed/awk/grep/find/tar from Android. Use those tools directly instead of claiming a command is unavailable.",
        "Use todowrite for multi-step work and webfetch to read web pages or APIs."
      ].join(`
`);
      const tools = this.getToolDefinitions(agentMode);
      for (let step = 0;step < 14; step++) {
        if (abortController.signal.aborted)
          break;
        const assistantMsgId = makeSortableId("msg_");
        const stepStartedAt = Date.now();
        let reasoningStarted = false;
        let textStarted = false;
        this.emitEvent({
          type: "session.step.started",
          data: {
            sessionID: session.id,
            assistantMessageID: assistantMsgId,
            agent: agentMode,
            model: activeModel,
            started: stepStartedAt
          },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        const onReasoningDelta = (delta) => {
          if (!reasoningStarted) {
            reasoningStarted = true;
            this.emitEvent({
              type: "session.reasoning.started",
              data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal: 0 },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          }
          this.emitEvent({
            type: "session.reasoning.delta",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal: 0, delta },
            location: loc
          });
        };
        const onTextDelta = (delta) => {
          const ordinal = reasoningStarted ? 1 : 0;
          if (!textStarted) {
            textStarted = true;
            this.emitEvent({
              type: "session.text.started",
              data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          }
          this.emitEvent({
            type: "session.text.delta",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal, delta },
            location: loc
          });
        };
        const onToolStart = (id, name) => {
          this.emitEvent({
            type: "session.tool.input.started",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, id, name },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
        };
        const onToolDelta = (id, delta) => {
          this.emitEvent({
            type: "session.tool.input.delta",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, id, delta },
            location: loc
          });
        };
        const stepResult = conn.protocol === "anthropic" ? await this.streamAnthropicStep({
          conn,
          modelID: activeModel.id,
          systemPrompt,
          history: llmHistory,
          tools,
          signal: abortController.signal,
          onReasoningDelta,
          onTextDelta,
          onToolStart,
          onToolDelta
        }) : await this.streamOpenAiStep({
          conn,
          modelID: activeModel.id,
          systemPrompt,
          history: llmHistory,
          tools,
          signal: abortController.signal,
          onReasoningDelta,
          onTextDelta,
          onToolStart,
          onToolDelta
        });
        const assistantContent = [];
        if (reasoningStarted) {
          this.emitEvent({
            type: "session.reasoning.ended",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal: 0, text: stepResult.reasoning },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          assistantContent.push({
            type: "reasoning",
            text: stepResult.reasoning,
            time: { created: stepStartedAt, completed: Date.now() }
          });
        }
        if (textStarted) {
          const ordinal = reasoningStarted ? 1 : 0;
          this.emitEvent({
            type: "session.text.ended",
            data: { sessionID: session.id, assistantMessageID: assistantMsgId, ordinal, text: stepResult.text },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          assistantContent.push({
            type: "text",
            text: stepResult.text
          });
        }
        this.emitEvent({
          type: "session.step.streamed",
          data: { sessionID: session.id, assistantMessageID: assistantMsgId },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        const changedFiles = [];
        if (stepResult.toolCalls.length > 0) {
          llmHistory.push({
            role: "assistant",
            content: stepResult.text || "",
            tool_calls: stepResult.toolCalls.map((tc) => ({
              id: tc.id,
              type: "function",
              function: { name: tc.name, arguments: tc.arguments || "{}" }
            }))
          });
          for (const tc of stepResult.toolCalls) {
            let parsedArgs = {};
            try {
              parsedArgs = JSON.parse(tc.arguments || "{}");
            } catch {
              parsedArgs = {};
            }
            const toolCreatedAt = Date.now();
            this.emitEvent({
              type: "session.tool.input.ended",
              data: {
                sessionID: session.id,
                assistantMessageID: assistantMsgId,
                id: tc.id,
                name: tc.name,
                input: tc.arguments || "{}"
              },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
            this.emitEvent({
              type: "session.tool.called",
              data: {
                sessionID: session.id,
                assistantMessageID: assistantMsgId,
                id: tc.id,
                name: tc.name,
                input: parsedArgs,
                executed: true
              },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
            try {
              const execRes = await this.executeAgentTool(session, tc.name, parsedArgs);
              if (execRes.metadata?.filePath && (tc.name === "write" || tc.name === "edit" || tc.name === "delete_file")) {
                changedFiles.push(execRes.metadata.filePath);
              }
              const contentArr = [{ type: "text", text: execRes.output }];
              this.emitEvent({
                type: "session.tool.success",
                data: {
                  sessionID: session.id,
                  assistantMessageID: assistantMsgId,
                  id: tc.id,
                  name: tc.name,
                  content: contentArr,
                  metadata: execRes.metadata ?? {},
                  executed: true
                },
                location: loc,
                durable: this.nextSessionDurable(session, 2)
              });
              assistantContent.push({
                type: "tool",
                id: tc.id,
                name: tc.name,
                executed: true,
                state: {
                  status: "completed",
                  input: parsedArgs,
                  content: contentArr,
                  metadata: execRes.metadata ?? {}
                },
                time: { created: toolCreatedAt, ran: toolCreatedAt, completed: Date.now() }
              });
              llmHistory.push({
                role: "tool",
                tool_call_id: tc.id,
                content: execRes.output
              });
            } catch (toolErr) {
              const errMsg = toolErr?.message ? String(toolErr.message) : "Tool execution error";
              const errObj = { type: "unknown", message: errMsg };
              this.emitEvent({
                type: "session.tool.failed",
                data: {
                  sessionID: session.id,
                  assistantMessageID: assistantMsgId,
                  id: tc.id,
                  name: tc.name,
                  error: errObj,
                  executed: true
                },
                location: loc,
                durable: this.nextSessionDurable(session, 2)
              });
              assistantContent.push({
                type: "tool",
                id: tc.id,
                name: tc.name,
                executed: true,
                state: {
                  status: "error",
                  input: parsedArgs,
                  error: errObj
                },
                time: { created: toolCreatedAt, ran: toolCreatedAt, completed: Date.now() }
              });
              llmHistory.push({
                role: "tool",
                tool_call_id: tc.id,
                content: `Error: ${errMsg}`
              });
            }
          }
        }
        const stepTokens = {
          input: stepResult.usage.input,
          output: stepResult.usage.output,
          reasoning: stepResult.usage.reasoning,
          cache: { read: 0, write: 0 }
        };
        session.tokens.input += stepTokens.input;
        session.tokens.output += stepTokens.output;
        session.tokens.reasoning += stepTokens.reasoning;
        const finish = stepResult.toolCalls.length > 0 ? "tool-calls" : "stop";
        this.emitEvent({
          type: "session.step.ended",
          data: {
            sessionID: session.id,
            assistantMessageID: assistantMsgId,
            finish,
            cost: 0,
            tokens: stepTokens,
            ...changedFiles.length > 0 ? { files: changedFiles } : {}
          },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
        this.emitEvent({
          type: "session.usage.updated",
          data: {
            sessionID: session.id,
            cost: session.cost,
            tokens: session.tokens
          },
          location: loc
        });
        session.messages.push({
          id: assistantMsgId,
          type: "assistant",
          agent: agentMode,
          model: activeModel,
          content: assistantContent,
          finish,
          cost: 0,
          tokens: stepTokens,
          ...changedFiles.length > 0 ? { snapshot: { files: changedFiles } } : {},
          time: { created: stepStartedAt, streamed: Date.now(), completed: Date.now() }
        });
        await this.persist();
        if (stepResult.toolCalls.length === 0)
          break;
      }
      session.messages.push({
        id: makeSortableId("msg_"),
        type: "idle",
        outcome: abortController.signal.aborted ? "interrupted" : "succeeded",
        time: { created: Date.now() }
      });
      session.outcome = abortController.signal.aborted ? "interrupted" : "succeeded";
      session.time.idle = Date.now();
      session.time.busy = undefined;
      session.time.updated = Date.now();
      if (abortController.signal.aborted) {
        this.emitEvent({
          type: "session.execution.interrupted",
          data: { sessionID: session.id, reason: "user" },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
      } else {
        this.emitEvent({
          type: "session.execution.succeeded",
          data: { sessionID: session.id },
          location: loc,
          durable: this.nextSessionDurable(session)
        });
      }
      await this.persist();
    } catch (err) {
      const errMsg = err?.message ? String(err.message) : "Execution failed";
      const errObj = { type: "unknown", message: errMsg };
      session.messages.push({
        id: makeSortableId("msg_"),
        type: "idle",
        outcome: "failed",
        error: errObj,
        time: { created: Date.now() }
      });
      session.outcome = "failed";
      session.time.idle = Date.now();
      session.time.busy = undefined;
      session.time.updated = Date.now();
      this.emitEvent({
        type: "session.execution.failed",
        data: { sessionID: session.id, error: errObj },
        location: loc,
        durable: this.nextSessionDurable(session)
      });
      await this.persist();
    } finally {
      this.runningAbortControllers.delete(session.id);
    }
  }
  async handle(request) {
    await this.ensureReady();
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const method = request.method.toUpperCase();
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "*"
    };
    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }
    const json = (data, status = 200) => new Response(JSON.stringify(data), {
      status,
      headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" }
    });
    const noContent = () => new Response(null, { status: 204, headers: corsHeaders });
    const readJson = async () => {
      try {
        const text = await request.text();
        return text ? JSON.parse(text) : {};
      } catch {
        return {};
      }
    };
    try {
      if (method === "GET" && path === "/api/info") {
        const defaultRoot = await this.host.getDefaultRoot();
        return json({
          version: "2.2.5",
          pid: this.host.platform === "android" ? 0 : 1,
          hostname: this.host.platform === "android" ? "android-local" : "opencode-local",
          urls: [url.origin],
          paths: { tmp: `${defaultRoot}/.tmp` },
          capabilities: { persistentPty: true }
        });
      }
      if (method === "POST" && path === "/api/pair") {
        return json({ code: "000000", expires_in: 300 });
      }
      if (method === "GET" && path === "/api/event") {
        const requestedTypes = url.searchParams.getAll("types");
        const filterSet = requestedTypes.length > 0 ? new Set(requestedTypes) : undefined;
        const encoder = new TextEncoder;
        let subEntry = null;
        let heartbeat = null;
        const stream = new ReadableStream({
          start: (controller) => {
            const connected = {
              id: makeSortableId("evt_"),
              type: "server.connected",
              data: {}
            };
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(connected)}

`));
            subEntry = {
              types: filterSet,
              push: (frame) => controller.enqueue(encoder.encode(frame)),
              close: () => {
                try {
                  controller.close();
                } catch {}
              }
            };
            this.subscribers.add(subEntry);
            heartbeat = setInterval(() => {
              try {
                controller.enqueue(encoder.encode(`: heartbeat

`));
              } catch {
                if (heartbeat)
                  clearInterval(heartbeat);
                if (subEntry)
                  this.subscribers.delete(subEntry);
              }
            }, 15000);
            heartbeat?.unref?.();
          },
          cancel: () => {
            if (heartbeat)
              clearInterval(heartbeat);
            if (subEntry)
              this.subscribers.delete(subEntry);
          }
        });
        request.signal?.addEventListener("abort", () => {
          if (heartbeat)
            clearInterval(heartbeat);
          if (subEntry)
            this.subscribers.delete(subEntry);
        });
        return new Response(stream, {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no"
          }
        });
      }
      if (method === "GET" && path === "/api/location") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json(loc);
      }
      if (method === "POST" && path === "/api/location/reload") {
        for (const cp of Object.values(this.state.customProviders)) {
          discoverModelsFromEndpoint(this.host, {
            baseURL: cp.baseURL,
            apiKey: cp.apiKey,
            protocol: cp.protocol,
            headers: cp.headers
          }).then((res) => {
            if (res.models.length > 0) {
              cp.discoveredModels = res.models;
              cp.lastSyncedAt = Date.now();
              this.persist();
              this.emitCatalogUpdated();
            }
          });
        }
        this.emitCatalogUpdated();
        return noContent();
      }
      if (method === "GET" && path === "/api/project") {
        const includeArchived = url.searchParams.get("archived") === "true";
        const rawProjects = await this.host.listProjects();
        const result = rawProjects.filter((p) => includeArchived || !p.archived).map((p) => ({
          id: p.id,
          canonical: p.directory,
          vcs: "git",
          name: p.name,
          ...p.icon ? { icon: p.icon } : {},
          ...p.commands ? { commands: p.commands } : {},
          time: {
            created: Math.floor(p.createdAt),
            updated: Math.floor(p.updatedAt),
            active: Math.floor(p.updatedAt),
            ...p.archived ? { archived: Math.floor(p.archived) } : {}
          },
          sandboxes: []
        }));
        return json(result);
      }
      const projectPatchMatch = /^\/api\/project\/([^/]+)$/.exec(path);
      if (method === "PATCH" && projectPatchMatch) {
        const projectID = decodeURIComponent(projectPatchMatch[1]);
        const body = await readJson();
        const list = await this.host.listProjects();
        const found = list.find((p) => p.id === projectID);
        const dir = body.canonical ?? found?.directory ?? await this.host.getDefaultRoot();
        const now = Date.now();
        const updated = {
          id: projectID,
          canonical: dir,
          vcs: "git",
          name: body.name ?? found?.name ?? dir.split("/").pop() ?? "Project",
          ...body.icon ? { icon: body.icon } : {},
          ...body.commands ? { commands: body.commands } : {},
          time: {
            created: Math.floor(found?.createdAt ?? now),
            updated: now,
            active: now
          },
          sandboxes: []
        };
        this.emitEvent({ type: "project.updated", data: updated });
        return json(updated);
      }
      if (method === "POST" && path === "/api/android/register-project") {
        const body = await readJson();
        const directory = String(body.directory ?? "").trim();
        if (!directory)
          return json({ message: "directory is required" }, 400);
        if (this.host.registerProject) {
          const registered = await this.host.registerProject(directory, body.name ? String(body.name) : undefined);
          return json({ project: registered }, 201);
        }
        const created = await this.host.createProject({
          name: body.name ? String(body.name) : directory.split("/").filter(Boolean).pop() ?? "workspace",
          template: "empty",
          directory
        });
        return json({ project: created }, 201);
      }
      if (method === "POST" && path === "/api/android/projects") {
        const body = await readJson();
        const created = await this.host.createProject({
          name: String(body.name ?? "new-project"),
          template: body.template ? String(body.template) : "empty",
          directory: body.directory ? String(body.directory) : undefined
        });
        const info = {
          id: created.id,
          canonical: created.directory,
          vcs: "git",
          name: created.name,
          time: {
            created: Math.floor(created.createdAt),
            updated: Math.floor(created.updatedAt),
            active: Math.floor(created.updatedAt)
          },
          sandboxes: []
        };
        this.emitEvent({ type: "project.updated", data: info });
        return json(info, 201);
      }
      if (method === "DELETE" && path === "/api/android/projects") {
        const body = await readJson();
        if (body.directory) {
          await this.host.deleteProject(String(body.directory));
        }
        return noContent();
      }
      if (path === "/api/worktree") {
        if (method === "GET") {
          const projectID = url.searchParams.get("projectID");
          const projects = await this.host.listProjects();
          const found = projects.find((p) => p.id === projectID) ?? projects[0];
          return json(found ? [{ directory: found.directory, strategy: "local" }] : []);
        }
        if (method === "POST") {
          const body = await readJson();
          const created = await this.host.createProject({
            name: body.name ?? body.branch ?? `worktree-${Date.now().toString(36)}`
          });
          return json({ directory: created.directory });
        }
        if (method === "DELETE") {
          return noContent();
        }
      }
      if (method === "POST" && path === "/api/worktree/refresh") {
        return noContent();
      }
      if (method === "GET" && path === "/api/android/custom-providers") {
        return json({
          providers: Object.values(this.state.customProviders).map((cp) => ({
            ...cp,
            apiKey: cp.apiKey ? `${cp.apiKey.slice(0, 4)}••••${cp.apiKey.slice(-3)}` : "",
            hasKey: Boolean(cp.apiKey)
          }))
        });
      }
      if (method === "POST" && path === "/api/android/discover-models") {
        const body = await readJson();
        const result = await discoverModelsFromEndpoint(this.host, {
          baseURL: String(body.baseURL ?? ""),
          apiKey: body.apiKey ? String(body.apiKey) : undefined,
          protocol: body.protocol === "anthropic" ? "anthropic" : "openai",
          headers: body.headers && typeof body.headers === "object" ? body.headers : undefined
        });
        return json(result);
      }
      if (method === "POST" && path === "/api/android/custom-providers") {
        const body = await readJson();
        const res = await this.upsertCustomProvider({
          id: body.id,
          name: String(body.name || "Custom Provider"),
          baseURL: String(body.baseURL || ""),
          protocol: body.protocol === "anthropic" ? "anthropic" : "openai",
          apiKey: body.apiKey !== undefined ? String(body.apiKey) : undefined,
          headers: body.headers,
          extraModels: body.extraModels,
          ...Array.isArray(body.discoveredModels) ? { discoveredModels: body.discoveredModels } : {}
        });
        return json(res, 201);
      }
      const customRefreshMatch = /^\/api\/android\/custom-providers\/([^/]+)\/refresh$/.exec(path);
      if (method === "POST" && customRefreshMatch) {
        const id = decodeURIComponent(customRefreshMatch[1]);
        const existing = this.state.customProviders[id];
        if (!existing)
          return json({ message: "Custom provider not found" }, 404);
        const res = await this.upsertCustomProvider({
          id: existing.id,
          name: existing.name,
          baseURL: existing.baseURL,
          protocol: existing.protocol,
          apiKey: existing.apiKey,
          headers: existing.headers,
          extraModels: existing.extraModels
        });
        return json(res);
      }
      const customDeleteMatch = /^\/api\/android\/custom-providers\/([^/]+)$/.exec(path);
      if (method === "DELETE" && customDeleteMatch) {
        const id = decodeURIComponent(customDeleteMatch[1]);
        delete this.state.customProviders[id];
        this.state.credentials = this.state.credentials.filter((c) => c.integrationID !== id);
        await this.persist();
        this.emitCatalogUpdated();
        return noContent();
      }
      if (method === "GET" && path === "/api/integration") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: this.buildIntegrationsList() });
      }
      const integrationGetMatch = /^\/api\/integration\/([^/]+)$/.exec(path);
      if (method === "GET" && integrationGetMatch) {
        const id = decodeURIComponent(integrationGetMatch[1]);
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const item = this.buildIntegrationsList().find((i) => i.id === id);
        if (!item) {
          return json({ _tag: "IntegrationNotFoundError", integrationID: id, message: `Unknown integration: ${id}` }, 404);
        }
        return json({ location: { directory: loc.directory }, data: item });
      }
      const connectKeyMatch = /^\/api\/integration\/([^/]+)\/connect\/key$/.exec(path);
      if (method === "POST" && connectKeyMatch) {
        const integrationID = decodeURIComponent(connectKeyMatch[1]);
        const body = await readJson();
        const key = String(body.key ?? "").trim();
        const answer = body.answer ?? {};
        if (integrationID === "custom-provider" || this.state.customProviders[integrationID]) {
          const existing = this.state.customProviders[integrationID];
          await this.upsertCustomProvider({
            id: integrationID === "custom-provider" ? undefined : integrationID,
            name: String(answer.providerName ?? existing?.name ?? body.label ?? "Custom Provider"),
            baseURL: String(answer.baseURL ?? existing?.baseURL ?? "https://api.openai.com/v1"),
            protocol: (answer.protocol ?? existing?.protocol) === "anthropic" ? "anthropic" : "openai",
            apiKey: key,
            extraModels: answer.extraModels ? String(answer.extraModels) : existing?.extraModels,
            integrationAlias: integrationID === "custom-provider" ? "custom-provider" : undefined
          });
          return noContent();
        }
        const preset = BUILTIN_PRESETS.find((p) => p.id === integrationID);
        const baseURL = answer.baseURL ? normalizeBaseUrl(String(answer.baseURL), preset?.protocol ?? "openai") : preset?.baseURL ?? "https://api.openai.com/v1";
        for (const c of this.state.credentials) {
          if (c.integrationID === integrationID)
            c.active = false;
        }
        this.state.credentials.unshift({
          id: makeSortableId("cred_"),
          integrationID,
          label: String(body.label || `${preset?.name ?? integrationID} API Key`),
          active: true,
          value: { type: "key", key, metadata: { baseURL } }
        });
        const discovery = await discoverModelsFromEndpoint(this.host, {
          baseURL,
          apiKey: key,
          protocol: preset?.protocol ?? "openai"
        });
        this.state.builtinOverrides[integrationID] = {
          baseURL,
          discoveredModels: discovery.models,
          lastSyncedAt: Date.now()
        };
        await this.persist();
        this.emitCatalogUpdated(this.extractQueryLocation(url));
        return noContent();
      }
      const connectExternalMatch = /^\/api\/integration\/([^/]+)\/connect\/external$/.exec(path);
      if (method === "POST" && connectExternalMatch) {
        const integrationID = decodeURIComponent(connectExternalMatch[1]);
        const body = await readJson();
        const answer = body.answer ?? {};
        if (integrationID === "custom-provider" || this.state.customProviders[integrationID]) {
          const existing = this.state.customProviders[integrationID];
          await this.upsertCustomProvider({
            id: integrationID === "custom-provider" ? undefined : integrationID,
            name: String(answer.providerName ?? existing?.name ?? body.label ?? "Local Custom Provider"),
            baseURL: String(answer.baseURL ?? existing?.baseURL ?? "http://127.0.0.1:11434/v1"),
            protocol: (answer.protocol ?? existing?.protocol) === "anthropic" ? "anthropic" : "openai",
            apiKey: "",
            extraModels: answer.extraModels ? String(answer.extraModels) : existing?.extraModels,
            integrationAlias: integrationID === "custom-provider" ? "custom-provider" : undefined
          });
          return noContent();
        }
        const preset = BUILTIN_PRESETS.find((p) => p.id === integrationID);
        const baseURL = normalizeBaseUrl(String(answer.baseURL ?? preset?.baseURL ?? "http://127.0.0.1:11434/v1"), preset?.protocol ?? "openai");
        for (const c of this.state.credentials) {
          if (c.integrationID === integrationID)
            c.active = false;
        }
        this.state.credentials.unshift({
          id: makeSortableId("cred_"),
          integrationID,
          label: String(body.label || `${preset?.name ?? integrationID} (${baseURL})`),
          active: true,
          value: { type: "external", methodID: String(body.methodID ?? "local-endpoint"), metadata: { baseURL } }
        });
        const discovery = await discoverModelsFromEndpoint(this.host, {
          baseURL,
          protocol: preset?.protocol ?? "openai"
        });
        this.state.builtinOverrides[integrationID] = {
          baseURL,
          discoveredModels: discovery.models,
          lastSyncedAt: Date.now()
        };
        await this.persist();
        this.emitCatalogUpdated(this.extractQueryLocation(url));
        return noContent();
      }
      if (path === "/api/credential") {
        if (method === "GET") {
          return json({ data: this.state.credentials });
        }
        if (method === "POST") {
          const body = await readJson();
          const entry = {
            id: body.id ?? makeSortableId("cred_"),
            integrationID: String(body.integrationID),
            label: String(body.label || body.integrationID),
            active: body.activate !== false,
            value: body.value
          };
          if (entry.active) {
            for (const c of this.state.credentials) {
              if (c.integrationID === entry.integrationID)
                c.active = false;
            }
          }
          this.state.credentials.unshift(entry);
          await this.persist();
          this.emitCatalogUpdated();
          return json({ data: entry });
        }
      }
      const credActivateMatch = /^\/api\/credential\/([^/]+)\/activate$/.exec(path);
      if (method === "POST" && credActivateMatch) {
        const credId = decodeURIComponent(credActivateMatch[1]);
        const target = this.state.credentials.find((c) => c.id === credId);
        if (target) {
          for (const c of this.state.credentials) {
            if (c.integrationID === target.integrationID)
              c.active = c.id === credId;
          }
          await this.persist();
          this.emitCatalogUpdated();
        }
        return noContent();
      }
      const credItemMatch = /^\/api\/credential\/([^/]+)$/.exec(path);
      if (credItemMatch) {
        const credId = decodeURIComponent(credItemMatch[1]);
        if (method === "PATCH") {
          const body = await readJson();
          const target = this.state.credentials.find((c) => c.id === credId);
          if (target && body.label) {
            target.label = String(body.label);
            await this.persist();
            this.emitCatalogUpdated();
          }
          return noContent();
        }
        if (method === "DELETE") {
          const target = this.state.credentials.find((c) => c.id === credId);
          this.state.credentials = this.state.credentials.filter((c) => c.id !== credId);
          if (target && this.state.customProviders[target.integrationID]) {
            const remaining = this.state.credentials.some((c) => c.integrationID === target.integrationID);
            if (!remaining)
              delete this.state.customProviders[target.integrationID];
          }
          await this.persist();
          this.emitCatalogUpdated();
          return noContent();
        }
      }
      if (method === "GET" && path === "/api/provider") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const { providers } = this.buildProvidersAndModels();
        return json({ location: { directory: loc.directory }, data: providers });
      }
      const providerGetMatch = /^\/api\/provider\/([^/]+)$/.exec(path);
      if (method === "GET" && providerGetMatch) {
        const id = decodeURIComponent(providerGetMatch[1]);
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const { providers } = this.buildProvidersAndModels();
        const found = providers.find((p) => p.id === id);
        if (!found)
          return json({ _tag: "ProviderNotFoundError", providerID: id, message: "Provider not found" }, 404);
        return json({ location: { directory: loc.directory }, data: found });
      }
      if (method === "GET" && path === "/api/model/default") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const { models } = this.buildProvidersAndModels();
        return json({ location: { directory: loc.directory }, data: models[0] });
      }
      if (method === "GET" && path === "/api/model") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const { models } = this.buildProvidersAndModels();
        return json({ location: { directory: loc.directory }, data: models });
      }
      if (method === "GET" && path === "/api/agent") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: this.getAgentDefinitions() });
      }
      const agentGetMatch = /^\/api\/agent\/([^/]+)$/.exec(path);
      if (method === "GET" && agentGetMatch) {
        const id = decodeURIComponent(agentGetMatch[1]);
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const found = this.getAgentDefinitions().find((a) => a.id === id);
        if (!found)
          return json({ _tag: "AgentNotFoundError", agentID: id, message: "Agent not found" }, 404);
        return json({ location: { directory: loc.directory }, data: found });
      }
      if (method === "GET" && path === "/api/config") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json([
          {
            type: "document",
            path: `${loc.directory}/opencode.json`,
            info: {
              shell: this.state.config.shell ?? "/bin/sh",
              default_agent: this.state.config.default_agent ?? "build"
            }
          }
        ]);
      }
      if (method === "GET" && path === "/api/config/shell") {
        return json([
          { path: "/bin/sh", name: "sh (Android / POSIX Shell)", acceptable: true },
          { path: "/system/bin/sh", name: "Android System Shell", acceptable: true }
        ]);
      }
      if (method === "PATCH" && path === "/api/experimental/config") {
        const body = await readJson();
        if ("shell" in body)
          this.state.config.shell = body.shell;
        await this.persist();
        this.emitEvent({ type: "config.updated", data: {} });
        return noContent();
      }
      if (method === "GET" && path === "/api/command") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({
          location: { directory: loc.directory },
          data: [
            { name: "init", description: "Analyze workspace and create/update AGENTS.md project guide" },
            { name: "review", description: "Review uncommitted changes and diffs in the current workspace" },
            { name: "compact", description: "Summarize and compact conversation context" },
            { name: "status", description: "Show active provider, discovered models, and Android daemon status" }
          ]
        });
      }
      if (method === "GET" && path === "/api/skill") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/plugin") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/mcp") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/permission/request") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/permission/saved") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/websearch/provider") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: [] });
      }
      if (method === "GET" && path === "/api/fs/list") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const subPath = url.searchParams.get("path") ?? undefined;
        const entries = await this.host.fsList(loc.directory, subPath);
        return json({ location: { directory: loc.directory }, data: entries });
      }
      if (method === "GET" && path === "/api/fs/find") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const query = url.searchParams.get("query") ?? "";
        const typeParam = url.searchParams.get("type");
        const type = typeParam === "file" || typeParam === "directory" ? typeParam : undefined;
        const limit = Number(url.searchParams.get("limit") ?? 100) || 100;
        const entries = await this.host.fsFind(loc.directory, query, type, limit);
        return json({ location: { directory: loc.directory }, data: entries });
      }
      if (method === "GET" && path.startsWith("/api/fs/read/")) {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const relPath = path.slice("/api/fs/read/".length).split("/").map((seg) => decodeURIComponent(seg)).join("/");
        const fileRes = await this.host.fsRead(loc.directory, relPath);
        if (!fileRes.exists) {
          return json({ _tag: "FileNotFoundError", path: relPath, message: `File not found: ${relPath}` }, 404);
        }
        const bytes = fileRes.bytes ?? new TextEncoder().encode(fileRes.text ?? "");
        return new Response(bytes, {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": fileRes.mime ?? "text/plain; charset=utf-8",
            "Content-Length": String(bytes.byteLength)
          }
        });
      }
      if (method === "POST" && path === "/api/experimental/fs/write") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const targetPath = url.searchParams.get("path") ?? "untitled.txt";
        const rawBytes = new Uint8Array(await request.arrayBuffer());
        const written = await this.host.fsWrite(loc.directory, targetPath, rawBytes);
        this.emitEvent({
          type: "filesystem.changed",
          data: { file: targetPath, event: "change" },
          location: { directory: loc.directory }
        });
        return json({ location: { directory: loc.directory }, data: { path: written.path } });
      }
      if ((method === "POST" || method === "DELETE") && path === "/api/experimental/fs/watch") {
        return noContent();
      }
      if (method === "GET" && path === "/api/vcs") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({
          location: { directory: loc.directory },
          data: { provider: "git", branch: { current: "main", default: "main" } }
        });
      }
      if (method === "GET" && path === "/api/vcs/base") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({
          location: { directory: loc.directory },
          data: { name: "main", ref: "HEAD", source: "default" }
        });
      }
      if (method === "GET" && path === "/api/vcs/branch") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        return json({ location: { directory: loc.directory }, data: ["main"] });
      }
      if (method === "GET" && path === "/api/vcs/status") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const diffs = Object.values(this.state.sessions).filter((s) => s.location.directory === loc.directory).flatMap((s) => s.diffs);
        const byFile = new Map;
        for (const d of diffs) {
          byFile.set(d.file, {
            file: d.file,
            additions: d.additions,
            deletions: d.deletions,
            status: d.status
          });
        }
        return json({ location: { directory: loc.directory }, data: Array.from(byFile.values()) });
      }
      if (method === "GET" && path === "/api/vcs/diff") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const diffs = Object.values(this.state.sessions).filter((s) => s.location.directory === loc.directory).flatMap((s) => s.diffs);
        const byFile = new Map;
        for (const d of diffs)
          byFile.set(d.file, d);
        return json({ location: { directory: loc.directory }, data: Array.from(byFile.values()) });
      }
      if (method === "POST" && path === "/api/vcs/init") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        await this.host.execShell(loc.directory, "git init", 1e4).catch(() => {
          return;
        });
        return noContent();
      }
      if (method === "GET" && path === "/api/session/active") {
        const active = {};
        for (const id of this.runningAbortControllers.keys()) {
          active[id] = { type: "running" };
        }
        return json({ data: active });
      }
      if (method === "GET" && path === "/api/experimental/session/stats") {
        return json({
          data: {
            sessions: Object.keys(this.state.sessions).length,
            messages: 0,
            cost: 0,
            tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
            tools: []
          }
        });
      }
      if (path === "/api/session") {
        if (method === "GET") {
          const dirFilter = url.searchParams.get("directory");
          const projectFilter = url.searchParams.get("project");
          const archivedFilter = url.searchParams.get("archived");
          const searchFilter = url.searchParams.get("search")?.toLowerCase();
          const order = url.searchParams.get("order") === "asc" ? "asc" : "desc";
          let items = Object.values(this.state.sessions);
          if (dirFilter)
            items = items.filter((s) => s.location.directory === dirFilter);
          if (projectFilter)
            items = items.filter((s) => s.projectID === projectFilter);
          if (archivedFilter === "true")
            items = items.filter((s) => s.time.archived !== undefined);
          if (archivedFilter === "false")
            items = items.filter((s) => s.time.archived === undefined);
          if (searchFilter)
            items = items.filter((s) => (s.title ?? "").toLowerCase().includes(searchFilter));
          items.sort((a, b) => order === "asc" ? a.time.updated - b.time.updated : b.time.updated - a.time.updated);
          return json({
            data: items.map((s) => this.toPublicSession(s)),
            cursor: {}
          });
        }
        if (method === "POST") {
          const body = await readJson();
          const loc = await this.resolveLocation(body.location?.directory ?? this.extractQueryLocation(url));
          const { models } = this.buildProvidersAndModels();
          const now = Date.now();
          const sessionID = body.id ?? makeSortableId("ses_", true, now);
          const modelRef = body.model ?? (models[0] ? { providerID: models[0].providerID, id: models[0].id } : undefined);
          const session = {
            id: sessionID,
            ...body.parentID ? { parentID: body.parentID } : {},
            projectID: loc.project.id,
            agent: body.agent ?? "build",
            ...modelRef ? { model: modelRef } : {},
            cost: 0,
            tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
            time: { created: now, updated: now },
            ...body.title ? { title: String(body.title) } : {},
            location: { directory: loc.directory },
            messages: [],
            diffs: [],
            seq: 0
          };
          this.state.sessions[sessionID] = session;
          await this.persist();
          this.emitEvent({
            type: "session.created",
            data: {
              sessionID: session.id,
              projectID: session.projectID,
              location: { directory: session.location.directory },
              slug: session.id.slice(0, 12),
              ...session.title ? { title: session.title } : {},
              agent: session.agent,
              ...session.model ? { model: session.model } : {},
              version: "2.2.5"
            },
            location: { directory: session.location.directory },
            durable: this.nextSessionDurable(session)
          });
          return json({ data: this.toPublicSession(session) });
        }
      }
      const sessionMsgListMatch = /^\/api\/session\/([^/]+)\/message$/.exec(path);
      if (method === "GET" && sessionMsgListMatch) {
        const sessionID = decodeURIComponent(sessionMsgListMatch[1]);
        const session = this.state.sessions[sessionID];
        if (!session)
          return json({ _tag: "SessionNotFoundError", sessionID, message: "Session not found" }, 404);
        const order = url.searchParams.get("order");
        const typeFilter = url.searchParams.get("type");
        let msgs = [...session.messages];
        if (typeFilter)
          msgs = msgs.filter((m) => m.type === typeFilter);
        if (order === "desc")
          msgs.reverse();
        return json({ data: msgs, cursor: {} });
      }
      const sessionSingleMsgMatch = /^\/api\/session\/([^/]+)\/message\/([^/]+)$/.exec(path);
      if (method === "GET" && sessionSingleMsgMatch) {
        const sessionID = decodeURIComponent(sessionSingleMsgMatch[1]);
        const msgID = decodeURIComponent(sessionSingleMsgMatch[2]);
        const session = this.state.sessions[sessionID];
        if (!session)
          return json({ _tag: "SessionNotFoundError", sessionID, message: "Session not found" }, 404);
        const msg = session.messages.find((m) => m.id === msgID);
        if (!msg)
          return json({ _tag: "MessageNotFoundError", sessionID, messageID: msgID, message: "Not found" }, 404);
        return json({ data: msg });
      }
      const sessionActionMatch = /^\/api\/session\/([^/]+)\/([a-zA-Z0-9_-]+)$/.exec(path);
      if (sessionActionMatch) {
        const sessionID = decodeURIComponent(sessionActionMatch[1]);
        const action = sessionActionMatch[2];
        const session = this.state.sessions[sessionID];
        if (!session)
          return json({ _tag: "SessionNotFoundError", sessionID, message: "Session not found" }, 404);
        const loc = { directory: session.location.directory };
        if (method === "POST" && action === "prompt") {
          const body = await readJson();
          const msgID = body.id ?? makeSortableId("msg_");
          const now = Date.now();
          const text = String(body.text ?? "");
          if (!session.title && text.trim()) {
            session.title = text.trim().split(`
`)[0].slice(0, 72);
            this.emitEvent({
              type: "session.renamed",
              data: { sessionID: session.id, title: session.title },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          }
          const userMessage = {
            id: msgID,
            type: "user",
            text,
            time: { created: now }
          };
          session.messages.push(userMessage);
          session.time.updated = now;
          const inboxItem = {
            id: msgID,
            sessionID: session.id,
            time: { created: now },
            type: "user",
            payload: { text },
            delivery: body.delivery ?? "queue"
          };
          this.emitEvent({
            type: "session.inbox.enqueued",
            data: {
              sessionID: session.id,
              inboxID: msgID,
              item: { type: "user", payload: { text }, delivery: inboxItem.delivery }
            },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          await this.persist();
          if (body.resume !== false) {
            this.runSessionLoop(session, msgID);
          }
          return json({ data: inboxItem });
        }
        if (method === "POST" && action === "command") {
          const body = await readJson();
          const cmdName = String(body.name ?? "").replace(/^\//, "");
          const extra = String(body.text ?? "").trim();
          let promptText = `/${cmdName} ${extra}`.trim();
          if (cmdName === "init") {
            promptText = "Inspect the files in this workspace and create or update an AGENTS.md file documenting the project structure, build commands, and conventions.";
          } else if (cmdName === "review") {
            promptText = "Inspect recent workspace files and changes, and provide a thorough code review.";
          } else if (cmdName === "status") {
            const { providers, models } = this.buildProvidersAndModels();
            const sysMsg = {
              id: makeSortableId("msg_"),
              type: "system",
              text: `OpenCode v2.2.5 (${this.host.platform}) • Connected Providers: ${providers.length} • Available Models: ${models.length} • Workspace: ${session.location.directory}`,
              description: "Runtime Status",
              time: { created: Date.now() }
            };
            session.messages.push(sysMsg);
            await this.persist();
            return noContent();
          }
          const msgID = makeSortableId("msg_");
          session.messages.push({ id: msgID, type: "user", text: promptText, time: { created: Date.now() } });
          this.runSessionLoop(session, msgID);
          return noContent();
        }
        if (method === "POST" && action === "shell") {
          const body = await readJson();
          const cmd = String(body.command ?? "");
          const shId = makeSortableId("sh_");
          const startedAt = Date.now();
          const shellInfo = {
            id: shId,
            status: "running",
            command: cmd,
            cwd: session.location.directory,
            shell: "/bin/sh",
            file: `${session.location.directory}/.tmp/${shId}.log`,
            metadata: { sessionID: session.id },
            time: { started: startedAt }
          };
          this.emitEvent({
            type: "session.shell.started",
            data: { sessionID: session.id, shell: shellInfo },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          const res = await this.host.execShell(session.location.directory, cmd, 45000);
          const outText = [res.stdout, res.stderr].filter(Boolean).join(`
`);
          const completedAt = Date.now();
          const doneInfo = {
            ...shellInfo,
            status: "exited",
            exit: res.exitCode,
            time: { started: startedAt, completed: completedAt }
          };
          const outObj = {
            output: outText,
            cursor: outText.length,
            size: outText.length,
            truncated: false
          };
          session.messages.push({
            id: body.id ?? makeSortableId("msg_"),
            type: "shell",
            shellID: shId,
            command: cmd,
            status: "exited",
            exit: res.exitCode,
            output: outObj,
            time: { created: startedAt, completed: completedAt }
          });
          this.emitEvent({
            type: "session.shell.ended",
            data: { sessionID: session.id, shell: doneInfo, output: outObj },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          await this.persist();
          return noContent();
        }
        if (method === "POST" && action === "agent") {
          const body = await readJson();
          const prev = session.agent;
          session.agent = String(body.agent || "build");
          session.messages.push({
            id: makeSortableId("msg_"),
            type: "agent-switched",
            agent: session.agent,
            ...prev ? { previous: prev } : {},
            time: { created: Date.now() }
          });
          this.emitEvent({
            type: "session.agent.selected",
            data: { sessionID: session.id, agent: session.agent, ...prev ? { previous: prev } : {} },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          await this.persist();
          return noContent();
        }
        if (method === "POST" && action === "model") {
          const body = await readJson();
          const prev = session.model;
          session.model = body.model;
          session.messages.push({
            id: makeSortableId("msg_"),
            type: "model-switched",
            model: session.model,
            ...prev ? { previous: prev } : {},
            time: { created: Date.now() }
          });
          this.emitEvent({
            type: "session.model.selected",
            data: { sessionID: session.id, model: session.model, ...prev ? { previous: prev } : {} },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          await this.persist();
          return noContent();
        }
        if (method === "POST" && action === "interrupt") {
          const ctrl = this.runningAbortControllers.get(session.id);
          if (ctrl) {
            ctrl.abort();
            return json({ interrupted: true });
          }
          return json({ interrupted: false });
        }
        if (method === "POST" && action === "background") {
          return noContent();
        }
        if (method === "POST" && action === "view") {
          session.time.viewed = Date.now();
          this.emitEvent({
            type: "session.viewed",
            data: { sessionID: session.id, idle: session.time.idle ?? Date.now() },
            location: loc,
            durable: this.nextSessionDurable(session)
          });
          await this.persist();
          return noContent();
        }
        if (method === "POST" && action === "fork") {
          const now = Date.now();
          const forkId = makeSortableId("ses_", true, now);
          const forked = {
            ...JSON.parse(JSON.stringify(session)),
            id: forkId,
            parentID: session.id,
            title: `${session.title ?? "Session"} (fork)`,
            time: { created: now, updated: now },
            seq: 0
          };
          this.state.sessions[forkId] = forked;
          await this.persist();
          return json({ data: this.toPublicSession(forked) });
        }
        if (method === "POST" && action === "generate") {
          const body = await readJson();
          const text = String(body.prompt ?? "").slice(0, 60);
          return json({ data: { text: session.title || text || "Coding Session" } });
        }
        if (method === "GET" && action === "diff") {
          return json({ data: session.diffs });
        }
        if (method === "GET" && action === "inbox") {
          return json({ data: [] });
        }
        if (method === "GET" && action === "context") {
          return json({ data: session.messages });
        }
        if (method === "GET" && action === "form") {
          return json({ data: [] });
        }
        if (method === "GET" && action === "permission") {
          return json({ data: [] });
        }
      }
      const sessionItemMatch = /^\/api\/session\/([^/]+)$/.exec(path);
      if (sessionItemMatch) {
        const sessionID = decodeURIComponent(sessionItemMatch[1]);
        const session = this.state.sessions[sessionID];
        if (!session)
          return json({ _tag: "SessionNotFoundError", sessionID, message: "Session not found" }, 404);
        const loc = { directory: session.location.directory };
        if (method === "GET") {
          return json({ data: this.toPublicSession(session) });
        }
        if (method === "PATCH") {
          const body = await readJson();
          if (typeof body.title === "string") {
            session.title = body.title;
            this.emitEvent({
              type: "session.renamed",
              data: { sessionID: session.id, title: session.title },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          }
          if (body.archived === true) {
            session.time.archived = Date.now();
            this.emitEvent({
              type: "session.archived",
              data: { sessionID: session.id },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          } else if (body.archived === false) {
            session.time.archived = undefined;
            this.emitEvent({
              type: "session.unarchived",
              data: { sessionID: session.id },
              location: loc,
              durable: this.nextSessionDurable(session)
            });
          }
          session.time.updated = Date.now();
          await this.persist();
          return noContent();
        }
        if (method === "DELETE") {
          delete this.state.sessions[sessionID];
          await this.persist();
          this.emitEvent({
            type: "session.deleted",
            data: { sessionID },
            location: loc,
            durable: { aggregateID: sessionID, seq: 1, version: 2 }
          });
          return noContent();
        }
      }
      if (path === "/api/shell") {
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        if (method === "GET") {
          return json({ location: { directory: loc.directory }, data: [] });
        }
        if (method === "POST") {
          const body = await readJson();
          const id = makeSortableId("sh_");
          const started = Date.now();
          const shellDir = body.workdir ? resolveWorkdir(body.cwd ?? loc.directory, String(body.workdir)) : body.cwd ?? loc.directory;
          const res = await this.host.execShell(shellDir, String(body.command ?? ""), body.timeout ?? 30000);
          const output = [res.stdout, res.stderr].filter(Boolean).join(`
`);
          const info = {
            id,
            status: "exited",
            command: String(body.command ?? ""),
            cwd: body.cwd ?? loc.directory,
            shell: "/bin/sh",
            file: `${loc.directory}/.tmp/${id}.log`,
            exit: res.exitCode,
            metadata: body.metadata ?? {},
            time: { started, completed: Date.now() }
          };
          this.shells.set(id, { info, output });
          return json({ location: { directory: loc.directory }, data: info });
        }
      }
      const shellGetMatch = /^\/api\/shell\/([^/]+)$/.exec(path);
      if (shellGetMatch) {
        const id = decodeURIComponent(shellGetMatch[1]);
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        if (method === "DELETE") {
          this.shells.delete(id);
          return noContent();
        }
        const entry = this.shells.get(id);
        if (!entry)
          return json({ _tag: "ShellNotFoundError", id, message: "Shell not found" }, 404);
        return json({ location: { directory: loc.directory }, data: entry.info });
      }
      const shellOutMatch = /^\/api\/shell\/([^/]+)\/output$/.exec(path);
      if (method === "GET" && shellOutMatch) {
        const id = decodeURIComponent(shellOutMatch[1]);
        const loc = await this.resolveLocation(this.extractQueryLocation(url));
        const entry = this.shells.get(id);
        const out = entry?.output ?? "";
        return json({
          location: { directory: loc.directory },
          data: { output: out, cursor: out.length, size: out.length, truncated: false }
        });
      }
      const sessionTermMatch = /^\/api\/experimental\/session\/([^/]+)\/terminal$/.exec(path);
      if (sessionTermMatch) {
        const sessionID = decodeURIComponent(sessionTermMatch[1]);
        const session = this.state.sessions[sessionID];
        const cwd = session?.location.directory ?? await this.host.getDefaultRoot();
        if (method === "GET") {
          const list = Array.from(this.ptys.values()).filter((p) => p.info.sessionID === sessionID).map((p) => p.info);
          return json({ data: list });
        }
        if (method === "POST") {
          const body = await readJson();
          const ptyID = makeSortableId("pty_");
          const info = {
            id: ptyID,
            sessionID,
            title: String(body.title || "Terminal"),
            userTitle: null,
            command: body.command ?? "/bin/sh",
            args: Array.isArray(body.args) ? body.args : [],
            cwd: body.cwd ?? cwd,
            status: "running",
            pid: 1,
            foregroundProcess: "sh",
            size: body.size ?? { cols: 80, rows: 24 },
            output: { head: 0, tail: 0 }
          };
          const banner = `\x1B[1;38;5;208mOpenCode Terminal\x1B[0m (${this.host.platform}) — ${info.cwd}\r
$ `;
          this.ptys.set(ptyID, { info, text: banner, listeners: new Set });
          this.emitEvent({ type: "persistent-pty.added", data: { sessionID, terminal: info } });
          return json({ data: info });
        }
      }
      const ptySnapshotMatch = /^\/api\/experimental\/persistent-pty\/([^/]+)\/snapshot$/.exec(path);
      if (method === "GET" && ptySnapshotMatch) {
        const ptyID = decodeURIComponent(ptySnapshotMatch[1]);
        const pty = this.ptys.get(ptyID);
        if (!pty)
          return json({ _tag: "PtyNotFoundError", id: ptyID, message: "PTY not found" }, 404);
        return json({
          data: {
            info: pty.info,
            text: pty.text,
            checkpoint: [],
            cursor: { x: 2, y: 1 }
          }
        });
      }
      const ptyTokenMatch = /^\/api\/experimental\/persistent-pty\/([^/]+)\/connect-token$/.exec(path);
      if (method === "POST" && ptyTokenMatch) {
        return json({ data: { ticket: `tk_${Date.now()}`, expiresAt: Date.now() + 60000 } });
      }
      const ptyItemMatch = /^\/api\/experimental\/persistent-pty\/([^/]+)$/.exec(path);
      if (ptyItemMatch) {
        const ptyID = decodeURIComponent(ptyItemMatch[1]);
        const pty = this.ptys.get(ptyID);
        if (method === "DELETE") {
          if (pty) {
            this.ptys.delete(ptyID);
            this.emitEvent({ type: "persistent-pty.removed", data: { sessionID: pty.info.sessionID, ptyID } });
          }
          return noContent();
        }
        if (!pty)
          return json({ _tag: "PtyNotFoundError", id: ptyID, message: "PTY not found" }, 404);
        if (method === "GET")
          return json({ data: pty.info });
        if (method === "PUT") {
          const body = await readJson();
          if (body.size)
            pty.info.size = body.size;
          if ("title" in body) {
            pty.info.userTitle = body.title;
            if (body.title)
              pty.info.title = body.title;
          }
          return json({ data: pty.info });
        }
      }
      if (method === "POST" && (path === "/api/experimental/persistent-pty/shutdown" || path === "/api/experimental/persistent-pty/handoff")) {
        return path.endsWith("handoff") ? json({ handoff: null }) : noContent();
      }
      return json({ message: `Route not found: ${method} ${path}` }, 404);
    } catch (err) {
      return json({ message: err?.message ? String(err.message) : "Internal server error" }, 500);
    }
  }
  subscribePtyOutput(ptyID, listener) {
    const pty = this.ptys.get(ptyID);
    if (!pty)
      return () => {
        return;
      };
    const entry = pty;
    entry.outputListeners = entry.outputListeners ?? new Set;
    entry.outputListeners.add(listener);
    return () => {
      try {
        entry.outputListeners?.delete(listener);
      } catch {}
    };
  }
  async writePtyInput(ptyID, rawInput) {
    const pty = this.ptys.get(ptyID);
    if (!pty)
      return;
    const entry = pty;
    const emit = (bytes) => {
      for (const listener of Array.from(entry.outputListeners ?? [])) {
        try {
          listener(bytes);
        } catch {}
      }
    };
    await this.sendPtyInput(ptyID, rawInput, emit);
  }
  getPtyReplayBytes(ptyID) {
    const pty = this.ptys.get(ptyID);
    return new TextEncoder().encode(pty?.text ?? "$ ");
  }
  async sendPtyInput(ptyID, rawInput, onOutput) {
    const pty = this.ptys.get(ptyID);
    if (!pty)
      return;
    const encoder = new TextEncoder;
    const ptyState = pty;
    ptyState.lineBuf = ptyState.lineBuf ?? "";
    for (const ch of rawInput) {
      if (ch === "\r" || ch === `
`) {
        onOutput(encoder.encode(`\r
`));
        const cmd = String(ptyState.lineBuf).trim();
        ptyState.lineBuf = "";
        if (cmd === "clear") {
          pty.text = "$ ";
          onOutput(encoder.encode("\x1B[2J\x1B[H$ "));
          continue;
        }
        if (cmd) {
          const previousCwd = ptyState.previousCwd;
          const cdMatch = /^(?:cd|pushd)\s+(.+)$/.exec(cmd);
          const isBareCd = cmd === "cd" || cmd === "cd ~" || cmd === "cd -";
          if (cdMatch || isBareCd) {
            const target = isBareCd ? cmd === "cd -" ? previousCwd ?? pty.info.cwd : "~" : cdMatch[1].trim().replace(/^["']|["']$/g, "");
            const resolvedTarget = resolveWorkdir(pty.info.cwd, target);
            const res = await this.host.execShell(pty.info.cwd, `cd ${JSON.stringify(resolvedTarget)} && pwd`, 8000);
            const newCwd = res.exitCode === 0 ? res.stdout.trim().split(`
`).pop()?.trim() : undefined;
            if (newCwd) {
              ptyState.previousCwd = pty.info.cwd;
              pty.info.cwd = newCwd;
              pty.info.foregroundProcess = "sh";
            } else {
              const message = (res.stderr || `cd: no such file or directory: ${target}`).replace(/\r?\n/g, `\r
`);
              pty.text = (pty.text + message + `\r
`).slice(-16000);
              onOutput(encoder.encode(message + `\r
`));
            }
          } else {
            const res = await this.host.execShell(pty.info.cwd, cmd, 30000);
            const combined = [res.stdout, res.stderr].filter(Boolean).join(`
`);
            if (combined) {
              const formatted = combined.replace(/\r?\n/g, `\r
`) + `\r
`;
              pty.text = (pty.text + formatted).slice(-16000);
              onOutput(encoder.encode(formatted));
            }
          }
        }
        onOutput(encoder.encode(`${pty.info.cwd.split("/").pop() || "/"} $ `));
      } else if (ch === "" || ch === "\b") {
        if (ptyState.lineBuf.length > 0) {
          ptyState.lineBuf = ptyState.lineBuf.slice(0, -1);
          onOutput(encoder.encode("\b \b"));
        }
      } else if (ch === "\x03") {
        ptyState.lineBuf = "";
        onOutput(encoder.encode(`^C\r
$ `));
      } else {
        ptyState.lineBuf += ch;
        onOutput(encoder.encode(ch));
      }
    }
  }
}
export {
  OpenCodeV2Engine,
  discoverModelsFromEndpoint,
  makeSortableId,
  normalizeBaseUrl
};
