package com.spirexa.app.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.spirexa.app.data.*
import com.spirexa.app.ui.*

@Composable
private fun SectionTitle(text: String) = Text(
    text.uppercase(),
    color = Spx.Muted,
    fontSize = 10.sp,
    fontWeight = FontWeight.SemiBold,
    letterSpacing = 1.6.sp,
    modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
)

@Composable
private fun SeverityPill(severity: String, percent: Int?) {
    val c = Spx.severityColor(severity)
    Row(
        modifier = Modifier
            .background(c.copy(alpha = 0.14f), RoundedCornerShape(50))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            buildString {
                percent?.let { append("$it% · ") }
                append(severity)
            },
            color = c, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.4.sp,
        )
    }
}

/* ------------------------------- alerts ------------------------------- */

@Composable
fun AlertsScreen(alerts: List<Alert>, connected: Boolean) {
    Column(Modifier.fillMaxSize().background(Spx.Bg).padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Alerts", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Spx.Accent)
            Spacer(Modifier.weight(1f))
            Box(
                Modifier
                    .size(9.dp)
                    .background(if (connected) Spx.Low else Spx.Muted, RoundedCornerShape(50))
            )
            Spacer(Modifier.width(6.dp))
            Text(if (connected) "live" else "offline", fontSize = 11.sp, color = Spx.Muted)
        }
        Spacer(Modifier.height(4.dp))
        Text(
            "Warnings pushed from the district dashboard",
            fontSize = 12.sp, color = Spx.Muted,
        )
        Spacer(Modifier.height(16.dp))

        if (alerts.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("No alerts yet", color = Spx.Muted, fontSize = 14.sp)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "When an authority sends a warning it appears here",
                        color = Spx.Muted, fontSize = 11.sp,
                    )
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                items(alerts, key = { it.id }) { AlertCard(it) }
            }
        }
    }
}

@Composable
private fun AlertCard(alert: Alert) {
    var expanded by remember { mutableStateOf(true) }

    Column(
        Modifier
            .fillMaxWidth()
            .neu(radius = 22)
            .clickable { expanded = !expanded }
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            SeverityPill(alert.severity, alert.riskPercent?.let { Math.round(it).toInt() })
            Spacer(Modifier.weight(1f))
            Text(alert.sentAt.replace("T", "  "), fontSize = 10.sp, color = Spx.Muted)
        }
        Spacer(Modifier.height(10.dp))
        Text(
            alert.location.ifBlank { "Unnamed location" },
            fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = Spx.Ink,
        )
        if (alert.state.isNotBlank()) {
            Text(alert.state, fontSize = 11.sp, color = Spx.Muted)
        }

        if (expanded) {
            Spacer(Modifier.height(12.dp))
            alert.messages.forEach { m ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(bottom = 10.dp)
                        .glass(radius = 16)
                        .padding(12.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            m.language.uppercase(),
                            fontSize = 9.5.sp, letterSpacing = 1.2.sp,
                            fontWeight = FontWeight.Bold, color = Spx.Accent,
                        )
                        if (!m.verified) {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "unverified translation",
                                fontSize = 9.sp, color = Spx.Moderate,
                            )
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(m.text, fontSize = 13.sp, color = Spx.Ink, lineHeight = 19.sp)
                }
            }
            Text("sent by ${alert.sentBy}", fontSize = 10.sp, color = Spx.Muted)
        }
    }
}

/* -------------------------------- map --------------------------------- */

// Same frame the web dashboard projects into, so the two agree.
private const val LON_MIN = 87.5f
private const val LON_MAX = 97.8f
private const val LAT_MIN = 21.5f
private const val LAT_MAX = 29.8f

