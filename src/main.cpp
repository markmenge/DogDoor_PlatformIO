/*    
      One day we might use this controller:
      VM PWMA  
      VCC AIN2  
      GND AIN1  
      A01 STBY  
      A02 BIN1  
      B02 BIN2
      B01 PWMB 
      GND GND
*/

/*
  dogdoor_controller_with_debug_oled.ino
  Heltec WiFi Kit 32 V2: automatic dog door control + OLED debug screen (SSD1306Wire)

  Startup rule:
    - If debug mode is enabled => motor stopped; no automatic movement
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
 Heltec WiFi Kit 32 V2 with OLED display
 2 x PIR HC-SR501
 2 x Reed sensors
L9110S  2.5 to 12V 800 ma
yellow TT gearbox motor 1.2–2.0 A at 5 V stall current

*/

#include <Arduino.h>
#include <Wire.h>
#include <SSD1306Wire.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <WebServer.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <stdarg.h>

#if __has_include("ota_config.h")
#include "ota_config.h"
#else
#include "ota_config.example.h"
#endif

/* ------------------ Pins ------------------ */
static const int PIR_IN  = 17;
static const int PIR_OUT = 2;

static const int LIMIT_OPEN  = 13;   // LOW when fully open
static const int LIMIT_CLOSE = 12;   // LOW when fully closed

static const int M1 = 25;   // open
static const int M2 = 26;   // close

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
  ST_FAULT,
  ST_FORCE_OPENING,
  ST_FORCE_CLOSING
};

static DoorStatus g_state = ST_CLOSED;
static DoorStatus g_prev_state = ST_CLOSED;

static uint32_t g_state_changed_ms = 0;
static uint32_t g_move_started_ms  = 0;
static uint32_t g_last_motion_ms   = 0;
static bool g_ota_started = false;
static bool g_ota_motor_locked = false;
static volatile bool g_debug_mode = true;
static volatile int g_debug_direction = 0;
static esp_timer_handle_t g_debug_timer;
static WebServer g_web_server(5000);
static const size_t EVENT_COUNT = 24;
static const size_t EVENT_LENGTH = 192;
static char g_events[EVENT_COUNT][EVENT_LENGTH];
static size_t g_event_next = 0;
static size_t g_event_count = 0;
static portMUX_TYPE g_event_lock = portMUX_INITIALIZER_UNLOCKED;

static void logEvent(const char* format, ...) {
  char message[EVENT_LENGTH] = {};
  int prefix = snprintf(message, sizeof(message), "[%lu s] ", (unsigned long)(millis() / 1000));
  va_list arguments;
  va_start(arguments, format);
  vsnprintf(message + prefix, sizeof(message) - prefix, format, arguments);
  va_end(arguments);
  portENTER_CRITICAL(&g_event_lock);
  memcpy(g_events[g_event_next], message, sizeof(message));
  g_event_next = (g_event_next + 1) % EVENT_COUNT;
  if (g_event_count < EVENT_COUNT) ++g_event_count;
  portEXIT_CRITICAL(&g_event_lock);
}

static const char* resetReasonText(esp_reset_reason_t reason) {
  switch (reason) {
    case ESP_RST_POWERON: return "Power-on reset";
    case ESP_RST_EXT: return "External reset";
    case ESP_RST_SW: return "Software reset (may follow OTA)";
    case ESP_RST_PANIC: return "Panic / crash";
    case ESP_RST_INT_WDT: return "Interrupt watchdog reset";
    case ESP_RST_TASK_WDT: return "Task watchdog reset";
    case ESP_RST_WDT: return "Other watchdog reset";
    case ESP_RST_DEEPSLEEP: return "Wake from deep sleep";
    case ESP_RST_BROWNOUT: return "Brownout reset (supply voltage dropped)";
    case ESP_RST_SDIO: return "SDIO reset";
    default: return "Unknown reset reason";
  }
}

