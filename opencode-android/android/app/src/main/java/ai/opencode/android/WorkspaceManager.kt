package ai.opencode.android

import android.content.Context
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.regex.Pattern
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class WorkspaceManager(private val context: Context) {

    val workspacesRoot: File = File(context.filesDir, "workspaces")
    val exportsRoot: File = File(context.cacheDir, "exports")

    @Volatile
    private var initialized = false

    private val ignoredDirs = setOf(".git", "node_modules", ".next", "dist", "build", "__pycache__", ".snapshots")

    @Synchronized
    fun ensureInitialized() {
        if (initialized) return
        if (!workspacesRoot.exists()) workspacesRoot.mkdirs()
        if (!exportsRoot.exists()) exportsRoot.mkdirs()
        val existing = workspacesRoot.listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") } ?: emptyList()
        if (existing.isEmpty()) {
            createProjectInternal("opencode-playground", "typescript", null)
        }
        initialized = true
    }

    fun defaultProjectDir(): File {
        ensureInitialized()
        val dirs = workspacesRoot.listFiles()
            ?.filter { it.isDirectory && !it.name.startsWith(".") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
        if (dirs.isNotEmpty()) return dirs[0]
        val obj = createProjectInternal("opencode-playground", "typescript", null)
        return File(obj.optString("directory", File(workspacesRoot, "opencode-playground").absolutePath))
    }

    fun resolveDirectoryOrDefault(directory: String): File {
        ensureInitialized()
        if (directory.isNotBlank()) {
            val f = File(directory)
            if (f.exists() && f.isDirectory) return f
            val bySlug = File(workspacesRoot, File(directory).name)
            if (bySlug.exists() && bySlug.isDirectory) return bySlug
        }
        return defaultProjectDir()
    }

    fun safeResolveTarget(baseDir: File, relPath: String): File {
        if (relPath.isBlank() || relPath == ".") return baseDir.canonicalFile
        val candidate = if (relPath.startsWith("/")) {
            val abs = File(relPath).canonicalFile
            val rootCanon = workspacesRoot.canonicalFile
            val baseCanon = baseDir.canonicalFile
            if (abs.path.startsWith(baseCanon.path) || abs.path.startsWith(rootCanon.path)) {
                abs
            } else {
                File(baseDir, relPath.trimStart('/')).canonicalFile
            }
        } else {
            File(baseDir, relPath).canonicalFile
        }
        val baseCanon = baseDir.canonicalFile
        val rootCanon = workspacesRoot.canonicalFile
        if (!candidate.path.startsWith(baseCanon.path) && !candidate.path.startsWith(rootCanon.path)) {
            throw SecurityException("Path escapes workspace: $relPath")
        }
        return candidate
    }

    private fun sanitizeSlug(raw: String): String {
        val cleaned = raw.trim().lowercase()
            .replace(Regex("[^a-z0-9._-]+"), "-")
            .trim('-')
        return if (cleaned.isEmpty()) "project-${System.currentTimeMillis() % 10000}" else cleaned
    }

    fun listProjectsJson(): JSONArray {
        ensureInitialized()
        val arr = JSONArray()
        val dirs = workspacesRoot.listFiles()
            ?.filter { it.isDirectory && !it.name.startsWith(".") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()

        val now = System.currentTimeMillis()
        for (d in dirs) {
            val ts = d.lastModified().takeIf { it > 0L } ?: now
            val obj = JSONObject()
            obj.put("id", d.name)
            obj.put("name", d.name)
            obj.put("directory", d.absolutePath)
            obj.put("createdAt", ts)
            obj.put("updatedAt", ts)
            arr.put(obj)
        }
        return arr
    }

    fun createProject(name: String, template: String, customDirectory: String? = null): JSONObject {
        ensureInitialized()
        return createProjectInternal(name, template, customDirectory)
    }

    private fun createProjectInternal(name: String, template: String, customDirectory: String?): JSONObject {
        val baseId = sanitizeSlug(name)
        val dir = if (!customDirectory.isNullOrBlank()) {
            val f = File(customDirectory)
            if (f.isAbsolute && f.canonicalPath.startsWith(workspacesRoot.canonicalPath)) f else File(workspacesRoot, baseId)
        } else {
            var finalId = baseId
            var idx = 2
            while (File(workspacesRoot, finalId).exists()) {
                finalId = "$baseId-$idx"
                idx++
            }
            File(workspacesRoot, finalId)
        }
        if (!dir.exists()) dir.mkdirs()

        val files = dir.listFiles()
        if (files == null || files.isEmpty()) {
            when (template) {
                "python" -> {
                    File(dir, "README.md").writeText("# ${dir.name}\n\nPython project created in OpenCode Android.\n")
                    File(dir, "main.py").writeText(
                        "def greet(target: str = \"OpenCode Android\") -> str:\n    return f\"Hello from {target}!\"\n\nif __name__ == \"__main__\":\n    print(greet())\n"
                    )
                }

                "web", "html" -> {
                    File(dir, "README.md").writeText("# ${dir.name}\n\nWeb project created in OpenCode Android.\n")
                    File(dir, "index.html").writeText(
                        "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\" />\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n  <title>${dir.name}</title>\n</head>\n<body>\n  <h1>${dir.name}</h1>\n</body>\n</html>\n"
                    )
                }

                "blank", "empty" -> {
                    File(dir, "README.md").writeText("# ${dir.name}\n")
                }

                else -> {
                    val src = File(dir, "src")
                    src.mkdirs()
                    File(dir, "README.md").writeText(
                        "# ${dir.name}\n\nWelcome to **OpenCode Android v2.2.5**!\n\n- Local project files stored on your Android device\n- Add any OpenAI / Anthropic / OpenRouter / Ollama / custom endpoint in **Connect provider -> + Custom Provider**\n- Models are discovered automatically from `/v1/models`\n"
                    )
                    File(dir, "package.json").writeText(
                        "{\n  \"name\": \"${dir.name}\",\n  \"version\": \"1.0.0\",\n  \"type\": \"module\"\n}\n"
                    )
                    File(src, "index.ts").writeText(
                        "export function greet(name = \"OpenCode Android\"): string {\n  return `Hello from \${name}!`\n}\n\nconsole.log(greet())\n"
                    )
                }
            }
        }

        val now = System.currentTimeMillis()
        return JSONObject().apply {
            put("id", dir.name)
            put("name", name.ifBlank { dir.name })
            put("directory", dir.absolutePath)
            put("createdAt", now)
            put("updatedAt", now)
        }
    }

    fun deleteProjectByDirectory(directory: String) {
        ensureInitialized()
        if (directory.isBlank()) return
        val target = resolveDirectoryOrDefault(directory)
        if (target.canonicalPath.startsWith(workspacesRoot.canonicalPath) && target != workspacesRoot) {
            target.deleteRecursively()
        }
        val remaining = workspacesRoot.listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") } ?: emptyList()
        if (remaining.isEmpty()) {
            createProjectInternal("opencode-playground", "typescript", null)
        }
    }

    fun fsList(directory: String, subPath: String): JSONArray {
        val baseDir = resolveDirectoryOrDefault(directory)
        val target = safeResolveTarget(baseDir, subPath)
        val out = JSONArray()
        if (!target.exists() || !target.isDirectory) return out

        val baseCanon = baseDir.canonicalPath
        val children = (target.listFiles() ?: emptyArray())
            .filter { it.name != ".git" }
            .sortedWith(compareBy<File>({ !it.isDirectory }, { it.name.lowercase() }))

        for (child in children) {
            val childCanon = child.canonicalPath
            val rel = if (childCanon.startsWith("$baseCanon/")) {
                childCanon.substring(baseCanon.length + 1).replace('\\', '/')
            } else {
                child.name
            }
            out.put(
                JSONObject()
                    .put("path", rel)
                    .put("type", if (child.isDirectory) "directory" else "file")
            )
        }
        return out
    }

    private fun walkWorkspace(baseDir: File, maxEntries: Int = 2500): List<Pair<String, File>> {
        val results = ArrayList<Pair<String, File>>()
        val baseCanon = baseDir.canonicalPath

        fun visit(cur: File) {
            if (results.size >= maxEntries) return
            val list = cur.listFiles() ?: return
            for (item in list) {
                if (results.size >= maxEntries) return
                if (ignoredDirs.contains(item.name)) continue
                val canon = item.canonicalPath
                val rel = if (canon.startsWith("$baseCanon/")) {
                    canon.substring(baseCanon.length + 1).replace('\\', '/')
                } else {
                    item.name
                }
                results.add(rel to item)
                if (item.isDirectory) {
                    visit(item)
                }
            }
        }

        visit(baseDir)
        return results
    }

    fun fsFind(directory: String, query: String, type: String?, limit: Int): JSONArray {
        val baseDir = resolveDirectoryOrDefault(directory)
        val all = walkWorkspace(baseDir, 2500)
        val q = query.trim().lowercase()
        val out = JSONArray()
        val cap = limit.coerceIn(1, 500)

        for ((rel, file) in all) {
            val itemType = if (file.isDirectory) "directory" else "file"
            if (type != null && type != itemType) continue
            if (q.isEmpty() || rel.lowercase().contains(q)) {
                out.put(JSONObject().put("path", rel).put("type", itemType))
                if (out.length() >= cap) break
            }
        }
        return out
    }

    private fun guessMime(name: String): String {
        val lower = name.lowercase()
        return when {
            lower.endsWith(".ts") || lower.endsWith(".tsx") -> "text/typescript; charset=utf-8"
            lower.endsWith(".js") || lower.endsWith(".mjs") || lower.endsWith(".jsx") -> "text/javascript; charset=utf-8"
            lower.endsWith(".json") -> "application/json; charset=utf-8"
            lower.endsWith(".md") -> "text/markdown; charset=utf-8"
            lower.endsWith(".html") -> "text/html; charset=utf-8"
            lower.endsWith(".css") -> "text/css; charset=utf-8"
            lower.endsWith(".png") -> "image/png"
            lower.endsWith(".jpg") || lower.endsWith(".jpeg") -> "image/jpeg"
            lower.endsWith(".webp") -> "image/webp"
            lower.endsWith(".gif") -> "image/gif"
            lower.endsWith(".svg") -> "image/svg+xml"
            else -> "text/plain; charset=utf-8"
        }
    }

    fun fsRead(directory: String, relPath: String): JSONObject {
        val baseDir = resolveDirectoryOrDefault(directory)
        val target = safeResolveTarget(baseDir, relPath)
        if (!target.exists() || !target.isFile) {
            return JSONObject().put("exists", false)
        }
        val bytes = target.readBytes()
        var isBinary = false
        val inspectLen = minOf(bytes.size, 1024)
        for (i in 0 until inspectLen) {
            if (bytes[i].toInt() == 0) {
                isBinary = true
                break
            }
        }
        val out = JSONObject()
            .put("exists", true)
            .put("mime", guessMime(target.name))
            .put("base64", Base64.encodeToString(bytes, Base64.NO_WRAP))
        if (!isBinary) {
            out.put("text", String(bytes, Charsets.UTF_8))
        }
        return out
    }

    fun fsWriteText(directory: String, relPath: String, text: String): File {
        val baseDir = resolveDirectoryOrDefault(directory)
        val target = safeResolveTarget(baseDir, relPath)
        target.parentFile?.mkdirs()
        target.writeText(text, Charsets.UTF_8)
        baseDir.setLastModified(System.currentTimeMillis())
        return target
    }

    fun fsWriteBytes(directory: String, relPath: String, bytes: ByteArray): File {
        val baseDir = resolveDirectoryOrDefault(directory)
        val target = safeResolveTarget(baseDir, relPath)
        target.parentFile?.mkdirs()
        target.writeBytes(bytes)
        baseDir.setLastModified(System.currentTimeMillis())
        return target
    }

    fun fsDelete(directory: String, relPath: String): Boolean {
        val baseDir = resolveDirectoryOrDefault(directory)
        val target = safeResolveTarget(baseDir, relPath)
        if (!target.exists() || target == baseDir) return false
        return target.deleteRecursively()
    }

    fun fsGrep(directory: String, pattern: String, include: String?, limit: Int): JSONArray {
        val baseDir = resolveDirectoryOrDefault(directory)
        val out = JSONArray()
        if (pattern.isEmpty()) return out
        val cap = limit.coerceIn(1, 200)
        val rx = try {
            Pattern.compile(pattern, Pattern.CASE_INSENSITIVE)
        } catch (_: Throwable) {
            null
        }
        val incLower = include?.trim()?.trimStart('*')?.lowercase()

        val all = walkWorkspace(baseDir, 1500)
        for ((rel, file) in all) {
            if (!file.isFile || file.length() > 512 * 1024) continue
            if (!incLower.isNullOrEmpty() && !rel.lowercase().endsWith(incLower) && !rel.lowercase().contains(incLower)) {
                continue
            }
            val lines = try {
                file.readLines(Charsets.UTF_8)
            } catch (_: Throwable) {
                continue
            }
            for ((idx, line) in lines.withIndex()) {
                val matched = if (rx != null) {
                    rx.matcher(line).find()
                } else {
                    line.lowercase().contains(pattern.lowercase())
                }
                if (matched) {
                    out.put(
                        JSONObject()
                            .put("path", rel)
                            .put("line", idx + 1)
                            .put("text", line.take(300))
                    )
                    if (out.length() >= cap) return out
                }
            }
        }
        return out
    }

    fun exportProjectZip(projectIdOrDir: String): File {
        val dir = resolveDirectoryOrDefault(projectIdOrDir)
        if (!exportsRoot.exists()) exportsRoot.mkdirs()
        val outZip = File(exportsRoot, "${dir.name}.zip")
        if (outZip.exists()) outZip.delete()

        ZipOutputStream(BufferedOutputStream(FileOutputStream(outZip))).use { zos ->
            fun walk(cur: File, relPrefix: String) {
                val children = cur.listFiles() ?: return
                for (c in children) {
                    if (ignoredDirs.contains(c.name)) continue
                    val rel = if (relPrefix.isEmpty()) c.name else "$relPrefix/${c.name}"
                    if (c.isDirectory) {
                        walk(c, rel)
                    } else {
                        zos.putNextEntry(ZipEntry(rel))
                        FileInputStream(c).use { fis -> fis.copyTo(zos) }
                        zos.closeEntry()
                    }
                }
            }
            walk(dir, "")
        }
        return outZip
    }
}
