import type {
  AgentId,
  FileDiffItem,
  PermissionPolicy,
  QuestionOption,
  TodoItem,
  ToolName,
} from '../types/opencode';
import { PlatformBridge } from '../bridge/platformBridge';

export interface OpenCodeToolSchema {
  name: ToolName;
  description: string;
  parameters: Record<string, unknown>;
}

export function getToolsForAgent(agent: AgentId): OpenCodeToolSchema[] {
  const readOnlyTools: OpenCodeToolSchema[] = [
    {
      name: 'read',
      description: 'Read a file from the local project workspace with line numbers.',
      parameters: {
        type: 'object',
        properties: {
          filePath: { type: 'string', description: 'Relative path inside the project (e.g. "src/index.ts")' },
          offset: { type: 'integer', description: '1-based starting line number (optional)' },
          limit: { type: 'integer', description: 'Max number of lines to read (optional, default 250)' },
        },
        required: ['filePath'],
      },
    },
    {
      name: 'glob',
      description: 'Find files in the project matching a glob pattern (e.g. "**/*.ts", "src/**").',
      parameters: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: 'Glob pattern to match file paths' },
        },
        required: ['pattern'],
      },
    },
    {
      name: 'grep',
      description: 'Search file contents across the project using a regular expression.',
      parameters: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: 'Regex or literal string to search for' },
          include: { type: 'string', description: 'Optional glob filter such as "*.ts"' },
        },
        required: ['pattern'],
      },
    },
    {
      name: 'todoread',
      description: 'Read the current structured todo list for this session.',
      parameters: { type: 'object', properties: {} },
    },
    {
      name: 'todowrite',
      description: 'Create or update the session todo checklist to track multi-step work.',
      parameters: {
        type: 'object',
        properties: {
          todos: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                content: { type: 'string' },
                status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
              },
              required: ['id', 'content', 'status'],
            },
          },
        },
        required: ['todos'],
      },
    },
    {
      name: 'webfetch',
      description: 'Fetch a web URL and extract readable text/markdown content.',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'HTTP/HTTPS URL to fetch' },
        },
        required: ['url'],
      },
    },
    {
      name: 'question',
      description: 'Ask the user a clarifying multiple-choice question when requirements are ambiguous.',
      parameters: {
        type: 'object',
        properties: {
          question: { type: 'string', description: 'The question to display to the user' },
          options: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                label: { type: 'string' },
                description: { type: 'string' },
              },
              required: ['id', 'label'],
            },
          },
        },
        required: ['question', 'options'],
      },
    },
  ];

  if (agent === 'plan') {
    return [
      ...readOnlyTools,
      {
        name: 'bash',
        description: 'Run a read-only shell command for inspection (requires user approval in plan mode).',
        parameters: {
          type: 'object',
          properties: {
            command: { type: 'string', description: 'POSIX sh command to execute in project root' },
          },
          required: ['command'],
        },
      },
    ];
  }

  const writeTools: OpenCodeToolSchema[] = [
    {
      name: 'write',
      description: 'Create a new file or overwrite an existing file in the project workspace.',
      parameters: {
        type: 'object',
        properties: {
          filePath: { type: 'string', description: 'Relative path inside the project' },
          content: { type: 'string', description: 'Full file content to write' },
        },
        required: ['filePath', 'content'],
      },
    },
    {
      name: 'edit',
      description: 'Edit an existing file by replacing oldString with newString (supports exact and indentation-tolerant matching).',
      parameters: {
        type: 'object',
        properties: {
          filePath: { type: 'string', description: 'Relative path inside the project' },
          oldString: { type: 'string', description: 'Existing text snippet to find' },
          newString: { type: 'string', description: 'Replacement text snippet' },
          replaceAll: { type: 'boolean', description: 'Replace every occurrence if true' },
        },
        required: ['filePath', 'oldString', 'newString'],
      },
    },
    {
      name: 'apply_patch',
      description: 'Apply a multi-file patch in OpenCode "*** Begin Patch" format (Add File, Update File, Delete File).',
      parameters: {
        type: 'object',
        properties: {
          patchText: { type: 'string', description: 'Full patch text starting with *** Begin Patch' },
        },
        required: ['patchText'],
      },
    },
    {
      name: 'delete_file',
      description: 'Delete a file or directory from the project workspace.',
      parameters: {
        type: 'object',
        properties: {
          filePath: { type: 'string', description: 'Relative path to delete' },
        },
        required: ['filePath'],
      },
    },
    {
      name: 'bash',
      description: 'Execute a shell command (/system/bin/sh on Android) in the project workspace directory.',
      parameters: {
        type: 'object',
        properties: {
          command: { type: 'string', description: 'Shell command to execute' },
          timeoutMs: { type: 'integer', description: 'Optional timeout in milliseconds (default 45000)' },
        },
        required: ['command'],
      },
    },
  ];

  if (agent !== 'general') {
    writeTools.push({
      name: 'task',
      description: 'Spawn the @general subagent to perform a focused multi-step research or coding sub-task.',
      parameters: {
        type: 'object',
        properties: {
          description: { type: 'string', description: 'Short 3-5 word label for the sub-task' },
          prompt: { type: 'string', description: 'Detailed instructions for the subagent' },
        },
        required: ['description', 'prompt'],
      },
    });
  }

  return [...readOnlyTools, ...writeTools];
}

