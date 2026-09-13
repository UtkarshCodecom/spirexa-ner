package com.spirexa.app.data

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Talks to the SPIREXA server over the local network.
 *
 * Deliberately plain HttpURLConnection and org.json, both in the platform:
 * no Retrofit, no serialization plugin, nothing to resolve at build time.
 * The whole surface is five short GETs.
 */
object Api {

    @Volatile
    var baseUrl: String = "http://10.95.92.224:8000"

    private fun get(path: String, timeoutMs: Int = 8000): String {
        val conn = (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            setRequestProperty("Accept", "application/json")
        }
        try {
            if (conn.responseCode !in 200..399) {
                throw RuntimeException("HTTP ${conn.responseCode} for $path")
            }
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    fun health(): Boolean = try {
        JSONObject(get("/api/health", 4000)).optString("status") == "ok"
    } catch (e: Exception) {
        false
    }

    fun hotspots(): List<Hotspot> {
        val root = JSONObject(get("/api/risk", 15000))
        val arr = root.optJSONArray("locations") ?: return emptyList()
        val out = ArrayList<Hotspot>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            out.add(
                Hotspot(
                    id = o.optString("id"),
                    location = o.optString("location").takeIf { it != "null" } ?: "",
                    state = o.optString("state"),
                    lat = o.optDouble("lat", 0.0),
                    lon = o.optDouble("lon", 0.0),
                    risk = o.optDouble("live_risk", 0.0),
                )
            )
        }
        return out
    }

    /** Everything queued after [sinceId]; oldest first. */
    fun alertsSince(sinceId: Int): Pair<List<Alert>, Int> {
        val root = JSONObject(get("/api/notifications?since=$sinceId"))
        val latest = root.optInt("latest_id", sinceId)
        val arr = root.optJSONArray("notifications") ?: return emptyList<Alert>() to latest

        val out = ArrayList<Alert>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val msgs = ArrayList<AlertMessage>()
            o.optJSONArray("messages")?.let { ms ->
                for (j in 0 until ms.length()) {
                    val m = ms.getJSONObject(j)
                    msgs.add(
                        AlertMessage(
                            code = m.optString("code"),
                            language = m.optString("native_name")
                                .ifBlank { m.optString("language") },
                            text = m.optString("text"),
                            verified = m.optBoolean("verified", false),
                        )
                    )
                }
            }
            out.add(
                Alert(
                    id = o.optInt("id"),
                    sentAt = o.optString("sent_at"),
                    location = o.optString("location"),
                    state = o.optString("state"),
                    lat = if (o.isNull("lat")) null else o.optDouble("lat"),
                    lon = if (o.isNull("lon")) null else o.optDouble("lon"),
                    riskPercent = if (o.isNull("risk_percent")) null else o.optDouble("risk_percent"),
                    severity = o.optString("severity", "LOW"),
                    sentBy = o.optString("sent_by"),
                    messages = msgs,
                )
            )
        }
        return out to latest
    }

    /**
     * Map geometry. Fetched once per connection and held in memory: it is
     * ~130 KB and never changes while the server is up.
     */
    fun geo(): Geo? = try {
        val root = JSONObject(get("/api/geo", 20000))
        val statesJson = root.getJSONObject("states")
        val states = LinkedHashMap<String, androidx.compose.ui.graphics.Path>()
        statesJson.keys().forEach { name ->
            states[name] = Geo.parsePath(statesJson.getString(name))
        }
        Geo(
            width = root.optDouble("width", 900.0).toFloat(),
            height = root.optDouble("height", 805.0).toFloat(),
            states = states,
            roadsMajor = Geo.parsePath(root.optString("roads_major")),
            roadsMinor = Geo.parsePath(root.optString("roads_minor")),
        )
    } catch (e: Exception) {
        // an older server has no /api/geo; the map falls back to markers only
        null
    }

    fun station(): Station? = try {
        val st = JSONObject(get("/api/live", 6000)).optJSONObject("station") ?: return null
        val readings = HashMap<String, Double>()
        st.optJSONObject("readings")?.let { r ->
            r.keys().forEach { k -> readings[k] = r.optDouble(k, 0.0) }
        }
        Station(
            connected = st.optBoolean("connected", false),
            nodeId = st.optString("node_id").takeIf { it.isNotBlank() },
            simulated = st.optBoolean("simulated", false),
            readings = readings,
        )
    } catch (e: Exception) {
        null
    }
}
