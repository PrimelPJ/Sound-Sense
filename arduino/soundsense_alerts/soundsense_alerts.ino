// SoundSense alert device (Arduino Uno)
//
// Shows each sound as a light and buzzer pattern. Two buttons:
//   "I'm OK" button     -> turns the alert off and sends "ACK"
//   "Get help" button   -> texts backup contacts now and sends "ESCALATE"
//
// Wiring:
//   RGB LED (common cathode, longest leg to GND), each colour through 220 ohm:
//     red -> pin 3, green -> pin 5, blue -> pin 6
//   Buzzer (or a vibration motor through a transistor) -> pin 9, other leg to GND
//   "I'm OK" button    -> pin 2 and GND (uses the built-in pull-up)
//   "Get help" button  -> pin 4 and GND (uses the built-in pull-up)
//
// Optional LED strip (WS2812B) instead of the RGB LED: set USE_STRIP to 1, data to pin 6
// through 330 ohm, and install "Adafruit NeoPixel" from the Library Manager.
//
// Serial, 115200 baud, one command per line:
//   ALERT smoke_alarm | glass_break | baby_cry | siren | doorbell | phone | kettle | help
//   CLEAR, PING (replies PONG), TEST (plays every pattern once)
// Sends: READY on boot, ACK ("I'm OK" pressed), ESCALATE ("Get help" pressed).

#define USE_STRIP 0  // 0 = kit RGB LED, 1 = WS2812B LED strip

#if USE_STRIP
#include <Adafruit_NeoPixel.h>
#endif

const int LED_PIN = 6;    // strip data
const int RED_PIN = 3;    // RGB LED legs (all PWM pins)
const int GREEN_PIN = 5;
const int BLUE_PIN = 6;
const int MOTOR_PIN = 9;
const int BUTTON_PIN = 2;       // "I'm OK"
const int HELP_BUTTON_PIN = 4;  // "Get help" (change to 11 if the wire is in pin 11)
const int NUM_LEDS = 8;
const uint8_t BRIGHTNESS = 60;  // keep low so the Uno's 5V pin can power the strip

const unsigned long DOOR_TIMEOUT = 10000;    // heads up sounds turn off on their own
const unsigned long KETTLE_TIMEOUT = 15000;
const unsigned long PHONE_TIMEOUT = 15000;
const unsigned long SIREN_TIMEOUT = 20000;

#if USE_STRIP
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);
#endif

enum Mode { NONE = 0, KETTLE = 1, PHONE = 2, DOOR = 3, SIREN = 4, BABY = 5, GLASS = 6, SMOKE = 7, HELP = 8 };  // higher = more important
Mode mode = NONE;
unsigned long modeStart = 0;

char line[40];
uint8_t lineLen = 0;

// One of these for each button, so each one is debounced on its own.
struct Button {
  int pin;
  int lastReading;
  int state;
  unsigned long lastChange;
};
Button okButton = {BUTTON_PIN, HIGH, HIGH, 0};
Button helpButton = {HELP_BUTTON_PIN, HIGH, HIGH, 0};

// "Get help" pattern: SOS in Morse (on/off times in ms, starting with "on").
const unsigned int SOS[] = {200, 200, 200, 200, 200, 600,   // S
                            600, 200, 600, 200, 600, 600,   // O
                            200, 200, 200, 200, 200, 1400}; // S
const int SOS_STEPS = sizeof(SOS) / sizeof(SOS[0]);

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

bool sosOn(unsigned long t) {
  unsigned long total = 0;
  for (int i = 0; i < SOS_STEPS; i++) total += SOS[i];
  unsigned long p = t % total;
  for (int i = 0; i < SOS_STEPS; i++) {
    if (p < SOS[i]) return i % 2 == 0;
    p -= SOS[i];
  }
  return false;
}

void runPattern() {
  unsigned long t = millis() - modeStart;

  switch (mode) {
    case HELP: {  // orange SOS flashes with matching beeps (orange = help is on the way)
      bool on = sosOn(t);
      setColor(on ? 255 : 0, on ? 60 : 0, 0);
      setMotor(on);
      break;
    }
    case SMOKE: {  // red fast flash, long buzzes
      bool on = (t % 300) < 150;
      setColor(on ? 255 : 0, 0, 0);
      setMotor((t % 1000) < 600);
      break;
    }
        case GLASS: {  // white fast strobe, quick buzzes
      bool on = (t % 200) < 100;
      setColor(on ? 255 : 0, on ? 255 : 0, on ? 255 : 0);
      setMotor((t % 800) < 400);
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
        case SIREN: {  // red and blue swapping, like an emergency vehicle
      bool red = (t % 800) < 400;
      setColor(red ? 255 : 0, 0, red ? 0 : 255);
      setMotor(t < 300);
      if (t > SIREN_TIMEOUT) setMode(NONE);
      break;
    }
    case PHONE: {  // green ring-ring, two taps
      unsigned long p = t % 3000;
      bool on = p < 400 || (p >= 600 && p < 1000);
      setColor(0, on ? 255 : 0, 0);
      setMotor(on);
      if (t > PHONE_TIMEOUT) setMode(NONE);
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
  if (strcmp(sound, "glass_break") == 0) return GLASS;
  if (strcmp(sound, "baby_cry") == 0) return BABY;
  if (strcmp(sound, "siren") == 0) return SIREN;
  if (strcmp(sound, "doorbell") == 0) return DOOR;
  if (strcmp(sound, "phone") == 0) return PHONE;
  if (strcmp(sound, "kettle") == 0) return KETTLE;
  if (strcmp(sound, "help") == 0) return HELP;
  return NONE;
}


void playTest() {
  Mode order[] = {SMOKE, GLASS, BABY, SIREN, DOOR, PHONE, KETTLE, HELP};
  for (int i = 0; i < 8; i++) {
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

// ---------- buttons ----------

// True once each time the button is pressed (after 40 ms of debounce).
bool pressed(Button &b) {
  int reading = digitalRead(b.pin);
  bool justPressed = false;
  if (reading != b.lastReading) b.lastChange = millis();
  if (millis() - b.lastChange > 40 && reading != b.state) {
    b.state = reading;
    justPressed = (b.state == LOW);
  }
  b.lastReading = reading;
  return justPressed;
}

void readButtons() {
  if (pressed(okButton)) {  // "I'm OK": everything off
    Serial.println("ACK");
    setMode(NONE);
  }
  if (pressed(helpButton)) {  // "Get help": text people now
    Serial.println("ESCALATE");
    setMode(HELP);
  }
}

// ---------- main ----------

void setup() {
  pinMode(MOTOR_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(HELP_BUTTON_PIN, INPUT_PULLUP);
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
  readButtons();
  runPattern();
}
