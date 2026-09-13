package com.spirexa.app.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import com.spirexa.app.data.Geo
import com.spirexa.app.data.Hotspot
import com.spirexa.app.ui.Spx
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

// Same frame the server projects into, so markers land on the right state.
const val LON_MIN = 87.5
const val LON_MAX = 97.8
const val LAT_MIN = 21.5
const val LAT_MAX = 29.8

/** Pan and zoom the user has applied on top of the fitted view. */
class MapCamera {
    var scale by mutableFloatStateOf(1f)
    var pan by mutableStateOf(Offset.Zero)
    fun reset() { scale = 1f; pan = Offset.Zero }
}

/**
 * The NER states, their road network and the monitored slopes, drawn from
 * the same projected geometry the web dashboard uses.
 *
 * The first version of this screen was 311 coloured dots on a blank panel.
 * Dots with no border and no road are not a map -- there is nothing to tell
 * you which dot is the one above your town.
 */
@Composable
fun NerMap(
    geo: Geo?,
    hotspots: List<Hotspot>,
    selected: Hotspot?,
    camera: MapCamera,
    modifier: Modifier = Modifier,
    onSelect: (Hotspot?) -> Unit,
    overlay: @Composable BoxScope.() -> Unit = {},
) {
    val frameW = geo?.width ?: 900f
    val frameH = geo?.height ?: 804.5f

    // The road extract covers the whole bounding box, so it runs on across
    // Bangladesh, Bhutan and Myanmar. Unclipped, the eight states disappear
    // into a field of brown scribble. Clip every road to the land.
    val land = remember(geo) {
        Path().apply { geo?.states?.values?.forEach { addPath(it) } }
    }

    // Written during draw, read by the gesture handlers to turn a screen
    // point back into map coordinates.
    var fitScale by remember { mutableFloatStateOf(0f) }
    var fitOrigin by remember { mutableStateOf(Offset.Zero) }

    Box(
        modifier
            .pointerInput(hotspots, geo) {
                detectTapGestures { tap ->
                    if (fitScale <= 0f) return@detectTapGestures
                    val mx = (tap.x - fitOrigin.x) / fitScale
                    val my = (tap.y - fitOrigin.y) / fitScale
                    var best: Hotspot? = null
                    var bestD = Float.MAX_VALUE
                    hotspots.forEach { h ->
                        val p = project(h, frameW, frameH)
                        val d = (p.x - mx) * (p.x - mx) + (p.y - my) * (p.y - my)
                        if (d < bestD) { bestD = d; best = h }
                    }
                    // a fingertip is about 20 map units across at the fitted
                    // scale, and proportionally less once zoomed in
                    val reach = 20f / max(camera.scale, 0.01f)
                    onSelect(if (bestD <= reach * reach) best else null)
                }
            }
            .pointerInput(Unit) {
                detectTransformGestures { centroid, panChange, zoom, _ ->
                    val next = (camera.scale * zoom).coerceIn(1f, 8f)
                    val k = next / camera.scale
                    val centre = Offset(size.width / 2f, size.height / 2f)
                    // Hold the point under the fingers still while zooming:
                    // derived from origin = centre - frame*scale/2 + pan.
                    var p = (centroid - centre) * (1f - k) + camera.pan * k + panChange

                    // ...and do not let the region be dragged off the screen
                    val base = min(size.width / frameW, size.height / frameH)
                    val slackX = max(0f, (frameW * base * next - size.width) / 2f)
                    val slackY = max(0f, (frameH * base * next - size.height) / 2f)
                    p = Offset(
                        p.x.coerceIn(-slackX, slackX),
                        p.y.coerceIn(-slackY, slackY),
                    )
                    camera.scale = next
                    camera.pan = p
                }
            }
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val base = min(size.width / frameW, size.height / frameH)
            val s = base * camera.scale
            val ox = (size.width - frameW * s) / 2f + camera.pan.x
            val oy = (size.height - frameH * s) / 2f + camera.pan.y
            fitScale = s
            fitOrigin = Offset(ox, oy)

            // strokes and dots are specified in dp, then divided by the
            // transform scale, so they stay the same size on screen at any zoom
            val hair = 1.dp.toPx() / s
            val dotBig = 3.1.dp.toPx() / s
            val dotSmall = 2.3.dp.toPx() / s

            // everything outside the eight states is "not our area", and it
            // should look like a deliberate ground rather than a gap
            drawRect(Spx.Water)

            withTransform({
                translate(ox, oy)
                scale(s, s, pivot = Offset.Zero)
            }) {
                if (geo != null) {
                    geo.states.values.forEach { p -> drawPath(p, Spx.Land) }
                    clipPath(land) {
                        drawPath(geo.roadsMinor, Spx.RoadMinor,
                            style = Stroke(width = hair * 0.8f), alpha = 0.45f)
                        drawPath(geo.roadsMajor, Spx.RoadMajor,
                            style = Stroke(width = hair * 1.2f), alpha = 0.7f)
                    }
                    // borders last, so roads do not paint over the coastline
                    geo.states.values.forEach { p ->
                        drawPath(p, Spx.LandEdge, style = Stroke(width = hair))
                    }
                }

                // low risk first, so the severe ones are never buried under
                // a hundred green dots
                hotspots.sortedBy { it.risk }.forEach { h ->
                    val p = project(h, frameW, frameH)
                    val c = Spx.severityColor(h.severity)
                    val r = if (h.risk >= 0.5) dotBig else dotSmall
                    drawCircle(c.copy(alpha = 0.14f), radius = r * 1.9f, center = p)
                    drawCircle(c, radius = r, center = p)
                }

                selected?.let { h ->
                    val p = project(h, frameW, frameH)
                    drawCircle(Color.White, radius = dotBig * 3.2f, center = p,
                        style = Stroke(width = hair * 1.8f))
                    drawCircle(Spx.severityColor(h.severity), radius = dotBig, center = p)
                }
            }
        }
        overlay()
    }
}

private fun project(h: Hotspot, w: Float, hgt: Float): Offset {
    val fx = ((h.lon - LON_MIN) / (LON_MAX - LON_MIN)).toFloat()
    val fy = ((LAT_MAX - h.lat) / (LAT_MAX - LAT_MIN)).toFloat()
    return Offset(fx * w, fy * hgt)
}
