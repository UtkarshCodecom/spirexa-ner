/*
  SPIREXA field node - ESP32 (WiFi)

  Built to run on partly-working hardware. Anything that is broken can be
  switched off below and the node still works with the rest - a dead part
  never blocks the whole thing.

  Wiring - ESP32 DevKit V1, 30-pin. The D number IS the GPIO number.

    REQUIRED
      Rain   VCC -> 3V3  GND -> GND  AO  -> D34
      Soil   VCC -> 3V3  GND -> GND  AO  -> D35
      White LED  D19 -> 220ohm -> LED long leg; short leg -> GND
      (onboard blue LED on D2 shows WiFi state - nothing to wire)

    OPTIONAL - leave unwired and set its flag false
      DHT    VCC -> 3V3  GND -> GND  DATA -> D4
      Touch  VCC -> 3V3  GND -> GND  SIG  -> D22
      Green LED  D21 -> 220ohm -> LED long leg; short leg -> GND

  Status, using only the white LED:
      brief flash every 2s  = running, site normal
      fast continuous blink = ALERT, site saturated
  And the onboard blue LED:
      blinking = connecting to WiFi      solid = connected

  Library Manager: "DHT sensor library" (Adafruit) + "Adafruit Unified Sensor"
    -> only needed if USE_DHT is true. Set it false and this sketch needs
       no libraries at all.
  Board Manager: "esp32" by Espressif -> board "ESP32 Dev Module"
*/

// ---------------------- WHAT IS ACTUALLY WIRED -----------------------
#define USE_DHT        true    // false if the DHT or its library is a problem
#define USE_TOUCH      false   // your touch pad is not working yet
#define USE_GREEN_LED  false   // your green LED is not working yet
#define USE_SOIL       true

#if USE_DHT
  #include <DHT.h>
#endif

#include <WiFi.h>
#include <HTTPClient.h>

// ----------------------------- CONFIG --------------------------------
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// Start the server with:  ./run.sh --lan     (it prints this URL for you)
const char* SERVER_URL = "http://10.95.92.224:8000/api/sensor";

const char*  NODE_ID  = "NODE-01";
const double NODE_LAT = 23.73480;
const double NODE_LON = 92.71870;

// true  = print raw ADC only, send nothing, skip WiFi. Calibrate first.
// false = normal operation.
const bool CALIBRATION_MODE = true;

#define DHTTYPE DHT11                // change to DHT22 if that is your part

// 12-bit calibration (0-4095). Replace using CALIBRATION_MODE readings.
const int RAIN_DRY = 3800;           // plate completely dry
const int RAIN_WET = 1500;           // plate soaked
const int SOIL_DRY = 3200;           // probe in open air
const int SOIL_WET = 1400;           // probe in a glass of water

const int ALERT_THRESHOLD = 65;      // wetness at/above this = alert

const unsigned long READ_INTERVAL_MS = 2000;
const unsigned long SEND_INTERVAL_MS = 5000;

// ------------------------------ PINS ---------------------------------
#define PIN_RAIN       34
#define PIN_SOIL       35
#define PIN_DHT         4
#define PIN_TOUCH      22
#define PIN_LED_WHITE  19            // status LED - the one that works
#define PIN_LED_GREEN  21
#define PIN_LED_WIFI    2            // onboard blue

#if USE_DHT
  DHT dht(PIN_DHT, DHTTYPE);
#endif

unsigned long lastRead = 0, lastSend = 0;
float rainPct = 0, soilPct = -1, tempC = 0, hum = 0;
bool  haveDht = false;
int   wetness = 0;

// --------------------------- helpers ---------------------------------
int readAvg(int pin) {
  long sum = 0;
  for (int i = 0; i < 12; i++) { sum += analogRead(pin); delay(3); }
  return (int)(sum / 12);
}

float mapPct(int raw, int dry, int wet) {
  if (dry == wet) return 0;
  float p = (float)(dry - raw) * 100.0 / (float)(dry - wet);
  return p < 0 ? 0 : (p > 100 ? 100 : p);
}

// Same scoring as the original UNO node, so the dashboard reads identically.
// Humidity simply contributes nothing when no DHT is fitted.
int wetnessScore(float rain, float humidity, float soil, bool humValid) {
  int score = 0;

  if      (rain > 75) score += 55;
  else if (rain > 45) score += 38;
  else if (rain > 20) score += 20;
  else if (rain > 5)  score += 8;

  if (humValid) {
    if      (humidity > 92) score += 20;
    else if (humidity > 80) score += 12;
    else if (humidity > 65) score += 5;
  }

  if (soil >= 0) {
    if      (soil > 85) score += 25;
    else if (soil > 70) score += 16;
    else if (soil > 55) score += 8;
  }

  return score > 100 ? 100 : score;
}

/* One LED has to carry the whole state, so normal is a brief heartbeat
   flash and alert is an unmistakable fast blink. */
