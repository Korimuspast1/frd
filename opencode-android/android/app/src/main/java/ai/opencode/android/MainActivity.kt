package ai.opencode.android

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Rect
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsetsController
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import java.io.ByteArrayInputStream

class MainActivity : Activity() {

    companion object {
        private const val REQ_FILE_CHOOSER = 2001
        private const val REQ_NOTIFICATIONS = 2002
        private const val APP_ORIGIN = "http://opencode.local/"
    }

    private var webView: WebView? = null
    private lateinit var runtime: OpenCodeRuntime
    private var serviceBound = false
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            serviceBound = true
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBound = false
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Initialize background runtime (starts workspace + LocalHttpDaemon strictly on worker threads)
        runtime = OpenCodeRuntime.getInstance(applicationContext)

        applySystemBarsTheme("#080808", true)

        val rootLayout = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#080808"))
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        val createdWebView = try {
            WebView(this)
        } catch (t: Throwable) {
            null
        }

        if (createdWebView == null) {
            val fallbackLabel = TextView(this).apply {
                text = "Android System WebView is unavailable on this device.\nPlease enable or update Android System WebView."
                setTextColor(Color.WHITE)
                textSize = 15f
                gravity = Gravity.CENTER
                setPadding(48, 48, 48, 48)
            }
            rootLayout.addView(fallbackLabel)
            setContentView(rootLayout)
            return
        }

        webView = createdWebView.apply {
            setBackgroundColor(Color.parseColor("#080808"))
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                allowFileAccess = false
                allowContentAccess = true
                mediaPlaybackRequiresUserGesture = false
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                cacheMode = WebSettings.LOAD_DEFAULT
                textZoom = 100
                setSupportMultipleWindows(false)
            }

            val bridge = NativeBridge(this@MainActivity, runtime) { webView }
            addJavascriptInterface(bridge, "OpenCodeNative")
            addJavascriptInterface(bridge, "OpenCodeAndroid")

