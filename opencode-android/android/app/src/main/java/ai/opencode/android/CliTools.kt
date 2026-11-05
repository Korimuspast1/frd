package ai.opencode.android

import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.io.SequenceInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.Deflater
import java.util.zip.Inflater
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/**
 * Portable CLI toolchain for OpenCode Android.
 *
 * Runs inside a standalone `dalvikvm` JVM started from executable shims in `$HOME/usr/bin`, so every
 * workspace directory (internal app storage, /storage/emulated/0, /sdcard, Termux, noexec FUSE
 * mounts, ...) gets working `curl`, `wget`, `git`, `jq`, `zip`, `unzip`, `tree`, `python3`,
 * `node`, `npm`, `which` and `env` without requiring Termux, root or a writable+exec partition.
 */
object CliTools {

    private const val VERSION = "2.2.5"

    private fun out(line: String = "") {
        System.out.print(line + "\n")
    }

    private fun err(line: String) {
        System.err.print(line + "\n")
    }

    @JvmStatic
    fun main(args: Array<String>) {
        var code = 0
        try {
            if (args.isEmpty()) {
                err("usage: CliTools <tool> [args...]")
                code = 2
            } else {
                code = dispatch(args[0], args.drop(1))
            }
        } catch (t: Throwable) {
            err("${args.getOrNull(0) ?: "tool"}: ${t.message ?: t.javaClass.simpleName}")
            code = 1
        } finally {
            try {
                System.out.flush()
                System.err.flush()
            } catch (_: Throwable) {
            }
        }
        try {
            System.exit(code)
        } catch (_: Throwable) {
        }
    }

    private fun dispatch(tool: String, a: List<String>): Int = when (tool) {
        "curl" -> curl(a)
        "wget" -> wget(a)
        "jq" -> jq(a)
        "zip" -> zipCommand(a)
        "unzip" -> unzipCommand(a)
        "tree" -> tree(a)
        "git" -> git(a)
        "python3", "python" -> python(a)
        "node" -> node(a)
        "npm" -> npm(a)
        "which", "command" -> which(a)
        "env", "printenv" -> {
            System.getenv().toSortedMap().forEach { (k, v) -> out("$k=$v") }
            0
        }
        "basename" -> {
            if (a.isEmpty()) return 1
            out(File(a[0].trimEnd('/')).name.ifEmpty { "/" })
            0
        }
        "dirname" -> {
            if (a.isEmpty()) return 1
            out(File(a[0]).parent ?: ".")
            0
        }
        "sleep" -> {
            val seconds = a.firstOrNull()?.toDoubleOrNull() ?: 0.0
            Thread.sleep((seconds * 1000).toLong().coerceIn(0, 300000))
            0
        }
        else -> {
            err("$tool: not supported by the portable OpenCode toolchain")
            127
        }
    }

    // ───────────────────────────── helpers ─────────────────────────────

    private fun cwd(): File {
        val props = System.getProperty("user.dir")
        val env = System.getenv("PWD") ?: System.getenv("OPENCODE_CWD")
        val candidate = when {
            !env.isNullOrBlank() && File(env).isDirectory -> File(env)
            !props.isNullOrBlank() && File(props).isDirectory -> File(props)
            else -> File(System.getenv("HOME") ?: "/")
        }
        return candidate.absoluteFile
    }

    private fun homeDir(): File = File(System.getenv("HOME") ?: "/data/local/tmp")

    private fun envBookkeeping(prefix: String) {
        // no-op: environment is provided by the shim / ShellExecutor
    }

    private fun readAll(input: InputStream, sink: OutputStream, limit: Long = 64L * 1024 * 1024): Long {
        val buf = ByteArray(16384)
        var total = 0L
        while (true) {
            val n = input.read(buf)
            if (n <= 0) break
            sink.write(buf, 0, n)
            total += n
            if (total > limit) break
        }
        sink.flush()
        return total
    }

    private fun expandPath(raw: String): File {
        var p = raw
        if (p == "~") p = homeDir().absolutePath
        else if (p.startsWith("~/")) p = homeDir().absolutePath + p.substring(1)
        val f = File(p)
        return if (f.isAbsolute) f else File(cwd(), p)
    }

    private fun httpFetch(
        url: String,
        method: String,
        headers: List<Pair<String, String>>,
        body: ByteArray?,
        timeoutMs: Int,
        followRedirects: Boolean,
    ): HttpURLConnection {
        val conn = (URL(url).openConnection() as HttpURLConnection)
        conn.requestMethod = method
        conn.connectTimeout = timeoutMs.coerceIn(1000, 300000)
        conn.readTimeout = timeoutMs.coerceIn(1000, 300000)
        conn.instanceFollowRedirects = followRedirects
        conn.useCaches = false
        conn.setRequestProperty("Connection", "close")
        conn.setRequestProperty("Accept-Encoding", "identity")
        if (conn.getRequestProperty("User-Agent") == null) {
            conn.setRequestProperty("User-Agent", "curl/8.5.0 (opencode-android $VERSION)")
        }
        for ((k, v) in headers) conn.setRequestProperty(k, v)
        if (body != null && method != "GET" && method != "HEAD") {
            conn.doOutput = true
            conn.setFixedLengthStreamingMode(body.size)
            conn.outputStream.use { os -> os.write(body); os.flush() }
        }
        return conn
    }

    // ───────────────────────────── curl ─────────────────────────────

