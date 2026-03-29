# Echolocation Vest — System Architecture

## Overview

A wearable blind navigation aid. An ESP32-CAM streams video over WiFi to a laptop running YOLOv8 + MiDaS depth estimation. Detected obstacles trigger haptic motors on the vest via a second ESP32. A voice assistant answers questions about the environment using GPT-4o mini.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         VEST (worn)                             │
│                                                                 │
│  ┌──────────────┐  MJPEG/HTTP   ┌──────────────────────────┐   │
│  │ ESP32-CAM    │ ────────────► │                          │   │
│  │ (streaming)  │               │        LAPTOP            │   │
│  └──────────────┘               │                          │   │
│                                 │  python/main.py          │   │
│  ┌──────────────┐               │  ├─ YOLOv8n detection    │   │
│  │ ESP32-Motors │ ◄──WS:8765─── │  ├─ MiDaS depth map      │   │
│  │ (haptics)    │               │  └─ motor WebSocket srv  │   │
│  │              │               │                          │   │
│  │  LEFT  GPIO23│               │  python/voice.py         │   │
│  │  CENTER GPIO21               │  └─ mic → Deepgram STT   │   │
│  │  RIGHT GPIO22│               │     → GPT-4o mini        │   │
│  └──────────────┘               │     → ElevenLabs TTS     │   │
│                                 │                          │   │
│                                 │  python/frontend.py      │   │
│                                 │  └─ FastAPI :8081        │   │
│                                 │     MJPEG / WS status    │   │
│                                 └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Hardware

| Component | Role |
|---|---|
| ESP32-CAM | Streams MJPEG video at `/stream` over WiFi |
| ESP32 (DevKit) | Receives motor JSON via WebSocket, drives 3 haptic motors via PWM |
| Haptic motors (×3) | Left / Center / Right — vibrate to indicate obstacle direction |
| 2N3904 NPN transistor | Switches each motor (GPIO → transistor → motor → 5V) |
| 1N4007 diode | Flyback protection across each motor |

**Motor GPIO pins (ESP32-Motors):** LEFT=23, CENTER=21, RIGHT=22
**PWM:** 1 kHz, 8-bit resolution (0–255 intensity)

---

## Software Components

### `python/main.py` — Ian
YOLO detection pipeline + motor WebSocket server.

- Reads MJPEG from ESP32-CAM via `FrameGrabber` (background thread — always latest frame)
- Runs **YOLOv8n** inference on 320×240 frames
- Runs **MiDaS_small** depth estimation every `DEPTH_EVERY_N_FRAMES` frames
- Maps each detection to a zone: **left** (cx < 1/3), **center**, **right** (cx > 2/3)
- Gates before firing motors:
  1. Label in `OBSTACLE_CLASSES`
  2. Depth score ≥ `DEPTH_THRESHOLD` (or bounding-box area ≥ `PROXIMITY_THRESHOLD` if depth disabled)
  3. Confidence ≥ `HIGH_PRIORITY_CONF` / `OBSTACLE_CONF`
  4. Label seen in ≥ `PERSISTENCE_FRAMES` consecutive frames
- PWM intensity scales with depth score via a power curve (`DEPTH_INTENSITY_CURVE`)
- Motor hold: zones stay on for `MOTOR_HOLD_SECONDS` after detection fades (anti-stutter)
- Sends `{"left": N, "center": N, "right": N}` JSON to all connected motor clients
- Exposes `speak(text)` — imported by `voice.py`

### `python/voice.py` — Jacob
Wake-word voice assistant, runs in a daemon thread.

- Wake word: "Hey Echo" (detected via Google STT)
- Question transcription: **Deepgram nova-2**
- Response generation: **GPT-4o mini** (8-word max replies for speed)
- Speech output: **ElevenLabs** `eleven_flash_v2_5` streaming TTS
- Reads `current_detections` from `shared.py` to give context to GPT
- Logs conversation turns to `shared.chat_messages` for the dashboard

### `python/shared.py` — Jaden
Shared mutable state between `main.py` and `voice.py`.

| Variable | Writer | Readers |
|---|---|---|
| `current_detections` | `main.py` | `voice.py`, `frontend.py` |
| `latest_frame` | `main.py` | `frontend.py` |
| `latest_raw_frame` | `main.py` | `frontend.py` |
| `latest_depth_frame` | `main.py` | `frontend.py` |
| `motor_connected` | `main.py` | `frontend.py` |
| `cam_connected` | `main.py` | `frontend.py` |
| `voice_status` | `voice.py` | `frontend.py` |
| `chat_messages` | `voice.py` | `frontend.py` |

### `python/frontend.py` — Jaden
FastAPI dashboard server on port 8081.

| Endpoint | Description |
|---|---|
| `GET /stream` | MJPEG stream — annotated YOLO frame |
| `GET /raw` | MJPEG stream — raw camera frame |
| `GET /depth` | MJPEG stream — MiDaS depth map |
| `WS /ws` | JSON status push at 10 Hz |
| `GET /` | Serves built React app (`frontend/dist`) |

### `python/config.py` — Jaden
Single source of truth for all constants. Never hardcode values elsewhere.

### `firmware/esp32-cam/` — Jaden / Deshawn
ESP32-CAM Arduino firmware. Streams MJPEG at `http://<ESP32_CAM_IP>/stream`.

### `firmware/esp32-motors/` — Jaden / Deshawn
Motor controller Arduino firmware.

- Connects to laptop WebSocket at `WS_HOST:8765`
- Parses JSON: `{"left": N, "center": N, "right": N}`
- Writes PWM to each motor pin via LEDC
- Safety: motors off on WebSocket disconnect

---

## Data Flow

```
ESP32-CAM
  └─► HTTP MJPEG ──► FrameGrabber thread
                          └─► YOLO inference (320×240)
                          └─► MiDaS depth (every N frames)
                                  └─► gate checks
                                        └─► send_motors() ──► WS:8765 ──► ESP32-Motors
                                        └─► shared.current_detections
                                              └─► voice.py (GPT Q&A)
                                              └─► frontend.py /ws (dashboard)
                          └─► shared.latest_frame ──► /stream MJPEG
                          └─► shared.latest_depth_frame ──► /depth MJPEG
```

---

## Ports & Addresses

| Service | Port | Protocol |
|---|---|---|
| ESP32-CAM video | 80 | HTTP MJPEG |
| Motor WebSocket server | 8765 | WebSocket |
| Voice WebSocket server | 8766 | WebSocket |
| Web dashboard | 8081 | HTTP + WebSocket |

---

## Key Design Decisions

- **FrameGrabber thread** — avoids stale buffered frames; YOLO always gets the latest.
- **MiDaS cached every N frames** — depth is expensive; reusing between frames keeps latency acceptable.
- **Motor hold timer** — prevents stuttering when YOLO briefly drops a detection mid-obstacle.
- **Power-curve intensity** — motors jump sharply only when objects are very close; softer at medium range.
- **Shared state module** — `shared.py` avoids circular imports and gives a clean boundary between Ian's and Jacob's code.
- **Port 8081 for dashboard** — 8080 is reserved by Colab's proxy.
