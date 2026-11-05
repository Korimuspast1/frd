import type {
  AgentId,
  AppSettings,
  AttachmentItem,
  PermissionRequest,
  ProjectInfo,
  ProviderConfig,
  QuestionOption,
  QuestionRequest,
  SessionMessage,
  TodoItem,
  ToolCallPart,
} from '../types/opencode';
import { PlatformBridge } from '../bridge/platformBridge';
import { buildOpenCodeSystemPrompt } from './systemPrompt';
import { describeToolCall, executeOpenCodeTool, getToolsForAgent, needsPermission } from './tools';
import { streamLlmCompletion, type LlmChatMessage } from './llmStream';
import { resolveActiveModel } from '../themes/presets';

export interface RunAgentTurnOptions {
  sessionId: string;
  project: ProjectInfo;
  agent: AgentId;
  prompt: string;
  attachments: AttachmentItem[];
  mentionedFiles: string[];
  priorMessages: SessionMessage[];
  todos: TodoItem[];
  settings: AppSettings;
  providers: ProviderConfig[];
  alwaysAllowedTools: Set<string>;
  signal: AbortSignal;
  onUpdateAssistantMessage: (updater: (msg: SessionMessage) => SessionMessage) => void;
  onUpdateTodos: (todos: TodoItem[]) => void;
  onRequestPermission: (req: PermissionRequest) => Promise<'approved_once' | 'approved_always' | 'rejected'>;
  onRequestQuestion: (req: QuestionRequest) => Promise<string>;
  onWorkspaceChanged: () => void;
}

