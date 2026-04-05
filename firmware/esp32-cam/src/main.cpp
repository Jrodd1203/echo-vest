// ESP32-CAM MJPEG streaming firmware — Echolocation Vest
// Connects to WiFi, serves MJPEG stream at http://<IP>/stream
// Python main.py reads from ESP32_CAM_IP defined in config.py

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"

// ── WiFi credentials ──────────────────────────────────────────────────────────
static const char *WIFI_SSID = "Deshawn's Iphone";
static const char *WIFI_PASS = "deeznuts";

// ── HTTP server on port 80 ────────────────────────────────────────────────────
static WebServer server(80);

// ── AI Thinker ESP32-CAM pin map ──────────────────────────────────────────────
#define PWDN_GPIO_NUM 32  // power-down pin
#define RESET_GPIO_NUM -1 // hardware reset (not connected)
#define XCLK_GPIO_NUM 0   // external clock output
#define SIOD_GPIO_NUM 26  // SCCB data
#define SIOC_GPIO_NUM 27  // SCCB clock
#define Y9_GPIO_NUM 35    // pixel data bit 7
#define Y8_GPIO_NUM 34    // pixel data bit 6
#define Y7_GPIO_NUM 39    // pixel data bit 5
#define Y6_GPIO_NUM 36    // pixel data bit 4
#define Y5_GPIO_NUM 21    // pixel data bit 3
#define Y4_GPIO_NUM 19    // pixel data bit 2
#define Y3_GPIO_NUM 18    // pixel data bit 1
#define Y2_GPIO_NUM 5     // pixel data bit 0
#define VSYNC_GPIO_NUM 25 // vertical sync
#define HREF_GPIO_NUM 23  // horizontal reference
#define PCLK_GPIO_NUM 22  // pixel clock

// MJPEG boundary string used in multipart HTTP response
static const char *MJPEG_BOUNDARY = "frame";

// ── initCamera() ──────────────────────────────────────────────────────────────
// Initialises the OV2640 sensor with settings tuned for real-time streaming.
// Returns true on success, false on hardware fault.
bool initCamera()
{
    camera_config_t config;

    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;       // 20 MHz XCLK
    config.pixel_format = PIXFORMAT_JPEG; // compressed JPEG output

    // Use PSRAM when available for larger frame buffers
    if (psramFound())
    {
        config.frame_size = FRAMESIZE_VGA; // 640×480 — good YOLO balance
        config.jpeg_quality = 12;          // 0=best, 63=worst; 10–15 is sweet spot
        config.fb_count = 2;               // double-buffer for smoother streaming
        config.fb_location = CAMERA_FB_IN_PSRAM;
        config.grab_mode = CAMERA_GRAB_LATEST;
    }
    else
    {
        config.frame_size = FRAMESIZE_QVGA; // 320×240 fallback without PSRAM
        config.jpeg_quality = 15;
        config.fb_count = 1;
        config.fb_location = CAMERA_FB_IN_DRAM;
        config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("[CAM] Init failed: 0x%x\n", err);
        return false;
    }

    // Sensor tweaks for better indoor performance
    sensor_t *s = esp_camera_sensor_get();
    s->set_brightness(s, 1);                 // slight brightness boost
    s->set_saturation(s, -1);                // reduce colour noise
    s->set_gainceiling(s, (gainceiling_t)4); // cap gain to limit noise

    Serial.println("[CAM] Init OK");
    return true;
}

// ── handleStream() ────────────────────────────────────────────────────────────
// HTTP handler for GET /stream.
// Pushes a never-ending multipart/x-mixed-replace MJPEG response.
// Python's cv2.VideoCapture reads this directly.
void handleStream()
{
    WiFiClient client = server.client();

    // Send multipart HTTP header
    String header =
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: multipart/x-mixed-replace; boundary=" +
        String(MJPEG_BOUNDARY) + "\r\n"
                                 "Access-Control-Allow-Origin: *\r\n"
                                 "Connection: keep-alive\r\n\r\n";
    client.print(header);

    while (client.connected())
    {
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb)
        {
            Serial.println("[CAM] Frame capture failed");
            delay(10);
            continue;
        }

        // Part header for this frame
        String partHeader =
            "--" + String(MJPEG_BOUNDARY) + "\r\n"
                                            "Content-Type: image/jpeg\r\n"
                                            "Content-Length: " +
            String(fb->len) + "\r\n\r\n";
        client.print(partHeader);

        // JPEG payload
        client.write(fb->buf, fb->len);
        client.print("\r\n");

        esp_camera_fb_return(fb);

        // Yield to allow WiFi stack to breathe
        delay(1);
    }

    Serial.println("[STREAM] Client disconnected");
}

// ── handleRoot() ──────────────────────────────────────────────────────────────
// Simple index page so you can verify the cam is alive in a browser.
void handleRoot()
{
    server.send(200, "text/html",
                "<html><body>"
                "<h2>Echolocation Vest — ESP32-CAM</h2>"
                "<img src='/stream' style='max-width:100%'/>"
                "</body></html>");
}

// ── setup() ───────────────────────────────────────────────────────────────────
void setup()
{
    Serial.begin(115200);
    Serial.println("\n[BOOT] Echolocation Vest — ESP32-CAM");

    if (!initCamera())
    {
        Serial.println("[BOOT] Camera init failed — halting");
        while (true)
        {
            delay(1000);
        }
    }

    // Connect to WiFi
    Serial.printf("[WIFI] Connecting to %s ...\n", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\n[WIFI] Connected — IP: %s\n", WiFi.localIP().toString().c_str());

    // Register HTTP routes
    server.on("/", HTTP_GET, handleRoot);
    server.on("/stream", HTTP_GET, handleStream);
    server.begin();

    Serial.println("[HTTP] Server started");
    Serial.printf("[HTTP] Stream URL: http://%s/stream\n", WiFi.localIP().toString().c_str());
}

// ── loop() ────────────────────────────────────────────────────────────────────
void loop()
{
    server.handleClient();
}
