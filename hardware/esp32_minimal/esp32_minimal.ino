/*
  Absolute minimum ESP32 test.

  No libraries. No sensors. No WiFi. No external wiring at all -
  just the LED already soldered onto the board.

  Unplug EVERYTHING from the ESP32 except the USB cable, then upload this.

  Expected: the small blue onboard LED blinks steadily, once a second,
  and the Serial Monitor (115200 baud) counts upward.

  If that happens  -> the board and the toolchain are fine, and the problem
                      is in the wiring of the sensors/LEDs.
  If it does NOT   -> nothing is reaching the board. The sketch is not
                      uploading, or is not compiling. Check the black
                      output panel at the bottom of the Arduino IDE for
                      a red error message.
*/

#define LED 2          // onboard blue LED, already wired on the board

unsigned long count = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(LED, OUTPUT);
  Serial.println();
  Serial.println("=================================");
  Serial.println(" MINIMAL TEST IS RUNNING");
  Serial.println(" If you can read this, the sketch");
  Serial.println(" uploaded and the board is alive.");
  Serial.println("=================================");
}

void loop() {
  digitalWrite(LED, HIGH);
  delay(500);
  digitalWrite(LED, LOW);
  delay(500);

  count++;
  Serial.print("alive, second ");
  Serial.println(count);
}
