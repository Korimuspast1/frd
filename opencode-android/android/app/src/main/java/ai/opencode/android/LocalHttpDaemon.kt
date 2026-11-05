package ai.opencode.android

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.net.URLDecoder
import java.util.concurrent.Executors

class LocalHttpDaemon(
    private val context: Context,
    private val workspace: WorkspaceManager,
    private val shell: ShellExecutor,
    private val onStatusUpdate: (String, Boolean) -> Unit
) {
    @Volatile
    var port: Int = 0
        private set

    @Volatile
    private var running = false
    private var serverSocket: ServerSocket? = null
    private val pool = Executors.newCachedThreadPool()

    @Volatile
    var currentTask: String = "OpenCode готов • Фоновый сервис активен"

    @Volatile
    var isBusy: Boolean = false

    fun start(): Int {
        if (running && port > 0) return port
        val socket = try {
            ServerSocket(4096, 64, InetAddress.getByName("127.0.0.1"))
        } catch (_: Exception) {
            ServerSocket(0, 64, InetAddress.getByName("127.0.0.1"))
        }
        serverSocket = socket
        port = socket.localPort
        running = true

        Thread({
            while (running) {
                try {
                    val client = socket.accept()
                    pool.execute { handleClient(client) }
                } catch (_: Exception) {
                    if (!running) break
                }
            }
        }, "OpenCode-HttpAccept").start()

        return port
    }

    fun stop() {
        running = false
        try {
            serverSocket?.close()
        } catch (_: Exception) {}
    }

    private fun readLineAscii(ins: InputStream): String? {
        val bos = ByteArrayOutputStream()
        while (true) {
            val b = ins.read()
            if (b == -1) return if (bos.size() == 0) null else bos.toString("UTF-8")
            if (b == '\n'.code) break
            if (b != '\r'.code) bos.write(b)
        }
        return bos.toString("UTF-8")
    }

    private fun handleClient(socket: Socket) {
        socket.use { s ->
            s.soTimeout = 120000
            val ins = BufferedInputStream(s.getInputStream())
            val out = BufferedOutputStream(s.getOutputStream())

            val reqLine = readLineAscii(ins) ?: return
            val parts = reqLine.split(" ")
            if (parts.size < 2) return
            val method = parts[0].uppercase()
            val rawTarget = parts[1]

            val headers = HashMap<String, String>()
            while (true) {
                val line = readLineAscii(ins) ?: break
                if (line.isEmpty()) break
                val idx = line.indexOf(':')
                if (idx > 0) {
                    headers[line.substring(0, idx).trim().lowercase()] = line.substring(idx + 1).trim()
                }
            }

            if (method == "OPTIONS") {
                writeResponse(out, 204, "text/plain", ByteArray(0))
                return
            }

            val contentLen = headers["content-length"]?.toIntOrNull() ?: 0
            val bodyBytes = ByteArray(contentLen)
            var readTotal = 0
            while (readTotal < contentLen) {
                val r = ins.read(bodyBytes, readTotal, contentLen - readTotal)
                if (r <= 0) break
                readTotal += r
            }
            val bodyStr = String(bodyBytes, 0, readTotal, Charsets.UTF_8)

            val qIdx = rawTarget.indexOf('?')
            val path = if (qIdx >= 0) rawTarget.substring(0, qIdx) else rawTarget
            val query = if (qIdx >= 0) rawTarget.substring(qIdx + 1) else ""

            try {
                if (path == "/api/proxy/stream" && method == "POST") {
                    handleStreamingProxy(JSONObject(bodyStr), out)
                    return
                }
                if (path.startsWith("/api/")) {
                    val respJson = dispatchApi(method, path, query, bodyStr)
                    writeJson(out, 200, respJson)
                    return
                }
                serveAsset(path, out)
            } catch (e: Exception) {
                val err = JSONObject().put("ok", false).put("error", e.message ?: e.toString())
                writeJson(out, 500, err)
            }
        }
    }

    private fun dispatchApi(method: String, path: String, query: String, bodyStr: String): JSONObject {
        if (path == "/api/health") {
            return JSONObject().apply {
                put("ok", true)
                put("running", true)
                put("platform", "android")
                put("daemonUrl", "http://127.0.0.1:$port")
                put("foregroundService", true)
                put("busy", isBusy)
                put("currentTask", currentTask)
                put("deviceModel", "${Build.MANUFACTURER} ${Build.MODEL}")
                put("androidVersion", Build.VERSION.RELEASE)
                put("workspacesRoot", workspace.workspacesRoot.absolutePath)
            }
        }

        val body = if (bodyStr.isNotBlank()) JSONObject(bodyStr) else JSONObject()

        when (path) {
            "/api/daemon/status" -> {
                val txt = body.optString("statusText", currentTask)
                val busy = body.optBoolean("busy", false)
                currentTask = txt
                isBusy = busy
                onStatusUpdate(txt, busy)
                return JSONObject().put("ok", true)
            }
            "/api/projects" -> {
                return JSONObject().put("ok", true).put("projects", workspace.listProjectsJson())
            }
            "/api/projects/create" -> {
                val proj = workspace.createProject(
                    body.optString("name", "project"),
                    body.optString("template", "typescript")
                )
                return JSONObject().put("ok", true).put("project", proj)
            }
            "/api/projects/clone" -> {
                val proj = workspace.cloneGithubRepo(
                    body.optString("repoUrl", ""),
                    body.optString("name", "").ifBlank { null }
                )
                return JSONObject().put("ok", true).put("project", proj)
            }
            "/api/projects/delete" -> {
                workspace.deleteProject(body.optString("projectId", ""))
                return JSONObject().put("ok", true)
            }
            "/api/fs/tree" -> return workspace.listTree(body.optString("projectId"))
            "/api/fs/read" -> return workspace.readFile(
                body.optString("projectId"),
                body.optString("path"),
                body.optInt("offset", 1),
                body.optInt("limit", 300)
            )
            "/api/fs/write" -> return workspace.writeFile(
                body.optString("projectId"),
                body.optString("path"),
                body.optString("content", "")
            )
            "/api/fs/edit" -> return workspace.editFile(
                body.optString("projectId"),
                body.optString("path"),
                body.optString("oldString", ""),
                body.optString("newString", ""),
                body.optBoolean("replaceAll", false)
            )
            "/api/fs/patch" -> return workspace.applyPatch(
                body.optString("projectId"),
                body.optString("patchText", "")
            )
            "/api/fs/delete" -> return workspace.deletePath(
                body.optString("projectId"),
                body.optString("path")
            )
            "/api/fs/mkdir" -> return workspace.mkdir(
                body.optString("projectId"),
                body.optString("path")
            )
            "/api/fs/rename" -> return workspace.renamePath(
                body.optString("projectId"),
                body.optString("oldPath"),
                body.optString("newPath")
            )
            "/api/fs/glob" -> return workspace.globFiles(
                body.optString("projectId"),
                body.optString("pattern", "**/*")
            )
            "/api/fs/grep" -> return workspace.grepFiles(
                body.optString("projectId"),
                body.optString("pattern", ""),
                body.optString("include", "").ifBlank { null }
            )
            "/api/snapshots/create" -> return workspace.createSnapshot(body.optString("projectId"))
            "/api/snapshots/diff" -> return workspace.diffSnapshot(
                body.optString("projectId"),
                body.optString("snapshotId")
            )
            "/api/snapshots/revert" -> return workspace.revertSnapshot(
                body.optString("projectId"),
                body.optString("snapshotId")
            )
            "/api/shell/exec" -> {
                val projDir = workspace.resolveProjectDir(body.optString("projectId"))
                return shell.execute(
                    projDir,
                    body.optString("command", ""),
                    body.optLong("timeoutMs", 45000L)
                )
            }
            "/api/proxy/fetch" -> {
                val targetUrl = URL(body.optString("url"))
                val conn = (targetUrl.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 15000
                    readTimeout = 30000
                    setRequestProperty("User-Agent", "OpenCode-Android/2.2.5")
                }
                val code = conn.responseCode
                val stream = if (code in 200..399) conn.inputStream else conn.errorStream
                val raw = stream?.bufferedReader(Charsets.UTF_8)?.readText() ?: ""
                val stripped = raw
                    .replace(Regex("<script[\\s\\S]*?</script>", RegexOption.IGNORE_CASE), " ")
                    .replace(Regex("<style[\\s\\S]*?</style>", RegexOption.IGNORE_CASE), " ")
                    .replace(Regex("<[^>]+>"), " ")
                    .replace(Regex("\\s+"), " ")
                    .trim()
                return JSONObject().apply {
                    put("ok", true)
                    put("status", code)
                    put("contentType", conn.contentType ?: "text/plain")
                    put("content", stripped)
                }
            }
        }

        // Export zip download fallback
        if (path == "/api/projects/export-zip" && method == "GET") {
            val pid = query.split("&")
                .firstOrNull { it.startsWith("projectId=") }
                ?.substringAfter("=")
                ?.let { URLDecoder.decode(it, "UTF-8") } ?: ""
            val zip = workspace.exportProjectZip(pid)
            return JSONObject().put("ok", true).put("zipPath", zip.absolutePath)
        }

        throw IllegalArgumentException("Unknown endpoint: $path")
    }

    private fun handleStreamingProxy(reqJson: JSONObject, out: OutputStream) {
        val url = URL(reqJson.getString("url"))
        val method = reqJson.optString("method", "POST").uppercase()
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 25000
            readTimeout = 180000
            doInput = true
        }

        val hdrs = reqJson.optJSONObject("headers")
        if (hdrs != null) {
            val keys = hdrs.keys()
            while (keys.hasNext()) {
                val k = keys.next()
                conn.setRequestProperty(k, hdrs.optString(k))
            }
        }

        if (method != "GET" && method != "HEAD" && reqJson.has("body") && !reqJson.isNull("body")) {
            conn.doOutput = true
            val payload = reqJson.get("body").toString().toByteArray(Charsets.UTF_8)
            conn.outputStream.use { os -> os.write(payload) }
        }

        val status = conn.responseCode
        val contentType = conn.contentType ?: "application/octet-stream"
        val headerBlock = buildString {
            append("HTTP/1.1 $status OK\r\n")
            append("Content-Type: $contentType\r\n")
            append("Cache-Control: no-cache\r\n")
            append("Connection: close\r\n")
            append("Access-Control-Allow-Origin: *\r\n\r\n")
        }
        out.write(headerBlock.toByteArray(Charsets.UTF_8))
        out.flush()

        val upstream = if (status in 200..399) conn.inputStream else conn.errorStream
        if (upstream != null) {
            upstream.use { ins ->
                val buf = ByteArray(2048)
                var n = ins.read(buf)
                while (n != -1) {
                    out.write(buf, 0, n)
                    out.flush()
                    n = ins.read(buf)
                }
            }
        }
    }

    private fun serveAsset(rawPath: String, out: OutputStream) {
        val clean = rawPath.trimStart('/').ifEmpty { "index.html" }
        val assetPath = "www/$clean"
        val bytes = try {
            context.assets.open(assetPath).use { it.readBytes() }
        } catch (_: Exception) {
            context.assets.open("www/index.html").use { it.readBytes() }
        }

        val mime = when {
            clean.endsWith(".js") -> "application/javascript; charset=utf-8"
            clean.endsWith(".css") -> "text/css; charset=utf-8"
            clean.endsWith(".svg") -> "image/svg+xml"
            clean.endsWith(".png") -> "image/png"
            clean.endsWith(".json") -> "application/json; charset=utf-8"
            else -> "text/html; charset=utf-8"
        }
        writeResponse(out, 200, mime, bytes)
    }

    private fun writeJson(out: OutputStream, status: Int, obj: JSONObject) {
        writeResponse(out, status, "application/json; charset=utf-8", obj.toString().toByteArray(Charsets.UTF_8))
    }

    private fun writeResponse(out: OutputStream, status: Int, contentType: String, bytes: ByteArray) {
        val hdr = buildString {
            append("HTTP/1.1 $status OK\r\n")
            append("Content-Type: $contentType\r\n")
            append("Content-Length: ${bytes.size}\r\n")
            append("Connection: close\r\n")
            append("Access-Control-Allow-Origin: *\r\n")
            append("Access-Control-Allow-Headers: *\r\n")
            append("Access-Control-Allow-Methods: GET,POST,OPTIONS\r\n\r\n")
        }
        out.write(hdr.toByteArray(Charsets.UTF_8))
        if (bytes.isNotEmpty()) out.write(bytes)
        out.flush()
    }
}
