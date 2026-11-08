// Button test: shows which pin each button is on.
// Open Serial Monitor at 115200 and press each button.
//   "I'm OK" on pin 2: green flash
//   "Get help" on pin 4 or 11: orange flash and a beep
// If "Get help" shows up on pin 11, set HELP_BUTTON_PIN to 11 in the main sketch.

const int PINS[] = {2, 4, 11};
const int N = 3;
int last[N];

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) {
    pinMode(PINS[i], INPUT_PULLUP);
    last[i] = HIGH;
  }
  pinMode(3, OUTPUT); pinMode(5, OUTPUT); pinMode(6, OUTPUT); pinMode(9, OUTPUT);
  Serial.println("Press each button");
}

void loop() {
  for (int i = 0; i < N; i++) {
    int now = digitalRead(PINS[i]);
    if (now == LOW && last[i] == HIGH) {
      Serial.print("Button on pin ");
      Serial.print(PINS[i]);
      Serial.println(" pressed");
      if (PINS[i] == 2) {          // I'm OK: green flash
        analogWrite(5, 255); delay(300); analogWrite(5, 0);
      } else {                     // Get help: orange flash and a beep
        analogWrite(3, 255); analogWrite(5, 60); digitalWrite(9, HIGH);
        delay(300);
        analogWrite(3, 0); analogWrite(5, 0); digitalWrite(9, LOW);
      }
      delay(50);
    }
    last[i] = now;
  }
}
