package ai.opencode.android

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * Tracks long-running processes started by the agent (`python3 bot.py`, `node server.js`, ...).
 *
 * A pending command is persisted to `files/run/pending.json` **before** it starts. If the app process is
 * killed while it runs (user swipes the app away, Android kills the background service), the watchdog in
 * [OpenCodeDaemonService] sees the stale record on the next start, marks it `crashed` and restarts the
 * command with `nohup` + `setsid` semantics (detached from the app), so bots and dev servers keep running.
 */
class ProcessRegistry(private val context: Context) {

    companion object {
        private const val MAX_ENTRIES = 12
    }

    private val dir: File by lazy {
        File(context.filesDir, "run").apply { mkdirs() }
    }

    private val pendingFile: File by lazy { File(dir, "pending.json") }
    private val logDir: File by lazy { File(dir, "logs").apply { mkdirs() } }

    /** id -> live handle */
    private val running = ConcurrentHashMap<String, Process>()

    private val lock = Any()

    fun logFileFor(id: String): File = File(logDir, "$id.log")

    fun list(): JSONArray {
        val arr = JSONArray()
        for ((id, proc) in running) {
            arr.put(
                JSONObject()
                    .put("id", id)
                    .put("alive", proc.isAlive)
                    .put("log", logFileFor(id).absolutePath),
            )
        }
        return arr
    }

    fun isRunning(id: String): Boolean = running[id]?.isAlive == true

    /** Registers a process; persists the command so a restart can resume it. */
    fun register(id: String, directory: String, command: String, restart: Boolean, pid: Long, proc: Process) {
        running[id] = proc
        writeEntry(
            JSONObject()
                .put("id", id)
                .put("directory", directory)
                .put("command", command)
                .put("restart", restart)
                .put("status", "running")
                .put("pid", pid)
                .put("startedAt", System.currentTimeMillis()),
        )
    }

    fun markStopped(id: String) {
        running.remove(id)
        updateEntry(id) { it.put("status", "stopped") }
    }

    fun reapFinished() {
        for ((id, proc) in running.entries.toList()) {
            if (!proc.isAlive) {
                running.remove(id)
                updateEntry(id) { it.put("status", "exited").put("exitCode", if (proc.isAlive) 0 else 1) }
            }
        }
    }

    private fun readAll(): JSONArray = try {
        if (pendingFile.isFile) JSONArray(pendingFile.readText(Charsets.UTF_8)) else JSONArray()
    } catch (_: Throwable) {
        JSONArray()
    }

    private fun writeAll(arr: JSONArray) {
        try {
            dir.mkdirs()
            pendingFile.writeText(arr.toString(), Charsets.UTF_8)
        } catch (_: Throwable) {
        }
    }

    @Synchronized
    private fun writeEntry(entry: JSONObject) {
        val id = entry.optString("id")
        val arr = JSONArray()
        val existing = readAll()
        for (i in 0 until existing.length()) {
            val item = existing.optJSONObject(i) ?: continue
            if (item.optString("id") == id) continue
            arr.put(item)
        }
        arr.put(entry)
        val trimmed = JSONArray()
        val start = maxOf(0, arr.length() - MAX_ENTRIES)
        for (i in start until arr.length()) trimmed.put(arr.optJSONObject(i))
        writeAll(trimmed)
    }

    @Synchronized
    private fun updateEntry(id: String, mutate: (JSONObject) -> Unit) {
        val arr = readAll()
        for (i in 0 until arr.length()) {
            val item = arr.optJSONObject(i) ?: continue
            if (item.optString("id") != id) continue
            mutate(item)
        }
        writeAll(arr)
    }

    /** Commands that were running when the app process died and asked to be restarted. */
    fun staleRestartable(): List<JSONObject> {
        val out = ArrayList<JSONObject>()
        val arr = readAll()
        for (i in 0 until arr.length()) {
            val item = arr.optJSONObject(i) ?: continue
            if (!item.optBoolean("restart", false)) continue
            if (item.optString("status") != "running") continue
            val id = item.optString("id")
            if (isRunning(id)) continue
            out.add(item)
        }
        return out
    }

    fun markCrashed(id: String) = updateEntry(id) { it.put("status", "crashed") }
}
