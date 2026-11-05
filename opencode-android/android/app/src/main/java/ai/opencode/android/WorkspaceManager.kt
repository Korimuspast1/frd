package ai.opencode.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.regex.Pattern
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

class WorkspaceManager(private val context: Context) {

    val workspacesRoot: File by lazy {
        val ext = context.getExternalFilesDir("workspaces")
        val dir = ext ?: File(context.filesDir, "workspaces")
        if (!dir.exists()) dir.mkdirs()
        seedStarterIfEmpty(dir)
        dir
    }

    private val snapshotsRoot: File by lazy {
        val dir = File(context.filesDir, "snapshots")
        if (!dir.exists()) dir.mkdirs()
        dir
    }

    val exportsRoot: File by lazy {
        val dir = File(context.cacheDir, "exports")
        if (!dir.exists()) dir.mkdirs()
        dir
    }

    private fun sanitizeSlug(raw: String): String {
        val cleaned = raw.lowercase()
            .replace(Regex("[^a-z0-9_-]+"), "-")
            .trim('-')
        return if (cleaned.isEmpty()) "project-${System.currentTimeMillis() % 10000}" else cleaned
    }

    private fun seedStarterIfEmpty(root: File) {
        val existing = root.listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") } ?: emptyList()
        if (existing.isEmpty()) {
            createProject("opencode-playground", "typescript")
        }
    }

    fun resolveProjectDir(projectId: String): File {
        val safeName = File(projectId).name
        val dir = File(workspacesRoot, safeName)
        if (!dir.exists() || !dir.isDirectory) {
            throw IllegalArgumentException("Project not found: $projectId")
        }
        return dir
    }

    fun safeResolveFile(projectDir: File, relPath: String): File {
        val cleanRel = relPath.trimStart('/', '\\')
        val target = File(projectDir, cleanRel).canonicalFile
        val rootCanon = projectDir.canonicalFile
        if (!target.path.startsWith(rootCanon.path)) {
            throw SecurityException("Path escapes workspace: $relPath")
        }
        return target
    }