static const char PIN_PAGE[] PROGMEM = R"HTML(
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dog Door | Pins</title>
<style>
:root{color-scheme:light;--ink:#202622;--muted:#627066;--line:#d5ddd7;--green:#176647}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:"Segoe UI",sans-serif;background:#f5f7f5;background-image:linear-gradient(90deg,#00000003 1px,transparent 1px);background-size:24px 24px}
main{max-width:820px;margin:auto;padding:32px 20px}header{border-bottom:2px solid var(--ink);padding-bottom:18px;display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-family:Georgia,serif;font-size:30px;margin:0}#connection{font-size:14px;color:var(--muted)}#connection[data-online="true"]{color:var(--green)}
dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:24px 0}dt{font-size:12px;color:var(--muted);margin-bottom:6px}dd{margin:0;font-weight:600;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;table-layout:fixed;background:#fff}th,td{text-align:left;padding:13px 10px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{font-size:12px;color:var(--muted);font-weight:600}th:first-child{width:34%}td:nth-child(2){font-family:Consolas,monospace}td:last-child{font-weight:600}footer{margin-top:18px;font-size:12px;color:var(--muted)}
.debug{border-top:2px solid var(--ink);margin-top:28px;padding-top:18px}.debug h2{font-family:Georgia,serif;font-size:22px;margin:0}.debug-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.debug label{font-size:14px}.debug-fields{display:grid;grid-template-columns:1fr 1fr;gap:18px}.debug-fields label{display:block}.debug input[type=password]{width:100%;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:4px;font:inherit}.debug input[type=range]{width:100%;margin-top:12px;accent-color:var(--green)}.debug output{font-family:Consolas,monospace;font-size:13px}.commands{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:18px}button{min-height:44px;border:1px solid var(--line);border-radius:4px;background:white;font:inherit;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}#stop{background:#a12f36;color:white;border-color:#a12f36}#debug-message{min-height:38px;font-size:13px;color:var(--muted);margin-bottom:0}input[type=checkbox]{accent-color:var(--green)}
@media(max-width:480px){main{padding:22px 12px}h1{font-size:26px}th,td{padding:12px 6px;font-size:13px}dl{gap:8px}}
@media(max-width:480px){.debug-fields{grid-template-columns:1fr}.commands{gap:6px}}
.events{margin-top:24px;border-top:1px solid var(--line);padding-top:18px}.events h2{font-family:Georgia,serif;font-size:22px;margin:0 0 12px}.events pre{font:13px/1.6 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto;margin:0;padding:12px;background:#fff;border:1px solid var(--line)}#events-status{font-size:12px;color:var(--muted)}
</style>
</head>
<body><main>
<header><h1>Dog Door</h1><span id="connection" role="status">Connecting</span></header>
<dl><div><dt>DOOR</dt><dd id="state">--</dd></div><div><dt>UPTIME</dt><dd id="uptime">--</dd></div><div><dt>WI-FI</dt><dd id="rssi">--</dd></div></dl>
<table aria-label="Live GPIO values"><thead><tr><th>Signal</th><th>GPIO</th><th>Mode</th><th>Value</th></tr></thead><tbody id="pins"></tbody></table>
<section class="debug" aria-labelledby="debug-title">
<div class="debug-header"><h2 id="debug-title">Motor Debug</h2><label><input type="checkbox" id="debug-mode" disabled> Debug mode</label></div>
<div class="debug-fields"><label>Output <output id="duty-value">0 (LOW)</output><input id="duty" type="range" min="0" max="1" step="1" value="0"></label></div>
<div class="commands"><button id="open" disabled>Open</button><button id="close" disabled>Close</button><button id="stop" disabled>Stop</button></div>
<p id="debug-message" role="status">--</p>
</section>
<section class="events" aria-labelledby="events-title"><h2 id="events-title">Events</h2><pre id="events">Connecting</pre><p id="events-status" role="status"></p></section>
<footer>Heltec WiFi Kit 32 V2 &middot; 192.168.1.251:5000</footer>
</main><script>
const pins=[['PIR inside',17,'Input','pir_in'],['PIR outside',2,'Input','pir_out'],['Open limit',13,'Pull-up','limit_open'],['Closed limit',12,'Pull-up','limit_close'],['Motor open',25,'Output','motor_open'],['Motor close',26,'Output','motor_close']];
const rows=document.getElementById('pins');
for(const [name,gpio,mode,key] of pins){const row=document.createElement('tr');for(const value of [name,gpio,mode,'--']){const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell)}row.lastChild.id=key;rows.appendChild(row)}
let latest=null,busy=false,online=false;
const mode=document.getElementById('debug-mode'),duty=document.getElementById('duty'),message=document.getElementById('debug-message');
function syncControls(){const ready=online&&!busy&&latest&&!latest.ota_locked;mode.disabled=!ready;if(!busy)mode.checked=!!latest?.debug_mode;for(const action of ['open','close'])document.getElementById(action).disabled=!ready||!latest.debug_mode||latest.debug_direction!==0||(action==='open'?latest.limit_open===0:latest.limit_close===0);document.getElementById('stop').disabled=!online||busy;duty.disabled=busy}
duty.addEventListener('input',()=>{document.getElementById('duty-value').textContent=duty.value+(duty.value==='1'?' (HIGH)':' (LOW)')});
async function command(action){busy=true;syncControls();try{const response=await fetch('/api/debug',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({action,duty:duty.value}),signal:AbortSignal.timeout(2500)});const result=await response.text();if(!response.ok)throw new Error(result);message.textContent=result;const status=await fetch('/api/pins',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!status.ok)throw new Error('Status unavailable');latest=await status.json()}catch(error){message.textContent=error.message}finally{busy=false;syncControls()}}
mode.addEventListener('change',()=>command(mode.checked?'enable':'disable'));
for(const action of ['open','close','stop'])document.getElementById(action).addEventListener('click',()=>command(action));
async function refresh(){const connection=document.getElementById('connection');try{const response=await fetch('/api/pins',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!response.ok)throw new Error('HTTP '+response.status);const data=await response.json();latest=data;online=true;document.getElementById('state').textContent=data.ota_locked?'OTA motor lock':data.debug_mode?(data.debug_direction>0?'Debug opening':data.debug_direction<0?'Debug closing':'Debug stopped'):data.state;document.getElementById('uptime').textContent=Math.floor(data.uptime_ms/1000)+' s';document.getElementById('rssi').textContent=data.rssi+' dBm';for(const [name,gpio,mode,key] of pins){const value=data[key];document.getElementById(key).textContent=(value?'HIGH':'LOW')+(key.startsWith('limit_')?(value?' (inactive)':' (active)'):'')}connection.textContent='Live';connection.dataset.online='true'}catch(error){online=false;connection.textContent='Offline / stale';connection.dataset.online='false'}finally{syncControls();setTimeout(refresh,1000)}}
refresh();
async function refreshEvents(){try{const response=await fetch('/api/events',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!response.ok)throw new Error('HTTP '+response.status);const text=await response.text();const log=document.getElementById('events');if(log.textContent!==text)log.textContent=text;document.getElementById('events-status').textContent=''}catch(error){document.getElementById('events-status').textContent='Events offline / stale'}finally{setTimeout(refreshEvents,2000)}}
refreshEvents();
</script></body></html>
)HTML";

