package ai.opencode.android

import android.content.Context
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class OpenCodeRuntime private constructor(private val appContext: Context) {

    companion object {
        @Volatile
        private var instance: OpenCodeRuntime? = null

        fun getInstance(context: Context): OpenCodeRuntime {
            val existing = instance
            if (existing != null) return existing
            return synchronized(this) {
                val second = instance
                if (second != null) {
                    second
                } else {
                    val created = OpenCodeRuntime(context.applicationContext)
                    instance = created
                    created.startBackgroundInit()
                    created
                }
            }
        }
    }

    val ioExecutor: ExecutorService = Executors.newCachedThreadPool()
    val workspaceManager: WorkspaceManager = WorkspaceManager(appContext)
    val shellExecutor: ShellExecutor = ShellExecutor(appContext)
    val httpDaemon: LocalHttpDaemon = LocalHttpDaemon(this)

    private val stateDir: File by lazy {
        val d = File(appContext.filesDir, "engine-state")
        if (!d.exists()) d.mkdirs()
        d
    }

    @Volatile
    var statusListener: ((String, Boolean) -> Unit)? = null

    private fun startBackgroundInit() {
        ioExecutor.execute {
            try {
                workspaceManager.ensureInitialized()
            } catch (_: Throwable) {
            }
            try {
                httpDaemon.startBlockingOnWorker()
            } catch (_: Throwable) {
            }
        }
    }

    val daemonPort: Int
        get() = httpDaemon.port

    fun sanitizeStateKey(raw: String): String {
        val cleaned = raw.replace(Regex("[^a-zA-Z0-9._-]+"), "_")
        return if (cleaned.isEmpty()) "default" else cleaned
    }

    fun loadState(key: String): String? {
        val f = File(stateDir, sanitizeStateKey(key) + ".json")
        if (!f.exists() || !f.isFile) return null
        return try {
            f.readText(Charsets.UTF_8)
        } catch (_: Throwable) {
            null
        }
    }

    fun saveState(key: String, value: String) {
        val f = File(stateDir, sanitizeStateKey(key) + ".json")
        try {
            if (!stateDir.exists()) stateDir.mkdirs()
            f.writeText(value, Charsets.UTF_8)
        } catch (_: Throwable) {
        }
    }

    fun dispatchRpcJson(requestJson: String): String {
        return try {
            val req = JSONObject(requestJson)
            val action = req.optString("action", "")
            val payload = req.optJSONObject("payload") ?: JSONObject()
            dispatchRpc(action, payload).toString()
        } catch (t: Throwable) {
            JSONObject().put("__error", t.message ?: t.javaClass.simpleName).toString()
        }
    }

    fun dispatchRpc(action: String, payload: JSONObject): JSONObject {
        workspaceManager.ensureInitialized()
        return when (action) {
            "getDefaultRoot" -> {
                JSONObject().put("root", workspaceManager.defaultProjectDir().absolutePath)
            }

            "listProjects" -> {
                JSONObject().put("projects", workspaceManager.listProjectsJson())
            }

            "createProject" -> {
                val name = payload.optString("name", "my-project")
                val template = payload.optString("template", "typescript")
                val customDir = payload.optString("directory", "").takeIf { it.isNotBlank() }
                val project = workspaceManager.createProject(name, template, customDir)
                JSONObject().put("project", project)
            }

            "deleteProject" -> {
                val directory = payload.optString("directory", "")
                workspaceManager.deleteProjectByDirectory(directory)
                JSONObject().put("ok", true)
            }

            "fsList" -> {
                val directory = payload.optString("directory", "")
                val subPath = payload.optString("subPath", "")
                val entries = workspaceManager.fsList(directory, subPath)
                JSONObject().put("entries", entries)
            }

            "fsFind" -> {
                val directory = payload.optString("directory", "")
                val query = payload.optString("query", "")
                val type = payload.optString("type", "").takeIf { it.isNotBlank() }
                val limit = payload.optInt("limit", 100)
                val entries = workspaceManager.fsFind(directory, query, type, limit)
                JSONObject().put("entries", entries)
            }

            "fsRead" -> {
                val directory = payload.optString("directory", "")
                val relPath = payload.optString("relPath", "")
                workspaceManager.fsRead(directory, relPath)
            }

            "fsWrite" -> {
                val directory = payload.optString("directory", "")
                val relPath = payload.optString("relPath", "")
                val hasBase64 = payload.has("base64") && !payload.isNull("base64")
                val written = if (hasBase64) {
                    val bytes = Base64.decode(payload.optString("base64", ""), Base64.DEFAULT)
                    workspaceManager.fsWriteBytes(directory, relPath, bytes)
                } else {
                    workspaceManager.fsWriteText(directory, relPath, payload.optString("text", ""))
                }
                JSONObject().put("path", written.absolutePath)
            }

            "fsDelete" -> {
                val directory = payload.optString("directory", "")
                val relPath = payload.optString("relPath", "")
                val deleted = workspaceManager.fsDelete(directory, relPath)
                JSONObject().put("deleted", deleted)
            }

            "fsGrep" -> {
                val directory = payload.optString("directory", "")
                val pattern = payload.optString("pattern", "")
                val include = payload.optString("include", "").takeIf { it.isNotBlank() }
                val limit = payload.optInt("limit", 80)
                val matches = workspaceManager.fsGrep(directory, pattern, include, limit)
                JSONObject().put("matches", matches)
            }

            "execShell" -> {
                val directory = payload.optString("directory", "")
                val command = payload.optString("command", "")
                val timeoutMs = payload.optLong("timeoutMs", 30000L)
                val dirFile = workspaceManager.resolveDirectoryOrDefault(directory)
                shellExecutor.execute(dirFile, command, timeoutMs)
            }

            "httpRequest" -> {
                executeHttpRequest(payload)
            }

            "loadState" -> {
                val key = payload.optString("key", "default")
                val v = loadState(key)
                val out = JSONObject()
                if (v == null) out.put("value", JSONObject.NULL) else out.put("value", v)
                out
            }

            "saveState" -> {
                val key = payload.optString("key", "default")
                val value = payload.optString("value", "")
                saveState(key, value)
                JSONObject().put("ok", true)
            }

            else -> {
                JSONObject().put("__error", "Unknown native RPC action: $action")
            }
        }
    }

    private fun executeHttpRequest(payload: JSONObject): JSONObject {
        val urlStr = payload.optString("url", "")
        val method = payload.optString("method", "GET").uppercase()
        val headersObj = payload.optJSONObject("headers")
        val bodyStr = if (payload.has("body") && !payload.isNull("body")) payload.optString("body", "") else null

        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 25000
                readTimeout = 120000
                instanceFollowRedirects = true
                if (headersObj != null) {
                    val keys = headersObj.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        setRequestProperty(k, headersObj.optString(k, ""))
                    }
                }
                if (bodyStr != null && method != "GET" && method != "HEAD") {
                    doOutput = true
                    val bytes = bodyStr.toByteArray(Charsets.UTF_8)
                    outputStream.use { os ->
                        os.write(bytes)
                        os.flush()
                    }
                }
            }

            val code = conn.responseCode
            val contentType = conn.contentType ?: "application/json; charset=utf-8"
            val stream = try {
                if (code in 200..399) conn.inputStream else (conn.errorStream ?: conn.inputStream)
            } catch (_: Throwable) {
                conn.errorStream
            }

            val bodyText = if (stream != null) {
                BufferedInputStream(stream).use { bis ->
                    val baos = ByteArrayOutputStream()
                    val buf = ByteArray(8192)
                    var n = bis.read(buf)
                    while (n != -1) {
                        baos.write(buf, 0, n)
                        n = bis.read(buf)
                    }
                    baos.toString("UTF-8")
                }
            } else {
                ""
            }

            JSONObject()
                .put("status", code)
                .put("contentType", contentType)
                .put("body", bodyText)
        } catch (t: Throwable) {
            JSONObject()
                .put("status", 502)
                .put("contentType", "application/json")
                .put("body", JSONObject().put("error", t.message ?: "Network error").toString())
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Throwable) {
            }
        }
    }
}
