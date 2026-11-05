import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(ROOT_DIR, '..');
const WWW_DIR = path.join(ROOT_DIR, 'android/app/src/main/assets/www');
const WORKSPACES_DIR = path.join(ROOT_DIR, '.workspaces-dev');
const SNAPSHOTS_DIR = path.join(WORKSPACES_DIR, '.snapshots');
const PORT = Number(process.env.PORT || 4096);

fs.mkdirSync(WORKSPACES_DIR, { recursive: true });
fs.mkdirSync(SNAPSHOTS_DIR, { recursive: true });

let daemonTaskStatus = 'OpenCode готов • Локальный демон активен';
let daemonBusy = false;

function sanitizeSlug(name) {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '') || `project-${Date.now()}`
  );
}

function safeResolve(projectDir, relPath) {
  const cleaned = String(relPath || '').replace(/^\/+/, '');
  const resolved = path.resolve(projectDir, cleaned);
  if (!resolved.startsWith(path.resolve(projectDir))) {
    throw new Error('Path escapes project workspace');
  }
  return resolved;
}

function seedStarterProjectIfEmpty() {
  const entries = fs.readdirSync(WORKSPACES_DIR).filter((n) => !n.startsWith('.'));
  if (entries.length > 0) return;
  createProjectSync('opencode-playground', 'typescript');
}

function createProjectSync(name, template) {
  const id = sanitizeSlug(name);
  let finalId = id;
  let n = 2;
  while (fs.existsSync(path.join(WORKSPACES_DIR, finalId))) {
    finalId = `${id}-${n++}`;
  }
  const dir = path.join(WORKSPACES_DIR, finalId);
  fs.mkdirSync(dir, { recursive: true });

  if (template === 'python') {
    fs.writeFileSync(
      path.join(dir, 'README.md'),
      `# ${name}\n\nЛокальный Python-проект в OpenCode Android.\n`,
    );
    fs.writeFileSync(
      path.join(dir, 'main.py'),
      `def greet(user: str) -> str:\n    return f"Привет, {user}! OpenCode работает локально."\n\nif __name__ == "__main__":\n    print(greet("Android"))\n`,
    );
  } else if (template === 'android') {
    fs.mkdirSync(path.join(dir, 'src/main/kotlin'), { recursive: true });
    fs.writeFileSync(
      path.join(dir, 'README.md'),
      `# ${name}\n\nKotlin / Android модуль в рабочей папке OpenCode.\n`,
    );
    fs.writeFileSync(
      path.join(dir, 'src/main/kotlin/App.kt'),
      `package demo\n\nfun main() {\n    println("OpenCode Android Kotlin workspace")\n}\n`,
    );
  } else if (template !== 'empty') {
    fs.mkdirSync(path.join(dir, 'src'), { recursive: true });
    fs.writeFileSync(
      path.join(dir, 'README.md'),
      `# ${name}\n\nДобро пожаловать в **OpenCode Android**!\n\n- Агент \`build\` читает, создаёт, редактирует и удаляет файлы прямо в локальной папке.\n- Агент \`plan\` безопасно анализирует код и строит планы.\n- Панель **Файлы** и **Терминал** доступны сверху.\n`,
    );
    fs.writeFileSync(
      path.join(dir, 'AGENTS.md'),
      `- Используй чистый модульный код.\n- Проверяй изменения через diff и локальные команды.\n`,
    );
    fs.writeFileSync(
      path.join(dir, 'package.json'),
      JSON.stringify({ name: finalId, version: '1.0.0', type: 'module' }, null, 2) + '\n',
    );
    fs.writeFileSync(
      path.join(dir, 'src/index.ts'),
      `export function sum(a: number, b: number): number {\n  return a + b;\n}\n\nconsole.log("OpenCode workspace ready:", sum(20, 22));\n`,
    );
  }

  const stat = fs.statSync(dir);
  return {
    id: finalId,
    name,
    path: dir,
    template,
    createdAt: stat.birthtimeMs || Date.now(),
    updatedAt: stat.mtimeMs || Date.now(),
  };
}

seedStarterProjectIfEmpty();

