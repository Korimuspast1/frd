package ai.opencode.android

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

class ShellExecutor(private val context: Context) {

    fun execute(projectDir: File, command: String, timeoutMs: Long = 30000L): JSONObject {
        val start = System.currentTimeMillis()
        if (command.isBlank()) {
            return JSONObject()
                .put("stdout", "")
                .put("stderr", "")
                .put("exitCode", 0)
                .put("durationMs", 0L)
        }

        return try {
            if (!projectDir.exists()) projectDir.mkdirs()
            val shellBin = if (File("/system/bin/sh").exists()) "/system/bin/sh" else "sh"
            val pb = ProcessBuilder(shellBin, "-c", command)
            pb.directory(projectDir)

            val env = pb.environment()
            val termuxBin = "/data/data/com.termux/files/usr/bin"
            val currentPath = env["PATH"] ?: "/system/bin:/system/xbin"
            env["PATH"] = if (File(termuxBin).exists()) "$termuxBin:$currentPath" else currentPath
            env["HOME"] = context.filesDir.absolutePath
            env["TMPDIR"] = context.cacheDir.absolutePath
            env["TERM"] = "xterm-256color"
            env["OPENCODE"] = "1"
            env["OPENCODE_PLATFORM"] = "android"

            val proc = pb.start()
            val stdoutBuilder = StringBuilder()
            val stderrBuilder = StringBuilder()

            val outThread = Thread {
                try {
                    proc.inputStream.bufferedReader(Charsets.UTF_8).use { r ->
                        val buf = CharArray(4096)
                        var n = r.read(buf)
                        while (n != -1) {
                            if (stdoutBuilder.length < 128000) stdoutBuilder.append(buf, 0, n)
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
                            if (stderrBuilder.length < 64000) stderrBuilder.append(buf, 0, n)
                            n = r.read(buf)
                        }
                    }
                } catch (_: Throwable) {
                }
            }

            outThread.start()
            errThread.start()

            val finished = proc.waitFor(timeoutMs.coerceIn(1000L, 120000L), TimeUnit.MILLISECONDS)
            if (!finished) {
                proc.destroyForcibly()
                stderrBuilder.append("\n[Command timed out after ${timeoutMs}ms]")
            }

            outThread.join(1000)
            errThread.join(1000)

            val exitCode = if (finished) proc.exitValue() else 124
            val duration = System.currentTimeMillis() - start

            JSONObject()
                .put("stdout", stdoutBuilder.toString())
                .put("stderr", stderrBuilder.toString())
                .put("exitCode", exitCode)
                .put("durationMs", duration)
        } catch (t: Throwable) {
            JSONObject()
                .put("stdout", "")
                .put("stderr", t.message ?: "Shell execution error")
                .put("exitCode", 1)
                .put("durationMs", System.currentTimeMillis() - start)
        }
    }
}