void showStatus(int w) {
  bool alert = (w >= ALERT_THRESHOLD);
  unsigned long t = millis();
  bool on = alert ? ((t / 150) % 2) : ((t % 2000) < 60);

  digitalWrite(PIN_LED_WHITE, on);
#if USE_GREEN_LED
  digitalWrite(PIN_LED_GREEN, alert ? LOW : HIGH);
#endif
}

void connectWifi() {
  Serial.print("connecting to ");
  Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    digitalWrite(PIN_LED_WIFI, !digitalRead(PIN_LED_WIFI));
    delay(400);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(PIN_LED_WIFI, HIGH);
    Serial.print("connected. node IP: ");
    Serial.println(WiFi.localIP());
  } else {
    digitalWrite(PIN_LED_WIFI, LOW);
    Serial.println("WiFi FAILED - check SSID/password, and that it is 2.4GHz");
    Serial.println("(ESP32 cannot join 5GHz-only networks)");
  }
}

void postReading(const String& payload) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  int code = http.POST(payload);
  if (code > 0 && code < 400) {
    Serial.print("  sent -> HTTP ");
    Serial.println(code);
  } else {
    Serial.print("  send FAILED (");
    Serial.print(code);
    Serial.println(") - is the server running with ./run.sh --lan ?");
  }
  http.end();
}

// ----------------------------- setup ---------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_LED_WHITE, OUTPUT);
  pinMode(PIN_LED_WIFI,  OUTPUT);
#if USE_GREEN_LED
  pinMode(PIN_LED_GREEN, OUTPUT);
#endif
#if USE_TOUCH
  pinMode(PIN_TOUCH, INPUT_PULLDOWN);
#endif

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

#if USE_DHT
  dht.begin();
#endif

  Serial.println();
  Serial.println("SPIREXA ESP32 node");
  Serial.print  ("  DHT ");   Serial.print(USE_DHT       ? "ON " : "off");
  Serial.print  ("  touch "); Serial.print(USE_TOUCH     ? "ON " : "off");
  Serial.print  ("  green "); Serial.print(USE_GREEN_LED ? "ON " : "off");
  Serial.print  ("  soil ");  Serial.println(USE_SOIL    ? "ON"  : "off");

  // Three flashes so you can see the sketch actually started.
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_LED_WHITE, HIGH); delay(120);
    digitalWrite(PIN_LED_WHITE, LOW);  delay(120);
  }

  if (CALIBRATION_MODE) {
    Serial.println("CALIBRATION MODE - raw values only, nothing sent, no WiFi.");
    return;
  }
  connectWifi();
}

// ------------------------------ loop ---------------------------------
void loop() {
  if (CALIBRATION_MODE) {
    Serial.print("rain raw=");
    Serial.print(readAvg(PIN_RAIN));
    Serial.print("   soil raw=");
    Serial.print(readAvg(PIN_SOIL));
#if USE_TOUCH
    Serial.print("   touch=");
    Serial.print(digitalRead(PIN_TOUCH) ? "YES" : "no");
#endif
    Serial.println();
    delay(1000);
    return;
  }

  if (millis() - lastRead >= READ_INTERVAL_MS) {
    lastRead = millis();

    rainPct = mapPct(readAvg(PIN_RAIN), RAIN_DRY, RAIN_WET);
    soilPct = USE_SOIL ? mapPct(readAvg(PIN_SOIL), SOIL_DRY, SOIL_WET) : -1;

#if USE_DHT
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) { tempC = t; hum = h; haveDht = true; }
#endif

    wetness = wetnessScore(rainPct, hum, soilPct, haveDht);
#if USE_TOUCH
    if (digitalRead(PIN_TOUCH) == HIGH) wetness = 90;   // demo trigger
#endif
  }

  showStatus(wetness);

  if (millis() - lastSend < SEND_INTERVAL_MS) return;
  lastSend = millis();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi dropped - reconnecting");
    connectWifi();
    return;
  }

  // Same JSON shape the UNO sent, so serve.py needs no changes. Fields for
  // parts that are not fitted are simply left out.
  String payload = "{";
  payload += "\"node_id\":\"" + String(NODE_ID) + "\"";
  payload += ",\"lat\":" + String(NODE_LAT, 5);
  payload += ",\"lon\":" + String(NODE_LON, 5);
  payload += ",\"rain_pct\":" + String(rainPct, 1);
  if (haveDht) {
    payload += ",\"temperature_c\":" + String(tempC, 1);
    payload += ",\"humidity_pct\":"  + String(hum, 1);
  }
  if (soilPct >= 0) payload += ",\"soil_moisture_pct\":" + String(soilPct, 1);
  payload += ",\"wetness_pct\":" + String(wetness);
  payload += "}";

  Serial.println(payload);
  postReading(payload);
}