export async function runOpenCodeAgentTurn(opts: RunAgentTurnOptions): Promise<void> {
  const { provider, model } = resolveActiveModel(
    opts.settings.selectedProvider,
    opts.settings.selectedModel,
    opts.providers,
  );

  await PlatformBridge.setDaemonTask(
    `OpenCode [${opts.agent}]: ${opts.prompt.slice(0, 48)}`,
    true,
  );

  try {
    const treeData = await PlatformBridge.listTree(opts.project.id);
    const daemon = await PlatformBridge.getDaemonStatus();

    const systemPrompt = await buildOpenCodeSystemPrompt({
      agent: opts.agent,
      project: opts.project,
      flatFiles: treeData.flatFiles,
      todos: opts.todos,
      platform: daemon.platform,
    });

    // Build LLM conversation history (with optional auto-compaction for huge histories)
    const historySlice = opts.settings.autoCompactContext && opts.priorMessages.length > 24
      ? opts.priorMessages.slice(-24)
      : opts.priorMessages;

    const llmMessages: LlmChatMessage[] = [{ role: 'system', content: systemPrompt }];

    for (const m of historySlice) {
      if (m.role === 'user') {
        llmMessages.push({ role: 'user', content: m.text });
      } else if (m.role === 'assistant') {
        if (m.toolCalls && m.toolCalls.length > 0) {
          llmMessages.push({
            role: 'assistant',
            content: m.text,
            toolCalls: m.toolCalls.map((tc) => ({
              id: tc.id,
              name: tc.tool,
              argumentsJson: JSON.stringify(tc.input),
            })),
          });
          for (const tc of m.toolCalls) {
            llmMessages.push({
              role: 'tool',
              toolCallId: tc.id,
              toolName: tc.tool,
              content: tc.output || tc.error || 'Done',
            });
          }
        } else if (m.text) {
          llmMessages.push({ role: 'assistant', content: m.text });
        }
      }
    }

    // Enrich current user message with @mentioned files & text attachments
    let enrichedUserPrompt = opts.prompt;
    if (opts.mentionedFiles.length > 0) {
      const fileBlocks: string[] = [];
      for (const relPath of opts.mentionedFiles) {
        try {
          const readRes = await PlatformBridge.readFile(opts.project.id, relPath, 1, 300);
          fileBlocks.push(`<referenced-file path="${relPath}">\n${readRes.numbered}\n</referenced-file>`);
        } catch {
          // skip unreadable
        }
      }
      if (fileBlocks.length > 0) {
        enrichedUserPrompt += `\n\n${fileBlocks.join('\n\n')}`;
      }
    }
    if (opts.attachments.length > 0) {
      for (const att of opts.attachments) {
        if (att.textContent) {
          enrichedUserPrompt += `\n\n<attached-file name="${att.name}">\n${att.textContent}\n</attached-file>`;
        }
      }
    }

    llmMessages.push({ role: 'user', content: enrichedUserPrompt });

    const tools = getToolsForAgent(opts.agent);
    let currentTodos = [...opts.todos];
    const maxSteps = 18;
    const thinkingStartedAt = Date.now();

    for (let step = 0; step < maxSteps; step++) {
      if (opts.signal.aborted) break;

      let stepText = '';
      let stepThinking = '';

      const turnRes = await streamLlmCompletion({
        provider,
        modelId: model.id,
        agent: opts.agent,
        effort: opts.settings.effort,
        messages: llmMessages,
        tools,
        projectId: opts.project.id,
        signal: opts.signal,
        onTextDelta: (delta) => {
          stepText += delta;
          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            text: (prev.text ? prev.text : '') + delta,
          }));
        },
        onThinkingDelta: (delta) => {
          stepThinking += delta;
          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            thinking: (prev.thinking ?? '') + delta,
            thinkingDurationMs: Date.now() - thinkingStartedAt,
          }));
        },
      });

      if (turnRes.usage) {
        opts.onUpdateAssistantMessage((prev) => ({
          ...prev,
          tokens: {
            input: (prev.tokens?.input ?? 0) + (turnRes.usage?.input ?? 0),
            output: (prev.tokens?.output ?? 0) + (turnRes.usage?.output ?? 0),
          },
        }));
      }

      if (turnRes.toolCalls.length === 0) {
        break;
      }

      // Add assistant tool-call turn to LLM history
      llmMessages.push({
        role: 'assistant',
        content: stepText,
        toolCalls: turnRes.toolCalls.map((tc) => ({
          id: tc.id,
          name: tc.name,
          argumentsJson: JSON.stringify(tc.input),
        })),
      });

      // Execute each tool call sequentially (updating UI cards in real time!)
      for (const tc of turnRes.toolCalls) {
        if (opts.signal.aborted) break;

        const meta = describeToolCall(tc.name, tc.input);
        const partId = tc.id;

        const newPart: ToolCallPart = {
          id: partId,
          tool: tc.name,
          status: 'running',
          input: tc.input,
          title: meta.title,
          subtitle: meta.subtitle,
          startedAt: Date.now(),
        };

        opts.onUpdateAssistantMessage((prev) => ({
          ...prev,
          toolCalls: [...(prev.toolCalls ?? []), newPart],
        }));

        await PlatformBridge.setDaemonTask(`OpenCode [${opts.agent}]: ${meta.title} ${meta.subtitle ?? ''}`, true);

        // Permission check (1:1 with PC OpenCode!)
        if (needsPermission(tc.name, opts.agent, opts.settings.permissionPolicy, opts.alwaysAllowedTools)) {
          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            toolCalls: (prev.toolCalls ?? []).map((p) =>
              p.id === partId ? { ...p, status: 'awaiting_permission' } : p,
            ),
          }));

          const decision = await opts.onRequestPermission({
            id: `perm_${partId}`,
            sessionId: opts.sessionId,
            toolCallId: partId,
            tool: tc.name,
            title: meta.title,
            description:
              opts.agent === 'plan'
                ? 'Агент в режиме Plan запрашивает разрешение на выполнение операции.'
                : 'Политика безопасности OpenCode требует подтверждения операции.',
            commandOrPath: String(tc.input.command ?? tc.input.filePath ?? tc.input.path ?? ''),
            status: 'pending',
          });

          if (decision === 'approved_always') {
            opts.alwaysAllowedTools.add(tc.name);
          }

          if (decision === 'rejected') {
            const rejMsg = 'Операция отклонена пользователем.';
            opts.onUpdateAssistantMessage((prev) => ({
              ...prev,
              toolCalls: (prev.toolCalls ?? []).map((p) =>
                p.id === partId ? { ...p, status: 'rejected', error: rejMsg, finishedAt: Date.now() } : p,
              ),
            }));
            llmMessages.push({
              role: 'tool',
              toolCallId: partId,
              toolName: tc.name,
              content: 'User rejected permission for this tool call. Do not retry without asking.',
            });
            continue;
          }

          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            toolCalls: (prev.toolCalls ?? []).map((p) => (p.id === partId ? { ...p, status: 'running' } : p)),
          }));
        }

        try {
          const execRes = await executeOpenCodeTool({
            projectId: opts.project.id,
            tool: tc.name,
            input: tc.input,
            getTodos: () => currentTodos,
            setTodos: (next) => {
              currentTodos = next;
              opts.onUpdateTodos(next);
            },
            askQuestion: async (question: string, options: QuestionOption[]) => {
              opts.onUpdateAssistantMessage((prev) => ({
                ...prev,
                toolCalls: (prev.toolCalls ?? []).map((p) =>
                  p.id === partId ? { ...p, status: 'awaiting_answer' } : p,
                ),
              }));
              const ans = await opts.onRequestQuestion({
                id: `q_${partId}`,
                sessionId: opts.sessionId,
                toolCallId: partId,
                question,
                options,
                allowCustom: true,
                status: 'pending',
              });
              return ans;
            },
            runSubagent: async (desc: string, subPrompt: string) => {
              const subLogs: string[] = [];
              const subHistory: LlmChatMessage[] = [
                {
                  role: 'system',
                  content: await buildOpenCodeSystemPrompt({
                    agent: 'general',
                    project: opts.project,
                    flatFiles: treeData.flatFiles,
                    todos: currentTodos,
                    platform: daemon.platform,
                  }),
                },
                { role: 'user', content: subPrompt },
              ];
              const subTools = getToolsForAgent('general');
              let finalReport = '';
              for (let s = 0; s < 6; s++) {
                if (opts.signal.aborted) break;
                let chunkText = '';
                const subRes = await streamLlmCompletion({
                  provider,
                  modelId: model.id,
                  agent: 'general',
                  effort: 'medium',
                  messages: subHistory,
                  tools: subTools,
                  projectId: opts.project.id,
                  signal: opts.signal,
                  onTextDelta: (d) => {
                    chunkText += d;
                  },
                  onThinkingDelta: () => {},
                });
                finalReport = chunkText || finalReport;
                if (subRes.toolCalls.length === 0) break;
                subHistory.push({
                  role: 'assistant',
                  content: chunkText,
                  toolCalls: subRes.toolCalls.map((st) => ({
                    id: st.id,
                    name: st.name,
                    argumentsJson: JSON.stringify(st.input),
                  })),
                });
                for (const st of subRes.toolCalls) {
                  const subMeta = describeToolCall(st.name, st.input);
                  subLogs.push(`${subMeta.title}: ${subMeta.subtitle ?? ''}`);
                  opts.onUpdateAssistantMessage((prev) => ({
                    ...prev,
                    toolCalls: (prev.toolCalls ?? []).map((p) =>
                      p.id === partId ? { ...p, subagentMessages: [...subLogs] } : p,
                    ),
                  }));
                  const stOut = await executeOpenCodeTool({
                    projectId: opts.project.id,
                    tool: st.name,
                    input: st.input,
                    getTodos: () => currentTodos,
                    setTodos: () => {},
                    askQuestion: async () => 'Skipped in subagent',
                    runSubagent: async () => 'Nested subagent disabled',
                    onWorkspaceChanged: opts.onWorkspaceChanged,
                  });
                  subHistory.push({
                    role: 'tool',
                    toolCallId: st.id,
                    toolName: st.name,
                    content: stOut.output,
                  });
                }
              }
              return finalReport || `Subagent "${desc}" completed (${subLogs.length} actions).`;
            },
            onWorkspaceChanged: opts.onWorkspaceChanged,
          });

          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            toolCalls: (prev.toolCalls ?? []).map((p) =>
              p.id === partId
                ? {
                    ...p,
                    status: 'completed',
                    output: execRes.output,
                    diff: execRes.diff,
                    finishedAt: Date.now(),
                  }
                : p,
            ),
          }));

          llmMessages.push({
            role: 'tool',
            toolCallId: partId,
            toolName: tc.name,
            content: execRes.output,
          });
        } catch (toolErr: any) {
          const errStr = toolErr?.message || String(toolErr);
          opts.onUpdateAssistantMessage((prev) => ({
            ...prev,
            toolCalls: (prev.toolCalls ?? []).map((p) =>
              p.id === partId ? { ...p, status: 'error', error: errStr, finishedAt: Date.now() } : p,
            ),
          }));
          llmMessages.push({
            role: 'tool',
            toolCallId: partId,
            toolName: tc.name,
            content: `Tool execution failed: ${errStr}`,
          });
        }
      }

      if (stepText) {
        opts.onUpdateAssistantMessage((prev) => ({
          ...prev,
          text: prev.text + '\n\n',
        }));
      }
    }

    opts.onUpdateAssistantMessage((prev) => ({
      ...prev,
      isStreaming: false,
      text: prev.text.trim(),
    }));

    if (opts.settings.notificationsEnabled) {
      PlatformBridge.notify('OpenCode завершил задачу', opts.prompt.slice(0, 80));
    }
  } finally {
    await PlatformBridge.setDaemonTask('OpenCode готов • Фоновый демон активен', false);
  }
}