/* ------------------ Helpers ------------------ */
static void motorStop() {
  digitalWrite(M1, LOW);
  digitalWrite(M2, LOW);
}

// With shaft pointed towards you, CounterClockWise
static void motorOpen() {
  digitalWrite(M2, LOW);
  delayMicroseconds(50);
  digitalWrite(M1, HIGH);
}

// With shaft pointed towards you, ClockWise
static void motorClose() {
  digitalWrite(M1, LOW);
  delayMicroseconds(50);
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
    case ST_FORCE_OPENING:   return "Force Opening";
    case ST_FORCE_CLOSING:   return "Force Closing";
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

static void transitionTo(DoorStatus next, const char *why) {
  if (next == g_state) return;
  Serial.printf("From %s to %s. Reason: %s\n", statusToStr(g_state), statusToStr(next), why);
  logEvent("%s -> %s: %s", statusToStr(g_state), statusToStr(next), why);
  g_prev_state = g_state;
  g_state = next;
  g_state_changed_ms = millis();

  // Start movement timer when entering a movement state
  if (g_state == ST_OPENING || g_state == ST_CLOSING) {
    g_move_started_ms = millis();
  }
}

static void debugWatchdog(void*) {
  if (!g_debug_mode || g_debug_direction == 0) return;
  bool atLimit = digitalRead(g_debug_direction > 0 ? LIMIT_OPEN : LIMIT_CLOSE) == LOW;
  if (atLimit || WiFi.status() != WL_CONNECTED || g_ota_motor_locked) {
    motorStop();
    g_debug_direction = 0;
    logEvent("Debug motor stopped: %s", atLimit ? "target limit active" :
             (g_ota_motor_locked ? "OTA lockout" : "Wi-Fi disconnected"));
  }
}

static bool authorizeDebug() {
  if (g_ota_motor_locked) {
    g_web_server.send(423, "text/plain", "Motor locked by OTA; reboot required");
    return false;
  }
  return true;
}

static void handleDebugCommand() {
  if (!authorizeDebug()) return;
  String action = g_web_server.arg("action");
  if (action == "enable" || action == "disable" || action == "stop") {
    motorStop();
    g_debug_direction = 0;
    if (action == "enable" || action == "stop") g_debug_mode = true;
    if (action == "disable") {
      g_debug_mode = false;
      g_last_motion_ms = millis();
      if (digitalRead(LIMIT_CLOSE) == LOW) transitionTo(ST_CLOSED, "Debug disabled");
      else if (digitalRead(LIMIT_OPEN) == LOW) transitionTo(ST_OPENED, "Debug disabled");
      else transitionTo(ST_FAULT, "Debug disabled between limits");
    }
    logEvent("Debug %s: motor stopped", action.c_str());
    g_web_server.send(200, "text/plain", "Stopped");
    return;
  }
  if (action != "open" && action != "close") {
    g_web_server.send(400, "text/plain", "Choose open, close, stop, enable, or disable");
    return;
  }
  if (!g_debug_mode || g_debug_direction != 0) {
    g_web_server.send(409, "text/plain", "Enable debug mode and stop before changing direction");
    return;
  }
  String dutyText = g_web_server.arg("duty");
  if (dutyText != "0" && dutyText != "1") {
    g_web_server.send(400, "text/plain", "Output must be 0 or 1");
    return;
  }
  int duty = dutyText.toInt();
  bool opening = action == "open";
  if (digitalRead(opening ? LIMIT_OPEN : LIMIT_CLOSE) == LOW && duty != 0) {
    logEvent("Debug %s rejected: target limit already active", action.c_str());
    g_web_server.send(409, "text/plain", "Requested limit is already active");
    return;
  }
  motorStop();
  delayMicroseconds(50);
  digitalWrite(opening ? M1 : M2, duty == 0 ? LOW : HIGH);
  g_debug_direction = duty == 0 ? 0 : (opening ? 1 : -1);
  logEvent("Debug %s: output %s", action.c_str(), duty == 0 ? "LOW" : "HIGH (latched)");
  g_web_server.send(200, "text/plain", duty == 0 ? "Stopped" : "Output latched on");
}

static void setupWebServer() {
  g_web_server.on("/", HTTP_GET, []() {
    g_web_server.sendHeader("Cache-Control", "no-store");
    g_web_server.send_P(200, "text/html", PIN_PAGE);
  });
  g_web_server.on("/api/pins", HTTP_GET, []() {
    char response[512];
    snprintf(response, sizeof(response),
             "{\"state\":\"%s\",\"uptime_ms\":%lu,\"rssi\":%d,"
             "\"ota_locked\":%s,\"pir_in\":%d,\"pir_out\":%d,"
             "\"limit_open\":%d,\"limit_close\":%d,"
             "\"motor_open\":%lu,\"motor_close\":%lu,"
             "\"debug_mode\":%s,\"debug_direction\":%d,\"debug_max_duty\":%u}",
             statusToStr(g_state), (unsigned long)millis(), WiFi.RSSI(),
             g_ota_motor_locked ? "true" : "false",
             digitalRead(PIR_IN), digitalRead(PIR_OUT),
             digitalRead(LIMIT_OPEN), digitalRead(LIMIT_CLOSE),
             (unsigned long)digitalRead(M1), (unsigned long)digitalRead(M2),
             g_debug_mode ? "true" : "false", g_debug_direction, 1U);
    g_web_server.sendHeader("Cache-Control", "no-store");
    g_web_server.send(200, "application/json", response);
  });
  g_web_server.on("/api/debug", HTTP_POST, handleDebugCommand);
  g_web_server.on("/api/events", HTTP_GET, []() {
    static char snapshot[EVENT_COUNT][EVENT_LENGTH];
    String response;
    response.reserve(EVENT_COUNT * EVENT_LENGTH + 128);
    response += "Last reset: ";
    response += resetReasonText(esp_reset_reason());
    response += "\n\n";
    portENTER_CRITICAL(&g_event_lock);
    size_t count = g_event_count;
    size_t next = g_event_next;
    memcpy(snapshot, g_events, sizeof(snapshot));
    portEXIT_CRITICAL(&g_event_lock);
    for (size_t offset = 0; offset < count; ++offset) {
      size_t index = (next + EVENT_COUNT - 1 - offset) % EVENT_COUNT;
      response += snapshot[index];
      response += '\n';
    }
    g_web_server.sendHeader("Cache-Control", "no-store");
    g_web_server.send(200, "text/plain; charset=utf-8", response);
  });
  g_web_server.onNotFound([]() {
    g_web_server.send(404, "text/plain", "Not found");
  });
}

static void setupOTA() {
  if (WIFI_SSID[0] == '\0') {
    Serial.println("OTA disabled: configure Wi-Fi in ota_config.h");
    logEvent("Wi-Fi / OTA disabled: SSID not configured");
    return;
  }

  WiFi.mode(WIFI_STA);
  if (!WiFi.config(IPAddress(192, 168, 1, 251), IPAddress(192, 168, 1, 1),
                   IPAddress(255, 255, 255, 0), IPAddress(192, 168, 1, 1))) {
    Serial.println("OTA disabled: static IP configuration failed");
    logEvent("Wi-Fi / OTA disabled: static IP configuration failed");
    WiFi.mode(WIFI_OFF);
    return;
  }
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  ArduinoOTA.setHostname("dogdoor");
  if (OTA_PASSWORD[0] != '\0') {
    ArduinoOTA.setPassword(OTA_PASSWORD);
  } else {
    Serial.println("Warning: OTA uploads have no password protection");
  }
  ArduinoOTA.onStart([]() {
    g_ota_motor_locked = true;
    motorStop();
    g_debug_direction = 0;
    Serial.println("OTA update started; motor locked until reboot");
    logEvent("OTA started: motor locked until reboot");
  });
  ArduinoOTA.onEnd([]() {
    motorStop();
    Serial.println("OTA complete; rebooting");
    logEvent("OTA complete: rebooting");
  });
  ArduinoOTA.onError([](ota_error_t error) {
    g_ota_motor_locked = true;
    motorStop();
    Serial.printf("OTA error %u; motor locked until reboot\n", error);
    logEvent("OTA error %u: motor locked until reboot", (unsigned int)error);
  });
}

static void serviceOTA() {
  static bool wasConnected = false;
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected != wasConnected) {
    logEvent(connected ? "Wi-Fi connected" : "Wi-Fi disconnected");
    wasConnected = connected;
  }
  if (!connected) return;
  if (!g_ota_started) {
    ArduinoOTA.begin();
    g_web_server.begin();
    g_ota_started = true;
    Serial.print("OTA ready at ");
    Serial.println(WiFi.localIP());
    logEvent("Web server ready: 192.168.1.251:5000; OTA ready");
  }
  ArduinoOTA.handle();
}