function buildUnifiedDiff(relPath, oldStr, newStr) {
  const oldLines = oldStr === '' ? [] : oldStr.split('\n');
  const newLines = newStr === '' ? [] : newStr.split('\n');
  let additions = 0;
  let deletions = 0;
  const out = [`--- a/${relPath}`, `+++ b/${relPath}`, `@@ -1,${oldLines.length} +1,${newLines.length} @@`];

  const max = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < max; i++) {
    const o = oldLines[i];
    const n = newLines[i];
    if (o === n) {
      if (o !== undefined) out.push(` ${o}`);
    } else {
      if (o !== undefined) {
        out.push(`-${o}`);
        deletions++;
      }
      if (n !== undefined) {
        out.push(`+${n}`);
        additions++;
      }
    }
  }
  const status = oldStr === '' ? 'added' : newStr === '' ? 'deleted' : 'modified';
  return {
    path: relPath,
    status,
    oldContent: oldStr,
    newContent: newStr,
    additions,
    deletions,
    unifiedDiff: out.slice(0, 260).join('\n'),
  };
}

function walkTree(baseDir, currentRel = '') {
  const full = path.join(baseDir, currentRel);
  const entries = fs.readdirSync(full, { withFileTypes: true });
  const nodes = [];
  const flat = [];

  entries.sort((a, b) => {
    if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  for (const ent of entries) {
    if (ent.name === '.git' || ent.name === 'node_modules' || ent.name === '.snapshots') continue;
    const rel = currentRel ? `${currentRel}/${ent.name}` : ent.name;
    const p = path.join(baseDir, rel);
    if (ent.isDirectory()) {
      const sub = walkTree(baseDir, rel);
      nodes.push({ name: ent.name, path: rel, type: 'directory', children: sub.nodes });
      flat.push(...sub.flat);
    } else {
      const st = fs.statSync(p);
      nodes.push({ name: ent.name, path: rel, type: 'file', size: st.size, mtime: st.mtimeMs });
      flat.push(rel);
    }
  }
  return { nodes, flat };
}

function globToRegExp(glob) {
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*\//g, '(?:.+/)?')
    .replace(/\*\*/g, '.*')
    .replace(/\*/g, '[^/]*')
    .replace(/\?/g, '.');
  return new RegExp(`^${escaped}$`, 'i');
}

function copyDirRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const ent of fs.readdirSync(src, { withFileTypes: true })) {
    if (ent.name === '.git' || ent.name === 'node_modules') continue;
    const s = path.join(src, ent.name);
    const d = path.join(dest, ent.name);
    if (ent.isDirectory()) copyDirRecursive(s, d);
    else fs.copyFileSync(s, d);
  }
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks).toString('utf8');
  return raw ? JSON.parse(raw) : {};
}

