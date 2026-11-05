package ai.opencode.android

import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL

class LocalHttpDaemon(private val runtime: OpenCodeRuntime) {

    @Volatile
    var port: Int = 0
        private set

    @Volatile
    private var running = false

    private var serverSocket: ServerSocket? = null

    @Synchronized
    fun startBlockingOnWorker() {
        if (running && port > 0) return
        running = true
        val sock = try {
            ServerSocket(4096, 64, InetAddress.getByName("127.0.0.1"))
        } catch (_: Throwable) {
            ServerSocket(0, 64, InetAddress.getByName("127.0.0.1"))
        }
        serverSocket = sock
        port = sock.localPort

        runtime.ioExecutor.execute {
            while (running) {
                val client = try {
                    sock.accept()
                } catch (_: Throwable) {
                    break
                }
                runtime.ioExecutor.execute {
                    handleClient(client)
                }
            }
        }
    }

    fun stop() {
        running = false
        port = 0
        try {
            serverSocket?.close()
        } catch (_: Throwable) {
        }
        serverSocket = null
    }

    private fun readHeaderLine(ins: InputStream): String? {
        val baos = ByteArrayOutputStream(128)
        var prev = -1
        while (true) {
            val b = ins.read()
            if (b == -1) {
                return if (baos.size() == 0) null else baos.toString("UTF-8").trimEnd('\r')
            }
            if (b == '\n'.code) {
                val arr = baos.toByteArray()
                val end = if (prev == '\r'.code && arr.isNotEmpty()) arr.size - 1 else arr.size
                return String(arr, 0, end, Charsets.UTF_8)
            }
            baos.write(b)
            prev = b
            if (baos.size() > 16384) {
                return baos.toString("UTF-8")
            }
        }
    }

    private fun readExactBytes(ins: InputStream, count: Int): ByteArray {
        if (count <= 0) return ByteArray(0)
        val out = ByteArray(count)
        var readTotal = 0
        while (readTotal < count) {
            val n = ins.read(out, readTotal, count - readTotal)
            if (n <= 0) break
            readTotal += n
        }
        return if (readTotal == count) out else out.copyOf(readTotal)
    }

    private fun writeJsonResponse(out: OutputStream, status: Int, statusText: String, jsonBody: String) {
        val bytes = jsonBody.toByteArray(Charsets.UTF_8)
        val header = buildString {
            append("HTTP/1.1 ").append(status).append(' ').append(statusText).append("\r\n")
            append("Content-Type: application/json; charset=utf-8\r\n")
            append("Content-Length: ").append(bytes.size).append("\r\n")
            append("Access-Control-Allow-Origin: *\r\n")
            append("Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS\r\n")
            append("Access-Control-Allow-Headers: *\r\n")
            append("Access-Control-Expose-Headers: x-upstream-status, x-upstream-content-type\r\n")
            append("Connection: close\r\n\r\n")
        }
        out.write(header.toByteArray(Charsets.UTF_8))
        out.write(bytes)
        out.flush()
    }

    private fun handleClient(socket: Socket) {
        try {
            socket.soTimeout = 180000
            val ins = socket.getInputStream()
            val out = BufferedOutputStream(socket.getOutputStream())

            val reqLine = readHeaderLine(ins) ?: return
            val parts = reqLine.split(' ')
            if (parts.size < 2) return
            val method = parts[0].uppercase()
            val rawPath = parts[1]
            val pathOnly = rawPath.substringBefore('?')

            var contentLength = 0
            while (true) {
                val hLine = readHeaderLine(ins) ?: break
                if (hLine.isEmpty()) break
                val colon = hLine.indexOf(':')
                if (colon > 0) {
                    val key = hLine.substring(0, colon).trim().lowercase()
                    val value = hLine.substring(colon + 1).trim()
                    if (key == "content-length") {
                        contentLength = value.toIntOrNull() ?: 0
                    }
                }
            }

            if (method == "OPTIONS") {
                val hdr = buildString {
                    append("HTTP/1.1 204 No Content\r\n")
                    append("Access-Control-Allow-Origin: *\r\n")
                    append("Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS\r\n")
                    append("Access-Control-Allow-Headers: *\r\n")
                    append("Access-Control-Expose-Headers: x-upstream-status, x-upstream-content-type\r\n")
                    append("Content-Length: 0\r\n")
                    append("Connection: close\r\n\r\n")
                }
                out.write(hdr.toByteArray(Charsets.UTF_8))
                out.flush()
                return
            }

            val bodyBytes = readExactBytes(ins, contentLength.coerceIn(0, 32 * 1024 * 1024))
            val bodyStr = String(bodyBytes, Charsets.UTF_8)

            when {
                method == "GET" && (pathOnly == "/health" || pathOnly == "/api/global/health") -> {
                    writeJsonResponse(out, 200, "OK", "{\"healthy\":true,\"version\":\"2.2.5\"}")
                }

                method == "POST" && pathOnly == "/__native/rpc" -> {
                    val resultJson = runtime.dispatchRpcJson(bodyStr)
                    writeJsonResponse(out, 200, "OK", resultJson)
                }

                method == "POST" && pathOnly == "/__native/http-proxy" -> {
                    handleStreamingHttpProxy(bodyStr, out)
                }

                else -> {
                    writeJsonResponse(out, 404, "Not Found", "{\"__error\":\"Route not found: $pathOnly\"}")
                }
            }
        } catch (_: Throwable) {
        } finally {
            try {
                socket.close()
            } catch (_: Throwable) {
            }
        }
    }