    fun listProjectsJson(): JSONArray {
        val arr = JSONArray()
        val dirs = workspacesRoot.listFiles()
            ?.filter { it.isDirectory && !it.name.startsWith(".") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()

        for (d in dirs) {
            val obj = JSONObject()
            obj.put("id", d.name)
            obj.put("name", d.name)
            obj.put("path", d.absolutePath)
            obj.put("createdAt", d.lastModified())
            obj.put("updatedAt", d.lastModified())
            arr.put(obj)
        }
        return arr
    }

    fun createProject(name: String, template: String): JSONObject {
        val baseId = sanitizeSlug(name)
        var finalId = baseId
        var idx = 2
        while (File(workspacesRoot, finalId).exists()) {
            finalId = "$baseId-$idx"
            idx++
        }
        val dir = File(workspacesRoot, finalId)
        dir.mkdirs()

        when (template) {
            "python" -> {
                File(dir, "README.md").writeText("# $name\n\nЛокальный проект Python в OpenCode Android.\n")
                File(dir, "main.py").writeText(
                    "def greet(target: str) -> str:\n    return f\"Hello from OpenCode Android, {target}!\"\n\nif __name__ == \"__main__\":\n    print(greet(\"Developer\"))\n"
                )
            }
            "android" -> {
                val src = File(dir, "src/main/kotlin")
                src.mkdirs()
                File(dir, "README.md").writeText("# $name\n\nKotlin / Android модуль в OpenCode.\n")
                File(src, "Main.kt").writeText("package app\n\nfun main() {\n    println(\"OpenCode Android Workspace\")\n}\n")
            }
            "empty" -> {
                // empty directory
            }
            else -> {
                val src = File(dir, "src")
                src.mkdirs()
                File(dir, "README.md").writeText(
                    "# $name\n\nДобро пожаловать в **OpenCode Android**!\n\n- Чтение, создание, редактирование и удаление локальных файлов.\n- Агенты `build`, `plan` и сабагент `@general`.\n- Фоновый сервис `OpenCodeDaemonService` и встроенный Android Shell.\n"
                )
                File(dir, "AGENTS.md").writeText("- Пиши чистый, модульный и понятный код.\n- Всегда проверяй файлы перед редактированием.\n")
                File(dir, "package.json").writeText("{\n  \"name\": \"$finalId\",\n  \"version\": \"1.0.0\",\n  \"type\": \"module\"\n}\n")
                File(src, "index.ts").writeText("export function add(a: number, b: number): number {\n  return a + b;\n}\n\nconsole.log(\"OpenCode Android:\", add(20, 22));\n")
            }
        }

        return JSONObject().apply {
            put("id", finalId)
            put("name", name.ifBlank { finalId })
            put("path", dir.absolutePath)
            put("template", template)
            put("createdAt", System.currentTimeMillis())
            put("updatedAt", System.currentTimeMillis())
        }
    }

    fun cloneGithubRepo(repoUrl: String, customName: String?): JSONObject {
        val clean = repoUrl.trim().removeSuffix(".git").removeSuffix("/")
        val regex = Regex("github\\.com/([^/]+)/([^/#?]+)", RegexOption.IGNORE_CASE)
        val match = regex.find(clean) ?: throw IllegalArgumentException("Укажите ссылку вида https://github.com/owner/repo")
        val owner = match.groupValues[1]
        val repo = match.groupValues[2]

        val baseId = sanitizeSlug(if (!customName.isNullOrBlank()) customName else repo)
        var finalId = baseId
        var idx = 2
        while (File(workspacesRoot, finalId).exists()) {
            finalId = "$baseId-$idx"
            idx++
        }
        val destDir = File(workspacesRoot, finalId)
        destDir.mkdirs()

        val zipUrl = URL("https://codeload.github.com/$owner/$repo/zip/HEAD")
        val conn = (zipUrl.openConnection() as HttpURLConnection).apply {
            connectTimeout = 20000
            readTimeout = 45000
            setRequestProperty("User-Agent", "OpenCode-Android/2.2.5")
        }

        if (conn.responseCode !in 200..299) {
            destDir.deleteRecursively()
            throw IllegalStateException("GitHub вернул HTTP ${conn.responseCode}")
        }

        ZipInputStream(BufferedInputStream(conn.inputStream)).use { zis ->
            var entry: ZipEntry? = zis.nextEntry
            while (entry != null) {
                val rawName = entry.name
                val slashIdx = rawName.indexOf('/')
                val stripped = if (slashIdx >= 0 && slashIdx + 1 < rawName.length) rawName.substring(slashIdx + 1) else ""
                if (stripped.isNotEmpty()) {
                    val outFile = safeResolveFile(destDir, stripped)
                    if (entry.isDirectory) {
                        outFile.mkdirs()
                    } else {
                        outFile.parentFile?.mkdirs()
                        BufferedOutputStream(FileOutputStream(outFile)).use { bos ->
                            zis.copyTo(bos)
                        }
                    }
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }

        return JSONObject().apply {
            put("id", finalId)
            put("name", finalId)
            put("path", destDir.absolutePath)
            put("createdAt", System.currentTimeMillis())
            put("updatedAt", System.currentTimeMillis())
        }
    }

    fun deleteProject(projectId: String) {
        val dir = resolveProjectDir(projectId)
        dir.deleteRecursively()
        seedStarterIfEmpty(workspacesRoot)
    }

    fun exportProjectZip(projectId: String): File {
        val dir = resolveProjectDir(projectId)
        val outZip = File(exportsRoot, "${dir.name}.zip")
        if (outZip.exists()) outZip.delete()

        ZipOutputStream(BufferedOutputStream(FileOutputStream(outZip))).use { zos ->
            fun walk(cur: File, relPrefix: String) {
                val children = cur.listFiles() ?: return
                for (c in children) {
                    if (c.name == ".git" || c.name == "node_modules") continue
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

    fun listTree(projectId: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val flat = JSONArray()

        fun walk(dir: File, prefix: String): JSONArray {
            val nodes = JSONArray()
            val list = (dir.listFiles() ?: emptyArray())
                .filter { it.name != ".git" && it.name != "node_modules" && it.name != ".snapshots" }
                .sortedWith(compareBy<File>({ !it.isDirectory }, { it.name.lowercase() }))

            for (f in list) {
                val rel = if (prefix.isEmpty()) f.name else "$prefix/${f.name}"
                val node = JSONObject()
                node.put("name", f.name)
                node.put("path", rel)
                if (f.isDirectory) {
                    node.put("type", "directory")
                    node.put("children", walk(f, rel))
                } else {
                    node.put("type", "file")
                    node.put("size", f.length())
                    node.put("mtime", f.lastModified())
                    flat.put(rel)
                }
                nodes.put(node)
            }
            return nodes
        }

        val tree = walk(projDir, "")
        return JSONObject().apply {
            put("ok", true)
            put("tree", tree)
            put("flatFiles", flat)
        }
    }

    fun buildUnifiedDiff(relPath: String, oldStr: String, newStr: String): JSONObject {
        val oldLines = if (oldStr.isEmpty()) emptyList() else oldStr.split("\n")
        val newLines = if (newStr.isEmpty()) emptyList() else newStr.split("\n")
        var additions = 0
        var deletions = 0
        val sb = ArrayList<String>()
        sb.add("--- a/$relPath")
        sb.add("+++ b/$relPath")
        sb.add("@@ -1,${oldLines.size} +1,${newLines.size} @@")

        val maxLen = maxOf(oldLines.size, newLines.size)
        for (i in 0 until maxLen) {
            val o = oldLines.getOrNull(i)
            val n = newLines.getOrNull(i)
            if (o == n) {
                if (o != null && sb.size < 260) sb.add(" $o")
            } else {
                if (o != null) {
                    deletions++
                    if (sb.size < 260) sb.add("-$o")
                }
                if (n != null) {
                    additions++
                    if (sb.size < 260) sb.add("+$n")
                }
            }
        }

        val status = when {
            oldStr.isEmpty() -> "added"
            newStr.isEmpty() -> "deleted"
            else -> "modified"
        }

        return JSONObject().apply {
            put("path", relPath)
            put("status", status)
            put("oldContent", oldStr)
            put("newContent", newStr)
            put("additions", additions)
            put("deletions", deletions)
            put("unifiedDiff", sb.joinToString("\n"))
        }
    }

    fun readFile(projectId: String, relPath: String, offset: Int, limit: Int): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val file = safeResolveFile(projDir, relPath)
        if (!file.exists() || !file.isFile) throw IllegalArgumentException("File not found: $relPath")

        val content = file.readText(Charsets.UTF_8)
        val lines = content.split("\n")
        val start = (offset - 1).coerceAtLeast(0)
        val end = (start + limit.coerceAtLeast(1)).coerceAtMost(lines.size)
        val numbered = StringBuilder()
        for (i in start until end) {
            numbered.append((i + 1).toString().padStart(4, ' ')).append(" | ").append(lines[i])
            if (i < end - 1) numbered.append('\n')
        }

        return JSONObject().apply {
            put("ok", true)
            put("content", content)
            put("totalLines", lines.size)
            put("numbered", numbered.toString())
            put("size", file.length())
        }
    }

    fun writeFile(projectId: String, relPath: String, content: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val cleanRel = relPath.trimStart('/')
        val file = safeResolveFile(projDir, cleanRel)
        val prev = if (file.exists() && file.isFile) file.readText(Charsets.UTF_8) else ""
        file.parentFile?.mkdirs()
        file.writeText(content, Charsets.UTF_8)
        return JSONObject().apply {
            put("ok", true)
            put("diff", buildUnifiedDiff(cleanRel, prev, content))
        }
    }

    fun editFile(projectId: String, relPath: String, oldStr: String, newStr: String, replaceAll: Boolean): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val cleanRel = relPath.trimStart('/')
        val file = safeResolveFile(projDir, cleanRel)
        if (!file.exists()) throw IllegalArgumentException("File does not exist: $cleanRel")
        val prev = file.readText(Charsets.UTF_8)
        if (!prev.contains(oldStr)) {
            throw IllegalArgumentException("oldString not found in $cleanRel")
        }
        val count = if (replaceAll) prev.split(oldStr).size - 1 else 1
        val next = if (replaceAll) prev.replace(oldStr, newStr) else prev.replaceFirst(oldStr, newStr)
        file.writeText(next, Charsets.UTF_8)
        return JSONObject().apply {
            put("ok", true)
            put("replacements", count)
            put("diff", buildUnifiedDiff(cleanRel, prev, next))
        }
    }

    fun applyPatch(projectId: String, patchText: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val diffs = JSONArray()
        val lines = patchText.split("\n")
        var i = 0
        while (i < lines.size) {
            val line = lines[i]
            when {
                line.startsWith("*** Add File: ") -> {
                    val rel = line.removePrefix("*** Add File: ").trim()
                    i++
                    val buf = ArrayList<String>()
                    while (i < lines.size && !lines[i].startsWith("*** ")) {
                        buf.add(if (lines[i].startsWith("+")) lines[i].substring(1) else lines[i])
                        i++
                    }
                    val f = safeResolveFile(projDir, rel)
                    f.parentFile?.mkdirs()
                    val text = buf.joinToString("\n")
                    f.writeText(text, Charsets.UTF_8)
                    diffs.put(buildUnifiedDiff(rel, "", text))
                    continue
                }
                line.startsWith("*** Delete File: ") -> {
                    val rel = line.removePrefix("*** Delete File: ").trim()
                    val f = safeResolveFile(projDir, rel)
                    val prev = if (f.exists() && f.isFile) f.readText(Charsets.UTF_8) else ""
                    f.delete()
                    diffs.put(buildUnifiedDiff(rel, prev, ""))
                }
            }
            i++
        }
        return JSONObject().apply {
            put("ok", true)
            put("diffs", diffs)
            put("summary", "Applied patch (${diffs.length()} file(s) changed)")
        }
    }

    fun deletePath(projectId: String, relPath: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val cleanRel = relPath.trimStart('/')
        val target = safeResolveFile(projDir, cleanRel)
        val prev = if (target.exists() && target.isFile) target.readText(Charsets.UTF_8) else ""
        target.deleteRecursively()
        return JSONObject().apply {
            put("ok", true)
            put("deletedCount", 1)
            put("diff", buildUnifiedDiff(cleanRel, prev, ""))
        }
    }

    fun mkdir(projectId: String, relPath: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val target = safeResolveFile(projDir, relPath)
        target.mkdirs()
        return JSONObject().put("ok", true)
    }

    fun renamePath(projectId: String, oldRel: String, newRel: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val src = safeResolveFile(projDir, oldRel)
        val dst = safeResolveFile(projDir, newRel)
        dst.parentFile?.mkdirs()
        if (!src.renameTo(dst)) {
            src.copyRecursively(dst, overwrite = true)
            src.deleteRecursively()
        }
        return JSONObject().put("ok", true)
    }

    private fun globToRegex(glob: String): Regex {
        val escaped = StringBuilder("^")
        var i = 0
        while (i < glob.length) {
            val c = glob[i]
            if (c == '*' && i + 1 < glob.length && glob[i + 1] == '*') {
                if (i + 2 < glob.length && glob[i + 2] == '/') {
                    escaped.append("(?:.+/)?")
                    i += 3
                    continue
                }
                escaped.append(".*")
                i += 2
                continue
            }
            when (c) {
                '*' -> escaped.append("[^/]*")
                '?' -> escaped.append(".")
                '.', '+', '^', '$', '{', '}', '(', ')', '|', '[', ']', '\\' -> escaped.append('\\').append(c)
                else -> escaped.append(c)
            }
            i++
        }
        escaped.append("$")
        return Regex(escaped.toString(), RegexOption.IGNORE_CASE)
    }

    fun globFiles(projectId: String, pattern: String): JSONObject {
        val rx = globToRegex(pattern.ifBlank { "**/*" })
        val flat = listTree(projectId).getJSONArray("flatFiles")
        val out = JSONArray()
        for (i in 0 until flat.length()) {
            val f = flat.getString(i)
            if (rx.matches(f)) out.put(f)
        }
        return JSONObject().put("ok", true).put("matches", out)
    }

    fun grepFiles(projectId: String, pattern: String, include: String?): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val rx = Pattern.compile(pattern, Pattern.CASE_INSENSITIVE)
        val incRx = if (!include.isNullOrBlank()) globToRegex(include) else null
        val flat = listTree(projectId).getJSONArray("flatFiles")
        val matches = JSONArray()

        for (i in 0 until flat.length()) {
            val rel = flat.getString(i)
            if (incRx != null && !incRx.matches(rel) && !incRx.matches(File(rel).name)) continue
            val file = File(projDir, rel)
            if (!file.isFile || file.length() > 1024 * 1024) continue
            val lines = try {
                file.readLines(Charsets.UTF_8)
            } catch (_: Exception) {
                continue
            }
            for ((idx, ln) in lines.withIndex()) {
                if (rx.matcher(ln).find()) {
                    matches.put(
                        JSONObject()
                            .put("path", rel)
                            .put("line", idx + 1)
                            .put("text", ln.take(220))
                    )
                    if (matches.length() >= 120) break
                }
            }
            if (matches.length() >= 120) break
        }

        return JSONObject().put("ok", true).put("matches", matches)
    }

    fun createSnapshot(projectId: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val snapId = "snap_${System.currentTimeMillis()}"
        val snapDir = File(snapshotsRoot, snapId)
        snapDir.mkdirs()
        projDir.copyRecursively(snapDir, overwrite = true)
        return JSONObject().put("ok", true).put("snapshotId", snapId)
    }

    fun diffSnapshot(projectId: String, snapshotId: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val snapDir = File(snapshotsRoot, File(snapshotId).name)
        val diffs = JSONArray()
        if (!snapDir.exists()) return JSONObject().put("ok", true).put("diffs", diffs)

        fun collectRel(root: File): Set<String> {
            val res = LinkedHashSet<String>()
            fun walk(d: File, pfx: String) {
                for (c in d.listFiles() ?: emptyArray()) {
                    if (c.name == ".git" || c.name == "node_modules") continue
                    val r = if (pfx.isEmpty()) c.name else "$pfx/${c.name}"
                    if (c.isDirectory) walk(c, r) else res.add(r)
                }
            }
            walk(root, "")
            return res
        }

        val before = collectRel(snapDir)
        val after = collectRel(projDir)
        val all = LinkedHashSet<String>().apply { addAll(before); addAll(after) }

        for (rel in all) {
            val o = if (before.contains(rel)) File(snapDir, rel).readText(Charsets.UTF_8) else ""
            val n = if (after.contains(rel)) File(projDir, rel).readText(Charsets.UTF_8) else ""
            if (o != n) diffs.put(buildUnifiedDiff(rel, o, n))
        }
        return JSONObject().put("ok", true).put("diffs", diffs)
    }

    fun revertSnapshot(projectId: String, snapshotId: String): JSONObject {
        val projDir = resolveProjectDir(projectId)
        val snapDir = File(snapshotsRoot, File(snapshotId).name)
        if (!snapDir.exists()) throw IllegalArgumentException("Snapshot not found: $snapshotId")

        for (child in projDir.listFiles() ?: emptyArray()) {
            if (child.name == ".git") continue
            child.deleteRecursively()
        }
        snapDir.copyRecursively(projDir, overwrite = true)
        return JSONObject().put("ok", true).put("restoredFiles", 1)
    }
}
