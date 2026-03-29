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
MOTOR_LEFT: int = 23
MOTOR_CENTER: int = 22
MOTOR_RIGHT: int = 21

# ── Obstacle classification filter ────────────────────────────────────────────
# Class names match YOLOv8n output exactly (COCO dataset labels).
# Only detections whose label appears in OBSTACLE_CLASSES will fire the motors.
# ALL detections are still written to current_detections for Jacob's voice thread.
OBSTACLE_CLASSES: set[str] = {
    'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
    'dog', 'cat',
    'chair', 'dining table', 'couch', 'potted plant', 'bed', 'toilet',
    'fire hydrant', 'stop sign', 'bench', 'suitcase', 'backpack',
}

# Subset of OBSTACLE_CLASSES — immediate collision risks get intensity 255.
# Everything in OBSTACLE_CLASSES but NOT here gets intensity 200.
HIGH_PRIORITY_CLASSES: set[str] = {
    'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'dog',
}

# ── Detection gate thresholds ─────────────────────────────────────────────────
# Motors only fire when ALL three conditions below pass (plus cooldown).
PROXIMITY_THRESHOLD: float = 0.08      # bounding box must cover ≥8 % of frame area
HIGH_PRIORITY_CONF: float = 0.45      # confidence required for HIGH_PRIORITY_CLASSES
OBSTACLE_CONF: float = 0.45           # confidence required for other OBSTACLE_CLASSES
PERSISTENCE_FRAMES: int = 1            # label must appear this many consecutive frames