@Composable
fun MapScreen(hotspots: List<Hotspot>, onSelect: (Hotspot) -> Unit) {
    var selected by remember { mutableStateOf<Hotspot?>(null) }

    Column(Modifier.fillMaxSize().background(Spx.Bg).padding(16.dp)) {
        Text("Risk map", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Spx.Accent)
        Text(
            "${hotspots.size} monitored slopes across the eight NER states",
            fontSize = 12.sp, color = Spx.Muted,
        )
        Spacer(Modifier.height(14.dp))

        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio((LON_MAX - LON_MIN) / (LAT_MAX - LAT_MIN))
                .neu(radius = 24)
                .padding(10.dp),
        ) {
            Canvas(Modifier.fillMaxSize()) {
                hotspots.forEach { h ->
                    val fx = (h.lon - LON_MIN) / (LON_MAX - LON_MIN)
                    val fy = (LAT_MAX - h.lat) / (LAT_MAX - LAT_MIN)
                    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return@forEach
                    val c = Spx.severityColor(h.severity)
                    val p = Offset(fx.toFloat() * size.width, fy.toFloat() * size.height)
                    drawCircle(c.copy(alpha = 0.22f), radius = 11f, center = p)
                    drawCircle(c, radius = 4.5f, center = p)
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        SectionTitle("Highest risk right now")

        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(hotspots.sortedByDescending { it.risk }.take(40), key = { it.id }) { h ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .neu(radius = 16, elevation = 4)
                        .clickable { selected = h; onSelect(h) }
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .size(10.dp)
                            .background(Spx.severityColor(h.severity), RoundedCornerShape(50))
                    )
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            h.location.ifBlank { h.id },
                            fontSize = 13.sp, color = Spx.Ink, maxLines = 1,
                        )
                        Text(h.state, fontSize = 10.sp, color = Spx.Muted)
                    }
                    Text(
                        "${h.riskPercent}%",
                        fontSize = 15.sp, fontWeight = FontWeight.Bold,
                        color = Spx.severityColor(h.severity),
                    )
                }
            }
        }
    }
}

/* ------------------------------ settings ------------------------------ */

@Composable
fun SettingsScreen(
    station: Station?,
    onSave: (String) -> Unit,
) {
    var url by remember { mutableStateOf(Api.baseUrl) }

    Column(
        Modifier
            .fillMaxSize()
            .background(Spx.Bg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Text("Setup", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Spx.Accent)
        Spacer(Modifier.height(16.dp))

        SectionTitle("Server")
        Column(Modifier.fillMaxWidth().neu(radius = 20).padding(16.dp)) {
            Text(
                "Address of the laptop running SPIREXA, on this same WiFi. "
                    + "Start it there with  ./run.sh --lan",
                fontSize = 11.5.sp, color = Spx.Muted, lineHeight = 16.sp,
            )
            Spacer(Modifier.height(12.dp))
            Box(Modifier.fillMaxWidth().neuInset().padding(12.dp)) {
                BasicTextField(
                    value = url,
                    onValueChange = { url = it },
                    singleLine = true,
                    textStyle = TextStyle(
                        fontSize = 13.sp, color = Spx.Ink, fontFamily = FontFamily.Monospace,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Spacer(Modifier.height(12.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(Spx.Accent, RoundedCornerShape(14.dp))
                    .clickable { onSave(url.trim()) }
                    .padding(vertical = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text("Save and reconnect", color = Color.White, fontSize = 13.sp,
                     fontWeight = FontWeight.SemiBold)
            }
        }

        Spacer(Modifier.height(20.dp))
        SectionTitle("Ground sensor")
        Column(Modifier.fillMaxWidth().glass(radius = 20).padding(16.dp)) {
            if (station == null || !station.connected) {
                Text("No station connected", fontSize = 13.sp, color = Spx.Muted)
                Spacer(Modifier.height(4.dp))
                Text(
                    "The dashboard reports no live node. Nothing is fabricated "
                        + "when the hardware is absent.",
                    fontSize = 11.sp, color = Spx.Muted, lineHeight = 15.sp,
                )
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(9.dp).background(Spx.Low, RoundedCornerShape(50)))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "${station.nodeId ?: "node"} connected"
                            + if (station.simulated) "  (simulated)" else "",
                        fontSize = 13.sp, color = Spx.Ink, fontWeight = FontWeight.SemiBold,
                    )
                }
                Spacer(Modifier.height(12.dp))
                station.readings.forEach { (k, v) ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                        Text(
                            k.replace('_', ' '),
                            fontSize = 12.sp, color = Spx.Muted, modifier = Modifier.weight(1f),
                        )
                        Text(
                            if (v % 1.0 == 0.0) v.toInt().toString() else String.format("%.1f", v),
                            fontSize = 12.sp, color = Spx.Ink, fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }

        Spacer(Modifier.height(20.dp))
        Text(
            buildAnnotatedString {
                append("SPIREXA advises; the responsible authority decides. ")
                withStyle(SpanStyle(color = Spx.Muted)) {
                    append("Alerts shown here are recommendations, not instructions.")
                }
            },
            fontSize = 10.5.sp, color = Spx.Muted, lineHeight = 15.sp,
        )
    }
}
