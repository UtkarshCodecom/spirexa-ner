/*
 * SPIREXA field node - Arduino UNO
 * ---------------------------------------------------------------
 * WHAT THIS IS
 *   A local weather station for a landslide-prone site. It measures
 *   rainfall and air conditions where it stands. The satellite's
 *   rainfall figure is an average over roughly 11 km; this is the
 *   real number for this hillside.
 *
 * WHAT THIS IS NOT
 *   It does not sense the slope. With no movement sensor attached it
 *   cannot tell you the ground is shifting, and it does not predict
 *   landslides. The prediction is made on the server by the model,
 *   using terrain and satellite data. Say that plainly if asked - it
 *   is a better answer than overclaiming.
 *
 * The UNO has no network. It prints one JSON line per reading over
 * USB; serial_bridge.py forwards those to the SPIREXA server.
 *
 * Board: Arduino Uno
 * Library Manager: "DHT sensor library" (Adafruit) + "Adafruit Unified Sensor"
 */

#include <DHT.h>

// ----------------------------- PINS -----------------------------
#define PIN_RAIN      A1    // rain drop board, analog out (AO)
#define PIN_DHT        2    // temperature + humidity data pin
#define PIN_TOUCH      8    // press to force an alarm, for the demo

// Optional soil probe. Set USE_SOIL to 1 only if it is wired to A0.
#define USE_SOIL       0
#define PIN_SOIL      A0

// Optional 3-LED traffic light. With no LEDs the sketch still runs -
// pin 13 is the board's own LED and is always present.
#define PIN_LED_LOW    9    // green
#define PIN_LED_MID   10    // yellow
#define PIN_LED_HIGH  11    // red
#define PIN_LED_ONBOARD 13

#define DHTTYPE DHT11       // change to DHT22 if that is the sensor you have

// --------------------------- CALIBRATE ---------------------------
// Open Serial Monitor at 9600 and read the raw numbers, then set these.
// Rain board: dry surface reads HIGH, wet reads LOW.
const int RAIN_DRY = 950;
const int RAIN_WET = 380;
// Soil probe, only used if USE_SOIL is 1. In air = dry, in water = wet.
const int SOIL_DRY = 620;
const int SOIL_WET = 280;
// -----------------------------------------------------------------

DHT dht(PIN_DHT, DHTTYPE);

unsigned long lastSend = 0;
const unsigned long SEND_EVERY_MS = 3000;

void setup() {
  Serial.begin(9600);

  pinMode(PIN_TOUCH, INPUT);
  pinMode(PIN_LED_LOW, OUTPUT);
  pinMode(PIN_LED_MID, OUTPUT);
  pinMode(PIN_LED_HIGH, OUTPUT);
  pinMode(PIN_LED_ONBOARD, OUTPUT);

  dht.begin();
  bootAnimation();
  Serial.println(F("# SPIREXA node ready - rainfall and air conditions"));
}

void loop() {
  int   rainRaw  = analogRead(PIN_RAIN);
  float rainPct  = mapPct(rainRaw, RAIN_DRY, RAIN_WET);
  float humidity = dht.readHumidity();
  float tempC    = dht.readTemperature();

  float soilPct = -1;
#if USE_SOIL
  soilPct = mapPct(analogRead(PIN_SOIL), SOIL_DRY, SOIL_WET);
#endif

  if (isnan(humidity)) humidity = -1;
  if (isnan(tempC))    tempC    = -1;

  int wetness = wetnessScore(rainPct, humidity, soilPct);
  if (digitalRead(PIN_TOUCH) == HIGH) wetness = 90;   // demo button

  showLeds(wetness);

  if (millis() - lastSend > SEND_EVERY_MS) {
    sendJson(rainPct, tempC, humidity, soilPct, wetness);
    lastSend = millis();
  }
  delay(200);
}

// -----------------------------------------------------------------
// How wet this site is right now. Deliberately NOT called risk - the
// node has no way to judge slope stability. Wet ground is a necessary
// condition for a rainfall-triggered slide, not a sufficient one.
int wetnessScore(float rain, float humidity, float soil) {
  int score = 0;

  if      (rain > 75) score += 55;      // heavy rain falling now
  else if (rain > 45) score += 38;
  else if (rain > 20) score += 20;
  else if (rain > 5)  score += 8;

  if      (humidity > 92) score += 20;  // air saturated, nothing evaporating
  else if (humidity > 80) score += 12;
  else if (humidity > 65) score += 5;

  if (soil >= 0) {                      // only when a probe is fitted
    if      (soil > 85) score += 25;
    else if (soil > 70) score += 16;
    else if (soil > 55) score += 8;
  }

  return constrain(score, 0, 100);
}

float mapPct(int raw, int dryVal, int wetVal) {
  float pct = 100.0 * (dryVal - raw) / (float)(dryVal - wetVal);
  return constrain(pct, 0, 100);
}

void showLeds(int wetness) {
  digitalWrite(PIN_LED_LOW,  wetness < 30);
  digitalWrite(PIN_LED_MID,  wetness >= 30 && wetness < 65);
  digitalWrite(PIN_LED_HIGH, wetness >= 65);

  // The board's own LED signals even with no external LEDs wired.
  if      (wetness >= 80) digitalWrite(PIN_LED_ONBOARD, (millis() / 150) % 2);
  else if (wetness >= 65) digitalWrite(PIN_LED_ONBOARD, (millis() / 600) % 2);
  else                    digitalWrite(PIN_LED_ONBOARD, LOW);
}

void bootAnimation() {
  int pins[4] = {PIN_LED_LOW, PIN_LED_MID, PIN_LED_HIGH, PIN_LED_ONBOARD};
  for (int r = 0; r < 2; r++)
    for (int i = 0; i < 4; i++) {
      digitalWrite(pins[i], HIGH); delay(80); digitalWrite(pins[i], LOW);
    }
}

// One JSON object per line - serial_bridge.py forwards these to SPIREXA.
void sendJson(float rain, float tempC, float hum, float soil, int wetness) {
  Serial.print(F("{\"node_id\":\"NODE-01\",\"lat\":23.73480,\"lon\":92.71870"));
  Serial.print(F(",\"rain_pct\":"));      Serial.print(rain, 1);
  Serial.print(F(",\"temperature_c\":")); Serial.print(tempC, 1);
  Serial.print(F(",\"humidity_pct\":"));  Serial.print(hum, 1);
  if (soil >= 0) { Serial.print(F(",\"soil_moisture_pct\":")); Serial.print(soil, 1); }
  Serial.print(F(",\"wetness_pct\":"));   Serial.print(wetness);
  Serial.println(F("}"));
}