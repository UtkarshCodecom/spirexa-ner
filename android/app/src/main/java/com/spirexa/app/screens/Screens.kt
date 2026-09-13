package com.spirexa.app.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.spirexa.app.data.*
import com.spirexa.app.ui.*

/* ------------------------------ shared bits ------------------------------ */

@Composable
private fun SeverityPill(severity: String, percent: Int?) {
    val c = Spx.severityColor(severity)
    Row(
        Modifier
            .background(c.copy(alpha = 0.16f), RoundedCornerShape(50))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(6.dp).background(c, RoundedCornerShape(50)))
        Box(Modifier.width(7.dp))
        Text(
            buildString { percent?.let { append("$it%  ") }; append(severity) },
            color = c, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.6.sp,
        )
    }
}

/** Left edge painted in the severity colour -- readable before any text is. */
@Composable
private fun SeverityEdge(severity: String, height: Dp = 0.dp) {
    val c = Spx.severityColor(severity)
    Box(
        Modifier
            .width(3.dp)
            .then(if (height > 0.dp) Modifier.height(height) else Modifier.fillMaxHeight())
            .background(
                Brush.verticalGradient(listOf(c, c.copy(alpha = 0.25f))),
                RoundedCornerShape(50),
            )
    )
}

@Composable
private fun EmptyState(title: String, body: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(58.dp).glass(radius = 50.dp, elevation = 0.dp),
            contentAlignment = Alignment.Center,
        ) { Text("◎", fontSize = 24.sp, color = Spx.Faint) }
        Spacer(Modifier.height(16.dp))
        Text(title, color = Spx.Muted, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        Text(
            body, color = Spx.Faint, fontSize = 12.sp, lineHeight = 18.sp,
            modifier = Modifier.padding(horizontal = 36.dp),
        )
    }
}

/* -------------------------------- alerts -------------------------------- */

@Composable
fun AlertsScreen(alerts: List<Alert>, connected: Boolean) {
    Column(Modifier.fillMaxSize().padding(horizontal = 18.dp)) {
        Spacer(Modifier.height(14.dp))
        ScreenTitle(
            "Alerts",
            "Warnings pushed from the district dashboard",
        ) { StatusDot(connected, if (connected) "live" else "offline") }
        Spacer(Modifier.height(18.dp))

        if (alerts.isEmpty()) {
            EmptyState(
                "No alerts yet",
                "When an authority sends a warning from the dashboard it lands here, "
                    + "in every language that district uses.",
            )
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(bottom = 18.dp),
            ) {
                itemsIndexed(alerts, key = { _, a -> a.id }) { i, a -> AlertCard(a, startOpen = i == 0) }
            }
        }
    }
}

@Composable
private fun AlertCard(alert: Alert, startOpen: Boolean) {
    var expanded by remember { mutableStateOf(startOpen) }
    val turn by animateFloatAsState(if (expanded) 1f else 0f, tween(180), label = "turn")

    Row(
        Modifier
            .fillMaxWidth()
            .glass(radius = 20.dp)
            .clickable { expanded = !expanded }
            .height(IntrinsicSize.Min)
            .padding(14.dp),
    ) {
        SeverityEdge(alert.severity)
        Spacer(Modifier.width(13.dp))

        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SeverityPill(alert.severity, alert.riskPercent?.let { Math.round(it).toInt() })
                Spacer(Modifier.weight(1f))
                Text(
                    alert.sentAt.take(16).replace("T", "  "),
                    fontSize = 10.sp, color = Spx.Faint,
                )
            }
            Spacer(Modifier.height(11.dp))
            Text(
                alert.location.ifBlank { "Unnamed location" },
                fontSize = 16.sp, fontWeight = FontWeight.SemiBold,
                color = Spx.Ink, lineHeight = 21.sp,
            )
            if (alert.state.isNotBlank()) {
                Text(alert.state, fontSize = 11.5.sp, color = Spx.Muted)
            }

            AnimatedVisibility(expanded) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    alert.messages.forEach { m ->
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .padding(bottom = 8.dp)
                                .well(14.dp)
                                .padding(12.dp),
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    m.language.uppercase(),
                                    fontSize = 9.5.sp, letterSpacing = 1.4.sp,
                                    fontWeight = FontWeight.Bold, color = Spx.Accent,
                                )
                                if (!m.verified) {
                                    Spacer(Modifier.width(8.dp))
                                    Text("unverified translation",
                                        fontSize = 9.sp, color = Spx.Moderate)
                                }
                            }
                            Spacer(Modifier.height(7.dp))
                            Text(m.text, fontSize = 13.5.sp, color = Spx.Ink, lineHeight = 20.sp)
                        }
                    }
                    Text("sent by ${alert.sentBy}", fontSize = 10.sp, color = Spx.Faint)
                }
            }
            if (turn < 0.5f) {
                Spacer(Modifier.height(6.dp))
                Text("${alert.messages.size} languages — tap to read",
                    fontSize = 10.5.sp, color = Spx.Faint)
            }
        }
    }
}

