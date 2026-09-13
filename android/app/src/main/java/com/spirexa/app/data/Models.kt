package com.spirexa.app.data

data class Hotspot(
    val id: String,
    val location: String,
    val state: String,
    val lat: Double,
    val lon: Double,
    val risk: Double,
) {
    val riskPercent: Int get() = Math.round(risk * 100).toInt()
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
