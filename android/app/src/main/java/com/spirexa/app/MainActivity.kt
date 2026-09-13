package com.spirexa.app

import android.Manifest
import android.content.Context
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.spirexa.app.data.*
import com.spirexa.app.screens.*
import com.spirexa.app.service.AlertWatchService
import com.spirexa.app.ui.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {

    private val askNotifications =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences(AlertWatchService.PREFS, Context.MODE_PRIVATE)
        prefs.getString("base_url", null)?.let { Api.baseUrl = it }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        AlertWatchService.start(this)

        setContent { SpirexaTheme { AppRoot(prefs) } }
    }
}

private enum class Tab(val label: String) { ALERTS("Alerts"), MAP("Map"), SETUP("Setup") }

@Composable
private fun AppRoot(prefs: android.content.SharedPreferences) {
    var tab by remember { mutableStateOf(Tab.ALERTS) }
    var alerts by remember { mutableStateOf<List<Alert>>(emptyList()) }
    var hotspots by remember { mutableStateOf<List<Hotspot>>(emptyList()) }
    var station by remember { mutableStateOf<Station?>(null) }
    var connected by remember { mutableStateOf(false) }
    var reconnectToken by remember { mutableStateOf(0) }

    // Alerts refresh quickly; the hotspot table is 311 rows and barely moves,
    // so it is fetched once per connection rather than on every tick.
    LaunchedEffect(reconnectToken) {
        while (true) {
            val ok = withContext(Dispatchers.IO) { Api.health() }
            connected = ok
            if (ok) {
                if (hotspots.isEmpty()) {
                    hotspots = withContext(Dispatchers.IO) {
                        runCatching { Api.hotspots() }.getOrDefault(emptyList())
                    }
                }
                station = withContext(Dispatchers.IO) { Api.station() }
                val seen = withContext(Dispatchers.IO) {
                    runCatching { Api.alertsSince(0).first }.getOrDefault(emptyList())
                }
                if (seen.isNotEmpty()) alerts = seen.sortedByDescending { it.id }
            }
            delay(5000)
        }
    }

    Column(Modifier.fillMaxSize().background(Spx.Bg)) {
        Box(Modifier.weight(1f)) {
            when (tab) {
                Tab.ALERTS -> AlertsScreen(alerts, connected)
                Tab.MAP -> MapScreen(hotspots) { }
                Tab.SETUP -> SettingsScreen(station) { url ->
                    Api.baseUrl = url
                    prefs.edit().putString("base_url", url).apply()
                    hotspots = emptyList()
                    reconnectToken++
                }
            }
        }
        NeuTabBar(tab) { tab = it }
    }
}

@Composable
private fun NeuTabBar(current: Tab, onPick: (Tab) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .neu(radius = 26, elevation = 8)
            .padding(6.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Tab.entries.forEach { t ->
            val active = t == current
            Box(
                Modifier
                    .weight(1f)
                    .then(
                        if (active) Modifier.background(Spx.Accent, RoundedCornerShape(20.dp))
                        else Modifier.neuInset(20)
                    )
                    .clickable { onPick(t) }
                    .padding(vertical = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    t.label,
                    color = if (active) Color.White else Spx.Muted,
                    fontSize = 12.5.sp,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                )
            }
        }
    }
}
