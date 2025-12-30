/*
  dogdoor_controller_with_debug_oled.ino
  Heltec WiFi Kit 32 V2: automatic dog door control + OLED debug screen (SSD1306Wire)

  Startup rule:
    - If LIMIT_CLOSE is active (LOW) at boot => CLOSED
    - Else => CLOSING (seek the closed limit)

  Assumptions:
    - LIMIT_OPEN  is active LOW when fully open (reed switch connected to gnd)
    - LIMIT_CLOSE is active LOW when fully closed (reed switch connected to gnd)
    - PIR_IN/PIR_OUT are HIGH when motion is detected
    - Motor driven by M1/M2:
        OPENING: M1=HIGH, M2=LOW
        CLOSING: M1=LOW,  M2=HIGH
        STOP:    both LOW
*/
/*
Parts list:
 Heltec WiFi Kit 32 V2
 2 x PIR HC-SR501
 2 x Reed sensors
L9110S
yellow TT gearbox motor

*/

#include <Arduino.h>
#include <Wire.h>
#include <SSD1306Wire.h>

/* ------------------ Pins ------------------ */
static const int PIR_IN  = 2;
static const int PIR_OUT = 17;

static const int LIMIT_OPEN  = 13;   // LOW when fully open
static const int LIMIT_CLOSE = 12;   // LOW when fully closed

//static const int ERROR_PIN = 7;     // OUTPUT: HIGH on fault (we drive it)

static const int M1 = 5;
static const int M2 = 18;

/* ------------------ OLED (Heltec WiFi Kit 32 V2) ------------------ */
#define OLED_ADDR 0x3C
#define SDA_PIN   4
#define SCL_PIN   15
#define OLED_RST  16
#define VEXT_PIN  21

SSD1306Wire display(OLED_ADDR, SDA_PIN, SCL_PIN);

/* ------------------ Timing ------------------ */
static const uint32_t HOLD_OPEN_MS      = 30000;   // keep door open after last motion
static const uint32_t MOVE_TIMEOUT_MS   = 12000;  // max time motor can run in one move
static const uint32_t DISPLAY_PERIOD_MS = 150;

/* ------------------ State ------------------ */
enum DoorStatus {
  ST_OPENED,
  ST_CLOSING,
  ST_CLOSED,
  ST_OPENING,
  ST_FAULT
};

static DoorStatus g_state = ST_CLOSED;
static DoorStatus g_prev_state = ST_CLOSED;

static uint32_t g_state_changed_ms = 0;
static uint32_t g_move_started_ms  = 0;
static uint32_t g_last_motion_ms   = 0;

/* ------------------ Helpers ------------------ */
static void motorStop() {
  digitalWrite(M1, LOW);
  digitalWrite(M2, LOW);
}

static void motorOpen() {
  digitalWrite(M1, HIGH);
  digitalWrite(M2, LOW);
}

static void motorClose() {
  digitalWrite(M1, LOW);
  digitalWrite(M2, HIGH);
}


static void setFault(bool on) {
//  digitalWrite(ERROR_PIN, on ? HIGH : LOW);
}

static const char* statusToStr(DoorStatus s) {
  switch (s) {
    case ST_OPENED:  return "Opened";
    case ST_CLOSING: return "Closing";
    case ST_CLOSED:  return "Closed";
    case ST_OPENING: return "Opening";
    case ST_FAULT:   return "Fault";
    default:         return "?";
  }
}

static void oledPowerOnAndReset() {
  pinMode(VEXT_PIN, OUTPUT);
  digitalWrite(VEXT_PIN, LOW);   // Vext ON
  delay(50);

  pinMode(OLED_RST, OUTPUT);
  digitalWrite(OLED_RST, LOW);
  delay(20);
  digitalWrite(OLED_RST, HIGH);
  delay(50);
}

static void drawBool(int x, int y, const char* label, bool val) {
  display.drawString(x, y, label);
  display.drawString(x + 78, y, val ? "True" : "False");
}

static void transitionTo(DoorStatus next) {
  if (next == g_state) return;
  g_prev_state = g_state;
  g_state = next;
  g_state_changed_ms = millis();

  // Start movement timer when entering a movement state
  if (g_state == ST_OPENING || g_state == ST_CLOSING) {
    g_move_started_ms = millis();
  }
}

