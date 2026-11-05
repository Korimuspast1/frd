package ai.opencode.android

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Universal shell execution for OpenCode Android.
 *
 * Every workspace directory works — internal app storage, `/storage/emulated/0/...`, `/sdcard/...`,
 * Termux paths, `noexec` FUSE mounts, or directories that do not exist yet — because:
 *  - the working directory is validated/created before the process starts and falls back to HOME
 *    (with an explicit `cd`) when `ProcessBuilder.directory()` is rejected on FUSE mounts;
 *  - `PATH` always contains a portable toolchain in `filesDir/usr/bin` (`bash`, `curl`, `wget`, `git`,
 *    `jq`, `zip`, `unzip`, `tree`, `node`, `npm`, `python3`, `which`), so CLI utilities are available
 *    even on a stock Android device without Termux;
 *  - `./script` invocations are transparently retried through `sh` on `noexec` mounts.
 */
class ShellExecutor(private val context: Context) {

    companion object {
        const val TOOLCHAIN_VERSION = 3
        private const val TERMUX_BIN = "/data/data/com.termux/files/usr/bin"
        private const val SYSTEM_PATHS =
            "/system/bin:/system/xbin:/product/bin:/vendor/bin:/data/local/bin"
    }

    private val toolchainDir: File by lazy { File(context.filesDir, "usr/bin") }
    private val tmpDir: File by lazy { File(context.cacheDir, "tmp").apply { mkdirs() } }

    @Volatile
    private var toolchainReady = false

    @Volatile
    private var dalvikWorks: Boolean? = null

    private fun apkPath(): String {
        val direct = context.packageCodePath
        return if (!direct.isNullOrBlank() && File(direct).exists()) direct else context.applicationInfo.sourceDir
    }

    private fun homeDir(): File = context.filesDir

    private val toolchainTools = listOf(
        "curl", "wget", "git", "jq", "zip", "unzip", "tree",
        "node", "npm", "python3", "python", "which", "basename", "dirname", "sleep",
    )

    /** Idempotently installs executable `#!/system/bin/sh` shims for the portable CLI toolchain. */
    @Synchronized
    fun ensurePortableToolchain(): File {
        if (!toolchainDir.exists()) toolchainDir.mkdirs()
        val stamp = File(toolchainDir, ".version")
        val installedVersion = try {
            if (stamp.isFile) stamp.readText().trim().toIntOrNull() ?: 0 else 0
        } catch (_: Throwable) {
            0
        }
        if (toolchainReady && installedVersion == TOOLCHAIN_VERSION) return toolchainDir

        val apk = apkPath()
        val dalvik = if (File("/system/bin/dalvikvm").exists()) "/system/bin/dalvikvm" else "dalvikvm"

        // bash: Android's /system/bin/sh is mksh, which understands [[ ]], arrays, functions and $((...)).
        writeShim(
            "bash",
            """
            #!/system/bin/sh
            # OpenCode Android portable toolchain v$TOOLCHAIN_VERSION — bash compatibility layer
            for d in $TERMUX_BIN /system/bin /system/xbin; do
              if [ -x "${'$'}d/bash" ] && [ "${'$'}d/bash" != "${'$'}0" ]; then exec "${'$'}d/bash" "${'$'}@"; fi
            done
            if [ "${'$'}#" -ge 2 ] && [ "${'$'}1" = "-c" ]; then
              exec /system/bin/sh -c "${'$'}2"
            fi
            exec /system/bin/sh "${'$'}@"
            """.trimIndent(),
        )

        for (tool in toolchainTools) {
            writeShim(
                tool,
                """
                #!/system/bin/sh
                # OpenCode Android portable toolchain v$TOOLCHAIN_VERSION — $tool
                # Prefer a real installation (Termux / system) when the device has one.
                for d in $TERMUX_BIN /system/bin /system/xbin /product/bin /vendor/bin /data/local/bin; do
                  if [ -x "${'$'}d/$tool" ] && [ "${'$'}d/$tool" != "${'$'}0" ]; then exec "${'$'}d/$tool" "${'$'}@"; fi
                done
                exec $dalvik -cp '$apk' ai.opencode.android.CliTools $tool "${'$'}@"
                """.trimIndent(),
            )
        }

        try {
            stamp.writeText(TOOLCHAIN_VERSION.toString())
        } catch (_: Throwable) {
        }
        toolchainReady = true
        return toolchainDir
    }