export function describeToolCall(tool: ToolName, input: Record<string, unknown>): { title: string; subtitle?: string } {
  switch (tool) {
    case 'read':
      return { title: 'Чтение файла', subtitle: String(input.filePath ?? input.path ?? '') };
    case 'write':
      return { title: 'Запись файла', subtitle: String(input.filePath ?? input.path ?? '') };
    case 'edit':
      return { title: 'Редактирование файла', subtitle: String(input.filePath ?? input.path ?? '') };
    case 'apply_patch':
      return { title: 'Применение патча', subtitle: 'Multi-file patch' };
    case 'delete_file':
      return { title: 'Удаление файла', subtitle: String(input.filePath ?? input.path ?? '') };
    case 'glob':
      return { title: 'Поиск файлов (glob)', subtitle: String(input.pattern ?? '*') };
    case 'grep':
      return { title: 'Поиск по коду (grep)', subtitle: String(input.pattern ?? '') };
    case 'bash':
      return { title: 'Shell команда', subtitle: String(input.command ?? '').slice(0, 80) };
    case 'todowrite':
      return { title: 'Обновление плана задач', subtitle: `${Array.isArray(input.todos) ? input.todos.length : 0} п.` };
    case 'todoread':
      return { title: 'Чтение плана задач' };
    case 'webfetch':
      return { title: 'Загрузка веб-страницы', subtitle: String(input.url ?? '') };
    case 'question':
      return { title: 'Уточняющий вопрос', subtitle: String(input.question ?? '') };
    case 'task':
      return { title: 'Сабагент @general', subtitle: String(input.description ?? '') };
  }
}

export function needsPermission(
  tool: ToolName,
  agent: AgentId,
  policy: PermissionPolicy,
  alwaysAllowedTools: Set<string>,
): boolean {
  if (alwaysAllowedTools.has(tool)) return false;
  if (agent === 'plan' && (tool === 'bash' || tool === 'write' || tool === 'edit' || tool === 'apply_patch' || tool === 'delete_file')) {
    return true;
  }
  if (policy === 'auto') return false;
  if (policy === 'ask_bash_and_delete') {
    return tool === 'bash' || tool === 'delete_file';
  }
  if (policy === 'ask_all_writes') {
    return tool === 'bash' || tool === 'write' || tool === 'edit' || tool === 'apply_patch' || tool === 'delete_file';
  }
  return false;
}

