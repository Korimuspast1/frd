package ai.opencode.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.webkit.JavascriptInterface
import org.json.JSONObject

class NativeBridge(
    private val activity: MainActivity,
    private val getDaemon: () -> OpenCodeDaemonService?
) {

    @JavascriptInterface
    fun isNativeAndroid(): Boolean = true

    @JavascriptInterface
    fun getDaemonUrl(): String {
        val port = getDaemon()?.daemonPort ?: 0
        return if (port > 0) "http://127.0.0.1:$port" else ""
    }

    @JavascriptInterface
    fun getDeviceInfo(): String {
        return JSONObject().apply {
            put("manufacturer", Build.MANUFACTURER)
            put("model", Build.MODEL)
            put("sdkInt", Build.VERSION.SDK_INT)
            put("release", Build.VERSION.RELEASE)
        }.toString()
    }

    @JavascriptInterface
    fun setDaemonTaskStatus(statusText: String, busy: Boolean) {
        getDaemon()?.updateForegroundNotification(statusText, busy)
    }

    @JavascriptInterface
    fun setSystemBarsTheme(bgHex: String, isDark: Boolean) {
        activity.applySystemBarsTheme(bgHex, isDark)
    }

    @JavascriptInterface
    fun copyToClipboard(text: String) {
        activity.runOnUiThread {
            val cm = activity.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("OpenCode", text))
        }
    }

    @JavascriptInterface
    fun notifyTaskComplete(title: String, body: String) {
        getDaemon()?.sendTaskAlertNotification(title, body)
    }

    @JavascriptInterface
    fun openExternalUrl(url: String) {
        activity.runOnUiThread {
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                activity.startActivity(intent)
            } catch (_: Exception) {}
        }
    }

    @JavascriptInterface
    fun shareProjectZip(projectId: String): String {
        return try {
            val svc = getDaemon() ?: return "service_unavailable"
            val zipFile = svc.workspaceManager.exportProjectZip(projectId)
            val uri = OpenCodeFileProvider.uriForExportFile(zipFile)
            activity.runOnUiThread {
                val share = Intent(Intent.ACTION_SEND).apply {
                    type = "application/zip"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                activity.startActivity(Intent.createChooser(share, "Экспорт проекта ${zipFile.name}"))
            }
            "ok"
        } catch (e: Exception) {
            "error:${e.message}"
        }
    }

    @JavascriptInterface
    fun vibrateTick() {
        try {
            @Suppress("DEPRECATION")
            val vib = activity.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            vib?.vibrate(VibrationEffect.createOneShot(12L, VibrationEffect.DEFAULT_AMPLITUDE))
        } catch (_: Exception) {}
    }
}
