package com.spirexa.app.data

import androidx.compose.ui.graphics.Path

/**
 * Map geometry, already projected by the server into the same frame the web
 * dashboard uses, so a marker at x,y means the same thing in both.
 *
 * The server sends SVG path strings. They only ever contain M, L and Z --
 * the generator writes nothing else -- so a twenty-line reader beats pulling
 * in an SVG library for it.
 */
data class Geo(
    val width: Float,
    val height: Float,
    val states: Map<String, Path>,
    val roadsMajor: Path,
    val roadsMinor: Path,
) {
    companion object {
        fun parsePath(d: String): Path {
            val path = Path()
            var i = 0
            val n = d.length
            var started = false

            fun skipSeparators() {
                while (i < n && (d[i] == ' ' || d[i] == ',' || d[i] == '\n' || d[i] == '\t')) i++
            }
            fun readNumber(): Float {
                skipSeparators()
                val start = i
                if (i < n && (d[i] == '-' || d[i] == '+')) i++
                while (i < n && (d[i].isDigit() || d[i] == '.')) i++
                return if (i > start) d.substring(start, i).toFloatOrNull() ?: 0f else 0f
            }

            while (i < n) {
                when (d[i]) {
                    'M' -> {
                        i++
                        val x = readNumber(); val y = readNumber()
                        path.moveTo(x, y); started = true
                    }
                    'L' -> {
                        i++
                        val x = readNumber(); val y = readNumber()
                        if (started) path.lineTo(x, y) else { path.moveTo(x, y); started = true }
                    }
                    'Z', 'z' -> { i++; path.close() }
                    else -> i++
                }
            }
            return path
        }
    }
}
