// SoundSense alert device (Arduino Uno)
//
// Shows each sound as a light and vibration pattern, and sends "ACK" when the
// "I'm OK" button is pressed.
//
// Wiring:
//   LED strip data (WS2812B)  -> pin 6 through a 330 ohm resistor, strip 5V -> 5V, GND -> GND
//   Vibration motor           -> pin 9 through a 1k resistor to a 2N2222 base,
//                                motor between 5V and collector, emitter to GND,
//                                1N4007 diode across the motor (stripe to 5V)
//   "I'm OK" button           -> pin 2 and GND (uses the built-in pull-up)
//
// No LED strip? Set USE_STRIP to 0 and use the kit's RGB LED instead (common cathode,
// longest leg to GND): red leg -> 220 ohm -> pin 3, green -> 220 ohm -> pin 5,
// blue -> 220 ohm -> pin 6.
// Library (only for the strip): Arduino IDE > Library Manager > "Adafruit NeoPixel".
//
// Serial, 115200 baud, one command per line:
//   ALERT smoke_alarm | ALERT baby_cry | ALERT doorbell | ALERT kettle
//   CLEAR, PING (replies PONG), TEST (plays every pattern once)
// Sends: READY on boot, ACK when the button is pressed.

#define USE_STRIP 0  // 0 = kit RGB LED, 1 = WS2812B LED strip

#if USE_STRIP
#include <Adafruit_NeoPixel.h>
#endif

const int LED_PIN = 6;    // strip data
const int RED_PIN = 3;    // RGB LED legs (all PWM pins)
const int GREEN_PIN = 5;
const int BLUE_PIN = 6;
const int MOTOR_PIN = 9;
const int BUTTON_PIN = 2;
const int NUM_LEDS = 8;
const uint8_t BRIGHTNESS = 60;  // keep low so the Uno's 5V pin can power the strip

const unsigned long DOOR_TIMEOUT = 10000;    // heads up sounds turn off on their own
const unsigned long KETTLE_TIMEOUT = 15000;

#if USE_STRIP
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);
#endif

enum Mode { NONE = 0, KETTLE = 1, DOOR = 2, BABY = 3, SMOKE = 4 };  // higher = more important
Mode mode = NONE;
unsigned long modeStart = 0;

char line[40];
uint8_t lineLen = 0;

int lastReading = HIGH;
int buttonState = HIGH;
unsigned long lastChange = 0;

// ---------- output helpers ----------

void setColor(uint8_t r, uint8_t g, uint8_t b) {
#if USE_STRIP
  for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, strip.Color(r, g, b));
  strip.show();
#else
  analogWrite(RED_PIN, r);
  analogWrite(GREEN_PIN, g);
  analogWrite(BLUE_PIN, b);
#endif
}

void setMotor(bool on) {
  digitalWrite(MOTOR_PIN, on ? HIGH : LOW);
}

void allOff() {
  setColor(0, 0, 0);
  setMotor(false);
}

void setMode(Mode m) {
  mode = m;
  modeStart = millis();
  if (m == NONE) allOff();
}

// ---------- patterns (non-blocking, run every loop) ----------

void runPattern() {
  unsigned long t = millis() - modeStart;

  switch (mode) {
    case SMOKE: {  // red fast flash, long buzzes
      bool on = (t % 300) < 150;
      setColor(on ? 255 : 0, 0, 0);
      setMotor((t % 1000) < 600);
      break;
    }
    case BABY: {  // purple slow pulse, short buzzes
      unsigned long p = t % 1600;
      uint8_t level = p < 800 ? p * 255 / 800 : (1600 - p) * 255 / 800;
      setColor(level * 140 / 255, 0, level);
      setMotor((t % 1500) < 200);
      break;
    }
    case DOOR: {  // blue double flash, two taps
      unsigned long p = t % 2000;
      bool on = p < 200 || (p >= 400 && p < 600);
      setColor(0, 0, on ? 255 : 0);
      setMotor(p < 150 || (p >= 400 && p < 550));
      if (t > DOOR_TIMEOUT) setMode(NONE);
      break;
    }
    case KETTLE: {  // amber steady, one tap at the start
      setColor(255, 120, 0);
      setMotor(t < 300);
      if (t > KETTLE_TIMEOUT) setMode(NONE);
      break;
    }
    default:
      break;
  }
}

// ---------- serial commands ----------

Mode modeFor(const char *sound) {
  if (strcmp(sound, "smoke_alarm") == 0) return SMOKE;
  if (strcmp(sound, "baby_cry") == 0) return BABY;
  if (strcmp(sound, "doorbell") == 0) return DOOR;
  if (strcmp(sound, "kettle") == 0) return KETTLE;
  return NONE;
}

void playTest() {
  Mode order[] = {SMOKE, BABY, DOOR, KETTLE};
  for (int i = 0; i < 4; i++) {
    setMode(order[i]);
    unsigned long start = millis();
    while (millis() - start < 2000) runPattern();
  }
  setMode(NONE);
}

void handleLine(char *cmd) {
  if (strncmp(cmd, "ALERT ", 6) == 0) {
    Mode m = modeFor(cmd + 6);
    // Don't let a doorbell hide a smoke alarm that is still going.
    if (m != NONE && m >= mode) setMode(m);
  } else if (strcmp(cmd, "CLEAR") == 0) {
    setMode(NONE);
  } else if (strcmp(cmd, "PING") == 0) {
    Serial.println("PONG");
  } else if (strcmp(cmd, "TEST") == 0) {
    playTest();
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      line[lineLen] = '\0';
      if (lineLen > 0) handleLine(line);
      lineLen = 0;
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = c;
    }
  }
}

// ---------- button ----------

void readButton() {
  int reading = digitalRead(BUTTON_PIN);
  if (reading != lastReading) lastChange = millis();
  if (millis() - lastChange > 40 && reading != buttonState) {
    buttonState = reading;
    if (buttonState == LOW) {  // pressed
      Serial.println("ACK");
      setMode(NONE);
    }
  }
  lastReading = reading;
}

// ---------- main ----------

void setup() {
  pinMode(MOTOR_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
#if USE_STRIP
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
#else
  pinMode(RED_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(BLUE_PIN, OUTPUT);
#endif
  allOff();

  // Quick green blink so you can see the board booted.
  setColor(0, 120, 0);
  delay(250);
  allOff();

  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  readSerial();
  readButton();
  runPattern();
}