function sendJson(res, status, obj) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  });
  res.end(JSON.stringify(obj));
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.apk': 'application/vnd.android.package-archive',
};

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': '*',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    });
    return res.end();
  }

  const parsedUrl = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;

  try {
    if (pathname === '/api/health') {
      return sendJson(res, 200, {
        ok: true,
        running: true,
        platform: 'web',
        daemonUrl: `http://0.0.0.0:${PORT}`,
        foregroundService: true,
        busy: daemonBusy,
        currentTask: daemonTaskStatus,
        workspacesRoot: WORKSPACES_DIR,
      });
    }

    if (pathname === '/api/daemon/status' && req.method === 'POST') {
      const body = await readJsonBody(req);
      daemonTaskStatus = String(body.statusText || daemonTaskStatus);
      daemonBusy = Boolean(body.busy);
      return sendJson(res, 200, { ok: true });
    }

    if (pathname === '/api/projects' && req.method === 'GET') {
      const dirs = fs.readdirSync(WORKSPACES_DIR, { withFileTypes: true }).filter((d) => d.isDirectory() && !d.name.startsWith('.'));
      const projects = dirs.map((d) => {
        const p = path.join(WORKSPACES_DIR, d.name);
        const st = fs.statSync(p);
        return {
          id: d.name,
          name: d.name,
          path: p,
          createdAt: st.birthtimeMs || Date.now(),
          updatedAt: st.mtimeMs || Date.now(),
        };
      });
      return sendJson(res, 200, { ok: true, projects });
    }

    if (pathname === '/api/projects/create' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const project = createProjectSync(String(body.name || 'project'), String(body.template || 'typescript'));
      return sendJson(res, 200, { ok: true, project });
    }

    if (pathname === '/api/projects/delete' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const dir = path.join(WORKSPACES_DIR, path.basename(String(body.projectId || '')));
      fs.rmSync(dir, { recursive: true, force: true });
      seedStarterProjectIfEmpty();
      return sendJson(res, 200, { ok: true });
    }

    if (pathname === '/api/projects/clone' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const repoUrl = String(body.repoUrl || '').trim().replace(/\.git$/, '');
      const m = repoUrl.match(/github\.com\/([^/]+)\/([^/#?]+)/i);
      if (!m) throw new Error('Укажите ссылку вида https://github.com/owner/repo');
      const [, owner, repo] = m;
      const slug = sanitizeSlug(body.name || repo);
      const dest = path.join(WORKSPACES_DIR, slug);
      fs.rmSync(dest, { recursive: true, force: true });
      await new Promise((resolve, reject) => {
        const proc = spawn('git', ['clone', '--depth', '1', `https://github.com/${owner}/${repo}.git`, dest]);
        proc.on('close', (code) => (code === 0 ? resolve() : reject(new Error(`git clone exited ${code}`))));
      });
      fs.rmSync(path.join(dest, '.git'), { recursive: true, force: true });
      return sendJson(res, 200, {
        ok: true,
        project: { id: slug, name: slug, path: dest, createdAt: Date.now(), updatedAt: Date.now() },
      });
    }

    if (pathname === '/api/projects/export-zip' && req.method === 'GET') {
      const projectId = path.basename(String(parsedUrl.searchParams.get('projectId') || ''));
      const projDir = path.join(WORKSPACES_DIR, projectId);
      const tmpZip = `/tmp/${projectId}-${Date.now()}.zip`;
      await new Promise((resolve, reject) => {
        const p = spawn('zip', ['-r', '-q', tmpZip, '.'], { cwd: projDir });
        p.on('close', (c) => (c === 0 ? resolve() : reject(new Error('zip failed'))));
      });
      res.writeHead(200, {
        'Content-Type': 'application/zip',
        'Content-Disposition': `attachment; filename="${projectId}.zip"`,
      });
      fs.createReadStream(tmpZip).pipe(res).on('finish', () => fs.rmSync(tmpZip, { force: true }));
      return;
    }

    if (pathname === '/download/OpenCode-Android-v2.2.5.apk') {
      const apkPath = path.join(REPO_ROOT, 'OpenCode-Android-v2.2.5.apk');
      if (!fs.existsSync(apkPath)) {
        res.writeHead(404);
        return res.end('APK not built yet');
      }
      const st = fs.statSync(apkPath);
      res.writeHead(200, {
        'Content-Type': MIME['.apk'],
        'Content-Length': st.size,
        'Content-Disposition': 'attachment; filename="OpenCode-Android-v2.2.5.apk"',
      });
      if (req.method === 'HEAD') return res.end();
      return fs.createReadStream(apkPath).pipe(res);
    }

    // FS endpoints
    if (pathname.startsWith('/api/fs/') || pathname.startsWith('/api/snapshots/') || pathname.startsWith('/api/shell/')) {
      const body = await readJsonBody(req);
      const projectId = path.basename(String(body.projectId || ''));
      const projDir = path.join(WORKSPACES_DIR, projectId);
      if (!fs.existsSync(projDir)) throw new Error(`Project not found: ${projectId}`);

      if (pathname === '/api/fs/tree') {
        const walked = walkTree(projDir);
        return sendJson(res, 200, { ok: true, tree: walked.nodes, flatFiles: walked.flat });
      }

      if (pathname === '/api/fs/read') {
        const target = safeResolve(projDir, body.path);
        const content = await fsp.readFile(target, 'utf8');
        const allLines = content.split('\n');
        const offset = Math.max(1, Number(body.offset || 1));
        const limit = Math.max(1, Number(body.limit || 300));
        const slice = allLines.slice(offset - 1, offset - 1 + limit);
        const numbered = slice.map((l, idx) => `${String(offset + idx).padStart(4, ' ')} | ${l}`).join('\n');
        return sendJson(res, 200, {
          ok: true,
          content,
          totalLines: allLines.length,
          numbered,
          size: Buffer.byteLength(content, 'utf8'),
        });
      }

      if (pathname === '/api/fs/write') {
        const rel = String(body.path || '').replace(/^\/+/, '');
        const target = safeResolve(projDir, rel);
        const prev = fs.existsSync(target) ? await fsp.readFile(target, 'utf8') : '';
        await fsp.mkdir(path.dirname(target), { recursive: true });
        const next = String(body.content ?? '');
        await fsp.writeFile(target, next, 'utf8');
        return sendJson(res, 200, { ok: true, diff: buildUnifiedDiff(rel, prev, next) });
      }

      if (pathname === '/api/fs/edit') {
        const rel = String(body.path || '').replace(/^\/+/, '');
        const target = safeResolve(projDir, rel);
        const prev = await fsp.readFile(target, 'utf8');
        const oldS = String(body.oldString ?? '');
        const newS = String(body.newString ?? '');
        if (!prev.includes(oldS)) {
          throw new Error(`oldString not found in ${rel}`);
        }
        const next = body.replaceAll ? prev.split(oldS).join(newS) : prev.replace(oldS, newS);
        const replacements = body.replaceAll ? prev.split(oldS).length - 1 : 1;
        await fsp.writeFile(target, next, 'utf8');
        return sendJson(res, 200, { ok: true, replacements, diff: buildUnifiedDiff(rel, prev, next) });
      }

      if (pathname === '/api/fs/patch') {
        const patchText = String(body.patchText || '');
        const diffs = [];
        const lines = patchText.split('\n');
        let i = 0;
        while (i < lines.length) {
          const line = lines[i];
          if (line.startsWith('*** Add File: ')) {
            const rel = line.slice('*** Add File: '.length).trim();
            i++;
            const buf = [];
            while (i < lines.length && !lines[i].startsWith('*** ')) {
              buf.push(lines[i].startsWith('+') ? lines[i].slice(1) : lines[i]);
              i++;
            }
            const target = safeResolve(projDir, rel);
            fs.mkdirSync(path.dirname(target), { recursive: true });
            const content = buf.join('\n');
            fs.writeFileSync(target, content, 'utf8');
            diffs.push(buildUnifiedDiff(rel, '', content));
            continue;
          }
          if (line.startsWith('*** Delete File: ')) {
            const rel = line.slice('*** Delete File: '.length).trim();
            const target = safeResolve(projDir, rel);
            const prev = fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : '';
            fs.rmSync(target, { force: true });
            diffs.push(buildUnifiedDiff(rel, prev, ''));
          }
          i++;
        }
        return sendJson(res, 200, { ok: true, diffs, summary: `Applied patch (${diffs.length} file(s) changed)` });
      }

      if (pathname === '/api/fs/delete') {
        const rel = String(body.path || '').replace(/^\/+/, '');
        const target = safeResolve(projDir, rel);
        let prev = '';
        if (fs.existsSync(target) && fs.statSync(target).isFile()) {
          prev = fs.readFileSync(target, 'utf8');
        }
        fs.rmSync(target, { recursive: true, force: true });
        return sendJson(res, 200, { ok: true, deletedCount: 1, diff: buildUnifiedDiff(rel, prev, '') });
      }

      if (pathname === '/api/fs/mkdir') {
        const target = safeResolve(projDir, body.path);
        await fsp.mkdir(target, { recursive: true });
        return sendJson(res, 200, { ok: true });
      }

      if (pathname === '/api/fs/rename') {
        const src = safeResolve(projDir, body.oldPath);
        const dst = safeResolve(projDir, body.newPath);
        await fsp.mkdir(path.dirname(dst), { recursive: true });
        await fsp.rename(src, dst);
        return sendJson(res, 200, { ok: true });
      }

      if (pathname === '/api/fs/glob') {
        const rx = globToRegExp(String(body.pattern || '**/*'));
        const walked = walkTree(projDir);
        return sendJson(res, 200, { ok: true, matches: walked.flat.filter((f) => rx.test(f)) });
      }

      if (pathname === '/api/fs/grep') {
        const rx = new RegExp(String(body.pattern || ''), 'i');
        const incRx = body.include ? globToRegExp(String(body.include)) : null;
        const walked = walkTree(projDir);
        const matches = [];
        for (const f of walked.flat) {
          if (incRx && !incRx.test(path.basename(f)) && !incRx.test(f)) continue;
          const full = path.join(projDir, f);
          const txt = fs.readFileSync(full, 'utf8');
          const lines = txt.split('\n');
          for (let ln = 0; ln < lines.length; ln++) {
            if (rx.test(lines[ln])) {
              matches.push({ path: f, line: ln + 1, text: lines[ln].slice(0, 220) });
              if (matches.length >= 120) break;
            }
          }
          if (matches.length >= 120) break;
        }
        return sendJson(res, 200, { ok: true, matches });
      }

      if (pathname === '/api/snapshots/create') {
        const snapshotId = `snap_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
        const snapPath = path.join(SNAPSHOTS_DIR, snapshotId);
        copyDirRecursive(projDir, snapPath);
        return sendJson(res, 200, { ok: true, snapshotId });
      }

      if (pathname === '/api/snapshots/diff') {
        const snapPath = path.join(SNAPSHOTS_DIR, path.basename(String(body.snapshotId || '')));
        if (!fs.existsSync(snapPath)) return sendJson(res, 200, { ok: true, diffs: [] });
        const beforeFiles = new Set(walkTree(snapPath).flat);
        const afterFiles = new Set(walkTree(projDir).flat);
        const all = new Set([...beforeFiles, ...afterFiles]);
        const diffs = [];
        for (const rel of all) {
          const oldTxt = beforeFiles.has(rel) ? fs.readFileSync(path.join(snapPath, rel), 'utf8') : '';
          const newTxt = afterFiles.has(rel) ? fs.readFileSync(path.join(projDir, rel), 'utf8') : '';
          if (oldTxt !== newTxt) diffs.push(buildUnifiedDiff(rel, oldTxt, newTxt));
        }
        return sendJson(res, 200, { ok: true, diffs });
      }

      if (pathname === '/api/snapshots/revert') {
        const snapPath = path.join(SNAPSHOTS_DIR, path.basename(String(body.snapshotId || '')));
        if (!fs.existsSync(snapPath)) throw new Error('Snapshot not found');
        for (const ent of fs.readdirSync(projDir)) {
          if (ent === '.git') continue;
          fs.rmSync(path.join(projDir, ent), { recursive: true, force: true });
        }
        copyDirRecursive(snapPath, projDir);
        const count = walkTree(projDir).flat.length;
        return sendJson(res, 200, { ok: true, restoredFiles: count });
      }

      if (pathname === '/api/shell/exec') {
        const command = String(body.command || '');
        const timeoutMs = Math.min(120000, Math.max(1000, Number(body.timeoutMs || 45000)));
        const t0 = Date.now();
        const result = await new Promise((resolve) => {
          const proc = spawn('/bin/sh', ['-c', command], {
            cwd: projDir,
            env: { ...process.env, OPENCODE: '1', TERM: 'xterm-256color' },
          });
          let stdout = '';
          let stderr = '';
          const timer = setTimeout(() => {
            proc.kill('SIGKILL');
            stderr += '\n[Timed out]';
          }, timeoutMs);
          proc.stdout.on('data', (d) => {
            stdout += d.toString();
          });
          proc.stderr.on('data', (d) => {
            stderr += d.toString();
          });
          proc.on('close', (code) => {
            clearTimeout(timer);
            resolve({
              stdout: stdout.slice(0, 64000),
              stderr: stderr.slice(0, 32000),
              exitCode: code ?? 0,
              durationMs: Date.now() - t0,
              cwd: projDir,
            });
          });
        });
        return sendJson(res, 200, { ok: true, ...result });
      }
    }

    // Proxy endpoints (mirrors Android ForegroundService native HttpURLConnection proxy)
    if (pathname === '/api/proxy/fetch' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const upstream = await fetch(String(body.url), {
        headers: { 'User-Agent': 'OpenCode-Android/2.2.5' },
      });
      const raw = await upstream.text();
      const stripped = raw
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
      return sendJson(res, 200, {
        ok: true,
        status: upstream.status,
        contentType: upstream.headers.get('content-type') || 'text/plain',
        content: stripped,
      });
    }

    if (pathname === '/api/proxy/stream' && req.method === 'POST') {
      const body = await readJsonBody(req);
      const upstream = await fetch(String(body.url), {
        method: String(body.method || 'POST'),
        headers: body.headers || {},
        body: body.body !== undefined && body.method !== 'GET' ? JSON.stringify(body.body) : undefined,
      });
      res.writeHead(upstream.status, {
        'Content-Type': upstream.headers.get('content-type') || 'application/octet-stream',
        'Cache-Control': 'no-cache',
        'Access-Control-Allow-Origin': '*',
      });
      if (!upstream.body) return res.end();
      for await (const chunk of upstream.body) {
        res.write(chunk);
      }
      return res.end();
    }

    // Serve built SPA static assets from WWW_DIR
    let assetPath = path.join(WWW_DIR, pathname === '/' ? 'index.html' : pathname);
    if (!fs.existsSync(assetPath) || fs.statSync(assetPath).isDirectory()) {
      assetPath = path.join(WWW_DIR, 'index.html');
    }
    if (fs.existsSync(assetPath)) {
      const ext = path.extname(assetPath).toLowerCase();
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
      return fs.createReadStream(assetPath).pipe(res);
    }

    res.writeHead(404);
    res.end('Not found');
  } catch (err) {
    sendJson(res, 500, { ok: false, error: err?.message || String(err) });
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`OpenCode Daemon listening on http://0.0.0.0:${PORT}`);
});
