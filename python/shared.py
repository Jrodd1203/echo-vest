"""
shared.py — Jaden only
Shared state between the YOLO pipeline (main.py) and the voice module (voice.py).

Ian writes to current_detections in his YOLO loop.
Jacob reads from current_detections in voice.py.
Neither should redefine or reassign this list — mutate it in place only (clear/append).
"""

# List of active detections in "label direction" format, e.g. ["person left", "chair center"].
# Ian: call current_detections.clear() then current_detections.append(...) each frame.
# Jacob: read current_detections — never reassign it.
current_detections: list[str] = []

# ── Frontend shared state (written by main.py, read by frontend.py) ───────────
latest_frame: bytes = b''        # JPEG bytes of latest annotated frame, written by main.py
latest_raw_frame: bytes = b''    # JPEG bytes of raw (unannotated) camera frame, written by main.py
latest_depth_frame: bytes = b''  # JPEG bytes of depth map, written by main.py
motor_connected: bool = False    # True when an ESP32 motor client is connected
cam_connected: bool = False      # True when the camera stream is returning valid frames
voice_status: str = 'idle'       # 'idle' | 'listening' | 'processing' — updated by voice.py

# Chat history for the web dashboard — Jacob appends dicts here from voice.py.
# Format: {'role': 'user' | 'assistant', 'text': str, 'timestamp': float}
# Never reassign — mutate in place only (append / clear).
chat_messages: list[dict] = []