/* ------------------ Setup ------------------ */
void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIR_IN, INPUT);
  pinMode(PIR_OUT, INPUT);

  pinMode(LIMIT_OPEN, INPUT_PULLUP);
  pinMode(LIMIT_CLOSE, INPUT_PULLUP);

  pinMode(M1, OUTPUT);
  pinMode(M2, OUTPUT);
  motorStop();

  //pinMode(ERROR_PIN, OUTPUT);
  //setFault(false);

  oledPowerOnAndReset();
  Wire.begin(SDA_PIN, SCL_PIN);

  display.init();
  display.flipScreenVertically();
  display.clear();
  display.display();

  // --- Startup state selection rule (yours) ---
  bool limCloseActive = (digitalRead(LIMIT_CLOSE) == LOW);

  g_state_changed_ms = millis();
  g_last_motion_ms   = millis();

  if (limCloseActive) {
    transitionTo(ST_CLOSED);
    motorStop();
  } else {
    transitionTo(ST_CLOSING);
    motorClose();
  }
}

/* ------------------ Main loop ------------------ */
void loop() {
  uint32_t now = millis();

  // Inputs
  bool pirIn  = (digitalRead(PIR_IN)  == HIGH);
  bool pirOut = (digitalRead(PIR_OUT) == HIGH);

  bool limOpenActive  = (digitalRead(LIMIT_OPEN)  == LOW);
  bool limCloseActive = (digitalRead(LIMIT_CLOSE) == LOW);

  bool motion = (pirIn || pirOut);
  if (motion) g_last_motion_ms = now;

  // State machine
  switch (g_state) {
    case ST_CLOSED:
      setFault(false);
      motorStop();
      if (motion) {
        transitionTo(ST_OPENING);
        motorOpen();
      }
      break;

    case ST_OPENING:
      setFault(false);
      // Stop when open limit reached
      if (limOpenActive) {
        motorStop();
        transitionTo(ST_OPENED);
      } else if (now - g_move_started_ms > MOVE_TIMEOUT_MS) {
        motorStop();
        setFault(true);
        transitionTo(ST_FAULT);
      }
      break;

    case ST_OPENED:
      setFault(false);
      motorStop();
      // Hold open until no motion for HOLD_OPEN_MS
      if (!motion && (now - g_last_motion_ms > HOLD_OPEN_MS)) {
        transitionTo(ST_CLOSING);
        motorClose();
      }
      break;

    case ST_CLOSING:
      setFault(false);
      // If motion occurs while closing, reopen immediately
      if (motion) {
        transitionTo(ST_OPENING);
        motorOpen();
        break;
      }
      // Stop when closed limit reached
      if (limCloseActive) {
        motorStop();
        transitionTo(ST_CLOSED);
      } else if (now - g_move_started_ms > MOVE_TIMEOUT_MS) {
        motorStop();
        setFault(true);
        transitionTo(ST_FAULT);
      }
      break;

    case ST_FAULT:
      motorStop();
      // Simple recovery: if it becomes closed, clear fault and go CLOSED
      if (limCloseActive) {
        setFault(false);
        transitionTo(ST_CLOSED);
      }
      break;
  }

  // Status timer (0..999 s)
  uint32_t elapsed_s = (now - g_state_changed_ms) / 1000UL;
  if (elapsed_s > 999) elapsed_s = 999;

  // OLED render (rate-limited)
  static uint32_t lastDisplayMs = 0;
  if (now - lastDisplayMs >= DISPLAY_PERIOD_MS) {
    lastDisplayMs = now;

    display.clear();
    display.setTextAlignment(TEXT_ALIGN_LEFT);
    display.setFont(ArialMT_Plain_10);

    display.drawString(0, 0, "Status:");
    display.drawString(78, 0, statusToStr(g_state));

    display.drawString(0, 10, "Timer:");
    char tbuf[16];
    snprintf(tbuf, sizeof(tbuf), "%lus", (unsigned long)elapsed_s);
    display.drawString(78, 10, tbuf);

    drawBool(0, 20, "PIR In:", pirIn);
    drawBool(0, 30, "PIR Out:", pirOut);
    drawBool(0, 40, "Limit Closed:", limCloseActive);
    drawBool(0, 50, "Limit Opened:", limOpenActive);

    display.display();
  }
}
