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
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsetsController
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout

class MainActivity : Activity() {

    companion object {
        private const val REQ_FILE_CHOOSER = 2001
        private const val REQ_NOTIFICATIONS = 2002
    }

    private lateinit var webView: WebView
    private var daemonService: OpenCodeDaemonService? = null
    private var serviceBound = false
    private var uiLoaded = false
    private var fileUploadCallback: ValueCallback<Array<Uri>>? = null

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as? OpenCodeDaemonService.LocalBinder
            daemonService = binder?.getService()
            serviceBound = true
            loadOpenCodeUiIfNeeded()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBound = false
            daemonService = null
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        applySystemBarsTheme("#131010", true)
        requestNotificationPermissionIfNeeded()

        val rootLayout = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#131010"))
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        webView = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#131010"))
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                mediaPlaybackRequiresUserGesture = false
                mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                cacheMode = WebSettings.LOAD_DEFAULT
                textZoom = 100
            }

            addJavascriptInterface(
                NativeBridge(this@MainActivity) { daemonService },
                "OpenCodeAndroid"
            )

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    val uri = request?.url ?: return false
                    val host = uri.host ?: ""
                    if (host == "127.0.0.1" || host == "localhost" || uri.scheme == "file") {
                        return false
                    }
                    return try {
                        startActivity(Intent(Intent.ACTION_VIEW, uri))
                        true
                    } catch (_: Exception) {
                        false
                    }
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest?) {
                    request?.grant(request.resources)
                }

                override fun onShowFileChooser(
                    webView: WebView?,
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
                    } catch (_: Exception) {
                        fileUploadCallback = null
                        false
                    }
                }
            }
        }

        rootLayout.addView(webView)
        setContentView(rootLayout)

        // Track Android soft keyboard height smoothly for floating composer
        val density = resources.displayMetrics.density
        rootLayout.viewTreeObserver.addOnGlobalLayoutListener {
            val r = Rect()
            rootLayout.getWindowVisibleDisplayFrame(r)
            val screenHeight = rootLayout.rootView.height
            val keypadPx = screenHeight - r.bottom
            val cssPx = if (keypadPx > screenHeight * 0.14) (keypadPx / density).toInt() else 0
            webView.evaluateJavascript(
                "window.__onAndroidKeyboardInset && window.__onAndroidKeyboardInset($cssPx);",
                null
            )
        }

        // Start & bind OpenCode Foreground Daemon Service!
        val serviceIntent = Intent(this, OpenCodeDaemonService::class.java)
        startForegroundService(serviceIntent)
        bindService(serviceIntent, connection, Context.BIND_AUTO_CREATE)
    }

    private fun loadOpenCodeUiIfNeeded() {
        if (uiLoaded) return
        val port = daemonService?.daemonPort ?: 0
        if (port > 0) {
            uiLoaded = true
            webView.loadUrl("http://127.0.0.1:$port/")
        } else {
            webView.postDelayed({ loadOpenCodeUiIfNeeded() }, 40)
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
            } catch (_: Exception) {}
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIFICATIONS)
            }
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
        webView.evaluateJavascript(
            "(function(){ return !!(window.__onAndroidBackPressed && window.__onAndroidBackPressed()); })()"
        ) { handled ->
            if (handled != "true") {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    @Suppress("DEPRECATION")
                    super.onBackPressed()
                }
            }
        }
    }

    override fun onDestroy() {
        if (serviceBound) {
            unbindService(connection)
            serviceBound = false
        }
        super.onDestroy()
    }
}
