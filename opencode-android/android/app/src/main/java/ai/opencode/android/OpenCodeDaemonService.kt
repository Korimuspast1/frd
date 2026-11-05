package ai.opencode.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.os.PowerManager

class OpenCodeDaemonService : Service() {

    companion object {
        const val CHANNEL_ID = "opencode_daemon_channel"
        const val NOTIFICATION_ID = 4096
        const val ACTION_STOP_DAEMON = "ai.opencode.android.STOP_DAEMON"
    }

    inner class LocalBinder : Binder() {
        fun getService(): OpenCodeDaemonService = this@OpenCodeDaemonService
    }

    private val binder = LocalBinder()
    lateinit var workspaceManager: WorkspaceManager
        private set
    private lateinit var shellExecutor: ShellExecutor
    private lateinit var httpDaemon: LocalHttpDaemon
    private var wakeLock: PowerManager.WakeLock? = null

    val daemonPort: Int
        get() = if (::httpDaemon.isInitialized) httpDaemon.port else 0

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        workspaceManager = WorkspaceManager(applicationContext)
        shellExecutor = ShellExecutor(applicationContext)
        httpDaemon = LocalHttpDaemon(
            applicationContext,
            workspaceManager,
            shellExecutor
        ) { statusText, busy ->
            updateForegroundNotification(statusText, busy)
        }
        httpDaemon.start()

        val initialNotification = buildNotification(
            getString(R.string.daemon_notification_idle),
            false
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                initialNotification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(NOTIFICATION_ID, initialNotification)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_DAEMON) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder

    fun updateForegroundNotification(statusText: String, busy: Boolean) {
        try {
            if (busy) {
                if (wakeLock?.isHeld != true) {
                    val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                    wakeLock = pm.newWakeLock(
                        PowerManager.PARTIAL_WAKE_LOCK,
                        "OpenCode::AgentWakeLock"
                    ).apply {
                        acquire(15 * 60 * 1000L)
                    }
                }
            } else {
                if (wakeLock?.isHeld == true) {
                    wakeLock?.release()
                }
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIFICATION_ID, buildNotification(statusText, busy))
        } catch (_: Exception) {}
    }

    fun sendTaskAlertNotification(title: String, body: String) {
        try {
            val openIntent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            val pi = PendingIntent.getActivity(this, 102, openIntent, pendingFlags)

            val notification = Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_opencode)
                .setContentTitle(title)
                .setContentText(body)
                .setContentIntent(pi)
                .setAutoCancel(true)
                .build()

            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify((System.currentTimeMillis() % 10000).toInt() + 5000, notification)
        } catch (_: Exception) {}
    }

    private fun buildNotification(statusText: String, busy: Boolean): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val contentPi = PendingIntent.getActivity(this, 100, openIntent, pendingFlags)

        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_opencode)
            .setContentTitle(if (busy) "OpenCode выполняет задачу…" else getString(R.string.daemon_notification_title))
            .setContentText(statusText)
            .setContentIntent(contentPi)
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.daemon_channel_name),
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Поддерживает локальный демон и выполнение ИИ-агента OpenCode в фоновом режиме"
            setShowBadge(false)
        }
        nm.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
        } catch (_: Exception) {}
        if (::httpDaemon.isInitialized) httpDaemon.stop()
        super.onDestroy()
    }
}