            webViewClient = object : WebViewClient() {
                override fun shouldInterceptRequest(
                    view: WebView?,
                    request: WebResourceRequest?
                ): WebResourceResponse? {
                    val uri = request?.url ?: return null
                    val host = (uri.host ?: "").lowercase()
                    if (host != "opencode.local") {
                        return super.shouldInterceptRequest(view, request)
                    }
                    return serveBundledAsset(uri.path ?: "/", request.method ?: "GET")
                }

                override fun shouldOverrideUrlLoading(
                    view: WebView?,
                    request: WebResourceRequest?
                ): Boolean {
                    val uri = request?.url ?: return false
                    val host = (uri.host ?: "").lowercase()
                    if (host == "opencode.local" || host == "127.0.0.1" || host == "localhost") {
                        return false
                    }
                    return try {
                        startActivity(Intent(Intent.ACTION_VIEW, uri))
                        true
                    } catch (_: Throwable) {
                        true
                    }
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest?) {
                    try {
                        request?.grant(request.resources)
                    } catch (_: Throwable) {
                    }
                }

                override fun onShowFileChooser(
                    view: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: FileChooserParams?
                ): Boolean {
                    fileUploadCallback?.onReceiveValue(null)
                    fileUploadCallback = filePathCallback
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = "*/*"
                        putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    }
                    return try {
                        startActivityForResult(intent, REQ_FILE_CHOOSER)
                        true
                    } catch (_: Throwable) {
                        fileUploadCallback = null
                        false
                    }
                }
            }
        }

        rootLayout.addView(createdWebView)
        setContentView(rootLayout)

        // Load literal upstream @opencode/app immediately from APK assets!
        createdWebView.loadUrl(APP_ORIGIN)

        // Track Android soft keyboard height smoothly
        val density = resources.displayMetrics.density
        rootLayout.viewTreeObserver.addOnGlobalLayoutListener {
            try {
                val r = Rect()
                rootLayout.getWindowVisibleDisplayFrame(r)
                val screenHeight = rootLayout.rootView.height
                val keypadPx = screenHeight - r.bottom
                val cssPx = if (keypadPx > screenHeight * 0.14) (keypadPx / density).toInt() else 0
                webView?.evaluateJavascript(
                    "document.documentElement.style.setProperty('--keyboard-inset', '${cssPx}px');",
                    null
                )
            } catch (_: Throwable) {
            }
        }

        // Start & bind background Foreground Daemon Service safely (never fatal if restricted by OEM)
        startDaemonServiceSafely()
        requestNotificationPermissionSafely()
    }

    private fun startDaemonServiceSafely() {
        try {
            val serviceIntent = Intent(this, OpenCodeDaemonService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
        } catch (_: Throwable) {
        }
    }

    private fun serveBundledAsset(rawPath: String, method: String): WebResourceResponse {
        val corsHeaders = HashMap<String, String>().apply {
            put("Access-Control-Allow-Origin", "*")
            put("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            put("Access-Control-Allow-Headers", "*")
        }

        if (method.equals("OPTIONS", ignoreCase = true)) {
            return WebResourceResponse(
                "text/plain",
                "UTF-8",
                204,
                "No Content",
                corsHeaders,
                ByteArrayInputStream(ByteArray(0))
            )
        }

        val normalized = rawPath.trimStart('/').ifEmpty { "index.html" }
        val assetPath = "www/$normalized"

        return try {
            val stream = assets.open(assetPath)
            val mime = guessAssetMime(normalized)
            val encoding = if (mime.startsWith("text/") || mime.contains("javascript") || mime.contains("json")) "UTF-8" else null
            if (normalized.startsWith("_assets/")) {
                corsHeaders["Cache-Control"] = "public, max-age=31536000, immutable"
            } else {
                corsHeaders["Cache-Control"] = "no-cache"
            }
            WebResourceResponse(mime, encoding, 200, "OK", corsHeaders, stream)
        } catch (_: Throwable) {
            // SPA client-side router fallback -> www/index.html for routes without file extension
            val lastSegment = normalized.substringAfterLast('/')
            if (!lastSegment.contains('.')) {
                return try {
                    val indexStream = assets.open("www/index.html")
                    corsHeaders["Cache-Control"] = "no-cache"
                    WebResourceResponse("text/html", "UTF-8", 200, "OK", corsHeaders, indexStream)
                } catch (_: Throwable) {
                    WebResourceResponse(
                        "text/plain",
                        "UTF-8",
                        404,
                        "Not Found",
                        corsHeaders,
                        ByteArrayInputStream("Asset not found".toByteArray(Charsets.UTF_8))
                    )
                }
            }
            WebResourceResponse(
                "text/plain",
                "UTF-8",
                404,
                "Not Found",
                corsHeaders,
                ByteArrayInputStream(ByteArray(0))
            )
        }
    }

    private fun guessAssetMime(path: String): String {
        val lower = path.lowercase()
        return when {
            lower.endsWith(".html") -> "text/html"
            lower.endsWith(".js") || lower.endsWith(".mjs") -> "text/javascript"
            lower.endsWith(".css") -> "text/css"
            lower.endsWith(".json") -> "application/json"
            lower.endsWith(".webmanifest") -> "application/manifest+json"
            lower.endsWith(".wasm") -> "application/wasm"
            lower.endsWith(".svg") -> "image/svg+xml"
            lower.endsWith(".png") -> "image/png"
            lower.endsWith(".jpg") || lower.endsWith(".jpeg") -> "image/jpeg"
            lower.endsWith(".webp") -> "image/webp"
            lower.endsWith(".gif") -> "image/gif"
            lower.endsWith(".ico") -> "image/x-icon"
            lower.endsWith(".woff2") -> "font/woff2"
            lower.endsWith(".woff") -> "font/woff"
            lower.endsWith(".ttf") -> "font/ttf"
            lower.endsWith(".aac") -> "audio/aac"
            lower.endsWith(".mp3") -> "audio/mpeg"
            else -> "application/octet-stream"
        }
    }

    fun applySystemBarsTheme(bgHex: String, isDark: Boolean) {
        runOnUiThread {
            try {
                val color = Color.parseColor(bgHex)
                window.statusBarColor = color
                window.navigationBarColor = color
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    val controller = window.insetsController
                    val mask = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or
                        WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
                    controller?.setSystemBarsAppearance(if (isDark) 0 else mask, mask)
                } else {
                    @Suppress("DEPRECATION")
                    var vis = window.decorView.systemUiVisibility
                    @Suppress("DEPRECATION")
                    vis = if (isDark) {
                        vis and View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR.inv()
                    } else {
                        vis or View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                    }
                    @Suppress("DEPRECATION")
                    window.decorView.systemUiVisibility = vis
                }
            } catch (_: Throwable) {
            }
        }
    }

    private fun requestNotificationPermissionSafely() {
        try {
            val perms = ArrayList<String>()
            if (Build.VERSION.SDK_INT >= 33) {
                if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                    perms.add(Manifest.permission.POST_NOTIFICATIONS)
                }
            }
            if (Build.VERSION.SDK_INT < 30) {
                if (checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                    perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    perms.add(Manifest.permission.READ_EXTERNAL_STORAGE)
                }
            }
            if (perms.isNotEmpty()) {
                requestPermissions(perms.toTypedArray(), REQ_NOTIFICATIONS)
            }
            if (Build.VERSION.SDK_INT >= 30 && !android.os.Environment.isExternalStorageManager()) {
                val intent = Intent(
                    android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
        } catch (_: Throwable) {
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQ_FILE_CHOOSER) {
            val cb = fileUploadCallback ?: return
            fileUploadCallback = null
            if (resultCode != RESULT_OK || data == null) {
                cb.onReceiveValue(null)
                return
            }
            val uris = ArrayList<Uri>()
            val clip = data.clipData
            if (clip != null) {
                for (i in 0 until clip.itemCount) {
                    uris.add(clip.getItemAt(i).uri)
                }
            } else {
                data.data?.let { uris.add(it) }
            }
            cb.onReceiveValue(uris.toTypedArray())
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        val wv = webView
        if (wv != null && wv.canGoBack()) {
            wv.goBack()
            return
        }
        @Suppress("DEPRECATION")
        super.onBackPressed()
    }

    override fun onDestroy() {
        if (serviceBound) {
            try {
                unbindService(connection)
            } catch (_: Throwable) {
            }
            serviceBound = false
        }
        super.onDestroy()
    }
}
