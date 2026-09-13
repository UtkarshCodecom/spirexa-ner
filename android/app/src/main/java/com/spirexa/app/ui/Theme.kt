package com.spirexa.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * SPIREXA on a phone.
 *
 * The first cut of this was neumorphic: mid-grey cards on a mid-grey ground,
 * shaped only by a pair of shadows. That works on a desktop monitor in a lit
 * room, which is where the dashboard lives. On a phone held at arm's length
 * in an exhibition hall it collapses into flat grey — every card the same
 * value as the wall behind it, nothing to catch the eye.
 *
 * So: a dark ground with slow colour underneath it, and glass on top. Glass
 * needs something to refract; a light theme gives it nothing. The extruded
 * edge from neumorphism survives as the two-tone border on every surface --
 * bright along the top-left, dark along the bottom-right.
 */
object Spx {
    val Bg = Color(0xFF070B14)
    val BgLift = Color(0xFF0E1728)

    // aurora blobs behind the glass -- the only saturated colour in the app
    val AuroraA = Color(0xFF2B4C9B)
    val AuroraB = Color(0xFF12626F)
    val AuroraC = Color(0xFF4B2B7A)

    val Ink = Color(0xFFEAF0FB)
    val Muted = Color(0xFF8E9BB4)
    val Faint = Color(0xFF5C6982)
    val Accent = Color(0xFF6E9BFF)

    // Lifted from the dashboard's bands, then brightened: #15803D on black is
    // unreadable, and these have to be legible across a room.
    val Low = Color(0xFF34D399)
    val Moderate = Color(0xFFFBBF24)
    val High = Color(0xFFFB923C)
    val Severe = Color(0xFFF87171)

    // map
    val Water = Color(0xFF091423)
    val Land = Color(0xFF1B2E47)
    val LandEdge = Color(0xFF4A73AD)
    val RoadMajor = Color(0xFF9B7857)
    val RoadMinor = Color(0xFF6A5540)

    fun severityColor(s: String): Color = when (s.uppercase()) {
        "SEVERE" -> Severe
        "HIGH" -> High
        "MODERATE" -> Moderate
        else -> Low
    }
}

/** Frosted panel: translucent fill, plus the lit/shaded edge pair. */
fun Modifier.glass(
    radius: Dp = 22.dp,
    alpha: Float = 1f,
    elevation: Dp = 10.dp,
): Modifier = this
    .shadow(elevation, RoundedCornerShape(radius), clip = false,
        ambientColor = Color.Black, spotColor = Color.Black)
    .background(
        Brush.verticalGradient(
            listOf(
                Color.White.copy(alpha = 0.085f * alpha),
                Color.White.copy(alpha = 0.030f * alpha),
            )
        ),
        RoundedCornerShape(radius),
    )
    .border(
        width = 1.dp,
        brush = Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.22f * alpha),
                Color.White.copy(alpha = 0.04f * alpha),
                Color.Black.copy(alpha = 0.18f * alpha),
            )
        ),
        shape = RoundedCornerShape(radius),
    )

/** Pressed well, for inactive tabs and text fields. */
fun Modifier.well(radius: Dp = 16.dp): Modifier = this
    .background(Color.Black.copy(alpha = 0.28f), RoundedCornerShape(radius))
    .border(1.dp, Color.White.copy(alpha = 0.07f), RoundedCornerShape(radius))

/** Slow colour under the glass. Static -- an animated one is a battery bill. */
@Composable
fun AuroraBackground(content: @Composable () -> Unit) {
    Box(
        Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(Spx.BgLift, Spx.Bg)))
            .drawBehind {
                fun blob(c: Color, cx: Float, cy: Float, r: Float, a: Float) {
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(c.copy(alpha = a), c.copy(alpha = 0f)),
                            center = Offset(size.width * cx, size.height * cy),
                            radius = size.minDimension * r,
                        ),
                        radius = size.minDimension * r,
                        center = Offset(size.width * cx, size.height * cy),
                    )
                }
                blob(Spx.AuroraA, 0.12f, 0.05f, 0.85f, 0.50f)
                blob(Spx.AuroraC, 0.95f, 0.30f, 0.70f, 0.34f)
                blob(Spx.AuroraB, 0.60f, 1.02f, 0.80f, 0.30f)
            }
    ) { content() }
}

/* ------------------------------ type ------------------------------ */

@Composable
fun ScreenTitle(text: String, sub: String? = null, trailing: @Composable () -> Unit = {}) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(text, fontSize = 27.sp, fontWeight = FontWeight.Bold,
                 color = Spx.Ink, letterSpacing = (-0.4).sp)
            if (sub != null) {
                Text(sub, fontSize = 12.sp, color = Spx.Muted, lineHeight = 16.sp)
            }
        }
        trailing()
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) = Text(
    text.uppercase(),
    color = Spx.Faint,
    fontSize = 10.sp,
    fontWeight = FontWeight.Bold,
    letterSpacing = 1.8.sp,
    modifier = modifier.padding(start = 2.dp, bottom = 9.dp),
)

@Composable
fun StatusDot(on: Boolean, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(8.dp)
                .background(if (on) Spx.Low else Spx.Faint, RoundedCornerShape(50))
        )
        Box(Modifier.width(6.dp))
        Text(label, fontSize = 11.sp, color = if (on) Spx.Low else Spx.Faint,
             fontWeight = FontWeight.Medium)
    }
}

@Composable
fun SpirexaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Spx.Accent,
            background = Spx.Bg,
            surface = Spx.BgLift,
            onBackground = Spx.Ink,
            onSurface = Spx.Ink,
        ),
        content = content,
    )
}