/* --------------------------------- map ---------------------------------- */

@Composable
fun MapScreen(geo: Geo?, hotspots: List<Hotspot>, loading: Boolean) {
    var selected by remember { mutableStateOf<Hotspot?>(null) }
    val camera = remember { MapCamera() }

    Column(Modifier.fillMaxSize().padding(horizontal = 18.dp)) {
        Spacer(Modifier.height(14.dp))
        ScreenTitle(
            "Risk map",
            if (hotspots.isEmpty()) "waiting for the server"
            else "${hotspots.size} monitored slopes · ${hotspots.count { it.risk >= 0.5 }} above the alert line",
        )
        Spacer(Modifier.height(14.dp))

        Box(
            Modifier
                .fillMaxWidth()
                // the frame's own proportions: a taller box just letterboxes
                // the region and steals rows from the list below
                .aspectRatio((geo?.width ?: 900f) / (geo?.height ?: 804.5f))
                .glass(radius = 24.dp)
                .clip(RoundedCornerShape(24.dp))
        ) {
            NerMap(
                geo = geo,
                hotspots = hotspots,
                selected = selected,
                camera = camera,
                modifier = Modifier.fillMaxSize(),
                onSelect = { selected = it },
            ) {
                if (loading && hotspots.isEmpty()) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("loading map…", color = Spx.Faint, fontSize = 12.sp)
                    }
                }

                // zoom controls
                Column(
                    Modifier.align(Alignment.TopEnd).padding(10.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    MapButton("+") { camera.scale = (camera.scale * 1.6f).coerceAtMost(8f) }
                    MapButton("−") {
                        camera.scale = (camera.scale / 1.6f).coerceAtLeast(1f)
                        if (camera.scale <= 1.001f) camera.reset()
                    }
                    MapButton("1:1", small = true) { camera.reset() }
                }

                if (selected == null) {
                    Text(
                        "pinch to zoom · tap a point",
                        color = Spx.Faint, fontSize = 10.sp,
                        modifier = Modifier.align(Alignment.BottomStart).padding(12.dp),
                    )
                }

                selected?.let { h ->
                    Column(
                        Modifier
                            .align(Alignment.BottomCenter)
                            .padding(10.dp)
                            .fillMaxWidth()
                            // solid first, then the glass film over it: a
                            // purely translucent card over a busy map is a
                            // card nobody can read
                            .background(Spx.Bg.copy(alpha = 0.93f), RoundedCornerShape(18.dp))
                            .glass(radius = 18.dp)
                            .clickable { selected = null }
                            .padding(14.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            SeverityPill(h.severity, h.riskPercent)
                            Spacer(Modifier.weight(1f))
                            Text("tap to dismiss", fontSize = 9.5.sp, color = Spx.Faint)
                        }
                        Spacer(Modifier.height(9.dp))
                        Text(h.location.ifBlank { h.id }, fontSize = 14.5.sp,
                             fontWeight = FontWeight.SemiBold, color = Spx.Ink, lineHeight = 19.sp)
                        Text(
                            "${h.state}  ·  ${"%.3f".format(h.lat)}, ${"%.3f".format(h.lon)}",
                            fontSize = 11.sp, color = Spx.Muted,
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        SectionTitle("Highest risk right now")

        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(bottom = 18.dp),
            modifier = Modifier.weight(1f),
        ) {
            items(hotspots.sortedByDescending { it.risk }.take(40), key = { it.id }) { h ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .glass(radius = 15.dp, elevation = 4.dp)
                        .clickable { selected = h }
                        .height(IntrinsicSize.Min)
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    SeverityEdge(h.severity, height = 26.dp)
                    Spacer(Modifier.width(11.dp))
                    Column(Modifier.weight(1f)) {
                        Text(h.location.ifBlank { h.id }, fontSize = 13.sp,
                             color = Spx.Ink, maxLines = 1)
                        Text(h.state, fontSize = 10.sp, color = Spx.Faint)
                    }
                    Text(
                        "${h.riskPercent}%",
                        fontSize = 16.sp, fontWeight = FontWeight.Bold,
                        color = Spx.severityColor(h.severity),
                    )
                }
            }
        }
    }
}

@Composable
private fun MapButton(label: String, small: Boolean = false, onClick: () -> Unit) {
    Box(
        Modifier
            .size(34.dp)
            .glass(radius = 11.dp, elevation = 3.dp)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = Spx.Ink, fontSize = if (small) 10.sp else 15.sp,
             fontWeight = FontWeight.Medium)
    }
}

/* ------------------------------- settings ------------------------------- */

@Composable
fun SettingsScreen(station: Station?, connected: Boolean, onSave: (String) -> Unit) {
    var url by remember { mutableStateOf(Api.baseUrl) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp),
    ) {
        Spacer(Modifier.height(14.dp))
        ScreenTitle("Setup", "Point the app at the machine running SPIREXA") {
            StatusDot(connected, if (connected) "connected" else "no server")
        }
        Spacer(Modifier.height(20.dp))

        SectionTitle("Server address")
        Column(Modifier.fillMaxWidth().glass(radius = 20.dp).padding(16.dp)) {
            Text(
                "The laptop running SPIREXA, on this same WiFi. Start it there with "
                    + "./run.sh --lan and use the address it prints.",
                fontSize = 12.sp, color = Spx.Muted, lineHeight = 18.sp,
            )
            Spacer(Modifier.height(14.dp))
            Box(Modifier.fillMaxWidth().well(13.dp).padding(13.dp)) {
                BasicTextField(
                    value = url,
                    onValueChange = { url = it },
                    singleLine = true,
                    cursorBrush = SolidColor(Spx.Accent),
                    textStyle = TextStyle(
                        fontSize = 13.sp, color = Spx.Ink, fontFamily = FontFamily.Monospace,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Spacer(Modifier.height(13.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.horizontalGradient(listOf(Color(0xFF3D6FD8), Spx.Accent)),
                        RoundedCornerShape(14.dp),
                    )
                    .clickable { onSave(url.trim()) }
                    .padding(vertical = 13.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text("Save and reconnect", color = Color.White, fontSize = 13.sp,
                     fontWeight = FontWeight.SemiBold)
            }
        }

        Spacer(Modifier.height(22.dp))
        SectionTitle("Ground sensor")
        Column(Modifier.fillMaxWidth().glass(radius = 20.dp).padding(16.dp)) {
            if (station == null || !station.connected) {
                Text("No station connected", fontSize = 13.5.sp, color = Spx.Muted,
                     fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "The dashboard reports no live node. Nothing is fabricated when "
                        + "the hardware is absent.",
                    fontSize = 11.5.sp, color = Spx.Faint, lineHeight = 17.sp,
                )
            } else {
                StatusDot(true, "${station.nodeId ?: "node"} connected"
                    + if (station.simulated) "  (simulated)" else "")
                Spacer(Modifier.height(14.dp))
                station.readings.entries.forEachIndexed { i, (k, v) ->
                    if (i > 0) Box(
                        Modifier.fillMaxWidth().height(1.dp)
                            .background(Color.White.copy(alpha = 0.06f))
                    )
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            k.replace('_', ' '),
                            fontSize = 12.sp, color = Spx.Muted, modifier = Modifier.weight(1f),
                        )
                        Text(
                            if (v % 1.0 == 0.0) v.toInt().toString() else "%.1f".format(v),
                            fontSize = 14.sp, color = Spx.Ink, fontWeight = FontWeight.SemiBold,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(22.dp))
        Column(Modifier.fillMaxWidth().well(16.dp).padding(14.dp)) {
            Text("SPIREXA advises; the responsible authority decides.",
                 fontSize = 11.5.sp, color = Spx.Muted, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text("Alerts shown here are recommendations, not instructions.",
                 fontSize = 11.sp, color = Spx.Faint, lineHeight = 16.sp)
        }
        Spacer(Modifier.height(24.dp))
    }
}
