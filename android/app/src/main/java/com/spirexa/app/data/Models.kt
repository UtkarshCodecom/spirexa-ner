package com.spirexa.app.data

/**
 * A monitored slope, carrying both halves of the answer.
 *
 * [risk] is today's rainfall trigger score: it moves every morning and says
 * nothing about the hillside. [susceptibilityTerrainOnly] is the static
 * ground score from the GSI-trained model with road features removed, and
 * [susceptibility] is the same model with them left in. [action] is the two
 * of them crossed -- ACT, PREPARE, WATCH or CLEAR -- which is the only field
 * on here a field officer has to read.
 *
 * All four are nullable because an older server, or one whose hotspots have
 * not been scored yet, simply does not send them.
 */
data class Hotspot(
    val id: String,
    val location: String,
    val state: String,
    val lat: Double,
    val lon: Double,
    val risk: Double,
    val susceptibility: Double? = null,
    val susceptibilityTerrainOnly: Double? = null,
    val ground: String? = null,
    val groundLabel: String? = null,
    val action: String? = null,
) {
    val riskPercent: Int get() = Math.round(risk * 100).toInt()
    val groundPercent: Int? get() =
        susceptibilityTerrainOnly?.let { Math.round(it * 100).toInt() }

    /** ACT first, then the slopes to prepare, then everything else. */
    val priority: Int get() = when (action) {
        "ACT" -> 0
        "PREPARE" -> 1
        "WATCH" -> 2
        "CLEAR" -> 3
        else -> 4
    }
    val severity: String get() = when {
        risk >= 0.75 -> "SEVERE"
        risk >= 0.50 -> "HIGH"
        risk >= 0.25 -> "MODERATE"
        else -> "LOW"
    }
}

data class AlertMessage(
    val code: String,
    val language: String,
    val text: String,
    val verified: Boolean,
)

data class Alert(
    val id: Int,
    val sentAt: String,
    val location: String,
    val state: String,
    val lat: Double?,
    val lon: Double?,
    val riskPercent: Double?,
    val severity: String,
    val sentBy: String,
    val messages: List<AlertMessage>,
)

data class Station(
    val connected: Boolean,
    val nodeId: String?,
    val simulated: Boolean,
    val readings: Map<String, Double>,
)
