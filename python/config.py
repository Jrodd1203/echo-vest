"""
config.py — Jaden only
All shared constants for the Echolocation Vest pipeline.
Import from here — never hardcode these values elsewhere.
"""

# ── Network ───────────────────────────────────────────────────────────────────
ESP32_CAM_IP: str = "10.22.26.167"      # ESP32-CAM stream address
MOTOR_WS_PORT: int = 8765               # WebSocket port for motor controller ESP32
VOICE_WS_PORT: int = 8766               # WebSocket port for voice module

# ── YOLO ──────────────────────────────────────────────────────────────────────
YOLO_CONF: float = 0.5                  # minimum confidence threshold for detections

# ── Haptic feedback ───────────────────────────────────────────────────────────
COOLDOWN_SECONDS: float = 2.0           # minimum seconds between motor triggers per label

# ── Motor GPIO pins (on motor controller ESP32) ───────────────────────────────
MOTOR_LEFT: int = 25
MOTOR_CENTER: int = 26
MOTOR_RIGHT: int = 27
