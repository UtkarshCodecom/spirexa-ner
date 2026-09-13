package com.spirexa.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/* SPIREXA palette. Neumorphism only reads as neumorphism when the surface is
   the same colour as the background it sits on -- the form comes entirely
   from the pair of shadows, one light and one dark. Hence Bg == Surface. */
object Spx {
    val Bg = Color(0xFFEEF1F6)
    val Surface = Color(0xFFEEF1F6)
    val ShadowDark = Color(0xFFC7CEDB)
    val ShadowLight = Color(0xFFFFFFFF)

    val Ink = Color(0xFF16191D)
    val Muted = Color(0xFF5D6874)
    val Accent = Color(0xFF1D3A5C)

    val Low = Color(0xFF15803D)
    val Moderate = Color(0xFFB45309)
    val High = Color(0xFFEA580C)
    val Severe = Color(0xFFDC2626)

    fun severityColor(s: String): Color = when (s.uppercase()) {
        "SEVERE" -> Severe
        "HIGH" -> High
        "MODERATE" -> Moderate
        else -> Low
    }
}

/** Raised neumorphic surface: dark shadow bottom-right, light shadow top-left. */
fun Modifier.neu(radius: Int = 20, elevation: Int = 6): Modifier = this
    .shadow(
        elevation = elevation.dp,
        shape = RoundedCornerShape(radius.dp),
        ambientColor = Spx.ShadowDark,
        spotColor = Spx.ShadowDark,
    )
    .drawBehind {
        // The light counter-shadow. Drawn as a soft offset highlight so the
        // surface reads as extruded rather than merely drop-shadowed.
        drawRoundRect(
            color = Spx.ShadowLight.copy(alpha = 0.85f),
            topLeft = Offset(-3f, -3f),
            size = size.copy(width = size.width + 3f, height = size.height + 3f),
            cornerRadius = androidx.compose.ui.geometry.CornerRadius(radius.dp.toPx()),
        )
    }
    .background(Spx.Surface, RoundedCornerShape(radius.dp))

/** Pressed/inset neumorphic well, for fields and inactive chips. */
fun Modifier.neuInset(radius: Int = 16): Modifier = this
    .background(
        Brush.linearGradient(listOf(Color(0xFFE3E8F0), Color(0xFFF6F8FC))),
        RoundedCornerShape(radius.dp),
    )
    .border(1.dp, Spx.ShadowDark.copy(alpha = 0.55f), RoundedCornerShape(radius.dp))

/** Translucent glass card: frosted fill plus a bright top-left border edge. */
fun Modifier.glass(radius: Int = 22): Modifier = this
    .background(
        Brush.linearGradient(
            listOf(Color(0xCCFFFFFF), Color(0x99F2F5FA)),
        ),
        RoundedCornerShape(radius.dp),
    )
    .border(
        width = 1.dp,
        brush = Brush.linearGradient(
            listOf(Color(0xE6FFFFFF), Color(0x33FFFFFF)),
        ),
        shape = RoundedCornerShape(radius.dp),
    )

fun Modifier.pad(all: Int = 16): Modifier = this.padding(all.dp)

@Composable
fun SpirexaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Spx.Accent,
            background = Spx.Bg,
            surface = Spx.Surface,
            onBackground = Spx.Ink,
            onSurface = Spx.Ink,
        ),
        content = content,
    )
}
