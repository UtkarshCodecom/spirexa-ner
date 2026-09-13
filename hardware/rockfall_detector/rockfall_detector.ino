/*
  Idle rockfall / slope-movement detector.

  Standalone sketch -- not part of SPIREXA, no serial protocol, no web
  link. Just an ultrasonic sensor and two LEDs on a breadboard.

  Point the HC-SR04 across a rock face or slope cutting. It measures
  distance every ~1.5s; if that distance moves more than
  CHANGE_THRESHOLD_CM away from the distance recorded at power-on
  (something entered or left the beam path -- e.g. a rock fell), it
  turns the red LED on and green off. Once the distance sits back
  within CHANGE_THRESHOLD_CM of that original baseline for
  RECOVERY_READINGS in a row (~2-3s), it goes back to green on its own
  -- no reset needed. A real permanent change (an actual rockfall)
  just never returns near the old baseline, so it stays red.

  Wiring:
    HC-SR04    VCC -> 5V   GND -> GND   TRIG -> D9   ECHO -> D10
    Green LED  D7 -> 220ohm resistor -> LED anode; cathode -> GND
    Red LED    D8 -> 220ohm resistor -> LED anode; cathode -> GND

  On every power-up both LEDs blink once in turn (red, then green)
  before calibration starts -- a quick way to confirm both are wired
  correctly independent of the sensor. If an LED doesn't blink during
  that self-test, it's a wiring problem (check polarity first -- the
  short leg/flat-edge side must face GND), not a code problem.
*/

const int TRIG_PIN = 9;
const int ECHO_PIN = 10;
const int GREEN_LED = 7;
const int RED_LED = 8;

const float CHANGE_THRESHOLD_CM = 15.0;    // how big a jump counts as "something moved"
const unsigned long READ_INTERVAL_MS = 1500;
const int BASELINE_SAMPLES = 8;            // averaged at startup for a stable reference
const int CONFIRM_READINGS = 2;            // consecutive over-threshold reads before turning red
const int RECOVERY_READINGS = 2;           // consecutive back-to-normal reads before turning green again (~3s at 1.5s/read)

float baselineCm = 0;
int overThresholdStreak = 0;
int normalStreak = 0;
bool alerted = false;

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);  // 30ms timeout =~ 5m range
  if (duration == 0) return -1;  // no echo -- out of range or a bad reading
  return duration * 0.0343 / 2.0;
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);

  Serial.println("Rockfall detector starting...");

  Serial.println("LED self-test: red, then green (400ms each)");
  digitalWrite(RED_LED, HIGH);
  delay(400);
  digitalWrite(RED_LED, LOW);
  digitalWrite(GREEN_LED, HIGH);
  delay(400);
  digitalWrite(GREEN_LED, LOW);

  Serial.println("Calibrating baseline distance (keep the beam path clear)...");

  float sum = 0;
  int got = 0;
  while (got < BASELINE_SAMPLES) {
    float d = readDistanceCm();
    if (d > 0) {
      sum += d;
      got++;
    }
    delay(200);
  }
  baselineCm = sum / BASELINE_SAMPLES;
  Serial.print("Baseline distance: ");
  Serial.print(baselineCm);
  Serial.println(" cm");
  Serial.println("Ready. Move an object >15cm into the beam to test the alert.");

  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(RED_LED, LOW);
}

void loop() {
  float d = readDistanceCm();

  if (d < 0) {
    Serial.println("Distance: no echo (out of range) -- skipping this reading");
    delay(READ_INTERVAL_MS);
    return;
  }

  float change = fabs(d - baselineCm);
  Serial.print("Distance: ");
  Serial.print(d);
  Serial.print(" cm  (change from baseline: ");
  Serial.print(change);
  Serial.print(" cm)");

  if (!alerted) {
    if (change > CHANGE_THRESHOLD_CM) {
      overThresholdStreak++;
      Serial.print("  [over threshold ");
      Serial.print(overThresholdStreak);
      Serial.print("/");
      Serial.print(CONFIRM_READINGS);
      Serial.println("]");
      if (overThresholdStreak >= CONFIRM_READINGS) {
        alerted = true;
        normalStreak = 0;
        digitalWrite(GREEN_LED, LOW);
        digitalWrite(RED_LED, HIGH);
        Serial.println("*** ALERT: significant distance change detected ***");
      }
    } else {
      overThresholdStreak = 0;
      Serial.println("  [OK]");
    }
  } else {
    if (change <= CHANGE_THRESHOLD_CM) {
      normalStreak++;
      Serial.print("  [ALERT -- recovering ");
      Serial.print(normalStreak);
      Serial.print("/");
      Serial.print(RECOVERY_READINGS);
      Serial.println("]");
      if (normalStreak >= RECOVERY_READINGS) {
        alerted = false;
        overThresholdStreak = 0;
        digitalWrite(RED_LED, LOW);
        digitalWrite(GREEN_LED, HIGH);
        Serial.println("--- back to normal ---");
      }
    } else {
      normalStreak = 0;
      Serial.println("  [ALERT]");
    }
  }

  delay(READ_INTERVAL_MS);
}
