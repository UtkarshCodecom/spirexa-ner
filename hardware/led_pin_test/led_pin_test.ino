/*
  Minimal LED pin test -- isolates whether D7/D8 and the LEDs work at
  all, independent of the rockfall_detector sketch's sensor and alert
  logic. Own folder, so it won't compile alongside any other sketch.

  Upload this alone. Green and red should alternate every 500ms,
  forever, starting the instant it boots -- no sensor, no calibration,
  no conditions to wait for.
*/

const int GREEN_LED = 7;
const int RED_LED = 8;

void setup() {
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
}

void loop() {
  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(RED_LED, LOW);
  delay(500);
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, HIGH);
  delay(500);
}
