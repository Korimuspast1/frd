import type { AgentId, EffortLevel, ProviderConfig, ToolName } from '../types/opencode';
import type { OpenCodeToolSchema } from './tools';
import { PlatformBridge } from '../bridge/platformBridge';

export interface LlmChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  toolCalls?: Array<{
    id: string;
    name: ToolName;
    argumentsJson: string;
  }>;
  toolCallId?: string;
  toolName?: string;
}

export interface StreamTurnResult {
  text: string;
  thinking: string;
  toolCalls: Array<{
    id: string;
    name: ToolName;
    input: Record<string, unknown>;
  }>;
  usage?: { input: number; output: number };
}

function safeJsonParse(raw: string): Record<string, unknown> {
  if (!raw || !raw.trim()) return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return { raw };
  }
}

export async function streamLlmCompletion(params: {
  provider: ProviderConfig;
  modelId: string;
  agent: AgentId;
  effort: EffortLevel;
  messages: LlmChatMessage[];
  tools: OpenCodeToolSchema[];
  projectId: string;
  onTextDelta: (delta: string) => void;
  onThinkingDelta: (delta: string) => void;
  signal?: AbortSignal;
}): Promise<StreamTurnResult> {
  const { provider, modelId } = params;

  // Built-in Offline Local Agent mode (works immediately without external API key!)
  if (provider.id === 'demo' || (!provider.apiKey && provider.id !== 'ollama')) {
    return runBuiltinSmartOfflineTurn(params);
  }

  if (provider.id === 'anthropic') {
    return streamAnthropicTurn(params);
  }

  return streamOpenAiCompatibleTurn(params);
}

async function streamOpenAiCompatibleTurn(params: {
  provider: ProviderConfig;
  modelId: string;
  effort: EffortLevel;
  messages: LlmChatMessage[];
  tools: OpenCodeToolSchema[];
  onTextDelta: (delta: string) => void;
  onThinkingDelta: (delta: string) => void;
  signal?: AbortSignal;
}): Promise<StreamTurnResult> {
  const baseUrl = params.provider.baseUrl.replace(/\/$/, '');
  const url = `${baseUrl}/chat/completions`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (params.provider.apiKey) {
    headers['Authorization'] = `Bearer ${params.provider.apiKey}`;
  }
  if (params.provider.id === 'openrouter') {
    headers['HTTP-Referer'] = 'https://opencode.ai';
    headers['X-Title'] = 'OpenCode Android';
  }

  const formattedMessages = params.messages.map((m) => {
    if (m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0) {
      return {
        role: 'assistant',
        content: m.content || null,
        tool_calls: m.toolCalls.map((tc) => ({
          id: tc.id,
          type: 'function',
          function: {
            name: tc.name,
            arguments: tc.argumentsJson,
          },
        })),
      };
    }
    if (m.role === 'tool') {
      return {
        role: 'tool',
        tool_call_id: m.toolCallId,
        content: m.content,
      };
    }
    return {
      role: m.role,
      content: m.content,
    };
  });

  const body: Record<string, unknown> = {
    model: params.modelId,
    stream: true,
    messages: formattedMessages,
  };

  if (params.tools.length > 0) {
    body.tools = params.tools.map((t) => ({
      type: 'function',
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      },
    }));
  }

  const res = await PlatformBridge.proxyStream(url, 'POST', headers, body, params.signal);
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`${params.provider.name} API (${res.status}): ${errText.slice(0, 400)}`);
  }

  let text = '';
  let thinking = '';
  const toolMap = new Map<number, { id: string; name: string; args: string }>();
  let usage: { input: number; output: number } | undefined;

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body stream available');
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;

      let parsed: Record<string, any>;
      try {
        parsed = JSON.parse(payload);
      } catch {
        continue;
      }

      if (parsed.error) {
        throw new Error(parsed.error.message || JSON.stringify(parsed.error));
      }

      if (parsed.usage) {
        usage = {
          input: Number(parsed.usage.prompt_tokens ?? 0),
          output: Number(parsed.usage.completion_tokens ?? 0),
        };
      }

      const choice = parsed.choices?.[0];
      if (!choice) continue;
      const delta = choice.delta ?? {};

      if (typeof delta.reasoning_content === 'string' && delta.reasoning_content) {
        thinking += delta.reasoning_content;
        params.onThinkingDelta(delta.reasoning_content);
      } else if (typeof delta.reasoning === 'string' && delta.reasoning) {
        thinking += delta.reasoning;
        params.onThinkingDelta(delta.reasoning);
      }

      if (typeof delta.content === 'string' && delta.content) {
        text += delta.content;
        params.onTextDelta(delta.content);
      }

      if (Array.isArray(delta.tool_calls)) {
        for (const tc of delta.tool_calls) {
          const idx = typeof tc.index === 'number' ? tc.index : 0;
          const existing = toolMap.get(idx) ?? {
            id: tc.id || `call_${Date.now()}_${idx}`,
            name: '',
            args: '',
          };
          if (tc.id) existing.id = tc.id;
          if (tc.function?.name) existing.name += tc.function.name;
          if (tc.function?.arguments) existing.args += tc.function.arguments;
          toolMap.set(idx, existing);
        }
      }
    }
  }

  const toolCalls = Array.from(toolMap.values())
    .filter((tc) => tc.name)
    .map((tc) => ({
      id: tc.id,
      name: tc.name as ToolName,
      input: safeJsonParse(tc.args),
    }));

  return { text, thinking, toolCalls, usage };
}

