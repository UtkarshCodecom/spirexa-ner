package com.spirexa.app

import android.Manifest
import android.content.Context
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
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
        enableEdgeToEdge()

        val prefs = getSharedPreferences(AlertWatchService.PREFS, Context.MODE_PRIVATE)
        prefs.getString("base_url", null)?.let { Api.baseUrl = it }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        AlertWatchService.start(this)

        setContent { SpirexaTheme { AuroraBackground { AppRoot(prefs) } } }
    }
}

private enum class Tab(val label: String, val glyph: String) {
    ALERTS("Alerts", "▲"),
    MAP("Map", "◉"),
    SETUP("Setup", "⚙"),
}

@Composable
private fun AppRoot(prefs: android.content.SharedPreferences) {
    var tab by remember { mutableStateOf(Tab.ALERTS) }
    var alerts by remember { mutableStateOf<List<Alert>>(emptyList()) }
    var hotspots by remember { mutableStateOf<List<Hotspot>>(emptyList()) }
    var geo by remember { mutableStateOf<Geo?>(null) }
    var station by remember { mutableStateOf<Station?>(null) }
    var connected by remember { mutableStateOf(false) }
    var reconnectToken by remember { mutableIntStateOf(0) }

    // Alerts refresh quickly; the hotspot table is 311 rows and the map
    // geometry never changes at all, so both are fetched once per connection
    // rather than on every tick.
    LaunchedEffect(reconnectToken) {
        while (true) {
            val ok = withContext(Dispatchers.IO) { Api.health() }
            connected = ok
            if (ok) {
                if (geo == null) {
                    geo = withContext(Dispatchers.IO) { Api.geo() }
                }
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

    Column(
        Modifier
            .fillMaxSize()
            .windowInsetsPadding(WindowInsets.systemBars)
    ) {
        Box(Modifier.weight(1f)) {
            when (tab) {
                Tab.ALERTS -> AlertsScreen(alerts, connected)
                Tab.MAP -> MapScreen(geo, hotspots, loading = !connected || hotspots.isEmpty())
                Tab.SETUP -> SettingsScreen(station, connected) { url ->
                    Api.baseUrl = url
                    prefs.edit().putString("base_url", url).apply()
                    hotspots = emptyList()
                    geo = null
                    reconnectToken++
                }
            }
        }
        TabBar(tab, alerts.size) { tab = it }
    }
}

@Composable
private fun TabBar(current: Tab, alertCount: Int, onPick: (Tab) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 18.dp, vertical = 10.dp)
            .glass(radius = 22.dp, elevation = 14.dp)
            .padding(5.dp),
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Tab.entries.forEach { t ->
            val active = t == current
            val lift by animateFloatAsState(if (active) 1f else 0f, tween(180), label = "tab")
            Box(
                Modifier
                    .weight(1f)
                    .graphicsLayer { scaleX = 1f + 0.02f * lift; scaleY = 1f + 0.02f * lift }
                    .then(
                        if (active) Modifier.background(
                            Brush.horizontalGradient(listOf(Color(0xFF3D6FD8), Spx.Accent)),
                            RoundedCornerShape(17.dp),
                        ) else Modifier
                    )
                    .clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                    ) { onPick(t) }
                    .padding(vertical = 11.dp),
                contentAlignment = Alignment.Center,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        t.glyph,
                        color = if (active) Color.White else Spx.Faint,
                        fontSize = 11.sp,
                    )
                    Box(Modifier.width(7.dp))
                    Text(
                        t.label,
                        color = if (active) Color.White else Spx.Muted,
                        fontSize = 12.5.sp,
                        fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                    )
                    if (t == Tab.ALERTS && alertCount > 0 && !active) {
                        Box(Modifier.width(6.dp))
                        Box(
                            Modifier
                                .size(6.dp)
                                .background(Spx.Severe, RoundedCornerShape(50))
                        )
                    }
                }
            }
        }
    }
}
