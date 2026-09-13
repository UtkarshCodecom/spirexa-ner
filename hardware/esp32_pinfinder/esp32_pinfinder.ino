/*
  Board + pin identifier.

  Run this FIRST. It answers two questions:
    1. Which chip is actually on your board (ESP32 vs ESP8266)?
    2. What GPIO number does each "D" label on your silkscreen mean?

  Then it walks through the common GPIOs one at a time, announcing each on
  serial while pulsing it. Put an LED (with its 220ohm resistor) in the pin
  you want to identify and watch which announced number makes it light.

  Serial Monitor: 115200 baud.
*/

void announce(const char* label, int gpio) {
  Serial.print("  ");
  Serial.print(label);
  Serial.print("  ->  GPIO ");
  Serial.println(gpio);
}

void setup() {
  Serial.begin(115200);
  delay(1200);
  Serial.println();
  Serial.println("=======================================");
  Serial.println(" SPIREXA board identifier");
  Serial.println("=======================================");

#if defined(ESP32)
  Serial.println("Chip family : ESP32");
  Serial.print  ("Chip model  : "); Serial.println(ESP.getChipModel());
  Serial.print  ("Cores       : "); Serial.println(ESP.getChipCores());
  Serial.print  ("Flash size  : "); Serial.println(ESP.getFlashChipSize());
#elif defined(ESP8266)
  Serial.println("Chip family : ESP8266   <-- NOT an ESP32!");
  Serial.println("  If you expected ESP32, the board or the IDE board");
  Serial.println("  selection is wrong. ESP8266 has only ONE analog pin (A0),");
  Serial.println("  so rain + soil cannot both be read on it.");
#else
  Serial.println("Chip family : unknown");
#endif

  Serial.println();
  Serial.println("D-label -> GPIO mapping for THIS board:");

#ifdef D0
  announce("D0", D0);
#endif
#ifdef D1
  announce("D1", D1);
#endif
#ifdef D2
  announce("D2", D2);
#endif
#ifdef D3
  announce("D3", D3);
#endif
#ifdef D4
  announce("D4", D4);
#endif
#ifdef D5
  announce("D5", D5);
#endif
#ifdef D6
  announce("D6", D6);
#endif
#ifdef D7
  announce("D7", D7);
#endif
#ifdef D8
  announce("D8", D8);
#endif
#ifdef D9
  announce("D9", D9);
#endif
#ifdef D10
  announce("D10", D10);
#endif
#ifndef D0
  Serial.println("  (no D labels defined for the board you selected in the IDE -");
  Serial.println("   your silkscreen D numbers are the manufacturer's own, so");
  Serial.println("   use the pin walk below to map them)");
#endif

  Serial.println();
  Serial.println("Starting pin walk in 3 seconds.");
  Serial.println("Put an LED + 220ohm resistor between a pin and GND,");
  Serial.println("then watch which announced GPIO makes it light.");
  delay(3000);
}

// Safe, commonly broken-out output pins. 34-39 are input-only so they are
// deliberately not in this list - they cannot drive an LED.
const int CANDIDATES[] = {2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33};
const int N = sizeof(CANDIDATES) / sizeof(CANDIDATES[0]);

void loop() {
  for (int i = 0; i < N; i++) {
    int g = CANDIDATES[i];
    Serial.print("blinking GPIO ");
    Serial.println(g);

    pinMode(g, OUTPUT);
    for (int k = 0; k < 6; k++) {       // ~1.8s of visible blinking
      digitalWrite(g, HIGH); delay(150);
      digitalWrite(g, LOW);  delay(150);
    }
    pinMode(g, INPUT);                  // release it before moving on
  }
  Serial.println("--- end of sweep, repeating ---");
  Serial.println();
}
