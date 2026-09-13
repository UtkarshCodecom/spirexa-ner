/*
  Step 2 - test the parts, one subsystem at a time. No libraries, so this
  is guaranteed to compile (which also means it cannot be the DHT library
  that is breaking it).

  Tests: the two external LEDs, the touch pad, and both analog sensors.
  The DHT is deliberately NOT here - it needs a library, and we test that
  separately once everything else is proven.

  WIRE IT UP IN THIS ORDER, re-running after each step:

    Step A - LEDs only
        Green LED   D18 -> 220ohm -> LED long leg; short leg -> GND
        White LED   D19 -> 220ohm -> LED long leg; short leg -> GND
      Expect: they alternate, half a second each. If one never lights,
      that LED/resistor/row is the fault - swap the LED's legs first.

    Step B - add the touch pad
        Touch  VCC -> 3V3   GND -> GND   SIG -> D13
      Expect: the printed touch value flips to YES while you hold it.

    Step C - add rain and soil
        Rain   VCC -> 3V3   GND -> GND   AO -> D34
        Soil   VCC -> 3V3   GND -> GND   AO -> D35
      Expect: numbers that CHANGE when you wet the sensor. A value stuck
      near 0, or stuck near 4095, or drifting randomly with nothing
      touching it, means that pin is not actually connected.

  Serial Monitor: 115200 baud.
*/

#define PIN_LED_GREEN  21     // moved off D18 - suspect pin
#define PIN_LED_WHITE  19     // known working
#define PIN_TOUCH      22     // moved off D13 - suspect pin
#define PIN_RAIN       34
#define PIN_SOIL       35

bool phase = false;

int readAvg(int pin) {
  long sum = 0;
  for (int i = 0; i < 12; i++) { sum += analogRead(pin); delay(3); }
  return (int)(sum / 12);
}

void setup() {
  Serial.begin(115200);
  delay(800);

  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_WHITE, OUTPUT);
  pinMode(PIN_TOUCH, INPUT_PULLDOWN);   // unconnected now reads LOW, not random

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  Serial.println();
  Serial.println("PARTS TEST v2 (no libraries used)");
  Serial.println("  green LED -> D21   white LED -> D19");
  Serial.println("  touch SIG -> D22   rain -> D34   soil -> D35");
  Serial.println("Touch uses a pulldown now: with nothing wired it reads 'no'.");
  Serial.println("If it reads YES constantly, the module or its wiring is wrong.");
  Serial.println();
}

void loop() {
  // alternate the two LEDs so a dead one is obvious
  phase = !phase;
  digitalWrite(PIN_LED_GREEN, phase ? HIGH : LOW);
  digitalWrite(PIN_LED_WHITE, phase ? LOW  : HIGH);

  Serial.print("green=");
  Serial.print(phase ? "ON " : "off");
  Serial.print("  white=");
  Serial.print(phase ? "off" : "ON ");
  Serial.print("   touch=");
  Serial.print(digitalRead(PIN_TOUCH) ? "YES" : "no ");
  Serial.print("   rain raw=");
  Serial.print(readAvg(PIN_RAIN));
  Serial.print("   soil raw=");
  Serial.println(readAvg(PIN_SOIL));

  delay(500);
}