export async function executeOpenCodeTool(params: {
  projectId: string;
  tool: ToolName;
  input: Record<string, unknown>;
  getTodos: () => TodoItem[];
  setTodos: (todos: TodoItem[]) => void;
  askQuestion: (question: string, options: QuestionOption[]) => Promise<string>;
  runSubagent: (description: string, prompt: string) => Promise<string>;
  onWorkspaceChanged: () => void;
}): Promise<{ output: string; diff?: FileDiffItem }> {
  const { projectId, tool, input } = params;

  switch (tool) {
    case 'read': {
      const filePath = String(input.filePath ?? input.path ?? '');
      const offset = typeof input.offset === 'number' ? input.offset : 1;
      const limit = typeof input.limit === 'number' ? input.limit : 250;
      const res = await PlatformBridge.readFile(projectId, filePath, offset, limit);
      return {
        output: `File: ${filePath} (${res.totalLines} lines, ${res.size} bytes)\n${res.numbered}`,
      };
    }

    case 'write': {
      const filePath = String(input.filePath ?? input.path ?? '');
      const content = String(input.content ?? '');
      const res = await PlatformBridge.writeFile(projectId, filePath, content);
      params.onWorkspaceChanged();
      return {
        output: `Successfully wrote ${filePath} (+${res.diff.additions} / -${res.diff.deletions} lines).`,
        diff: res.diff,
      };
    }

    case 'edit': {
      const filePath = String(input.filePath ?? input.path ?? '');
      const oldString = String(input.oldString ?? '');
      const newString = String(input.newString ?? '');
      const replaceAll = Boolean(input.replaceAll);
      const res = await PlatformBridge.editFile(projectId, filePath, oldString, newString, replaceAll);
      params.onWorkspaceChanged();
      return {
        output: `Edited ${filePath} (${res.replacements} replacement(s), +${res.diff.additions} / -${res.diff.deletions} lines).`,
        diff: res.diff,
      };
    }

    case 'apply_patch': {
      const patchText = String(input.patchText ?? '');
      const res = await PlatformBridge.applyPatch(projectId, patchText);
      params.onWorkspaceChanged();
      return {
        output: res.summary,
        diff: res.diffs[0],
      };
    }

    case 'delete_file': {
      const filePath = String(input.filePath ?? input.path ?? '');
      const res = await PlatformBridge.deletePath(projectId, filePath);
      params.onWorkspaceChanged();
      return {
        output: `Deleted ${filePath} (${res.deletedCount} item(s) removed).`,
        diff: res.diff,
      };
    }

    case 'glob': {
      const pattern = String(input.pattern ?? '**/*');
      const res = await PlatformBridge.globFiles(projectId, pattern);
      return {
        output: res.matches.length
          ? `Found ${res.matches.length} file(s):\n${res.matches.join('\n')}`
          : `No files matched pattern "${pattern}".`,
      };
    }

    case 'grep': {
      const pattern = String(input.pattern ?? '');
      const include = input.include ? String(input.include) : undefined;
      const res = await PlatformBridge.grepFiles(projectId, pattern, include);
      return {
        output: res.matches.length
          ? res.matches.map((m) => `${m.path}:${m.line}: ${m.text}`).join('\n')
          : `No matches found for "${pattern}".`,
      };
    }

    case 'bash': {
      const command = String(input.command ?? '');
      const timeoutMs = typeof input.timeoutMs === 'number' ? input.timeoutMs : 45000;
      const res = await PlatformBridge.execShell(projectId, command, timeoutMs);
      params.onWorkspaceChanged();
      const combined = [
        `exit_code: ${res.exitCode} (${res.durationMs}ms)`,
        res.stdout ? `stdout:\n${res.stdout}` : '',
        res.stderr ? `stderr:\n${res.stderr}` : '',
      ]
        .filter(Boolean)
        .join('\n');
      return { output: combined };
    }

    case 'todoread': {
      const todos = params.getTodos();
      return {
        output: todos.length ? JSON.stringify(todos, null, 2) : 'Todo list is currently empty.',
      };
    }

    case 'todowrite': {
      const raw = Array.isArray(input.todos) ? input.todos : [];
      const next: TodoItem[] = raw.map((item: Record<string, unknown>, idx: number) => ({
        id: String(item.id ?? `todo-${idx + 1}`),
        content: String(item.content ?? ''),
        status: (['pending', 'in_progress', 'completed', 'cancelled'].includes(String(item.status))
          ? String(item.status)
          : 'pending') as TodoItem['status'],
      }));
      params.setTodos(next);
      return {
        output: `Updated ${next.length} todo item(s):\n` + next.map((t) => `[${t.status}] ${t.content}`).join('\n'),
      };
    }

    case 'webfetch': {
      const url = String(input.url ?? '');
      const res = await PlatformBridge.proxyFetchText(url);
      return {
        output: `URL: ${url} (HTTP ${res.status})\n\n${res.content.slice(0, 12000)}`,
      };
    }

    case 'question': {
      const q = String(input.question ?? 'Уточните выбор:');
      const rawOpts = Array.isArray(input.options) ? input.options : [];
      const opts: QuestionOption[] = rawOpts.map((o: Record<string, unknown>, idx: number) => ({
        id: String(o.id ?? `opt-${idx + 1}`),
        label: String(o.label ?? `Вариант ${idx + 1}`),
        description: o.description ? String(o.description) : undefined,
      }));
      const answer = await params.askQuestion(q, opts);
      return { output: `User answered: ${answer}` };
    }

    case 'task': {
      const desc = String(input.description ?? 'Subtask');
      const prompt = String(input.prompt ?? '');
      const result = await params.runSubagent(desc, prompt);
      return { output: result };
    }
  }
}