    private fun handleStreamingHttpProxy(bodyStr: String, out: OutputStream) {
        var conn: HttpURLConnection? = null
        val isCompletion = bodyStr.contains("/chat/completions") || bodyStr.contains("/v1/messages")
        if (isCompletion) {
            try {
                runtime.statusListener?.invoke("Выполняется запрос к модели ИИ…", true)
            } catch (_: Throwable) {
            }
        }

        try {
            val req = JSONObject(bodyStr)
            val targetUrl = req.optString("url", "")
            val targetMethod = req.optString("method", "GET").uppercase()
            val headersObj = req.optJSONObject("headers")
            val payloadBody = if (req.has("body") && !req.isNull("body")) req.optString("body", "") else null

            conn = (URL(targetUrl).openConnection() as HttpURLConnection).apply {
                requestMethod = targetMethod
                connectTimeout = 25000
                readTimeout = 180000
                instanceFollowRedirects = true
                if (headersObj != null) {
                    val keys = headersObj.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        setRequestProperty(k, headersObj.optString(k, ""))
                    }
                }
                if (payloadBody != null && targetMethod != "GET" && targetMethod != "HEAD") {
                    doOutput = true
                    val outBytes = payloadBody.toByteArray(Charsets.UTF_8)
                    outputStream.use { os ->
                        os.write(outBytes)
                        os.flush()
                    }
                }
            }

            val upstreamCode = conn.responseCode
            val upstreamType = (conn.contentType ?: "application/json; charset=utf-8")
                .replace("\r", "")
                .replace("\n", "")

            val respHeader = buildString {
                append("HTTP/1.1 200 OK\r\n")
                append("Content-Type: ").append(upstreamType).append("\r\n")
                append("x-upstream-status: ").append(upstreamCode).append("\r\n")
                append("x-upstream-content-type: ").append(upstreamType).append("\r\n")
                append("Access-Control-Allow-Origin: *\r\n")
                append("Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS\r\n")
                append("Access-Control-Allow-Headers: *\r\n")
                append("Access-Control-Expose-Headers: x-upstream-status, x-upstream-content-type\r\n")
                append("Cache-Control: no-cache\r\n")
                append("Connection: close\r\n\r\n")
            }
            out.write(respHeader.toByteArray(Charsets.UTF_8))
            out.flush()

            val upstreamStream = try {
                if (upstreamCode in 200..399) conn.inputStream else (conn.errorStream ?: conn.inputStream)
            } catch (_: Throwable) {
                conn.errorStream
            }

            if (upstreamStream != null) {
                upstreamStream.use { stream ->
                    val buf = ByteArray(4096)
                    var n = stream.read(buf)
                    while (n != -1) {
                        out.write(buf, 0, n)
                        out.flush()
                        n = stream.read(buf)
                    }
                }
            }
        } catch (t: Throwable) {
            val errJson = JSONObject().put("error", JSONObject().put("message", t.message ?: "Upstream connection failed")).toString()
            try {
                writeJsonResponse(out, 502, "Bad Gateway", errJson)
            } catch (_: Throwable) {
            }
        } finally {
            if (isCompletion) {
                try {
                    runtime.statusListener?.invoke("Фоновый сервис активен • Локальная среда готова", false)
                } catch (_: Throwable) {
                }
            }
            try {
                conn?.disconnect()
            } catch (_: Throwable) {
            }
        }
    }
}
