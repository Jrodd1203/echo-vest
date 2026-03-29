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