async function streamAnthropicTurn(params: {
  provider: ProviderConfig;
  modelId: string;
  effort: EffortLevel;
  messages: LlmChatMessage[];
  tools: OpenCodeToolSchema[];
  onTextDelta: (delta: string) => void;
  onThinkingDelta: (delta: string) => void;
  signal?: AbortSignal;
}): Promise<StreamTurnResult> {
  const baseUrl = params.provider.baseUrl.replace(/\/$/, '');
  const url = `${baseUrl}/messages`;

  const systemMsg = params.messages
    .filter((m) => m.role === 'system')
    .map((m) => m.content)
    .join('\n\n');

  const anthropicMsgs: Array<Record<string, unknown>> = [];
  for (const m of params.messages) {
    if (m.role === 'system') continue;
    if (m.role === 'assistant') {
      const contentBlocks: Array<Record<string, unknown>> = [];
      if (m.content) contentBlocks.push({ type: 'text', text: m.content });
      if (m.toolCalls) {
        for (const tc of m.toolCalls) {
          contentBlocks.push({
            type: 'tool_use',
            id: tc.id,
            name: tc.name,
            input: safeJsonParse(tc.argumentsJson),
          });
        }
      }
      anthropicMsgs.push({ role: 'assistant', content: contentBlocks });
    } else if (m.role === 'tool') {
      const prev = anthropicMsgs[anthropicMsgs.length - 1];
      const resultBlock = {
        type: 'tool_result',
        tool_use_id: m.toolCallId,
        content: m.content,
      };
      if (prev && prev.role === 'user' && Array.isArray(prev.content)) {
        (prev.content as Array<Record<string, unknown>>).push(resultBlock);
      } else {
        anthropicMsgs.push({ role: 'user', content: [resultBlock] });
      }
    } else {
      anthropicMsgs.push({ role: 'user', content: m.content });
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'x-api-key': params.provider.apiKey,
    'anthropic-version': '2023-06-01',
  };

  const body: Record<string, unknown> = {
    model: params.modelId,
    max_tokens: 8192,
    system: systemMsg,
    messages: anthropicMsgs,
    stream: true,
    tools: params.tools.map((t) => ({
      name: t.name,
      description: t.description,
      input_schema: t.parameters,
    })),
  };

  const res = await PlatformBridge.proxyStream(url, 'POST', headers, body, params.signal);
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Anthropic API (${res.status}): ${errText.slice(0, 400)}`);
  }

  let text = '';
  let thinking = '';
  const blocks = new Map<number, { type: string; id: string; name: string; json: string }>();
  let usage = { input: 0, output: 0 };

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body stream');
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      let ev: Record<string, any>;
      try {
        ev = JSON.parse(payload);
      } catch {
        continue;
      }

      if (ev.type === 'message_start' && ev.message?.usage) {
        usage.input = Number(ev.message.usage.input_tokens ?? 0);
      } else if (ev.type === 'message_delta' && ev.usage) {
        usage.output = Number(ev.usage.output_tokens ?? 0);
      } else if (ev.type === 'content_block_start') {
        const cb = ev.content_block ?? {};
        blocks.set(ev.index, {
          type: cb.type,
          id: cb.id ?? `tool_${Date.now()}_${ev.index}`,
          name: cb.name ?? '',
          json: '',
        });
      } else if (ev.type === 'content_block_delta') {
        const d = ev.delta ?? {};
        if (d.type === 'text_delta' && d.text) {
          text += d.text;
          params.onTextDelta(d.text);
        } else if (d.type === 'thinking_delta' && d.thinking) {
          thinking += d.thinking;
          params.onThinkingDelta(d.thinking);
        } else if (d.type === 'input_json_delta' && d.partial_json) {
          const blk = blocks.get(ev.index);
          if (blk) blk.json += d.partial_json;
        }
      }
    }
  }

  const toolCalls = Array.from(blocks.values())
    .filter((b) => b.type === 'tool_use' && b.name)
    .map((b) => ({
      id: b.id,
      name: b.name as ToolName,
      input: safeJsonParse(b.json),
    }));

  return { text, thinking, toolCalls, usage };
}

/**
 * Built-in Smart Offline Local Agent!
 * Lets the user test real file reading, creation, editing, deletion, grep, glob, todo, and shell execution
 * right on their Android phone with ZERO API keys, while guiding how to connect Claude/GPT/Gemini/OpenRouter!
 */
async function runBuiltinSmartOfflineTurn(params: {
  agent: AgentId;
  messages: LlmChatMessage[];
  onTextDelta: (delta: string) => void;
  onThinkingDelta: (delta: string) => void;
  signal?: AbortSignal;
}): Promise<StreamTurnResult> {
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const lastMsg = params.messages[params.messages.length - 1];
  const lastUserMsg = [...params.messages].reverse().find((m) => m.role === 'user')?.content ?? '';
  const lower = lastUserMsg.toLowerCase();

  // If previous message was a tool result, summarize the real tool execution!
  if (lastMsg?.role === 'tool') {
    const toolResults: string[] = [];
    for (let i = params.messages.length - 1; i >= 0; i--) {
      if (params.messages[i].role === 'tool') {
        toolResults.unshift(params.messages[i].content);
      } else {
        break;
      }
    }
    const think = 'Анализирую результат выполнения локального инструмента на устройстве…';
    params.onThinkingDelta(think);
    await sleep(160);

    const summary =
      `Готово! Инструмент выполнен локально фоновым демоном OpenCode:\n\n` +
      '```\n' +
      toolResults.join('\n---\n').slice(0, 1800) +
      '\n```\n\n' +
      `_Совет: сейчас активен встроенный автономный движок без ключа. Чтобы подключить полноценный облачный ИИ (Claude Sonnet 4.5, GPT-4.1, Gemini 2.5, бесплатные модели OpenRouter или DeepSeek), откройте **Настройки → AI Провайдеры**._`;

    for (const chunk of summary.match(/.{1,24}/gs) ?? [summary]) {
      if (params.signal?.aborted) break;
      params.onTextDelta(chunk);
      await sleep(14);
    }
    return { text: summary, thinking: think, toolCalls: [], usage: { input: 240, output: 140 } };
  }

  const thinkText = `Режим агента: [${params.agent}]. Разбираю запрос пользователя "${lastUserMsg.slice(0, 70)}" и подбираю локальные инструменты рабочей папки…`;
  params.onThinkingDelta(thinkText);
  await sleep(200);

  // Plan mode: inspect workspace with glob/read
  if (params.agent === 'plan') {
    return {
      text: '',
      thinking: thinkText,
      toolCalls: [
        {
          id: `call_plan_${Date.now()}`,
          name: 'glob',
          input: { pattern: '**/*' },
        },
      ],
    };
  }

  // Detect explicit shell request (e.g. "выполни ls", "запусти uname", "bash: ...")
  const bashMatch = lastUserMsg.match(/(?:выполни|запусти|команд[ау]|bash:?|sh:?)\s+[`"]?([^\n`"]+)[`"]?/i);
  if (bashMatch) {
    return {
      text: '',
      thinking: thinkText,
      toolCalls: [
        {
          id: `call_bash_${Date.now()}`,
          name: 'bash',
          input: { command: bashMatch[1].trim() },
        },
      ],
    };
  }

  // Detect file deletion request ("удали файл foo.txt" / "delete foo.txt")
  const delMatch = lastUserMsg.match(/(?:удали(?:ть)?|delete|rm)\s+(?:файл\s+|папку\s+)?[`"']?([a-zA-Z0-9_./-]+)[`"']?/i);
  if (delMatch) {
    return {
      text: '',
      thinking: thinkText,
      toolCalls: [
        {
          id: `call_del_${Date.now()}`,
          name: 'delete_file',
          input: { filePath: delMatch[1].trim() },
        },
      ],
    };
  }

  // Detect file read request ("прочитай README.md" / "покажи файл src/index.ts" / "read package.json")
  const readMatch = lastUserMsg.match(/(?:прочитай|открой|покажи\s+файл|read|cat)\s+[`"']?([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)[`"']?/i);
  if (readMatch) {
    return {
      text: '',
      thinking: thinkText,
      toolCalls: [
        {
          id: `call_read_${Date.now()}`,
          name: 'read',
          input: { filePath: readMatch[1].trim() },
        },
      ],
    };
  }

  // Detect file creation request ("создай файл hello.py" / "создай калькулятор" / "create app.js")
  if (lower.includes('создай') || lower.includes('сделай') || lower.includes('напиши') || lower.includes('create')) {
    const explicitFile = lastUserMsg.match(/([a-zA-Z0-9_/-]+\.(?:html|js|ts|tsx|py|kt|md|json|css|sh|txt))/i)?.[1];
    const targetFile = explicitFile ?? (lower.includes('python') || lower.includes('питон') ? 'main.py' : 'app-demo.html');

    const content = targetFile.endsWith('.py')
      ? `#!/usr/bin/env python3\n"""Generated by OpenCode Android Local Agent"""\n\ndef main() -> None:\n    print("Hello from OpenCode Android Workspace!")\n\nif __name__ == "__main__":\n    main()\n`
      : targetFile.endsWith('.html')
        ? `<!doctype html>\n<html lang="ru">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1" />\n  <title>OpenCode Demo</title>\n  <style>\n    body { font-family: system-ui, sans-serif; background: #131010; color: #f5f2f0; display: grid; place-items: center; min-height: 100vh; margin: 0; }\n    .card { background: #1b1717; border: 1px solid #3e3636; border-radius: 14px; padding: 24px; max-width: 380px; }\n    button { background: #dcde8d; color: #161610; border: 0; padding: 10px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; }\n  </style>\n</head>\n<body>\n  <div class="card">\n    <h2>Создано в OpenCode Android</h2>\n    <p>Запрос: ${lastUserMsg.replace(/[<>&"]/g, '')}</p>\n    <button onclick="alert('Работает!')">Проверить</button>\n  </div>\n</body>\n</html>\n`
        : `// Generated by OpenCode Android\n// Prompt: ${lastUserMsg}\nexport const createdBy = "OpenCode Android v2.2.5";\nconsole.log(createdBy);\n`;

    return {
      text: '',
      thinking: thinkText,
      toolCalls: [
        {
          id: `call_todo_${Date.now()}`,
          name: 'todowrite',
          input: {
            todos: [
              { id: '1', content: `Создать файл ${targetFile} в локальном проекте`, status: 'completed' },
              { id: '2', content: 'Зафиксировать diff в панели «Изменения»', status: 'completed' },
            ],
          },
        },
        {
          id: `call_write_${Date.now()}`,
          name: 'write',
          input: { filePath: targetFile, content },
        },
      ],
    };
  }

  // Default: inspect project files via glob!
  return {
    text: '',
    thinking: thinkText,
    toolCalls: [
      {
        id: `call_glob_${Date.now()}`,
        name: 'glob',
        input: { pattern: '**/*' },
      },
    ],
  };
}