    private fun writeShim(name: String, content: String) {
        val target = File(toolchainDir, name)
        val body = content.trim() + "\n"
        if (target.isFile && target.length() == body.toByteArray().size.toLong()) {
            try {
                if (target.readText() == body) {
                    target.setExecutable(true, false)
                    return
                }
            } catch (_: Throwable) {
            }
        }
        try {
            target.writeText(body)
            target.setExecutable(true, false)
            target.setReadable(true, false)
        } catch (_: Throwable) {
        }
    }

    /** Verifies that `dalvikvm` can load the portable toolchain from the installed APK. */
    fun probeDalvik(): Boolean {
        dalvikWorks?.let { return it }
        ensurePortableToolchain()
        val result = try {
            val pb = ProcessBuilder("/system/bin/sh", "-c", "basename probe")
            pb.directory(homeDir())
            configureEnv(pb, homeDir())
            val proc = pb.start()
            val output = proc.inputStream.bufferedReader().readText()
            val ok = proc.waitFor(15, TimeUnit.SECONDS) && proc.exitValue() == 0 && output.trim() == "probe"
            dalvikWorks = ok
            ok
        } catch (_: Throwable) {
            dalvikWorks = null
            false
        }
        return result
    }

    private fun buildPath(): String {
        val parts = ArrayList<String>()
        parts.add(toolchainDir.absolutePath)
        if (File(TERMUX_BIN).isDirectory) parts.add(TERMUX_BIN)
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
        val shellBin = if (File("/system/bin/sh").exists()) "/system/bin/sh" else "sh"
        val execMount = isExecutableMount(workDir)
        val effective = if (execMount) command else demoteExecutables(command)

        var result = runOnce(shellBin, effective, workDir, timeoutMs)
        // Retry through `sh` when an executable bit was refused (noexec / stripped permissions).
        val stderr = result.optString("stderr", "")
        if (result.optInt("exitCode", 0) in intArrayOf(126, 127) &&
            (stderr.contains("Permission denied") || stderr.contains("not found"))
        ) {
            val rewritten = demoteExecutables(command)
            if (rewritten != effective) {
                result = runOnce(shellBin, rewritten, workDir, timeoutMs)
            }
        }
        result.put("durationMs", System.currentTimeMillis() - start)
        result.put("cwd", workDir.absolutePath)
        return result
    }

    private val executablePattern = Regex("(?<![\\w/.])[./][^\\s;&|()<>]*[^\\s;&|()<>]")

    /** Rewrites `./script` and `/abs/script` into `sh ./script` so `noexec` mounts still run scripts. */
    private fun demoteExecutables(command: String): String =
        command.replace(executablePattern) { match ->
            val token = match.value
            val looksLikeScript = !token.contains("/bin/") && (
                token.startsWith("./") || token.startsWith("../") ||
                    token.endsWith(".sh") || token.endsWith(".bash") || !token.substringAfterLast('/').contains('.')
                )
            if (looksLikeScript && !command.contains("sh $token") && !command.contains("sh -c $token")) {
                "sh $token"
            } else {
                token
            }
        }

    private fun runOnce(shellBin: String, command: String, workDir: File, timeoutMs: Long): JSONObject {
        val effectiveCommand = if (workDir.canRead()) command else joinCommand(workDir, command)
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
                val fallback = ProcessBuilder(shellBin, "-c", joinCommand(workDir, command))
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
