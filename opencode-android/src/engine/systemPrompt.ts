import type { AgentId, ProjectInfo, TodoItem } from '../types/opencode';
import { PlatformBridge } from '../bridge/platformBridge';

export async function buildOpenCodeSystemPrompt(params: {
  agent: AgentId;
  project: ProjectInfo;
  flatFiles: string[];
  todos: TodoItem[];
  platform: 'android' | 'web';
}): Promise<string> {
  const { agent, project, flatFiles, todos, platform } = params;

  let agentsMd = '';
  if (flatFiles.includes('AGENTS.md') || flatFiles.includes('CLAUDE.md')) {
    const docName = flatFiles.includes('AGENTS.md') ? 'AGENTS.md' : 'CLAUDE.md';
    try {
      const res = await PlatformBridge.readFile(project.id, docName, 1, 200);
      agentsMd = `\n\n<project-instructions file="${docName}">\n${res.content}\n</project-instructions>`;
    } catch {
      // ignore
    }
  }

  const modeRules =
    agent === 'plan'
      ? `## CURRENT AGENT MODE: PLAN (READ-ONLY & ARCHITECTURE PLANNING)
- You are running in OpenCode's **plan** agent mode.
- DO NOT create, modify, patch, or delete files directly. Write/edit/patch/delete tools are restricted in plan mode.
- Use \`read\`, \`glob\`, \`grep\`, \`webfetch\`, and \`question\` to thoroughly inspect the codebase and clarify requirements.
- Produce a clear, actionable step-by-step implementation plan with exact file paths and code snippets.`
      : agent === 'general'
        ? `## CURRENT AGENT MODE: @GENERAL SUBAGENT
- You are OpenCode's autonomous **general** subagent executing a focused multi-step research or coding sub-task.
- Complete the assigned sub-task thoroughly using tools and return a concise, high-signal report.`
        : `## CURRENT AGENT MODE: BUILD (FULL ACCESS CODING AGENT)
- You are OpenCode, the open-source AI coding agent (ported to Android with full local background daemon, workspace filesystem, diff snapshots, and POSIX shell).
- You have FULL access to create, read, edit, patch, and delete files, search code with \`glob\` and \`grep\`, manage tasks with \`todowrite\`, run commands via \`bash\`, ask clarifying questions via \`question\`, and delegate complex sub-tasks via \`task\`.
- Always read existing files before editing them so your \`edit\` replacements match exact lines.
- Keep responses concise, direct, and engineering-focused. Match the user's language (Russian if the user writes in Russian).`;

  const filePreview =
    flatFiles.length > 0
      ? flatFiles.slice(0, 80).join('\n') + (flatFiles.length > 80 ? `\n... (+${flatFiles.length - 80} more files)` : '')
      : '(empty workspace)';

  const todoPreview =
    todos.length > 0
      ? `\n\n## Current Session Todo List\n` +
        todos.map((t) => `- [${t.status}] (${t.id}) ${t.content}`).join('\n')
      : '';

  return `You are OpenCode v2.2.5 running natively on ${platform === 'android' ? 'Android OS (Foreground Daemon + Local POSIX Workspace)' : 'OpenCode Local Daemon'}.
Working Project: "${project.name}"
Workspace Root Path: ${project.path}

${modeRules}

## Project File Tree Snapshot
\`\`\`
${filePreview}
\`\`\`${todoPreview}${agentsMd}`;
}