/* ------------------ Setup ------------------ */
void setup() {
  Serial.begin(115200);
  esp_reset_reason_t reason = esp_reset_reason();
  logEvent("Boot: %s (code %d)", resetReasonText(reason), (int)reason);
  delay(200);

  pinMode(PIR_IN, INPUT);
  pinMode(PIR_OUT, INPUT);

  pinMode(LIMIT_OPEN, INPUT_PULLUP);
  pinMode(LIMIT_CLOSE, INPUT_PULLUP);

  digitalWrite(M1, LOW);
  digitalWrite(M2, LOW);
  pinMode(M1, OUTPUT);
  pinMode(M2, OUTPUT);
  motorStop();  

  esp_timer_create_args_t debugTimerConfig = {};
  debugTimerConfig.callback = debugWatchdog;
  debugTimerConfig.name = "debug-stop";
  if (esp_timer_create(&debugTimerConfig, &g_debug_timer) != ESP_OK ||
      esp_timer_start_periodic(g_debug_timer, 10000) != ESP_OK) {
    Serial.println("Debug watchdog initialization failed; halting with motor off");
    while (true) delay(1000);
  }

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

  if (g_debug_mode) {
    motorStop();
    g_debug_direction = 0;
    logEvent("Debug startup: both motor outputs LOW");
    if (limCloseActive) transitionTo(ST_CLOSED, "Debug startup");
    else if (digitalRead(LIMIT_OPEN) == LOW) transitionTo(ST_OPENED, "Debug startup");
    else transitionTo(ST_FAULT, "Debug startup between limits");
  } else if (limCloseActive) {
    transitionTo(ST_CLOSED, "Limit Closed(169)");
    motorStop();
  } else {
    transitionTo(ST_CLOSING, "Initialize");
    motorClose();
  }
  setupWebServer();
  setupOTA();
}

