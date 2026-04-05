#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// ── WiFi credentials ─────────────────────────────────────────────────────────
// TODO: set these to the network both the ESP32 and laptop are on
const char *WIFI_SSID = "Deshawn's Iphone";
const char *WIFI_PASSWORD = "deeznuts";

// ── Laptop WebSocket server ───────────────────────────────────────────────────
const char *WS_HOST = "10.247.157.123"; // TODO: change to laptop IP on your network
const uint16_t WS_PORT = 8765;
const char *WS_PATH = "/";

// ── Motor GPIO pins ───────────────────────────────────────────────────────────
const int MOTOR_LEFT = 23;   // left haptic motor via 2N3904 transistor
const int MOTOR_CENTER = 21; // center haptic motor via 2N3904 transistor
const int MOTOR_RIGHT = 22;  // right haptic motor via 2N3904 transistor

// ── PWM config ────────────────────────────────────────────────────────────────
const int PWM_FREQ = 1000;    // Hz
const int PWM_RESOLUTION = 8; // bits (0–255)
const int PWM_CH_LEFT = 0;    // LEDC channel for left motor
const int PWM_CH_CENTER = 1;  // LEDC channel for center motor
const int PWM_CH_RIGHT = 2;   // LEDC channel for right motor

WebSocketsClient ws;

void setMotors(int left, int center, int right)
{
    ledcWrite(PWM_CH_LEFT, constrain(left, 0, 255));
    ledcWrite(PWM_CH_CENTER, constrain(center, 0, 255));
    ledcWrite(PWM_CH_RIGHT, constrain(right, 0, 255));
}

void onWebSocketEvent(WStype_t type, uint8_t *payload, size_t length)
{
    switch (type)
    {
    case WStype_CONNECTED:
        Serial.println("[WS] Connected to laptop");
        break;

    case WStype_DISCONNECTED:
        Serial.println("[WS] Disconnected — will reconnect");
        setMotors(0, 0, 0); // safety: turn off motors on disconnect
        break;

    case WStype_TEXT:
    {
        // Expected JSON: {"left": 200, "center": 0, "right": 0}
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, payload, length);
        if (err)
        {
            Serial.printf("[WS] JSON parse error: %s\n", err.c_str());
            break;
        }
        int left = doc["left"] | 0;
        int center = doc["center"] | 0;
        int right = doc["right"] | 0;
        Serial.printf("[Motor] L=%d C=%d R=%d\n", left, center, right);
        setMotors(left, center, right);
        break;
    }

    default:
        break;
    }
}

void setup()
{
    Serial.begin(115200);

    // ── PWM setup ─────────────────────────────────────────────────────────────
    ledcSetup(PWM_CH_LEFT, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CH_CENTER, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CH_RIGHT, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(MOTOR_LEFT, PWM_CH_LEFT);
    ledcAttachPin(MOTOR_CENTER, PWM_CH_CENTER);
    ledcAttachPin(MOTOR_RIGHT, PWM_CH_RIGHT);
    setMotors(0, 0, 0);

    // ── WiFi ──────────────────────────────────────────────────────────────────
    Serial.printf("[WiFi] Connecting to %s\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(250);
        Serial.print(".");
    }
    Serial.printf("\n[WiFi] Connected — IP: %s\n", WiFi.localIP().toString().c_str());

    // ── WebSocket ─────────────────────────────────────────────────────────────
    ws.begin(WS_HOST, WS_PORT, WS_PATH);
    ws.onEvent(onWebSocketEvent);
    ws.setReconnectInterval(1000); // retry every 1s if connection drops
}

void loop()
{
    ws.loop(); // must be called every loop — handles incoming messages
}
