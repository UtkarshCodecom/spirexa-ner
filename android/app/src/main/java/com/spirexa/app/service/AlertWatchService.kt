package com.spirexa.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.spirexa.app.MainActivity
import com.spirexa.app.data.Alert
import com.spirexa.app.data.Api
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Watches the server for alerts pushed from the dashboard and raises a system
 * notification for each one.
 *
 * A foreground service polling every few seconds rather than Firebase: the
 * server is a laptop on the same WiFi, often with no route to the internet at
 * all, so FCM could not deliver even if it were configured. Polling also
 * keeps the whole thing account-free and inspectable.
 */
class AlertWatchService : Service() {

    companion object {
        const val CHANNEL_ONGOING = "spirexa_watch"
        const val CHANNEL_ALERTS = "spirexa_alerts"
        const val PREFS = "spirexa"
        const val KEY_LAST_ID = "last_alert_id"
        private const val POLL_MS = 5000L

        fun start(ctx: Context) {
            val i = Intent(ctx, AlertWatchService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }

        fun stop(ctx: Context) = ctx.stopService(Intent(ctx, AlertWatchService::class.java))
    }

    private var job: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
        startForeground(1, ongoingNotification("Watching for alerts"))
        job = CoroutineScope(Dispatchers.IO).launch { pollLoop() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        job?.cancel()
        super.onDestroy()
    }

    private suspend fun pollLoop() {
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        while (currentCoroutineContext().isActive) {
            try {
                val lastId = prefs.getInt(KEY_LAST_ID, 0)
                val (alerts, latest) = Api.alertsSince(lastId)
                alerts.forEach { raiseAlert(it) }
                if (latest > lastId) prefs.edit().putInt(KEY_LAST_ID, latest).apply()
            } catch (e: Exception) {
                // Offline or the laptop moved networks. Keep waiting quietly;
                // a field device losing signal is expected, not an error state.
            }
            delay(POLL_MS)
        }
    }

    private fun createChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ONGOING, "Alert watch", NotificationManager.IMPORTANCE_MIN)
        )
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ALERTS, "Landslide alerts", NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Warnings sent by the district control room"
                enableVibration(true)
            }
        )
    }

    private fun ongoingNotification(text: String) =
        NotificationCompat.Builder(this, CHANNEL_ONGOING)
            .setContentTitle("SPIREXA")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .build()

    private fun raiseAlert(alert: Alert) {
        val open = PendingIntent.getActivity(
            this, alert.id,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        // Both languages in one notification: the English line as the summary,
        // the local-language text expanded beneath. A recipient who reads only
        // one of the two still gets the warning without opening the app.
        val english = alert.messages.firstOrNull { it.code == "en" }?.text.orEmpty()
        val local = alert.messages.firstOrNull { it.code != "en" }
        val body = buildString {
            append(english)
            if (local != null) {
                append("\n\n")
                append(local.text)
            }
        }

        val title = buildString {
            append(alert.severity)
            alert.riskPercent?.let { append(" · ${Math.round(it)}%") }
            if (alert.location.isNotBlank()) append(" · ${alert.location.take(40)}")
        }

        val n = NotificationCompat.Builder(this, CHANNEL_ALERTS)
            .setContentTitle(title)
            .setContentText(english.take(120))
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentIntent(open)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        androidx.core.app.NotificationManagerCompat.from(this)
            .let { mgr ->
                try { mgr.notify(1000 + alert.id, n) } catch (se: SecurityException) {
                    // POST_NOTIFICATIONS not granted yet; the in-app list still shows it.
                }
            }
    }
}
