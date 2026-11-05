package ai.opencode.android

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Universal shell execution for OpenCode Android.
 *
 * Every workspace directory works — internal app storage, `/storage/emulated/0/...`, `/sdcard/...`,
 * Termux paths, `noexec` FUSE mounts, or directories that do not exist yet — because:
 *
 *  1. Android 10+ **forbids `execve()` on files inside the app data directory**, so the toolchain is
 *     not a set of executable scripts: `PATH` points to a folder of plain-text *templates*, and
 *     [rewriteCommand] resolves every known tool (python3, node, jq, curl, git, ...) to an explicit,
 *     always-executable interpreter invocation — `/system/bin/sh`, `/system/bin/dalvikvm` or the
 *     Termux binaries. Shell functions with the same names keep `bash -c`/scripts working too.
 *  2. The working directory is validated/created before the process starts and falls back to HOME
 *     (with an explicit `cd`) when `ProcessBuilder.directory()` is rejected on FUSE mounts.
 *  3. `./script` invocations are transparently rewritten through `sh` on `noexec` mounts, and the
 *     command is retried whenever a shell reports `Permission denied`/`not found`.
 *  4. Real Termux installations are preferred automatically when present.
 */
class ShellExecutor private constructor(
    private val filesDir: File,
    private val cacheDir: File,
    private val codePathProvider: () -> String,
) {

    constructor(context: Context) : this(
        context.filesDir,
        context.cacheDir,
        { context.packageCodePath ?: context.applicationInfo.sourceDir },
    )

    /** Non-Android constructor, used by the desktop verification harness. */
    constructor(filesDir: File, cacheDir: File, codePath: String) : this(filesDir, cacheDir, { codePath })


    companion object {
        const val TOOLCHAIN_VERSION = 4
        private const val TERMUX_BIN = "/data/data/com.termux/files/usr/bin"
        private const val TERMUX_PREFIX = "/data/data/com.termux/files/usr"
        private const val SYSTEM_PATHS =
            "/system/bin:/system/xbin:/product/bin:/vendor/bin:/data/local/bin"
        private const val TOOL_ENTRY = "ai.opencode.android.CliTools"

        /** Tools implemented inside the APK by [CliTools]; every other tool is passed through. */
        val PORTABLE_TOOLS = listOf(
            "curl", "wget", "git", "jq", "zip", "unzip", "tree",
            "node", "npm", "python3", "python", "which", "basename", "dirname", "sleep",
        )

        /** Aliases that must resolve to the same portable implementation. */
        private val ALIASES = mapOf("python" to "python3")
    }

    private val toolchainDir: File by lazy { File(filesDir, "usr/bin") }

    private val tmpDir: File by lazy {
        val dir = File(cacheDir, "tmp")
        try {
            dir.mkdirs()
        } catch (_: Throwable) {
        }
        dir
    }

    @Volatile
    private var toolchainReady = false

    @Volatile
    private var dalvikVerified: Boolean? = null

    @Volatile
    private var termuxAvailable: Boolean? = null

    private fun homeDir(): File = filesDir

    /**
     * Installs the toolchain support files. Nothing here needs the executable bit (Android 10+
     * blocks exec on app data): the folder only carries templates and the `usr` prefix that some
     * scripts expect (`$HOME/usr/bin`), while execution always goes through a system binary.
     */
    @Synchronized
    fun ensurePortableToolchain(): File {
        try {
            if (!toolchainDir.exists()) toolchainDir.mkdirs()
            File(filesDir, "usr/lib").mkdirs()
            File(filesDir, "usr/share").mkdirs()
        } catch (_: Throwable) {
        }
        val stamp = File(toolchainDir, ".version")
        val installedVersion = try {
            if (stamp.isFile) stamp.readText().trim().toIntOrNull() ?: 0 else 0
        } catch (_: Throwable) {
            0
        }
        if (toolchainReady && installedVersion == TOOLCHAIN_VERSION) return toolchainDir

        for (tool in PORTABLE_TOOLS) {
            writeTemplate(tool, portableInvocation(tool) + " \"$@\"\n")
        }
        writeTemplate("bash", "#!/system/bin/sh\nexec /system/bin/sh \"$@\"\n")
        writeTemplate(
            "README",
            "OpenCode Android portable toolchain v$TOOLCHAIN_VERSION\n" +
                "Tools: ${PORTABLE_TOOLS.joinToString(", ")}\n" +
                "Execution goes through /system/bin/dalvikvm -cp <apk> $TOOL_ENTRY <tool>.\n",
        )

        try {
            stamp.writeText(TOOLCHAIN_VERSION.toString())
        } catch (_: Throwable) {
        }
        toolchainReady = true
        return toolchainDir
    }

    private fun writeTemplate(name: String, content: String) {
        try {
            val target = File(toolchainDir, name)
            target.writeText(content)
        } catch (_: Throwable) {
        }
    }

    private fun termuxReady(): Boolean {
        termuxAvailable?.let { return it }
        val ready = try {
            File("$TERMUX_BIN/sh").isFile && File("$TERMUX_BIN/python3").isFile
        } catch (_: Throwable) {
            false
        }
        termuxAvailable = ready
        return ready
    }

    private fun dalvikBin(): String =
        if (File("/system/bin/dalvikvm").exists()) "/system/bin/dalvikvm" else "dalvikvm"

    /**
     * `-cp` argument for `dalvikvm`. `dalvikvm` reads the APK as an ordinary file (no `execve`), so the
     * installed `base.apk` under `/data/app/...` works — except on devices that store it under
     * `/data/data/...`, where the shorter real path resolved from `/proc/self/maps` is used instead.
     */
    private fun classPath(): String {
        val candidate = codePathProvider()
        if (!candidate.contains("/data/data/")) return candidate
        return resolveRealApkPath() ?: candidate
    }

    private fun resolveRealApkPath(): String? = try {
        File("/proc/self/maps").useLines { lines ->
            lines.map { it.substringAfter(' ') }
                .firstOrNull { it.contains("base.apk") }
        }
    } catch (_: Throwable) {
        null
    }

    /** Explicit interpreter invocation for a portable tool (never depends on the executable bit). */
    fun portableInvocation(tool: String): String {
        val resolved = ALIASES[tool] ?: tool
        if (resolved == "bash") return "/system/bin/sh"
        if (termuxReady()) {
            val termuxTool = if (resolved == "python3") "python" else resolved
            if (File("$TERMUX_BIN/$termuxTool").exists()) return "$TERMUX_BIN/$termuxTool"
        }
        val apk = File(classPath()).absolutePath
        val runtime = System.getenv("OPENCODE_TOOLCHAIN_JVM")?.takeIf { it.isNotBlank() } ?: dalvikBin()
        val cpValue = if (runtime.contains("dalvikvm")) apk else System.getProperty("java.class.path") ?: apk
        return "$runtime -cp '$cpValue' $TOOL_ENTRY $resolved"
    }

    /**
     * Rewrites a command so that every portable tool is invoked through a real system binary.
     *
     * Handles: `python3 bot.py`, `FOO=1 python3 x.py`, `python3 x.py > log 2>&1`, `cd dir && python3 x.py`,
     * `timeout 300 python3 x.py`, `nohup python3 x.py &`, absolute/relative paths to the tool,
     * `node`, `npm`, `jq`, `curl`, `wget`, `git`, `zip`, `unzip`, `tree`, plus Termux-style paths.
     */
    fun rewriteCommand(command: String): String {
        if (command.isBlank()) return command
        var result = command
        for (tool in PORTABLE_TOOLS) {
            result = replaceTool(result, tool)
        }
        // absolute Termux-style invocations: /usr/bin/python3, /data/data/com.termux/files/usr/bin/python3
        for (tool in PORTABLE_TOOLS) {
            result = result.replace(
                Regex("(?<![\\w./-])(?:\\$?PREFIX|$TERMUX_PREFIX|/usr)/bin/" + Regex.escape(tool) + "(?=\\s|${'$'})"),
                portableInvocation(tool),
            )
        }
        return result
    }

    private fun replaceTool(command: String, tool: String): String {
        val invocation = portableInvocation(tool)
        if (invocation.endsWith("/$tool")) return command // real Termux binary already, nothing to rewrite
        val pattern = Regex("(?<![\\w./-])" + Regex.escape(tool) + "(?=\\s|${'$'})")
        return pattern.replace(command) { match ->
            // Skip when already part of an explicit dalvik/sh invocation or a quoted path.
            val start = match.range.first
            val prefix = command.substring(maxOf(0, start - 64), start)
            val alreadyWrapped = prefix.contains("dalvikvm") || prefix.contains(TOOL_ENTRY)
            if (alreadyWrapped) match.value else invocation
        }
    }

    /**
     * Shell functions with the same names as the portable tools. Sourced into every `sh -c` session so
     * `bash -c "python3 x.py"` and scripts calling `curl`/`jq` also work without a PATH shim.
     */
    fun toolchainFunctions(): String = buildString {
        appendLine("# OpenCode Android portable toolchain v$TOOLCHAIN_VERSION")
        for (tool in PORTABLE_TOOLS) {
            val invocation = portableInvocation(tool)
            if (invocation.endsWith("/$tool")) continue
            if (tool == "bash") {
                appendLine("bash() { /system/bin/sh \"\$@\"; }")
                continue
            }
            appendLine("$tool() { $invocation \"\$@\"; }")
        }
    }

    /** Verifies that `dalvikvm` can load the portable toolchain from the installed APK. */
    fun probeDalvik(): Boolean {
        dalvikVerified?.let { return it }
        ensurePortableToolchain()
        val result = try {
            val pb = ProcessBuilder("/system/bin/sh", "-c", "basename probe")
            pb.directory(homeDir())
            configureEnv(pb, homeDir())
            val proc = pb.start()
            val output = proc.inputStream.bufferedReader().readText()
            val ok = proc.waitFor(20, TimeUnit.SECONDS) && proc.exitValue() == 0 && output.trim() == "probe"
            dalvikVerified = ok
            ok
        } catch (_: Throwable) {
            dalvikVerified = false
            false
        }
        return result
    }

    private fun buildPath(): String {
        val parts = ArrayList<String>()
        if (termuxReady()) parts.add(TERMUX_BIN)
        parts.add(toolchainDir.absolutePath)
        parts.add(SYSTEM_PATHS)
        return parts.joinToString(":")
    }

    private fun configureEnv(pb: ProcessBuilder, workDir: File) {
        val env = pb.environment()
        env["PATH"] = buildPath()
        env["HOME"] = homeDir().absolutePath
        env["PWD"] = workDir.absolutePath
        env["TMPDIR"] = tmpDir.absolutePath
        env["TMP"] = tmpDir.absolutePath
        env["TERM"] = "xterm-256color"
        env["LANG"] = "en_US.UTF-8"
        env["LC_ALL"] = "en_US.UTF-8"
        env["OPENCODE"] = "1"
        env["OPENCODE_PLATFORM"] = "android"
        env["OPENCODE_ANDROID_TOOLCHAIN"] = toolchainDir.absolutePath
        // Desktop harness / tests can swap the Java runtime (dalvikvm) without touching device logic.
        val jvmOverride = System.getenv("OPENCODE_TOOLCHAIN_JVM")
        if (!jvmOverride.isNullOrBlank()) env["OPENCODE_TOOLCHAIN_JVM"] = jvmOverride
        env["ANDROID_DATA"] = System.getenv("ANDROID_DATA") ?: "/data"
        env["ANDROID_ROOT"] = System.getenv("ANDROID_ROOT") ?: "/system"
        val daemonPort = daemonPort
        if (daemonPort > 0) env["OPENCODE_DAEMON_PORT"] = daemonPort.toString()
        // Make plain `curl`/`wget`/`git` inside sh scripts reachable through the local proxy as well.
        val proxy = proxyUrl
        if (proxy != null) {
            env["http_proxy"] = proxy
            env["https_proxy"] = proxy
            env["HTTP_PROXY"] = proxy
            env["HTTPS_PROXY"] = proxy
            env["ALL_PROXY"] = proxy
            env["NO_PROXY"] = "127.0.0.1,localhost,::1"
        }
        if (shellExecutorAscii) {
            env["OPENCODE_ASCII"] = "1"
        }
        if (File(TERMUX_BIN).isDirectory) {
            env["PREFIX"] = "/data/data/com.termux/files/usr"
        }
    }

    /** Android consoles are usually not UTF-8 capable — use ASCII tree/box drawing. */
    @Volatile
    var shellExecutorAscii: Boolean = true

    @Volatile
    var daemonPort: Int = 0

    @Volatile
    var proxyUrl: String? = null

    /** Resolves any user-supplied directory, creating it when needed. Never throws. */
    fun resolveWorkDir(directory: String?): File {
        val fallback = homeDir()
        if (directory.isNullOrBlank()) return fallback
        val normalized = when {
            directory.startsWith("/sdcard/") -> "/storage/emulated/0/" + directory.removePrefix("/sdcard/")
            directory == "/sdcard" -> "/storage/emulated/0"
            else -> directory
        }
        val target = if (normalized.startsWith("/")) File(normalized) else File(fallback, normalized)
        return try {
            if (!target.exists()) target.mkdirs()
            if (target.isDirectory && target.canWrite()) target else if (target.isDirectory) target else fallback
        } catch (_: Throwable) {
            fallback
        }
    }

    private fun isExecutableMount(dir: File): Boolean {
        // FUSE / storage mounts are commonly mounted `noexec`; detect by looking at /proc/mounts once.
        val path = dir.absolutePath
        if (!path.startsWith("/storage/") && !path.startsWith("/mnt/media_rw")) return true
        return try {
            val mounts = File("/proc/mounts").readLines()
            val entry = mounts.firstOrNull { line ->
                val fields = line.split(' ')
                fields.size >= 4 && path.startsWith(fields[1]) && fields[1] != "/"
            } ?: return false
            val opts = entry.split(' ')[3]
            !opts.split(',').contains("noexec")
        } catch (_: Throwable) {
            false
        }
    }

    /** Optional registry so "listening"/bot style commands keep running after the session ends. */
    @Volatile
    var processRegistry: ProcessRegistry? = null

    private val longRunningPattern = Regex(
        "(pol ling|poll)\\b|while\\s+True|while\\s*\\(|getUpdates|setWebhook|listen\\s*\\(|app\\.run|serve\\s*\\(|\\buvicorn\\b|\\bgunicorn\\b|\\bnodemon\\b|--watch\\b|\\bserve\\b.*-l",
        RegexOption.IGNORE_CASE,
    )

    private fun isLongRunning(command: String): Boolean {
        if (longRunningPattern.containsMatchIn(command)) return true
        val trailing = command.trimEnd().trimEnd('&').trimEnd()
        return trailing.endsWith(".py") || trailing.endsWith(".js") || trailing.endsWith(".mjs")
    }

    /**
     * Starts a detached long-running process (`python3 bot.py`) with output redirected to a log file.
     * The child is spawned by `/system/bin/sh` directly from Kotlin, so it survives the WebView session
     * and is restarted by the daemon watchdog after an app restart (see [ProcessRegistry]).
     */
    fun startBackground(projectDir: File, command: String): JSONObject {
        ensurePortableToolchain()
        val workDir = resolveWorkDir(projectDir.absolutePath)
        val registry = processRegistry
        val id = "bg_" + System.currentTimeMillis().toString(36)
        val logFile = registry?.logFileFor(id) ?: File(filesDir, "run/logs/$id.log")
        logFile.parentFile?.mkdirs()
        val rewritten = rewriteCommand(command)
        val shell = "/system/bin/sh"
        val script = buildString {
            appendLine(toolchainFunctions())
            appendLine("cd ${shellQuote(workDir.absolutePath)} 2>/dev/null || true")
            appendLine(rewritten)
        }
        return try {
            val pb = ProcessBuilder(shell, "-c", script)
            pb.directory(workDir)
            configureEnv(pb, workDir)
            pb.redirectOutput(ProcessBuilder.Redirect.appendTo(logFile))
            pb.redirectError(ProcessBuilder.Redirect.appendTo(logFile))
            val proc = pb.start()
            val pid = processPid(proc)
            registry?.register(id, workDir.absolutePath, rewritten, true, pid, proc)
            // Give the process a moment so instant failures (syntax errors) are reported inline.
            Thread.sleep(1200)
            val alive = proc.isAlive
            val tail = try {
                logFile.readText(Charsets.UTF_8).takeLast(4000)
            } catch (_: Throwable) {
                ""
            }
            JSONObject()
                .put("stdout", (if (alive) "Запущено в фоне (pid " + pid + ").\n" else "") + tail)
                .put("stderr", "")
                .put("exitCode", if (alive) 0 else (if (proc.isAlive) 0 else 1))
                .put("durationMs", 1200L)
                .put("cwd", workDir.absolutePath)
                .put("background", true)
                .put("pid", pid)
                .put("log", logFile.absolutePath)
                .put("alive", alive)
        } catch (t: Throwable) {
            JSONObject()
                .put("stdout", "")
                .put("stderr", "Не удалось запустить процесс: ${t.message ?: t.javaClass.simpleName}")
                .put("exitCode", 1)
                .put("durationMs", 0L)
                .put("cwd", workDir.absolutePath)
        }
    }

    /** Process id, read reflectively so the code also links on API level 24/25 toolchains. */
    private fun processPid(proc: Process): Long = try {
        val method = proc.javaClass.getMethod("pid")
        (method.invoke(proc) as? Long) ?: -1L
    } catch (_: Throwable) {
        -1L
    }

    private fun shellQuote(raw: String): String = "'" + raw.replace("'", "'\\''") + "'"

    fun execute(projectDir: File, command: String, timeoutMs: Long = 30000L): JSONObject {
        val start = System.currentTimeMillis()
        if (command.isBlank()) {
            return JSONObject()
                .put("stdout", "")
                .put("stderr", "")
                .put("exitCode", 0)
                .put("durationMs", 0L)
                .put("cwd", projectDir.absolutePath)
        }
        ensurePortableToolchain()
        val workDir = resolveWorkDir(projectDir.absolutePath)
        val shellBin = "/system/bin/sh"

        if (isLongRunning(command) && processRegistry != null) {
            val bg = startBackground(projectDir, command)
            bg.put("durationMs", System.currentTimeMillis() - start)
            return bg
        }

        var effective = rewriteCommand(command)
        if (!isExecutableMount(workDir)) effective = demoteExecutables(effective)

        var result = runOnce(shellBin, effective, workDir, timeoutMs)

        // A shell can still hit `Permission denied` (noexec mount, stripped exec bit, sandbox storage).
        // Retry progressively: first demote `./script`, then run everything without exec.
        if (needsRetry(result)) {
            val demoted = demoteExecutables(rewriteCommand(command))
            if (demoted != effective) {
                effective = demoted
                result = runOnce(shellBin, effective, workDir, timeoutMs)
            }
        }
        if (needsRetry(result)) {
            val noExec = "sh " + effective
            val retried = runOnce(shellBin, noExec, workDir, timeoutMs)
            if (!needsRetry(retried) || retried.optString("stdout").isNotEmpty()) result = retried
        }

        result.put("durationMs", System.currentTimeMillis() - start)
        result.put("cwd", workDir.absolutePath)
        return result
    }

    private fun needsRetry(result: JSONObject): Boolean {
        val code = result.optInt("exitCode", 0)
        if (code != 126 && code != 127) return false
        val stderr = result.optString("stderr", "")
        return stderr.contains("Permission denied") ||
            stderr.contains("not found") ||
            stderr.contains("Exec format error") ||
            stderr.contains("can't execute")
    }

    private val executablePattern = Regex("(?<![\\w/.])(?:\\.{1,2}/|/)[^\\s;&|()<>]*[^\\s;&|()<>]")

    /** Rewrites `./script` and `/abs/script` into `sh ./script` so `noexec` mounts still run scripts. */
    private fun demoteExecutables(command: String): String =
        command.replace(executablePattern) { match ->
            val token = match.value.trim()
            val isScriptish = token.endsWith(".sh") || token.endsWith(".bash") ||
                (token.startsWith("./") && !token.substringAfterLast('/').contains('.'))
            val isInsideSystemBin = token.startsWith("/system/") || token.startsWith("/data/local/tmp/")
            if (isScriptish && !isInsideSystemBin) "sh $token" else token
        }

    private fun runOnce(shellBin: String, command: String, workDir: File, timeoutMs: Long): JSONObject {
        val withEnv = toolchainFunctions() + "\n" + command
        val effectiveCommand = if (workDir.canRead()) withEnv else joinCommand(workDir, withEnv)
        return try {
            val pb = ProcessBuilder(shellBin, "-c", effectiveCommand)
            pb.directory(if (workDir.canRead()) workDir else homeDir())
            configureEnv(pb, workDir)
            pb.redirectErrorStream(false)

            val proc = try {
                pb.start()
            } catch (_: Throwable) {
                // FUSE / external paths can refuse to be used as the process CWD — fall back to HOME
                // and `cd` explicitly so the command still runs against the requested directory.
                val fallback = ProcessBuilder(shellBin, "-c", joinCommand(workDir, withEnv))
                fallback.directory(homeDir())
                configureEnv(fallback, workDir)
                fallback.redirectErrorStream(false)
                fallback.start()
            }
            val stdoutBuilder = StringBuilder()
            val stderrBuilder = StringBuilder()

            val outThread = Thread {
                try {
                    proc.inputStream.bufferedReader(Charsets.UTF_8).use { r ->
                        val buf = CharArray(4096)
                        var n = r.read(buf)
                        while (n != -1) {
                            if (stdoutBuilder.length < 256000) stdoutBuilder.append(buf, 0, n)
                            n = r.read(buf)
                        }
                    }
                } catch (_: Throwable) {
                }
            }

            val errThread = Thread {
                try {
                    proc.errorStream.bufferedReader(Charsets.UTF_8).use { r ->
                        val buf = CharArray(4096)
                        var n = r.read(buf)
                        while (n != -1) {
                            if (stderrBuilder.length < 128000) stderrBuilder.append(buf, 0, n)
                            n = r.read(buf)
                        }
                    }
                } catch (_: Throwable) {
                }
            }

            outThread.start()
            errThread.start()

            val finished = proc.waitFor(timeoutMs.coerceIn(1000L, 600000L), TimeUnit.MILLISECONDS)
            if (!finished) {
                proc.destroyForcibly()
                stderrBuilder.append("\n[Command timed out after ${timeoutMs}ms]")
            }

            outThread.join(1500)
            errThread.join(1500)

            val exitCode = if (finished) proc.exitValue() else 124

            JSONObject()
                .put("stdout", stdoutBuilder.toString())
                .put("stderr", stderrBuilder.toString())
                .put("exitCode", exitCode)
        } catch (t: Throwable) {
            JSONObject()
                .put("stdout", "")
                .put("stderr", "Shell execution error: " + (t.message ?: t.javaClass.simpleName))
                .put("exitCode", 1)
        }
    }

    private fun joinCommand(workDir: File, command: String): String =
        "cd '" + workDir.absolutePath.replace("'", "'\\''") + "' 2>/dev/null || cd '" +
            homeDir().absolutePath + "'\n" + command

    /** Describes the runtime environment for the agent / diagnostics panel. */
    fun environmentInfo(): JSONObject {
        ensurePortableToolchain()
        val commands = ArrayList<String>()
        val pb = ProcessBuilder("/system/bin/sh", "-c", "for c in bash sh curl wget git jq zip unzip tree node npm python3 sed awk grep find tar xargs; do command -v \$c >/dev/null 2>&1 && printf '%s ' \$c; done")
        try {
            pb.directory(homeDir())
            configureEnv(pb, homeDir())
            val proc = pb.start()
            commands.add(proc.inputStream.bufferedReader().readText().trim())
            proc.waitFor(10, TimeUnit.SECONDS)
        } catch (_: Throwable) {
        }
        return JSONObject()
            .put("platform", "android")
            .put("home", homeDir().absolutePath)
            .put("toolchainDir", toolchainDir.absolutePath)
            .put("toolchainVersion", TOOLCHAIN_VERSION)
            .put("path", buildPath())
            .put("daemonPort", daemonPort)
            .put("termuxDetected", File(TERMUX_BIN).isDirectory)
            .put("tools", commands.firstOrNull() ?: "")
    }
}
