package ai.opencode.android

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONObject

class NativeBridge(
    private val activity: MainActivity,
    private val runtime: OpenCodeRuntime,
    private val getWebView: () -> WebView?
) {

    @JavascriptInterface
    fun isNativeAndroid(): Boolean = true

    @JavascriptInterface
    fun getDaemonUrl(): String {
        val p = runtime.daemonPort
        return if (p > 0) "http://127.0.0.1:$p" else ""
    }

    @JavascriptInterface
    fun getRuntimeInfo(): String {
        return JSONObject()
            .put("platform", "android")
            .put("version", "2.2.5")
            .put("manufacturer", Build.MANUFACTURER)
            .put("model", Build.MODEL)
            .put("sdkInt", Build.VERSION.SDK_INT)
            .put("release", Build.VERSION.RELEASE)
            .put("daemonPort", runtime.daemonPort)
            .toString()
    }

    @JavascriptInterface
    fun invokeAsync(requestJson: String, callbackId: String) {
        runtime.ioExecutor.execute {
            val resultJson = try {
                runtime.dispatchRpcJson(requestJson)
            } catch (t: Throwable) {
                JSONObject().put("__error", t.message ?: "Native bridge error").toString()
            }
            val jsCall = "window.__ocNativeResolve && window.__ocNativeResolve(" +
                JSONObject.quote(callbackId) + "," +
                JSONObject.quote(resultJson) + ");"
            activity.runOnUiThread {
                try {
                    getWebView()?.evaluateJavascript(jsCall, null)
                } catch (_: Throwable) {
                }
            }
        }
    }

    @JavascriptInterface
    fun setSystemBarsTheme(bgHex: String, isDark: Boolean) {
        activity.applySystemBarsTheme(bgHex, isDark)
    }

    @JavascriptInterface
    fun copyToClipboard(text: String) {
        activity.runOnUiThread {
            try {
                val cm = activity.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                cm?.setPrimaryClip(ClipData.newPlainText("OpenCode", text))
            } catch (_: Throwable) {
            }
        }
    }

    @JavascriptInterface
    fun openExternalUrl(url: String) {
        activity.runOnUiThread {
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                activity.startActivity(intent)
            } catch (_: Throwable) {
            }
        }
    }

    @JavascriptInterface
    fun shareProjectZip(projectIdOrDir: String) {
        runtime.ioExecutor.execute {
            try {
                val zipFile = runtime.workspaceManager.exportProjectZip(projectIdOrDir)
                val uri = OpenCodeFileProvider.uriForExportFile(zipFile)
                activity.runOnUiThread {
                    try {
                        val share = Intent(Intent.ACTION_SEND).apply {
                            type = "application/zip"
                            putExtra(Intent.EXTRA_STREAM, uri)
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        activity.startActivity(Intent.createChooser(share, "Export ${zipFile.name}"))
                    } catch (_: Throwable) {
                    }
                }
            } catch (_: Throwable) {
            }
        }
    }
}
