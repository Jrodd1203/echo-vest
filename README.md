# Echo Vest

A wearable blind navigation vest that uses computer vision and haptic feedback to help visually impaired users navigate their environment. An ESP32-CAM streams live video to a laptop running YOLOv8 + MiDaS depth estimation. Detected obstacles trigger directional haptic motors on the vest. A voice assistant answers spoken questions about the environment using GPT-4o mini.

---

## How It Works

1. **ESP32-CAM** streams MJPEG video over WiFi to the laptop
2. **YOLOv8n** detects objects in each frame; **MiDaS** estimates depth
3. Objects are assigned a zone — **left**, **center**, or **right** — based on bounding box position
4. If an object passes all detection gates (class filter, depth threshold, confidence, persistence), the corresponding haptic motor vibrates at an intensity proportional to how close the object is
5. The user can say **"Hey Echo"** to activate the voice assistant, then ask a question like *"What's in front of me?"* — GPT-4o mini replies in 8 words or less and speaks the answer aloud
6. A **web dashboard** at `http://localhost:8081` shows the live annotated feed, depth map, detection list, and voice chat log

---

## Hardware

| Part | Role |
|---|---|
| ESP32-CAM (AI Thinker) | Streams MJPEG video |
| ESP32 DevKit v1 | Receives motor commands, drives haptic motors |
| Haptic disc motors ×3 | Vibrate to indicate obstacle direction (left / center / right) |
| 2N3904 NPN transistor ×3 | Switches each motor from a GPIO signal |
| 1N4007 diode ×3 | Flyback protection across each motor |

**Motor GPIO pins:** LEFT = 23, CENTER = 21, RIGHT = 22
**PWM:** 1 kHz, 8-bit (0–255 intensity)

---

## Repo Structure

```
echo-vest/
├── firmware/
│   ├── esp32-cam/          # ESP32-CAM streaming firmware (C++/PlatformIO)
│   └── esp32-motors/       # Motor controller firmware (C++/PlatformIO)
├── python/
│   ├── main.py             # YOLO pipeline + WebSocket motor server (Ian)
│   ├── voice.py            # Wake word + GPT voice assistant (Jacob)
│   ├── frontend.py         # FastAPI dashboard server (Jaden)
│   ├── shared.py           # Shared state between modules (Jaden)
│   ├── config.py           # All constants — IPs, ports, thresholds (Jaden)
│   └── requirements.txt
├── frontend/               # React web dashboard (Vite)
├── ARCHITECTURE.md         # Full system architecture doc
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the dashboard)
- PlatformIO (for flashing firmware)
- A `.env` file in the repo root with your API keys (see below)

### 1. Clone & install Python dependencies

```bash
git clone https://github.com/Jrodd1203/echo-vest.git
cd echo-vest
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r python/requirements.txt
```

### 2. Create a `.env` file

```
ELEVENLABS_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DEEPGRAM_API_KEY=your_key_here
```

Never commit this file.

### 3. Build the frontend dashboard

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Flash the ESP32-CAM firmware

Open `firmware/esp32-cam/` in PlatformIO and flash to your ESP32-CAM board.

### 5. Flash the motor controller firmware

Open `firmware/esp32-motors/` in PlatformIO. Before flashing, update these two lines in `src/main.cpp`:

```cpp
const char *WIFI_SSID = "YourNetworkName";
const char *WS_HOST   = "YOUR_LAPTOP_IP";   // must be on same WiFi
```

Flash to your ESP32 DevKit.

### 6. Update `python/config.py`

Set `ESP32_CAM_IP` to your ESP32-CAM's IP address (shown in the serial monitor on boot).

### 7. Run

```bash
cd python
python main.py
```

This starts:
- Motor WebSocket server on port **8765**
- Voice assistant thread (mic → Deepgram → GPT-4o mini → ElevenLabs)
- Web dashboard at **http://localhost:8081**

To run without the voice assistant (e.g. headless):
```bash
SKIP_VOICE=1 python main.py
```

To run without opening OpenCV display windows:
```bash
SKIP_DISPLAY=1 python main.py
```

---

## Web Dashboard

Navigate to `http://localhost:8081` after starting `main.py`.

| Endpoint | Description |
|---|---|
| `/stream` | Annotated YOLO feed (MJPEG) |
| `/raw` | Raw camera feed (MJPEG) |
| `/depth` | MiDaS depth map (MJPEG) |
| `/ws` | Live status JSON at 10 Hz |

---

## Detection & Motor Logic

Motors only fire when **all** of the following pass:

1. Object label is in `OBSTACLE_CLASSES` (defined in `config.py`)
2. MiDaS depth score ≥ `DEPTH_THRESHOLD` (object is close enough)
3. Confidence ≥ `HIGH_PRIORITY_CONF` (high-risk classes: person, car, bicycle…) or `OBSTACLE_CONF` (everything else)
4. Label has appeared in ≥ `PERSISTENCE_FRAMES` consecutive frames (reduces false triggers)

**Intensity** scales with depth — closer = stronger vibration — via a configurable power curve (`DEPTH_INTENSITY_CURVE`). Motors hold on for `MOTOR_HOLD_SECONDS` after a detection fades to prevent stuttering.

All detections (even those that don't fire motors) are available to the voice assistant.

---

## Voice Assistant

Say **"Hey Echo"** to wake the assistant. Then ask anything:

> *"What's in front of me?"*
> *"Is there a person nearby?"*
> *"What's on my left?"*

Say **"Goodbye"** or **"Stop"** to return to wake-word mode.

The assistant uses:
- **Google STT** for wake-word detection
- **Deepgram nova-2** for question transcription
- **GPT-4o mini** for responses (8-word limit for speed)
- **ElevenLabs** `eleven_flash_v2_5` for spoken output

---

## Configuration

All tunable values live in `python/config.py`. Key ones:

| Constant | Default | Description |
|---|---|---|
| `DEPTH_ENABLED` | `True` | Use MiDaS depth instead of bounding-box area |
| `DEPTH_THRESHOLD` | `0.55` | Normalized depth score to trigger motors (higher = must be closer) |
| `DEPTH_EVERY_N_FRAMES` | `3` | Run MiDaS every N frames (lower = more responsive, slower) |
| `DEPTH_INTENSITY_CURVE` | `2.0` | Power curve for intensity scaling (higher = sharper dropoff at medium range) |
| `MOTOR_HOLD_SECONDS` | `1.5` | How long motors stay on after detection fades |
| `PERSISTENCE_FRAMES` | `1` | Consecutive frames required before firing |
| `YOLO_CONF` | `0.5` | Minimum YOLO confidence |

---

## Team

| Person | Owns |
|---|---|
| Ian | `python/main.py` — YOLO pipeline |
| Jacob | `python/voice.py` — voice assistant |
| Jaden | `python/shared.py`, `python/config.py`, `python/frontend.py`, firmware |
| Deshawn | `firmware/esp32-motors/` — motor controller |

Branch rules: never commit to `main` directly. Only Jaden merges PRs into `main`.
Branch naming: `python/feature-name` or `hardware/feature-name`.
