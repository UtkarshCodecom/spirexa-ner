/*
 * SPIREXA FIELD NODE - ARDUINO UNO
 *
 * Sensors:
 *   Rain sensor  -> A1
 *   Soil sensor  -> A0
 *   DHT11        -> D2
 *   Touch module -> D8
 *
 * LEDs:
 *   Alert/Green LED -> D7
 *   White LED       -> D10
 *
 * Green LED BLINKS when:
 *   - Touch detected
 *   - Wetness >= 65%
 *
 * White LED stays ON.
 *
 * Prints a JSON line per reading. hardware/serial_bridge.py forwards those
 * to the SPIREXA server, which puts them on the dashboard.
 */

#include <DHT.h>

#define PIN_RAIN   A1
#define PIN_SOIL   A0
#define PIN_DHT    2
#define PIN_TOUCH  8

#define PIN_LED_GREEN  7
#define PIN_LED_WHITE 10

#define DHTTYPE DHT11

DHT dht(PIN_DHT, DHTTYPE);

const int RAIN_DRY = 950;
const int RAIN_WET = 380;

const int SOIL_DRY = 620;
const int SOIL_WET = 280;

const int ALERT_THRESHOLD = 65;

unsigned long lastRead = 0;
unsigned long lastBlink = 0;

const unsigned long READ_EVERY_MS = 3000;
const unsigned long BLINK_EVERY_MS = 300;

int wetness = 0;
bool touchDetected = false;
bool alertActive = false;
bool greenLedState = false;

void setup() {
  Serial.begin(9600);

  pinMode(PIN_TOUCH, INPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_WHITE, OUTPUT);

  digitalWrite(PIN_LED_WHITE, HIGH);   // white = system on
  digitalWrite(PIN_LED_GREEN, LOW);    // alert off

  dht.begin();
  delay(2000);

  Serial.println();
  Serial.println("================================");
  Serial.println("      SPIREXA FIELD NODE");
  Serial.println("================================");
  Serial.println("Arduino UNO");
  Serial.println("Rain + Soil + DHT11 + Touch");
  Serial.println("Green LED = ALERT");
  Serial.println("White LED = SYSTEM ON");
  Serial.println();
  Serial.println("SYSTEM READY");
}

void loop() {
  unsigned long now = millis();

  if (now - lastRead >= READ_EVERY_MS) {
    lastRead = now;
    readSensors();
  }

  if (alertActive) {
    if (now - lastBlink >= BLINK_EVERY_MS) {
      lastBlink = now;
      greenLedState = !greenLedState;
      digitalWrite(PIN_LED_GREEN, greenLedState);
    }
  } else {
    greenLedState = false;
    digitalWrite(PIN_LED_GREEN, LOW);
  }

  digitalWrite(PIN_LED_WHITE, HIGH);
}

void readSensors() {
  int rainRaw = analogRead(PIN_RAIN);
  float rainPct = mapPct(rainRaw, RAIN_DRY, RAIN_WET);

  int soilRaw = analogRead(PIN_SOIL);
  float soilPct = mapPct(soilRaw, SOIL_DRY, SOIL_WET);

  float humidity = dht.readHumidity();
  float tempC = dht.readTemperature();

  if (isnan(humidity)) humidity = -1;
  if (isnan(tempC))    tempC = -1;

  touchDetected = digitalRead(PIN_TOUCH) == HIGH;

  wetness = wetnessScore(rainPct, humidity, soilPct);
  if (touchDetected) wetness = 90;          // demo alarm

  alertActive = touchDetected || wetness >= ALERT_THRESHOLD;

  Serial.println();
  Serial.println("--------------------------------");
  Serial.print("Rain raw: ");   Serial.println(rainRaw);
  Serial.print("Rain: ");       Serial.print(rainPct, 1);  Serial.println("%");
  Serial.print("Soil raw: ");   Serial.println(soilRaw);
  Serial.print("Soil: ");       Serial.print(soilPct, 1);  Serial.println("%");

  Serial.print("Temperature: ");
  if (tempC < 0) Serial.println("DHT READ FAILED");
  else { Serial.print(tempC, 1); Serial.println(" C"); }

  Serial.print("Humidity: ");
  if (humidity < 0) Serial.println("DHT READ FAILED");
  else { Serial.print(humidity, 1); Serial.println(" %"); }

  Serial.print("Touch: ");
  Serial.println(touchDetected ? "TOUCHED" : "NO");

  Serial.print("Wetness: "); Serial.print(wetness); Serial.println("%");
  Serial.print("ALERT: ");   Serial.println(alertActive ? "YES" : "NO");

  // --- the line serial_bridge.py picks up ---
  Serial.print("{\"node_id\":\"NODE-01\"");
  Serial.print(",\"lat\":23.73480");
  Serial.print(",\"lon\":92.71870");
  Serial.print(",\"rain_pct\":");          Serial.print(rainPct, 1);
  Serial.print(",\"soil_moisture_pct\":"); Serial.print(soilPct, 1);

  Serial.print(",\"temperature_c\":");
  if (tempC < 0) Serial.print("null"); else Serial.print(tempC, 1);

  Serial.print(",\"humidity_pct\":");
  if (humidity < 0) Serial.print("null"); else Serial.print(humidity, 1);

  Serial.print(",\"wetness_pct\":");       Serial.print(wetness);
  Serial.print(",\"touch\":");
  Serial.print(touchDetected ? "true" : "false");
  Serial.println("}");
}

int wetnessScore(float rain, float humidity, float soil) {
  int score = 0;

  if      (rain > 75) score += 40;
  else if (rain > 45) score += 30;
  else if (rain > 20) score += 18;
  else if (rain > 5)  score += 8;

  if      (humidity > 92) score += 15;
  else if (humidity > 80) score += 10;
  else if (humidity > 65) score += 5;

  if      (soil > 85) score += 45;
  else if (soil > 70) score += 30;
  else if (soil > 55) score += 15;

  return constrain(score, 0, 100);
}

float mapPct(int raw, int dryVal, int wetVal) {
  float pct = 100.0 * (dryVal - raw) / (float)(dryVal - wetVal);
  return constrain(pct, 0, 100);
}