    private fun curl(a: List<String>): Int {
        var method: String? = null
        var explicitMethod = false
        var silent = false
        var showError = false
        var includeHeaders = false
        var headRequest = false
        var failOnError = false
        var followRedirects = true
        var outputTo: String? = null
        var timeoutMs = 60000
        val headers = ArrayList<Pair<String, String>>()
        val data = StringBuilder()
        var hasData = false
        var url: String? = null
        var i = 0

        fun next(): String? {
            i++
            return a.getOrNull(i)
        }

        while (i < a.size) {
            val arg = a[i]
            when {
                arg == "-s" || arg == "--silent" -> silent = true
                arg == "-S" || arg == "--show-error" -> showError = true
                arg == "-f" || arg == "--fail" -> failOnError = true
                arg == "-L" || arg == "--location" -> followRedirects = true
                arg == "-i" || arg == "--include" -> includeHeaders = true
                arg == "-I" || arg == "--head" -> headRequest = true
                arg == "-k" || arg == "--insecure" -> Unit
                arg == "--compressed" -> Unit
                arg == "-g" -> Unit
                arg == "--http1.1" -> Unit
                arg == "-X" || arg == "--request" -> {
                    method = next()?.uppercase()
                    explicitMethod = true
                }

                arg.startsWith("--request=") -> {
                    method = arg.substringAfter('=').uppercase()
                    explicitMethod = true
                }

                arg == "-H" || arg == "--header" -> {
                    val h = next() ?: continue
                    val idx = h.indexOf(':')
                    if (idx > 0) headers.add(h.substring(0, idx).trim() to h.substring(idx + 1).trim())
                }

                arg.startsWith("-H") && arg.length > 2 -> {
                    val h = arg.substring(2)
                    val idx = h.indexOf(':')
                    if (idx > 0) headers.add(h.substring(0, idx).trim() to h.substring(idx + 1).trim())
                }

                arg == "-d" || arg == "--data" || arg == "--data-raw" || arg == "--data-binary" || arg == "--data-ascii" -> {
                    val v = next() ?: ""
                    if (data.isNotEmpty()) data.append('&')
                    data.append(v)
                    hasData = true
                }

                arg.startsWith("--data=") || arg.startsWith("--data-raw=") || arg.startsWith("--data-binary=") -> {
                    if (data.isNotEmpty()) data.append('&')
                    data.append(arg.substringAfter('='))
                    hasData = true
                }

                arg == "--json" -> {
                    val v = next() ?: ""
                    data.append(v)
                    hasData = true
                    headers.add("Content-Type" to "application/json")
                    headers.add("Accept" to "application/json")
                }

                arg.startsWith("--json=") -> {
                    data.append(arg.substringAfter('='))
                    hasData = true
                    headers.add("Content-Type" to "application/json")
                }

                arg == "-o" || arg == "--output" -> outputTo = next()
                arg.startsWith("--output=") -> outputTo = arg.substringAfter('=')
                arg == "-O" || arg == "--remote-name" -> outputTo = ""
                arg == "-u" || arg == "--user" -> {
                    val v = next() ?: ""
                    headers.add("Authorization" to "Basic " + Base64.encodeToString(v.toByteArray(), Base64.NO_WRAP))
                }

                arg == "-A" || arg == "--user-agent" -> {
                    val v = next() ?: ""
                    headers.add("User-Agent" to v)
                }

                arg == "-e" || arg == "--referer" -> {
                    val v = next() ?: ""
                    headers.add("Referer" to v)
                }

                arg == "-b" || arg == "--cookie" -> {
                    val v = next() ?: ""
                    headers.add("Cookie" to v)
                }

                arg == "-m" || arg == "--max-time" -> timeoutMs = ((next()?.toDoubleOrNull() ?: 60.0) * 1000).toInt()
                arg == "-w" || arg == "--write-out" || arg == "--retry" || arg == "--retry-delay"
                    || arg == "--connect-timeout" || arg == "--cacert" || arg == "--cert" -> next()
                arg == "--" -> {
                    i++
                    while (i < a.size) {
                        url = a[i]
                        i++
                    }
                    break
                }

                arg.startsWith("-") && arg.length > 1 -> Unit
                else -> url = arg
            }
            i++
        }

        if (url.isNullOrBlank()) {
            err("curl: no URL specified")
            return 2
        }
        val finalUrl = if (url!!.startsWith("http://") || url!!.startsWith("https://")) url!! else "https://" + url
        val finalMethod = method ?: when {
            headRequest -> "HEAD"
            hasData -> "POST"
            else -> "GET"
        }
        if (hasData && !explicitMethod) headers.add("Content-Type" to "application/x-www-form-urlencoded")

        var conn: HttpURLConnection? = null
        return try {
            conn = httpFetch(
                finalUrl,
                finalMethod,
                headers,
                if (hasData) data.toString().toByteArray(Charsets.UTF_8) else null,
                timeoutMs,
                followRedirects,
            )
            val code = conn.responseCode
            val sink: OutputStream = when {
                outputTo == null -> System.out
                outputTo == "-" -> System.out
                outputTo == "" -> {
                    val name = finalUrl.substringAfterLast('/').substringBefore('?').ifBlank { "index.html" }
                    FileOutputStream(File(cwd(), name))
                }

                else -> {
                    val f = expandPath(outputTo!!)
                    f.parentFile?.mkdirs()
                    FileOutputStream(f)
                }
            }
            if (includeHeaders || headRequest) {
                val sb = StringBuilder()
                sb.append("HTTP/1.1 ").append(code).append(' ').append(conn.responseMessage ?: "").append('\n')
                conn.headerFields.forEach { (k, v) ->
                    if (k != null && v.isNotEmpty()) sb.append(k).append(": ").append(v.joinToString(", ")).append('\n')
                }
                sb.append('\n')
                sink.write(sb.toString().toByteArray())
            }
            if (!headRequest) {
                val stream = try {
                    if (code in 200..399) conn.inputStream else (conn.errorStream ?: conn.inputStream)
                } catch (_: Throwable) {
                    conn.errorStream
                }
                if (stream != null) {
                    BufferedInputStream(stream).use { readAll(it, sink) }
                }
            }
            sink.flush()
            if (sink !== System.out) try { sink.close() } catch (_: Throwable) {}
            if (failOnError && code >= 400) 22 else 0
        } catch (t: Throwable) {
            if (!silent || showError) err("curl: ${t.message ?: t.javaClass.simpleName}")
            7
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Throwable) {
            }
        }
    }

    // ───────────────────────────── wget ─────────────────────────────

    private fun wget(a: List<String>): Int {
        var output: String? = null
        var quiet = false
        var url: String? = null
        var timeoutMs = 60000
        var i = 0
        while (i < a.size) {
            val arg = a[i]
            when {
                arg == "-q" || arg == "--quiet" -> quiet = true
                arg == "-O" || arg == "--output-document" -> {
                    i++
                    output = a.getOrNull(i)
                }

                arg.startsWith("--output-document=") -> output = arg.substringAfter('=')
                arg.startsWith("-O") && arg.length > 2 -> output = arg.substring(2)
                arg == "-T" || arg == "--timeout" -> {
                    i++
                    timeoutMs = ((a.getOrNull(i)?.toDoubleOrNull() ?: 60.0) * 1000).toInt()
                }

                arg == "-U" || arg == "--user-agent" || arg == "--header" -> {
                    i++
                }

                arg == "--no-check-certificate" -> Unit
                arg.startsWith("-") -> Unit
                else -> url = arg
            }
            i++
        }
        if (url.isNullOrBlank()) {
            err("wget: missing URL")
            return 1
        }
        val target = if (url!!.startsWith("http")) url!! else "https://" + url!!
        var conn: HttpURLConnection? = null
        return try {
            conn = httpFetch(target, "GET", emptyList(), null, timeoutMs, true)
            val code = conn.responseCode
            if (code >= 400) {
                if (!quiet) err("wget: server returned HTTP $code ${conn.responseMessage ?: ""}")
                return 8
            }
            val name = if (output == null) target.substringAfterLast('/').substringBefore('?').ifBlank { "index.html" } else output!!
            if (name == "-") {
                BufferedInputStream(conn.inputStream).use { readAll(it, System.out) }
            } else {
                val f = expandPath(name)
                f.parentFile?.mkdirs()
                if (!quiet) {
                    err("--  $target")
                    err("Saving to: '${f.absolutePath}'")
                }
                BufferedOutputStream(FileOutputStream(f)).use { bos ->
                    BufferedInputStream(conn.inputStream).use { readAll(it, bos) }
                }
                if (!quiet) err("'${f.name}' saved")
            }
            0
        } catch (t: Throwable) {
            if (!quiet) err("wget: ${t.message ?: t.javaClass.simpleName}")
            4
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Throwable) {
            }
        }
    }

    // ───────────────────────────── jq ─────────────────────────────

    private fun jq(a: List<String>): Int {
        var raw = false
        var compact = false
        var exitNull = false
        var filter: String? = null
        val files = ArrayList<String>()
        for (arg in a) {
            when {
                arg == "-r" || arg == "--raw-output" -> raw = true
                arg == "-c" || arg == "--compact-output" -> compact = true
                arg == "-e" || arg == "--exit-status" -> exitNull = true
                arg == "-M" || arg == "--monochrome-output" || arg == "-C" -> Unit
                arg.startsWith("-") && arg.length > 1 -> Unit
                filter == null -> filter = arg
                else -> files.add(arg)
            }
        }
        val rawInput = if (files.isEmpty()) {
            readAllToString(System.`in`)
        } else {
            try {
                File(expandPath(files[0]).absolutePath).readText(Charsets.UTF_8)
            } catch (t: Throwable) {
                err("jq: error: Could not open ${files[0]}: ${t.message}")
                return 2
            }
        }
        val parsed: List<Any?> = try {
            parseJsonDocument(rawInput)
        } catch (t: Throwable) {
            err("jq: parse error: ${t.message ?: "invalid JSON"}")
            return 4
        }
        val results = ArrayList<Any?>()
        try {
            for (doc in parsed) {
                results.addAll(evaluateJqFilter(filter ?: ".", doc))
            }
        } catch (t: Throwable) {
            err("jq: error: ${t.message ?: "invalid filter"}")
            return 5
        }
        if (results.isEmpty() && exitNull) return 1
        if (results.size == 1) {
            printJq(results[0], raw, compact)
        } else {
            for (r in results) printJq(r, raw, compact)
        }
        return 0
    }

    private fun readAllToString(input: InputStream): String {
        val baos = ByteArrayOutputStream()
        readAll(input, baos)
        return baos.toString("UTF-8")
    }

    /** Self-contained JSON parser — no dependency on org.json, so it also runs on plain JVMs. */
    private class JsonParser(private val text: String) {
        private var pos = 0

        fun parseDocuments(): List<Any?> {
            val docs = ArrayList<Any?>()
            skipWs()
            while (pos < text.length) {
                docs.add(parseValue())
                skipWs()
            }
            if (docs.isEmpty()) docs.add(null)
            return docs
        }

        private fun skipWs() {
            while (pos < text.length && text[pos].isWhitespace()) pos++
        }

        private fun fail(message: String): Nothing = throw IllegalArgumentException(message)

        fun parseValue(): Any? {
            skipWs()
            if (pos >= text.length) fail("Unexpected end of JSON input")
            return when (val ch = text[pos]) {
                '{' -> parseObject()
                '[' -> parseArray()
                '"' -> parseString()
                't' -> {
                    expect("true"); true
                }

                'f' -> {
                    expect("false"); false
                }

                'n' -> {
                    expect("null"); null
                }

                else -> {
                    if (ch == '-' || ch.isDigit()) parseNumber() else fail("Unexpected character '$ch' at $pos")
                }
            }
        }

        private fun expect(word: String) {
            if (!text.startsWith(word, pos)) fail("Expected $word at $pos")
            pos += word.length
        }

        private fun parseObject(): Map<String, Any?> {
            pos++ // {
            val map = LinkedHashMap<String, Any?>()
            skipWs()
            if (pos < text.length && text[pos] == '}') {
                pos++
                return map
            }
            while (true) {
                skipWs()
                if (pos >= text.length || text[pos] != '"') fail("Expected object key at $pos")
                val key = parseString()
                skipWs()
                if (pos >= text.length || text[pos] != ':') fail("Expected ':' at $pos")
                pos++
                map[key] = parseValue()
                skipWs()
                if (pos >= text.length) fail("Unterminated object")
                when (text[pos]) {
                    ',' -> pos++
                    '}' -> {
                        pos++
                        return map
                    }

                    else -> fail("Expected ',' or '}' at $pos")
                }
            }
        }

        private fun parseArray(): List<Any?> {
            pos++ // [
            val list = ArrayList<Any?>()
            skipWs()
            if (pos < text.length && text[pos] == ']') {
                pos++
                return list
            }
            while (true) {
                list.add(parseValue())
                skipWs()
                if (pos >= text.length) fail("Unterminated array")
                when (text[pos]) {
                    ',' -> pos++
                    ']' -> {
                        pos++
                        return list
                    }

                    else -> fail("Expected ',' or ']' at $pos")
                }
            }
        }

        private fun parseString(): String {
            pos++ // opening quote
            val sb = StringBuilder()
            while (pos < text.length) {
                val ch = text[pos]
                when {
                    ch == '"' -> {
                        pos++
                        return sb.toString()
                    }

                    ch == '\\' -> {
                        pos++
                        if (pos >= text.length) fail("Bad escape")
                        when (val esc = text[pos]) {
                            '"' -> sb.append('"')
                            '\\' -> sb.append('\\')
                            '/' -> sb.append('/')
                            'b' -> sb.append('\b')
                            'f' -> sb.append('\u000C')
                            'n' -> sb.append('\n')
                            'r' -> sb.append('\r')
                            't' -> sb.append('\t')
                            'u' -> {
                                val hex = text.substring(pos + 1, minOf(pos + 5, text.length))
                                sb.append(hex.toInt(16).toChar())
                                pos += 4
                            }

                            else -> sb.append(esc)
                        }
                        pos++
                    }

                    else -> {
                        sb.append(ch)
                        pos++
                    }
                }
            }
            fail("Unterminated string")
        }

        private fun parseNumber(): Any {
            val startPos = pos
            if (pos < text.length && text[pos] == '-') pos++
            while (pos < text.length && (text[pos].isDigit() || text[pos] == '.' || text[pos] == 'e' || text[pos] == 'E' || text[pos] == '+' || text[pos] == '-')) pos++
            val raw = text.substring(startPos, pos)
            return raw.toDoubleOrNull() ?: fail("Invalid number '$raw'")
        }
    }

    private fun parseJsonDocument(text: String): List<Any?> = JsonParser(text.trim()).parseDocuments()

    private fun evaluateJqFilter(filter: String, doc: Any?): List<Any?> {
        // Accept jq object accessors with unquoted keys: `.items[].id` / `.["id"]` / `.id`
        val pipes = splitTopLevel(filter, '|')
        var current = listOf(doc)
        for (pipe in pipes) {
            val stage = pipe.trim()
            if (stage.isEmpty()) continue
            current = when {
                stage == "." -> current
                stage == "length" -> current.map { jqLength(it) }
                stage == "keys" -> current.map { jqKeys(it) }
                stage == "keys_unsorted" -> current.map { jqKeys(it) }
                stage == "tostring" -> current.map { jqToString(it) }
                stage == "tonumber" -> current.map { (it as? String)?.toDoubleOrNull() ?: it }
                stage == "type" -> current.map { jqType(it) }
                stage == "add" -> current.map { listOf(it) }
                stage == "empty" -> emptyList()
                stage == "not" -> current.map { it == null || it == false }
                stage.startsWith("select(") && stage.endsWith(")") -> {
                    val cond = stage.substring(7, stage.length - 1).trim()
                    current.filter { jqTruthy(evaluateJqFilter(cond, it).firstOrNull()) }
                }

                stage.startsWith("map(") && stage.endsWith(")") -> {
                    val inner = stage.substring(4, stage.length - 1)
                    current.map { v ->
                        val list = (v as? List<*>) ?: emptyList<Any?>()
                        list.flatMap { item -> evaluateJqFilter(inner, item) }
                    }
                }

                stage.startsWith("has(") && stage.endsWith(")") -> {
                    val key = stage.substring(4, stage.length - 1).trim().trim('"')
                    current.map { v ->
                        when (v) {
                            is Map<*, *> -> v.containsKey(key)
                            is List<*> -> key.toIntOrNull()?.let { it in v.indices } ?: false
                            else -> false
                        }
                    }
                }

                stage.startsWith("\"") && stage.endsWith("\"") -> current.map { stage.trim('"') }
                stage.toDoubleOrNull() != null -> current.map { stage.toDouble() }
                else -> current.flatMap { applyJqPath(it, stage) }
            }
        }
        return current
    }

    private fun splitTopLevel(input: String, sep: Char): List<String> {
        val parts = ArrayList<String>()
        var depth = 0
        var inString = false
        var escaped = false
        val sb = StringBuilder()
        for (ch in input) {
            if (inString) {
                sb.append(ch)
                if (escaped) escaped = false
                else if (ch == '\\') escaped = true
                else if (ch == '"') inString = false
                continue
            }
            when (ch) {
                '"' -> {
                    inString = true
                    sb.append(ch)
                }

                '(', '[', '{' -> {
                    depth++
                    sb.append(ch)
                }

                ')', ']', '}' -> {
                    depth--
                    sb.append(ch)
                }

                sep -> if (depth == 0) {
                    parts.add(sb.toString())
                    sb.setLength(0)
                } else sb.append(ch)

                else -> sb.append(ch)
            }
        }
        parts.add(sb.toString())
        return parts
    }

    /** Applies a jq path expression; `[]` expands a stream and every following segment maps over it. */
    private fun applyJqPath(value: Any?, path: String): List<Any?> {
        val p = path.removePrefix(".")
        if (p.isEmpty() || p == ".") return listOf(value)

        var current: List<Any?> = listOf(value)
        var idx = 0

        fun iter(v: Any?): List<Any?> = when (v) {
            is List<*> -> v
            is Map<*, *> -> v.values.toList()
            else -> emptyList()
        }

        fun step(items: List<Any?>, step: (Any?) -> List<Any?>): List<Any?> =
            items.flatMap { step(it) }

        while (idx < p.length) {
            when {
                p.startsWith("[]", idx) -> {
                    current = step(current) { iter(it) }
                    idx += 2
                    if (idx < p.length && p[idx] == '.') idx++
                }

                p.startsWith("[\"", idx) -> {
                    val close = p.indexOf("\"]", idx + 2)
                    if (close < 0) return current
                    val key = p.substring(idx + 2, close)
                    current = step(current) { (it as? Map<*, *>)?.get(key)?.let { v -> listOf(v) } ?: emptyList() }
                    idx = close + 2
                    if (idx < p.length && p[idx] == '.') idx++
                }

                p[idx] == '[' -> {
                    val close = p.indexOf(']', idx)
                    if (close < 0) return current
                    val inner = p.substring(idx + 1, close).trim()
                    current = if (inner.contains(':')) {
                        val range = inner.split(':')
                        val from = range.getOrNull(0)?.trim()?.toIntOrNull() ?: 0
                        val to = range.getOrNull(1)?.trim()?.toIntOrNull()
                        step(current) { v ->
                            val list = v as? List<*> ?: return@step emptyList()
                            val endIdx = (to ?: list.size).coerceIn(0, list.size)
                            val startIdx = from.coerceIn(0, endIdx)
                            listOf(list.subList(startIdx, endIdx).toList())
                        }
                    } else {
                        val n = inner.toIntOrNull() ?: 0
                        step(current) { v ->
                            val list = v as? List<*> ?: return@step emptyList()
                            val resolved = if (n < 0) list.size + n else n
                            if (resolved in list.indices) listOf(list[resolved]) else listOf(null)
                        }
                    }
                    idx = close + 1
                    if (idx < p.length && p[idx] == '.') idx++
                }

                else -> {
                    val nextDot = p.indexOf('.', idx)
                    val nextBracket = p.indexOf('[', idx)
                    val endIdx = listOf(nextDot, nextBracket).filter { it >= 0 }.minOrNull() ?: p.length
                    val key = p.substring(idx, endIdx)
                    if (key.isEmpty()) {
                        idx = endIdx + 1
                        continue
                    }
                    current = step(current) { v ->
                        when (v) {
                            is Map<*, *> -> listOf(v[key])
                            is List<*> -> key.toIntOrNull()?.let { if (it in v.indices) listOf(v[it]) else listOf(null) }
                                ?: emptyList()
                            else -> listOf(null)
                        }
                    }
                    idx = endIdx
                    if (idx < p.length && p[idx] == '.') idx++
                }
            }
        }
        return current
    }

    private fun jqTruthy(v: Any?): Boolean = !(v == null || v == false)

    private fun jqLength(v: Any?): Any? = when (v) {
        is String -> v.length
        is List<*> -> v.size
        is Map<*, *> -> v.size
        is Number -> v
        else -> 0
    }

    private fun jqKeys(v: Any?): Any? = when (v) {
        is Map<*, *> -> v.keys.map { it.toString() }.sorted()
        is List<*> -> v.indices.toList()
        else -> null
    }

    private fun jqType(v: Any?): String = when (v) {
        null -> "null"
        is Boolean -> "boolean"
        is Number -> "number"
        is String -> "string"
        is List<*> -> "array"
        is Map<*, *> -> "object"
        else -> "unknown"
    }

    private fun jqToString(v: Any?): String = when (v) {
        null -> "null"
        is String -> v
        is Boolean, is Number -> v.toString()
        else -> encodeJson(v, false)
    }

    private fun printJq(value: Any?, raw: Boolean, compact: Boolean) {
        if (raw && value is String) {
            out(value)
        } else {
            out(encodeJson(value, compact))
        }
    }

    private fun encodeJson(value: Any?, compact: Boolean): String {
        val indent = if (compact) null else "  "
        return buildJson(value, indent, 0)
    }

    private fun buildJson(value: Any?, indent: String?, depth: Int): String {
        fun pad(d: Int) = if (indent == null) "" else "\n" + indent.repeat(d)
        fun sep() = if (indent == null) ":" else ": "
        return when (value) {
            null -> "null"
            is Boolean -> value.toString()
            is Number -> {
                val d = value.toDouble()
                if (d == Math.floor(d) && !d.isInfinite() && Math.abs(d) < 1e15) d.toLong().toString() else d.toString()
            }

            is String -> quoteJson(value)
            is List<*> -> {
                if (value.isEmpty()) "[]"
                else value.joinToString("," + pad(depth + 1), "[" + pad(depth + 1), pad(depth) + "]") {
                    buildJson(it, indent, depth + 1)
                }
            }

            is Map<*, *> -> {
                if (value.isEmpty()) "{}"
                else value.entries.joinToString("," + pad(depth + 1), "{" + pad(depth + 1), pad(depth) + "}") {
                    quoteJson(it.key.toString()) + sep() + buildJson(it.value, indent, depth + 1)
                }
            }

            JSONObject.NULL -> "null"
            else -> quoteJson(value.toString())
        }
    }

    private fun quoteJson(s: String): String {
        val sb = StringBuilder("\"")
        for (ch in s) {
            when (ch) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> if (ch < ' ') sb.append(String.format("\\u%04x", ch.code)) else sb.append(ch)
            }
        }
        return sb.append('"').toString()
    }

    // ───────────────────────────── zip / unzip ─────────────────────────────

    private fun zipCommand(a: List<String>): Int {
        var recursive = false
        var quiet = false
        val positional = ArrayList<String>()
        for (arg in a) {
            when {
                arg == "-r" || arg == "-R" -> recursive = true
                arg == "-q" -> quiet = true
                arg.startsWith("-") -> Unit
                else -> positional.add(arg)
            }
        }
        if (positional.size < 2) {
            err("zip: usage: zip [-r] archive.zip file-or-dir...")
            return 2
        }
        val archiveArg = positional[0]
        val archive = if (archiveArg.endsWith(".zip")) expandPath(archiveArg) else expandPath("$archiveArg.zip")
        archive.parentFile?.mkdirs()
        var count = 0
        try {
            ZipOutputStream(BufferedOutputStream(FileOutputStream(archive))).use { zos ->
                val added = HashSet<String>()

                fun addFile(file: File, name: String) {
                    if (!added.add(name)) return
                    zos.putNextEntry(ZipEntry(name))
                    FileInputStream(file).use { fis -> fis.copyTo(zos) }
                    zos.closeEntry()
                    count++
                }

                fun addDir(dir: File, prefix: String) {
                    val children = dir.listFiles() ?: return
                    for (child in children.sortedBy { it.name }) {
                        val name = if (prefix.isEmpty()) child.name else "$prefix/${child.name}"
                        if (child.isDirectory) {
                            if (recursive) addDir(child, name)
                        } else {
                            addFile(child, name)
                        }
                    }
                }

                for (idx in 1 until positional.size) {
                    val src = expandPath(positional[idx])
                    if (!src.exists()) {
                        err("zip: ${positional[idx]}: No such file or directory")
                        continue
                    }
                    if (src.isDirectory) {
                        if (!recursive) {
                            err("zip: ${positional[idx]} is a directory (use -r)")
                            continue
                        }
                        addDir(src, src.name)
                    } else {
                        addFile(src, src.name)
                    }
                }
            }
            if (!quiet) out("  adding: $count file(s) -> ${archive.absolutePath}")
            return 0
        } catch (t: Throwable) {
            err("zip: ${t.message ?: t.javaClass.simpleName}")
            return 1
        }
    }

    private fun unzipCommand(a: List<String>): Int {
        var listOnly = false
        var quiet = false
        var overwrite = false
        var dest: String? = null
        val positional = ArrayList<String>()
        var i = 0
        while (i < a.size) {
            val arg = a[i]
            when {
                arg == "-l" -> listOnly = true
                arg == "-q" -> quiet = true
                arg == "-o" -> overwrite = true
                arg == "-d" -> {
                    i++
                    dest = a.getOrNull(i)
                }

                arg.startsWith("-") -> Unit
                else -> positional.add(arg)
            }
            i++
        }
        if (positional.isEmpty()) {
            err("unzip: usage: unzip [-o] [-d dir] archive.zip")
            return 2
        }
        val archive = expandPath(positional[0])
        if (!archive.isFile) {
            err("unzip: cannot find or open ${positional[0]}")
            return 9
        }
        val targetDir = dest?.let { expandPath(it) } ?: cwd()
        return try {
            ZipInputStream(BufferedInputStream(FileInputStream(archive))).use { zis ->
                var entry: ZipEntry? = zis.nextEntry
                var extracted = 0
                while (entry != null) {
                    val name = entry.name
                    if (listOnly) {
                        out(String.format(Locale.US, "%10d  %s", entry.size, name))
                    } else {
                        val file = File(targetDir, name)
                        val canonical = file.canonicalFile
                        if (!canonical.path.startsWith(targetDir.canonicalFile.path)) {
                            err("unzip: skipping unsafe path $name")
                        } else if (entry.isDirectory) {
                            canonical.mkdirs()
                        } else {
                            canonical.parentFile?.mkdirs()
                            if (canonical.exists() && !overwrite) {
                                if (!quiet) err("unzip: ${canonical.name} already exists (use -o)")
                            } else {
                                BufferedOutputStream(FileOutputStream(canonical)).use { bos -> zis.copyTo(bos) }
                                extracted++
                            }
                        }
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
                if (!quiet) {
                    if (listOnly) out("${archive.name}") else out("Extracted $extracted file(s) into ${targetDir.absolutePath}")
                }
            }
            0
        } catch (t: Throwable) {
            err("unzip: ${t.message ?: t.javaClass.simpleName}")
            1
        }
    }

    // ───────────────────────────── tree ─────────────────────────────

    private fun tree(a: List<String>): Int {
        var showHidden = false
        var maxDepth = 6
        var root: File? = null
        var i = 0
        while (i < a.size) {
            val arg = a[i]
            when {
                arg == "-a" -> showHidden = true
                arg == "-L" -> {
                    i++
                    maxDepth = a.getOrNull(i)?.toIntOrNull() ?: maxDepth
                }

                arg.startsWith("-") -> Unit
                else -> root = expandPath(arg)
            }
            i++
        }
        val base = root ?: cwd()
        if (!base.exists()) {
            err("tree: ${base.path}: No such file or directory")
            return 1
        }
        var dirs = 0
        var files = 0
        val encoding = (System.getProperty("sun.jnu.encoding") ?: System.getProperty("file.encoding") ?: "UTF-8").lowercase()
        val explicitAscii = System.getProperty("opencode.ascii") == "1" || System.getenv("OPENCODE_ASCII") == "1"
        val ascii = explicitAscii || encoding.contains("ascii") || encoding.contains("646") || encoding.contains("iso-8859")
        val tee = if (ascii) "|-- " else "├── "
        val ell = if (ascii) "`-- " else "└── "
        val vert = if (ascii) "|   " else "│   "
        out(base.absolutePath)

        fun walk(dir: File, prefix: String, depth: Int) {
            if (depth > maxDepth) return
            val children = (dir.listFiles() ?: return)
                .filter { showHidden || !it.name.startsWith(".") }
                .sortedWith(compareBy({ !it.isDirectory }, { it.name.lowercase() }))
            for ((idx, child) in children.withIndex()) {
                val last = idx == children.size - 1
                out(prefix + (if (last) ell else tee) + child.name)
                if (child.isDirectory) {
                    dirs++
                    walk(child, prefix + if (last) "    " else vert, depth + 1)
                } else {
                    files++
                }
            }
        }

        walk(base, "", 0)
        out()
        out("$dirs directories, $files files")
        return 0
    }

    // ───────────────────────────── minimal git ─────────────────────────────

    private fun sha1Hex(bytes: ByteArray): String {
        val md = MessageDigest.getInstance("SHA-1")
        val digest = md.digest(bytes)
        val sb = StringBuilder(digest.size * 2)
        for (b in digest) sb.append(String.format("%02x", b.toInt() and 0xff))
        return sb.toString()
    }

    private fun zlibCompress(bytes: ByteArray): ByteArray {
        val deflater = Deflater(Deflater.BEST_SPEED)
        deflater.setInput(bytes)
        deflater.finish()
        val baos = ByteArrayOutputStream()
        val buf = ByteArray(16384)
        while (!deflater.finished()) {
            val n = deflater.deflate(buf)
            if (n <= 0) break
            baos.write(buf, 0, n)
        }
        deflater.end()
        return baos.toByteArray()
    }

    private fun zlibDecompress(bytes: ByteArray): ByteArray {
        val inflater = Inflater()
        inflater.setInput(bytes)
        val baos = ByteArrayOutputStream()
        val buf = ByteArray(16384)
        try {
            while (!inflater.finished()) {
                val n = inflater.inflate(buf)
                if (n <= 0) {
                    if (inflater.needsInput() || inflater.needsDictionary()) break
                } else baos.write(buf, 0, n)
            }
        } catch (_: Throwable) {
        }
        inflater.end()
        return baos.toByteArray()
    }

    private class GitRepo(val root: File) {
        val gitDir = File(root, ".git")
        val objectsDir = File(gitDir, "objects")
        val indexFile = File(gitDir, "index")

        fun isRepo() = gitDir.isDirectory

        fun writeObject(type: String, content: ByteArray): String {
            val header = "$type ${content.size}\u0000".toByteArray(Charsets.UTF_8)
            val full = ByteArray(header.size + content.size)
            System.arraycopy(header, 0, full, 0, header.size)
            System.arraycopy(content, 0, full, header.size, content.size)
            val sha = sha1Hex(full)
            val dir = File(objectsDir, sha.substring(0, 2))
            dir.mkdirs()
            val target = File(dir, sha.substring(2))
            if (!target.exists()) target.writeBytes(zlibCompress(full))
            return sha
        }

        fun readObject(sha: String): Pair<String, ByteArray>? {
            val file = File(File(objectsDir, sha.substring(0, 2)), sha.substring(2))
            if (!file.exists()) return null
            val raw = zlibDecompress(file.readBytes())
            var idx = 0
            while (idx < raw.size && raw[idx].toInt() != 0) idx++
            val header = String(raw, 0, idx, Charsets.UTF_8)
            val type = header.substringBefore(' ')
            val content = raw.copyOfRange(idx + 1, raw.size)
            return type to content
        }

        fun readIndex(): LinkedHashMap<String, String> {
            val map = LinkedHashMap<String, String>()
            if (!indexFile.isFile) return map
            indexFile.readLines(Charsets.UTF_8).forEach { line ->
                val tab = line.indexOf('\t')
                if (tab > 0) map[line.substring(tab + 1)] = line.substring(0, tab)
            }
            return map
        }

        fun writeIndex(map: LinkedHashMap<String, String>) {
            indexFile.parentFile?.mkdirs()
            indexFile.writeText(map.entries.joinToString("\n") { "${it.value}\t${it.key}" } + if (map.isEmpty()) "" else "\n")
        }

        fun headRef(): String? {
            val head = File(gitDir, "HEAD")
            if (!head.isFile) return null
            val text = head.readText(Charsets.UTF_8).trim()
            return if (text.startsWith("ref: ")) text.substring(5) else text
        }

        fun headSha(): String? {
            val ref = headRef() ?: return null
            if (ref.length == 40) return ref
            val file = File(gitDir, ref)
            if (!file.isFile) return null
            val sha = file.readText(Charsets.UTF_8).trim()
            return sha.ifEmpty { null }
        }

        fun refName(): String = (headRef() ?: "refs/heads/main").removePrefix("refs/heads/")

        fun commitMessage(sha: String): Pair<String, String> {
            val obj = readObject(sha) ?: return "" to ""
            val text = String(obj.second, Charsets.UTF_8)
            val headerEnd = text.indexOf("\n\n")
            val headers = if (headerEnd >= 0) text.substring(0, headerEnd) else text
            val body = if (headerEnd >= 0) text.substring(headerEnd + 2) else ""
            val parent = headers.lines().firstOrNull { it.startsWith("parent ") }?.substring(7) ?: ""
            return body.trim() to parent
        }

        fun relPaths(base: File): List<String> {
            val outList = ArrayList<String>()
            fun visit(dir: File, prefix: String) {
                val children = dir.listFiles() ?: return
                for (c in children.sortedBy { it.name }) {
                    if (c.name == ".git") continue
                    val rel = if (prefix.isEmpty()) c.name else "$prefix/${c.name}"
                    if (c.isDirectory) visit(c, rel) else outList.add(rel)
                }
            }
            visit(base, "")
            return outList
        }
    }

    private fun git(a: List<String>): Int {
        if (a.isEmpty()) {
            err("git: usage: git <init|status|add|commit|log|diff|rev-parse|branch|clone>")
            return 1
        }
        if (a[0] == "--version" || a[0] == "version") {
            out("git version 2.44.0 (opencode-android portable)")
            return 0
        }
        val repo = GitRepo(cwd())
        val sub = a[0]
        val rest = a.drop(1)

        return when (sub) {
            "init" -> {
                if (repo.isRepo()) {
                    out("Reinitialized existing Git repository in ${repo.gitDir.absolutePath}/")
                    return 0
                }
                repo.gitDir.mkdirs()
                File(repo.gitDir, "objects").mkdirs()
                File(repo.gitDir, "refs/heads").mkdirs()
                File(repo.gitDir, "HEAD").writeText("ref: refs/heads/main\n")
                File(repo.gitDir, "config").writeText(
                    "[core]\n\trepositoryformatversion = 0\n\tfilemode = false\n\tbare = false\n[user]\n\tname = OpenCode Android\n\temail = android@opencode.local\n"
                )
                out("Initialized empty Git repository in ${repo.gitDir.absolutePath}/")
                0
            }

            "status" -> {
                if (!repo.isRepo()) return notARepo()
                val index = repo.readIndex()
                val all = repo.relPaths(repo.root).toSet()
                val untracked = all.filter { !index.containsKey(it) }
                val modified = index.filter { (path, sha) ->
                    val f = File(repo.root, path)
                    !f.isFile || repo.writeObject("blob", f.readBytes()) != sha
                }.keys
                out("On branch ${repo.refName()}")
                if (modified.isNotEmpty()) {
                    out("Changes not staged for commit:")
                    modified.forEach { out("\tmodified:   $it") }
                }
                if (untracked.isNotEmpty()) {
                    out("Untracked files:")
                    untracked.take(500).forEach { out("\t$it") }
                }
                if (modified.isEmpty() && untracked.isEmpty()) out("nothing to commit, working tree clean")
                0
            }

            "add" -> {
                if (!repo.isRepo()) return notARepo()
                val targets = rest.filter { !it.startsWith("-") }
                val index = repo.readIndex()
                val paths = if (targets.isEmpty() || targets.contains(".") || targets.contains("-A")) {
                    repo.relPaths(repo.root)
                } else {
                    targets.flatMap { t ->
                        val f = expandPath(t)
                        if (f.isDirectory) repo.relPaths(f).map { t.trimEnd('/') + "/" + it } else listOf(t)
                    }
                }
                for (p in paths) {
                    val f = File(repo.root, p)
                    if (!f.isFile) continue
                    index[p] = repo.writeObject("blob", f.readBytes())
                }
                repo.writeIndex(index)
                0
            }

            "commit" -> {
                if (!repo.isRepo()) return notARepo()
                var message: String? = null
                var i = 0
                while (i < rest.size) {
                    when (rest[i]) {
                        "-m" -> {
                            i++
                            message = rest.getOrNull(i)
                        }

                        "-am" -> {
                            i++
                            message = rest.getOrNull(i)
                        }

                        "--message" -> {
                            i++
                            message = rest.getOrNull(i)
                        }

                        else -> if (!rest[i].startsWith("-") && message == null) message = rest[i]
                    }
                    i++
                }
                val msg = message?.trim().orEmpty().ifEmpty { "Update from OpenCode Android" }

                // Stage every tracked-or-new file when nothing was added explicitly
                val index = repo.readIndex()
                val wasTracked = HashSet(index.keys)
                val allFiles = repo.relPaths(repo.root)
                var changed = 0
                for (p in allFiles) {
                    val f = File(repo.root, p)
                    val sha = repo.writeObject("blob", f.readBytes())
                    if (index[p] != sha || !wasTracked.contains(p)) changed++
                    index[p] = sha
                }
                repo.writeIndex(index)
                if (changed == 0 && repo.headSha() != null) {
                    out("nothing to commit, working tree clean")
                    return 1
                }
                val sb = StringBuilder()
                sb.append("commit ").append(repo.writeObject("commit-tree", ByteArray(0))).append('\n')
                // Build a deterministic pseudo-tree hash from the index
                val treeSeed = index.entries.sortedBy { it.key }.joinToString("\n") { "${it.key} ${it.value}" }
                val treeSha = repo.writeObject("tree", treeSeed.toByteArray(Charsets.UTF_8))
                val parent = repo.headSha()
                val author = "OpenCode Android <android@opencode.local> ${System.currentTimeMillis() / 1000} +0000"
                val commitBody = buildString {
                    append("tree ").append(treeSha).append('\n')
                    if (parent != null) append("parent ").append(parent).append('\n')
                    append("author ").append(author).append('\n')
                    append("committer ").append(author).append('\n')
                    append('\n')
                    append(msg).append('\n')
                }
                val commitSha = repo.writeObject("commit", commitBody.toByteArray(Charsets.UTF_8))
                val refFile = File(repo.gitDir, repo.headRef() ?: "refs/heads/main")
                refFile.parentFile?.mkdirs()
                refFile.writeText("$commitSha\n")
                out("[${repo.refName()} ${commitSha.take(7)}] ${msg.lineSequence().first()}")
                out(" ${changed} file(s) changed")
                0
            }

            "log" -> {
                if (!repo.isRepo()) return notARepo()
                val oneline = rest.contains("--oneline")
                val limit = rest.firstOrNull { it.toIntOrNull() != null }?.toIntOrNull()
                    ?: rest.getOrNull(rest.indexOf("-n") + 1)?.toIntOrNull()
                    ?: 15
                var sha = repo.headSha()
                var count = 0
                if (sha == null) {
                    err("fatal: your current branch '${repo.refName()}' does not have any commits yet")
                    return 128
                }
                while (sha != null && count < limit) {
                    val (msg, parent) = repo.commitMessage(sha)
                    if (oneline) {
                        out("${sha.take(7)} ${msg.lineSequence().firstOrNull() ?: ""}")
                    } else {
                        out("commit $sha")
                        out("Author: OpenCode Android <android@opencode.local>")
                        out("Date:   ${SimpleDateFormat("EEE MMM d HH:mm:ss yyyy Z", Locale.US).format(Date())}")
                        out()
                        msg.lines().forEach { out("    $it") }
                        out()
                    }
                    sha = parent.ifEmpty { null }
                    count++
                }
                0
            }

            "diff" -> {
                if (!repo.isRepo()) return notARepo()
                val index = repo.readIndex()
                var total = 0
                for ((path, sha) in index) {
                    val f = File(repo.root, path)
                    if (!f.isFile) continue
                    val current = repo.writeObject("blob", f.readBytes())
                    if (current == sha) continue
                    total++
                    out("diff --git a/$path b/$path")
                    out("--- a/$path")
                    out("+++ b/$path")
                    out("@@ content changed @@")
                }
                if (total == 0) out("(no changes)")
                0
            }

            "rev-parse" -> {
                if (!repo.isRepo()) return notARepo()
                val target = rest.firstOrNull() ?: "HEAD"
                if (target == "HEAD" || target.startsWith("refs/") || target == repo.refName()) {
                    val sha = repo.headSha()
                    if (sha == null) {
                        err("fatal: ambiguous argument '$target': unknown revision")
                        return 128
                    }
                    out(sha)
                    0
                } else {
                    err("fatal: ambiguous argument '$target'")
                    128
                }
            }

            "branch" -> {
                if (!repo.isRepo()) return notARepo()
                out("* ${repo.refName()}")
                0
            }

            "checkout" -> {
                if (!repo.isRepo()) return notARepo()
                val createBranch = rest.contains("-b")
                if (createBranch) {
                    val name = rest.getOrNull(rest.indexOf("-b") + 1) ?: "main"
                    File(repo.gitDir, "HEAD").writeText("ref: refs/heads/$name\n")
                    out("Switched to a new branch '$name'")
                    0
                } else {
                    err("git: checkout of working tree paths is not supported by the portable toolchain")
                    1
                }
            }

            "clone" -> {
                err("git: 'clone' requires the full git implementation. Use `curl` to download a tarball/zip instead,")
                err("or run the agent's bash tool which performs the clone through the OpenCode engine.")
                1
            }

            "remote", "config", "show", "ls-files" -> 0
            else -> {
                err("git: '$sub' is not supported by the portable Android toolchain")
                err("supported: init, status, add, commit, log, diff, rev-parse, branch, checkout -b")
                1
            }
        }
    }

    private fun notARepo(): Int {
        err("fatal: not a git repository (or any of the parent directories): .git")
        return 128
    }

    // ───────────────────────────── python3 (mini) ─────────────────────────────

    private fun python(a: List<String>): Int {
        if (a.isEmpty() || a[0] == "--version" || a[0] == "-V") {
            out("Python 3.11.9 (opencode-android portable subset)")
            return 0
        }
        var script: String? = null
        val scriptArgs = ArrayList<String>()
        var i = 0
        if (a[0] == "-c") {
            script = a.getOrNull(1) ?: ""
            i = 2
        } else if (a[0] == "-u" || a[0] == "-B") {
            val rest = a.drop(1)
            if (rest.firstOrNull() == "-c") script = rest.getOrNull(1) ?: "" else if (rest.isNotEmpty()) {
                val f = expandPath(rest[0])
                if (!f.isFile) {
                    err("python3: can't open file '${rest[0]}': [Errno 2] No such file or directory")
                    return 2
                }
                script = f.readText(Charsets.UTF_8)
                scriptArgs.addAll(rest.drop(1))
            }
            i = a.size
        } else {
            val f = expandPath(a[0])
            if (!f.isFile) {
                err("python3: can't open file '${a[0]}': [Errno 2] No such file or directory")
                return 2
            }
            script = f.readText(Charsets.UTF_8)
            scriptArgs.addAll(a.drop(1))
            i = a.size
        }
        if (script == null) {
            err("python3: no script provided")
            return 2
        }
        return Py.runScript(script, scriptArgs)
    }

    // ───────────────────────────── node / npm ─────────────────────────────

    private fun daemonPort(): Int {
        System.getenv("OPENCODE_DAEMON_PORT")?.toIntOrNull()?.let { if (it > 0) return it }
        val portFile = File(homeDir(), "daemon-port")
        if (portFile.isFile) {
            val p = portFile.readText().trim().toIntOrNull()
            if (p != null && p > 0) return p
        }
        return 0
    }

    private fun callDaemon(path: String, payload: JSONObject, timeoutMs: Int): JSONObject {
        val port = daemonPort()
        if (port <= 0) throw IllegalStateException("OpenCode runtime is not running (open the app once)")
        val conn = httpFetch("http://127.0.0.1:$port$path", "POST", listOf("Content-Type" to "application/json"), payload.toString().toByteArray(), timeoutMs, false)
        return try {
            val text = ByteArrayOutputStream().also { baos ->
                val stream = try {
                    if (conn.responseCode in 200..399) conn.inputStream else (conn.errorStream ?: conn.inputStream)
                } catch (_: Throwable) {
                    conn.errorStream
                }
                if (stream != null) BufferedInputStream(stream).use { readAll(it, baos) }
            }.toString("UTF-8")
            if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            try {
                conn.disconnect()
            } catch (_: Throwable) {
            }
        }
    }

    private fun node(a: List<String>): Int {
        if (a.isEmpty()) {
            out("Welcome to Node.js v22.11.0 (OpenCode Android V8 bridge).")
            out("Type \".exit\" to exit, or run `node script.js`.")
            return 0
        }
        if (a[0] == "--version" || a[0] == "-v") {
            out("v22.11.0")
            return 0
        }
        var script: String? = null
        val argv = ArrayList<String>()
        val cwdNow = cwd()
        when {
            a[0] == "-e" || a[0] == "--eval" || a[0] == "-p" || a[0] == "--print" -> {
                script = a.getOrNull(1) ?: ""
                argv.addAll(a.drop(2))
            }

            a[0].startsWith("-") -> {
                err("node: unsupported option ${a[0]}")
                return 9
            }

            else -> {
                val file = expandPath(a[0])
                if (!file.isFile) {
                    err("node: Cannot find module '${a[0]}'")
                    err("    at Function.Module._resolveFilename (node:internal/modules/cjs/loader)")
                    return 1
                }
                script = file.readText(Charsets.UTF_8)
                argv.add(file.absolutePath)
                argv.addAll(a.drop(1))
            }
        }
        if (script == null) {
            err("node: no script provided")
            return 9
        }
        val payload = JSONObject()
            .put("code", script)
            .put("argv", JSONArray(argv))
            .put("cwd", cwdNow.absolutePath)
            .put("filename", argv.firstOrNull() ?: "<eval>")
            .put("timeoutMs", 120000)
            .put("toolchainDir", File(homeDir(), "usr/bin").absolutePath)
            .put("home", homeDir().absolutePath)
        return try {
            val res = callDaemon("/__native/eval-js", payload, 150000)
            if (res.has("__error") && !res.isNull("__error")) {
                err("node: ${res.optString("__error")}")
                return 1
            }
            val stdoutText = res.optString("stdout", "")
            val stderrText = res.optString("stderr", "")
            val keepFiles = java.util.ArrayList<Pair<String, String>>()
            if (stdoutText.isNotEmpty()) System.out.print(stdoutText)
            if (stderrText.isNotEmpty()) {
                if (!stderrText.endsWith("\n")) {
                    System.err.println(stderrText)
                } else {
                    System.err.print(stderrText)
                }
            }
            if (keepFiles.isNotEmpty()) {
                for ((path, b64) in keepFiles) {
                    try {
                        val target = expandPath(path)
                        target.parentFile?.mkdirs()
                        target.writeBytes(Base64.decode(b64, Base64.DEFAULT))
                    } catch (_: Throwable) {
                    }
                }
            }
            if (!res.optBoolean("ok", false)) {
                val message = res.optString("error", "script failed")
                err("node: $message")
                1
            } else {
                (res.optInt("exitCode", 0)).coerceIn(0, 255)
            }
        } catch (t: Throwable) {
            err("node: ${t.message ?: t.javaClass.simpleName}")
            err("OpenCode Android evaluates JavaScript inside the app's V8/WebView runtime; open the app, then retry.")
            1
        }
    }

    private fun npm(a: List<String>): Int {
        if (a.isEmpty() || a[0] == "--version" || a[0] == "-v") {
            out("10.9.0")
            return 0
        }
        val packageFile = File(cwd(), "package.json")
        val pkg: JSONObject? = try {
            if (packageFile.isFile) JSONObject(packageFile.readText(Charsets.UTF_8)) else null
        } catch (_: Throwable) {
            null
        }
        val sub = a[0]
        when (sub) {
            "run", "run-script" -> {
                val scriptName = a.getOrNull(1) ?: run {
                    val scripts = pkg?.optJSONObject("scripts")
                    out("Available scripts:")
                    if (scripts != null) {
                        val keys = scripts.keys()
                        while (keys.hasNext()) out("  ${keys.next()}")
                    }
                    return 0
                }
                return runNpmScript(pkg, scriptName, a.drop(2))
            }

            "start" -> return runNpmScript(pkg, "start", a.drop(1))
            "test" -> return runNpmScript(pkg, "test", a.drop(1))
            "install", "i", "add" -> {
                err("npm: package installation needs a full Node.js toolchain, which Android cannot execute from app storage.")
                err("Use `curl` to fetch files, or ask the OpenCode agent to write the dependency sources instead.")
                return 1
            }

            "init" -> {
                if (packageFile.exists()) {
                    out("package.json already exists")
                    return 0
                }
                val name = cwd().name.lowercase().replace(Regex("[^a-z0-9._-]"), "-")
                packageFile.writeText(
                    "{\n  \"name\": \"$name\",\n  \"version\": \"1.0.0\",\n  \"type\": \"module\",\n  \"scripts\": {\n    \"start\": \"node index.js\"\n  }\n}\n"
                )
                out("Wrote ${packageFile.absolutePath}")
                return 0
            }

            "ls", "list" -> {
                val deps = pkg?.optJSONObject("dependencies")
                if (deps == null || deps.length() == 0) out("(no dependencies)") else {
                    val keys = deps.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        out("$k@${deps.optString(k)}")
                    }
                }
                return 0
            }

            else -> {
                err("npm: unsupported command '$sub' by the portable toolchain")
                return 1
            }
        }
    }

    private fun runNpmScript(pkg: JSONObject?, name: String, extra: List<String>): Int {
        val command = pkg?.optJSONObject("scripts")?.optString(name, "")?.takeIf { it.isNotBlank() }
        if (command.isNullOrBlank()) {
            err("npm: missing script: \"$name\"")
            return 1
        }
        val shell = if (File("/system/bin/sh").exists()) "/system/bin/sh" else "sh"
        val path = System.getenv("PATH") ?: "/system/bin:/system/xbin"
        val pb = ProcessBuilder(shell, "-c", command + if (extra.isEmpty()) "" else " " + extra.joinToString(" "))
        pb.directory(cwd())
        pb.environment()["PATH"] = path
        pb.environment()["HOME"] = homeDir().absolutePath
        pb.environment()["OPENCODE_DAEMON_PORT"] = daemonPort().toString()
        pb.redirectErrorStream(true)
        return try {
            val proc = pb.start()
            proc.inputStream.copyTo(System.out)
            proc.waitFor()
        } catch (t: Throwable) {
            err("npm: ${t.message ?: t.javaClass.simpleName}")
            1
        }
    }

    // ───────────────────────────── which ─────────────────────────────

    private fun which(a: List<String>): Int {
        if (a.isEmpty()) return 1
        val name = a[0]
        val path = System.getenv("PATH") ?: "/system/bin:/system/xbin"
        for (dir in path.split(':')) {
            if (dir.isBlank()) continue
            val f = File(dir, name)
            if (f.isFile && f.canExecute()) {
                out(f.absolutePath)
                return 0
            }
            if (f.isFile) {
                out(f.absolutePath)
                return 0
            }
        }
        err("$name: not found")
        return 1
    }
}
