# Echolocation Vest — Claude Code Instructions

## Project Overview

Wearable blind navigation vest. ESP32-CAM streams MJPEG video over WiFi
to a laptop running YOLOv8. Python detects objects and direction, sends
motor commands via WebSocket to a Regular ESP32 that drives 3 haptic motors.
GPT-4o mini handles voice Q&A. OpenAI TTS speaks responses.

## Repo Structure

firmware/camera/ → ESP32-CAM streaming firmware (C++/Arduino)
firmware/motors/ → Motor controller firmware (C++/Arduino)
python/main.py → YOLO pipeline + WebSocket server (Ian)
python/voice.py → Speech recognition + GPT responses (Jacob)
python/shared.py → Shared state (current_detections list)
python/config.py → All constants (IP addresses, ports, thresholds)

## File Ownership — NEVER edit someone else's file

main.py → Ian only
voice.py → Jacob only
shared.py → Jaden only (read-only for Ian and Jacob)
config.py → Jaden only
firmware/ → Jaden and Deshawn only

## Branch Rules

Never commit to main directly.
Branch naming: python/feature-name or hardware/feature-name
Only Jaden merges PRs into main.

## Hardware Constants

ESP32-CAM IP: defined in config.py as ESP32_CAM_IP
WebSocket motor server port: 8765
WebSocket voice server port: 8766
Motor GPIO pins: LEFT=25, CENTER=26, RIGHT=27
Transistor: 2N3904 NPN
Diode: 1N4007

## Python Conventions

- All shared constants imported from config.py — never hardcode IPs or ports
- current_detections imported from shared.py — never redefined locally
- speak() function lives in main.py — Jacob imports it, never redefines it
- All async functions use asyncio — no threading except for voice thread
- Cooldown for TTS: 2 seconds per unique label minimum

## Code Style

- Python: type hints on all function signatures
- Python: docstring on every function explaining what it does
- C++: comment every GPIO pin assignment
- No magic numbers — everything goes in config.py or platformio.ini
- Commit message format: "area: what you did" (e.g. "yolo: add cooldown logic")

## Dependencies

Python: requirements.txt in repo root
Arduino: declared in platformio.ini lib_deps
Never pip install something without adding it to requirements.txt

## What NOT To Do

- Never hardcode WiFi credentials — use config.py
- Never commit .env files — API keys stay local
- Never edit main branch directly
- Never redefine current_detections outside shared.py
- Never add blocking sleep() calls in the YOLO main loop

```

---

## Per-Person Agent Instructions

Beyond the shared CLAUDE.md, each person should give their agent a session prompt at the start of every working session. Think of it as briefing the agent before it touches anything.

**Ian's session opener:**
```

I am Ian working on python/yolo-pipeline branch.
My file is python/main.py only.
Do not edit voice.py, shared.py, or config.py.
Do not change any function signatures that Jacob imports.
The speak() function is imported by Jacob — never rename or remove it.
Current task: [describe what you're building right now]

```

**Jacob's session opener:**
```

I am Jacob working on python/voice-commands branch.
My file is python/voice.py only.
Do not edit main.py, shared.py, or config.py.
Import current_detections from shared.py — never redefine it.
Import speak() from main.py — never redefine it.
Current task: [describe what you're building right now]

```

**Deshawn's session opener:**
```

I am Deshawn working on hardware/motor-firmware branch.
My files are firmware/motors/src/main.cpp only.
Do not edit camera firmware.
All GPIO pins are defined as constants at the top — never hardcode pin numbers inline.
WebSocket port is always 8765.
Current task: [describe what you're building right now]