/* ------------------ Main loop ------------------ */
void loop() {
  serviceOTA();
  if (WiFi.status() == WL_CONNECTED) g_web_server.handleClient();
  if (g_ota_motor_locked) {
    motorStop();
    delay(1);
    return;
  }

  char buf[10];
  uint32_t now = millis();

  // Inputs
  bool pirIn  = (digitalRead(PIR_IN)  == HIGH);
  bool pirOut = (digitalRead(PIR_OUT) == HIGH);

  bool limOpenActive  = (digitalRead(LIMIT_OPEN)  == LOW);
  bool limCloseActive = (digitalRead(LIMIT_CLOSE) == LOW);

  bool motion = (pirIn || pirOut);
  if (motion) g_last_motion_ms = now;

  if (g_debug_mode) {
    while (Serial.available()) Serial.read();
  }
  if (!g_debug_mode && Serial.available() && Serial.readBytes(buf, 1) >= 0)
  {
    if (buf[0] == 'o')
      transitionTo(ST_FORCE_OPENING, "o key");
    else if (buf[0] == 'c')
      transitionTo(ST_FORCE_CLOSING, "c key");
    else if (buf[0] == 'f')
      transitionTo(ST_FAULT, "f key");
  }

  // State machine
  if (!g_debug_mode) switch (g_state)
  {
  case ST_CLOSED:
    setFault(false);
    motorStop();
    if (motion)
    {
      transitionTo(ST_OPENING, "Motion");
      motorOpen();
    }
    break;

  case ST_OPENING:
    setFault(false);
    // Stop when open limit reached
    if (limOpenActive)
    {
      motorStop();
      transitionTo(ST_OPENED, "Limit Opened");
    }
    else if (now - g_move_started_ms > MOVE_TIMEOUT_MS)
    {
      motorStop();
      setFault(true);
      transitionTo(ST_FAULT, "Move Timeout (211)");
    }
    break;

  case ST_OPENED:
    setFault(false);
    motorStop();
    // Hold open until no motion for HOLD_OPEN_MS
    if (!motion && (now - g_last_motion_ms > HOLD_OPEN_MS))
    {
      transitionTo(ST_CLOSING, "Hold Timeout without Motion");
      motorClose();
    }
    break;

  case ST_CLOSING:
    setFault(false);
    // If motion occurs while closing, reopen immediately
    if (motion)
    {
      transitionTo(ST_OPENING, "Motion Detected");
      motorOpen();
      break;
    }
    // Stop when closed limit reached
    if (limCloseActive)
    {
      motorStop();
      transitionTo(ST_CLOSED, "limit closed");
    }
    else if (now - g_move_started_ms > MOVE_TIMEOUT_MS)
    {
      motorStop();
      setFault(true);
      transitionTo(ST_FAULT, "Move Timeout");
    }
    break;

  case ST_FAULT:
    motorStop();
    // Simple recovery: if it becomes closed, clear fault and go CLOSED
    if (limCloseActive)
    {
      setFault(false);
      transitionTo(ST_CLOSED, "Limit Closed");
    }
    break;
  case ST_FORCE_CLOSING:
    motorClose();
    break;
  case ST_FORCE_OPENING:
    motorOpen();
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
