"""
main.py — Ian only (python/yolo-pipeline branch)
YOLO detection pipeline + WebSocket motor server + speak() for Jacob.

DO NOT edit: voice.py, shared.py, config.py
speak() is imported by Jacob — never rename or remove it.
"""
import asyncio
import json
import os
import time

import cv2
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from ultralytics import YOLO
import websockets

load_dotenv()

# ── Shared constants + state from Jaden's files ──────────────────────────────
# These imports work once Jaden creates config.py and shared.py.
# The fallback values below let you run solo in the meantime.
try:
    from config import ESP32_CAM_IP, MOTOR_WS_PORT, YOLO_CONF, COOLDOWN_SECONDS
    from shared import current_detections
except ImportError:
    # TODO: Remove these once Jaden creates config.py and shared.py
    ESP32_CAM_IP = '192.168.x.x'   # Jaden will give you the real IP
    MOTOR_WS_PORT = 8765
    YOLO_CONF = 0.5
    COOLDOWN_SECONDS = 2.0
    current_detections: list[str] = []

# ── Model + camera setup ─────────────────────────────────────────────────────
model = YOLO('yolov8n.pt')

# Using webcam for now — swap to ESP32-CAM URL once Jaden gives you the IP:
#   cap = cv2.VideoCapture(f'http://{ESP32_CAM_IP}/stream')
cap = cv2.VideoCapture(0)

motor_clients: set = set()


# ── TTS — Jacob imports this. Never rename or remove. ────────────────────────

elevenlabs_client = ElevenLabs(api_key=os.environ['ELEVENLABS_API_KEY'])


def speak(text: str) -> None:
    """Speak text aloud using ElevenLabs TTS via elevenlabs.play()."""
    audio = elevenlabs_client.text_to_speech.convert(
        voice_id='JBFqnCBsd6RMkjVDRZzb',
        model_id='eleven_turbo_v2_5',
        text=text,
    )
    stream(audio)


# ── Direction logic ──────────────────────────────────────────────────────────

def get_direction(cx: float, frame_width: int) -> str:
    """Return 'left', 'center', or 'right' based on bounding box center X vs frame width."""
    if cx < frame_width / 3:
        return 'left'
    elif cx < 2 * frame_width / 3:
        return 'center'
    else:
        return 'right'


# ── WebSocket motor server ───────────────────────────────────────────────────

async def motor_handler(ws: websockets.WebSocketServerProtocol) -> None:
    """Register an ESP32 motor client and keep the connection open until it drops."""
    motor_clients.add(ws)
    try:
        await ws.wait_closed()
    finally:
        motor_clients.discard(ws)


async def send_motors(left: int, center: int, right: int) -> None:
    """Send motor intensity JSON to all connected ESP32 clients."""
    if motor_clients:
        msg = json.dumps({'left': left, 'center': center, 'right': right})
        await asyncio.gather(*[c.send(msg) for c in motor_clients])


# ── YOLO loop ────────────────────────────────────────────────────────────────

async def run_yolo_loop() -> None:
    """
    Read frames from the camera, run YOLO detection, update current_detections,
    and fire the correct haptic motor with a per-label cooldown.

    Uses run_in_executor for cap.read() so the blocking camera call doesn't
    stall the asyncio event loop (and the WebSocket server).
    """
    loop = asyncio.get_event_loop()
    last_fired: dict[str, float] = {}

    while True:
        ret, frame = await loop.run_in_executor(None, cap.read)
        if not ret:
            break

        # Resize before YOLO — speeds up inference significantly
        frame = cv2.resize(frame, (320, 240))
        results = model(frame, conf=YOLO_CONF)
        fw = frame.shape[1]

        # Update shared list so Jacob's voice thread can read it
        current_detections.clear()
        for box in results[0].boxes:
            cx = float((box.xyxy[0][0] + box.xyxy[0][2]) / 2)
            direction = get_direction(cx, fw)
            label = model.names[int(box.cls)]
            current_detections.append(f'{label} {direction}')

        # Fire motors — one motor per detection, with cooldown to stop spam
        now = time.time()
        for det in current_detections:
            # rsplit from right once: handles multi-word labels like "traffic light"
            label, direction = det.rsplit(' ', 1)
            if label not in last_fired or now - last_fired[label] > COOLDOWN_SECONDS:
                last_fired[label] = now
                if direction == 'left':
                    await send_motors(200, 0, 0)
                elif direction == 'center':
                    await send_motors(0, 200, 0)
                else:
                    await send_motors(0, 0, 200)

        # Show annotated frame
        annotated = results[0].plot()

        # Draw L/C/R zone dividers
        h, w = annotated.shape[:2]
        third = w // 3
        cv2.line(annotated, (third, 0), (third, h), (200, 200, 200), 1)
        cv2.line(annotated, (2 * third, 0), (2 * third, h), (200, 200, 200), 1)
        cv2.putText(annotated, 'LEFT',   (10, 25),           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 100), 2)
        cv2.putText(annotated, 'CENTER', (third + 10, 25),   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
        cv2.putText(annotated, 'RIGHT',  (2*third + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

        cv2.imshow('Echolocation Vest', annotated)
        if cv2.waitKey(1) == ord('q'):
            break

        await asyncio.sleep(0)  # yield to event loop so WebSocket messages process


# ── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    """Start the WebSocket motor server and the YOLO loop concurrently."""
    async with websockets.serve(motor_handler, '0.0.0.0', MOTOR_WS_PORT):
        print(f'Motor WebSocket server running on port {MOTOR_WS_PORT}')
        await run_yolo_loop()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    import voice  # noqa: F401 — imported for side effect (starts voice WS thread on port 8766)
    asyncio.run(main())
