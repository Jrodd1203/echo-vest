"""
main.py — Ian only (python/yolo-pipeline branch)
YOLO detection pipeline + WebSocket motor server + speak() for Jacob.

DO NOT edit: voice.py, shared.py, config.py
speak() is imported by Jacob — never rename or remove it.
"""
import asyncio
import json
import os
import threading
import time

import cv2
import numpy as np
import torch
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
    from config import (ESP32_CAM_IP, MOTOR_WS_PORT, YOLO_CONF, COOLDOWN_SECONDS,
                        OBSTACLE_CLASSES, HIGH_PRIORITY_CLASSES,
                        PROXIMITY_THRESHOLD, HIGH_PRIORITY_CONF, OBSTACLE_CONF,
                        PERSISTENCE_FRAMES, DEPTH_ENABLED, DEPTH_THRESHOLD,
                        HIGH_PRIORITY_MAX, HIGH_PRIORITY_MIN, OBSTACLE_MAX, OBSTACLE_MIN,
                        DEPTH_EVERY_N_FRAMES, DEPTH_INTENSITY_CURVE, FRONTEND_PORT)
    import shared
    from shared import current_detections
except ImportError:
    # TODO: Remove these once Jaden creates config.py and shared.py
    
    current_detections: list[str] = []

# ── Model + camera setup ─────────────────────────────────────────────────────
model = YOLO('yolov8n.pt')

# ── MiDaS depth model setup ──────────────────────────────────────────────────
_device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
if DEPTH_ENABLED:
    _midas: torch.nn.Module = torch.hub.load(
        'intel-isl/MiDaS', 'MiDaS_small', verbose=False
    )
    _midas.to(_device).eval()
    _midas_transform = torch.hub.load(
        'intel-isl/MiDaS', 'transforms', verbose=False
    ).small_transform

# Camera source: CAMERA_URL env var → ESP32-CAM IP from config
_camera_url = os.environ.get('CAMERA_URL') or f'http://{ESP32_CAM_IP}/stream'
cap = cv2.VideoCapture(_camera_url)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimize internal buffer


# ── Background frame grabber ──────────────────────────────────────────────────

class FrameGrabber(threading.Thread):
    """Continuously reads frames from the camera in a background thread.

    Always keeps only the latest frame so the YOLO loop never processes
    stale buffered frames. This is the primary fix for stream latency.
    """

    def __init__(self, cap: cv2.VideoCapture) -> None:
        super().__init__(daemon=True)
        self._cap = cap
        self._ret: bool = False
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()

    def run(self) -> None:
        """Grab frames as fast as the camera sends them, keeping only the latest."""
        while True:
            ret, frame = self._cap.read()
            with self._lock:
                self._ret = ret
                self._frame = frame

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Return the most recently grabbed frame. Non-blocking."""
        with self._lock:
            return self._ret, self._frame


grabber = FrameGrabber(cap)
grabber.start()

motor_clients: set = set()


# ── TTS — Jacob imports this. Never rename or remove. ────────────────────────

elevenlabs_client = ElevenLabs(api_key=os.environ['ELEVENLABS_API_KEY'])


def speak(text: str) -> None:
    """Speak text aloud using ElevenLabs TTS via elevenlabs.play()."""
    audio_stream = elevenlabs_client.text_to_speech.stream(
        voice_id='JBFqnCBsd6RMkjVDRZzb',
        model_id='eleven_turbo_v2_5',
        text=text,
    )
    stream(audio_stream)


# ── Obstacle filter ──────────────────────────────────────────────────────────

def motor_intensity(label: str, depth_score: float = 1.0) -> int:
    """Return PWM intensity for a label scaled by how close the object is.

    Linearly interpolates between *_MIN (object just crossed DEPTH_THRESHOLD)
    and *_MAX (object is as close as MiDaS can measure, depth score ~1.0).
    Returns 0 for non-hazard labels — use this as the obstacle gate check too.

    Args:
        label: YOLO class name.
        depth_score: normalized MiDaS depth (0–1, higher = closer). Defaults to
                     1.0 so calling with no depth arg still returns the max value
                     (useful for the initial gate check).
    """
    if label in HIGH_PRIORITY_CLASSES:
        max_i, min_i = HIGH_PRIORITY_MAX, HIGH_PRIORITY_MIN
    elif label in OBSTACLE_CLASSES:
        max_i, min_i = OBSTACLE_MAX, OBSTACLE_MIN
    else:
        return 0

    # t=0 at DEPTH_THRESHOLD, t=1 at depth score 1.0
    t = (depth_score - DEPTH_THRESHOLD) / max(1.0 - DEPTH_THRESHOLD, 1e-6)
    t = max(0.0, min(1.0, t)) ** DEPTH_INTENSITY_CURVE  # power curve: higher = steeper drop-off
    return int(min_i + t * (max_i - min_i))


# ── Direction logic ──────────────────────────────────────────────────────────

def get_direction(cx: float, frame_width: int) -> str:
    """Return 'left', 'center', or 'right' based on bounding box center X vs frame width."""
    if cx < frame_width / 3:
        return 'left'
    elif cx < 2 * frame_width / 3:
        return 'center'
    else:
        return 'right'


def is_close_enough(x1: int, y1: int, x2: int, y2: int,
                    frame_width: int, frame_height: int) -> bool:
    """Return True if bounding box occupies at least PROXIMITY_THRESHOLD of frame area.

    Fallback used when DEPTH_ENABLED is False.
    Compares box area (pixels²) against total frame area scaled by PROXIMITY_THRESHOLD.
    """
    box_area = (x2 - x1) * (y2 - y1)
    frame_area = frame_width * frame_height
    return box_area >= PROXIMITY_THRESHOLD * frame_area


def compute_depth_map(frame: np.ndarray) -> np.ndarray:
    """Run MiDaS on a BGR frame and return a normalized depth map (0–1, higher = closer).

    MiDaS outputs inverse depth (disparity), so larger values mean the object
    is closer to the camera. The output is min-max normalized per frame so the
    threshold in config.py is stable across lighting conditions.
    """
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    input_tensor = _midas_transform(img_rgb).to(_device)
    with torch.no_grad():
        raw = _midas(input_tensor)
        raw = torch.nn.functional.interpolate(
            raw.unsqueeze(1),
            size=frame.shape[:2],
            mode='bicubic',
            align_corners=False,
        ).squeeze()
    depth = raw.cpu().numpy()
    d_min, d_max = depth.min(), depth.max()
    if d_max > d_min:
        return (depth - d_min) / (d_max - d_min)
    return np.zeros_like(depth)


def sample_depth(depth_map: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
    """Return the median normalized depth score inside a bounding box.

    Uses median rather than mean to ignore partial occlusions and noisy edges.
    Returns 0.0 if the crop is empty (degenerate box).
    """
    roi = depth_map[y1:y2, x1:x2]
    return float(np.median(roi)) if roi.size > 0 else 0.0


# ── WebSocket motor server ───────────────────────────────────────────────────

async def motor_handler(ws: websockets.ServerConnection) -> None:
    """Register an ESP32 motor client and keep the connection open until it drops."""
    motor_clients.add(ws)
    shared.motor_connected = True
    try:
        await ws.wait_closed()
    finally:
        motor_clients.discard(ws)
        if not motor_clients:
            shared.motor_connected = False


async def send_motors(left: int, center: int, right: int) -> None:
    """Send motor intensity JSON to all connected ESP32 clients."""
    if motor_clients:
        msg = json.dumps({'left': left, 'center': center, 'right': right})
        await asyncio.gather(*[c.send(msg) for c in motor_clients])


# ── YOLO loop ────────────────────────────────────────────────────────────────

async def run_yolo_loop() -> None:
    """
    Read frames from the camera, run YOLO detection, update current_detections,
    and fire the correct haptic motor when all detection gates pass.

    Motor-fire gates (all must be true):
      1. label is in OBSTACLE_CLASSES (motor_intensity > 0)
      2. bounding box covers ≥ PROXIMITY_THRESHOLD of frame area
      3. confidence ≥ HIGH_PRIORITY_CONF (high-priority) or OBSTACLE_CONF (other)
      4. label appeared in ≥ PERSISTENCE_FRAMES consecutive frames
      5. per-label COOLDOWN_SECONDS has elapsed since last fire

    ALL detections (regardless of gates) are written to current_detections
    so Jacob's voice thread can answer questions about anything in view.

    Uses run_in_executor for cap.read() so the blocking camera call doesn't
    stall the asyncio event loop (and the WebSocket server).
    """
    loop = asyncio.get_event_loop()
    last_fired: dict[str, float] = {}
    detection_streak: dict[str, int] = {}  # consecutive frames each label has appeared
    frame_count: int = 0
    cached_depth_map: np.ndarray | None = None

    while True:
        ret, frame = grabber.read()
        if not ret or frame is None:
            shared.cam_connected = False
            await asyncio.sleep(0.01)  # camera not ready yet, yield and retry
            continue
        shared.cam_connected = True

        # Resize before YOLO — speeds up inference significantly
        frame = cv2.resize(frame, (320, 240))

        # Store raw frame for the dashboard's clean feed (no annotations)
        _, raw_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        shared.latest_raw_frame = raw_buf.tobytes()

        results = model(frame, conf=YOLO_CONF)

        # Recompute depth every N frames in a thread so it never blocks the event loop
        frame_count += 1
        if DEPTH_ENABLED and frame_count % DEPTH_EVERY_N_FRAMES == 0:
            cached_depth_map = await loop.run_in_executor(None, compute_depth_map, frame)
        depth_map = cached_depth_map
        fw = frame.shape[1]
        fh = frame.shape[0]

        # Update shared list so Jacob's voice thread can read it.
        # Also build box_meta (not put in current_detections — Jacob expects 'label direction').
        current_detections.clear()
        box_meta: dict[str, dict] = {}  # label → {x1, y1, x2, y2, conf}
        for box in results[0].boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            cx = float((x1 + x2) / 2)
            direction = get_direction(cx, fw)
            label = model.names[int(box.cls)]
            conf = float(box.conf[0])
            current_detections.append(f'{label} {direction}')
            # Keep highest-confidence box if label appears more than once in a frame
            if label not in box_meta or conf > box_meta[label]['conf']:
                box_meta[label] = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'conf': conf}

        # Decay streak — zero out any label absent this frame
        detected_labels = {det.rsplit(' ', 1)[0] for det in current_detections}
        for lbl in list(detection_streak.keys()):
            if lbl not in detected_labels:
                detection_streak[lbl] = 0
        # Increment streak for every label seen this frame
        for lbl in detected_labels:
            detection_streak[lbl] = detection_streak.get(lbl, 0) + 1

        # Fire motors — all three gates must pass in addition to the existing cooldown.
        # Gate 1: label is in OBSTACLE_CLASSES (motor_intensity returns non-zero).
        # Gate 2: bounding box is large enough (is_close_enough).
        # Gate 3: confidence meets per-class threshold.
        # Gate 4: label has appeared in at least PERSISTENCE_FRAMES consecutive frames.
        now = time.time()
        for det in current_detections:
            # rsplit from right once: handles multi-word labels like "dining table"
            label, direction = det.rsplit(' ', 1)
            # Gate 1 — is this label an obstacle at all?
            if motor_intensity(label) == 0:
                continue

            meta = box_meta.get(label)
            if meta is None:
                continue

            # Gate 2 — proximity; capture depth_score for intensity scaling below
            if DEPTH_ENABLED and depth_map is not None:
                depth_score = sample_depth(depth_map, meta['x1'], meta['y1'], meta['x2'], meta['y2'])
                if depth_score < DEPTH_THRESHOLD:
                    continue
            else:
                if not is_close_enough(meta['x1'], meta['y1'], meta['x2'], meta['y2'], fw, fh):
                    continue
                depth_score = 1.0  # fallback: no depth info, use max intensity

            # Gate 3 — confidence threshold varies by priority tier
            required_conf = HIGH_PRIORITY_CONF if label in HIGH_PRIORITY_CLASSES else OBSTACLE_CONF
            if meta['conf'] < required_conf:
                continue

            # Gate 4 — persistence (suppresses single-frame false positives)
            if detection_streak.get(label, 0) < PERSISTENCE_FRAMES:
                continue

            # All gates passed — scale intensity by depth then apply cooldown and fire
            intensity = motor_intensity(label, depth_score)
            if label not in last_fired or now - last_fired[label] > COOLDOWN_SECONDS:
                last_fired[label] = now
                if direction == 'left':
                    await send_motors(intensity, 0, 0)
                elif direction == 'center':
                    await send_motors(0, intensity, 0)
                else:
                    await send_motors(0, 0, intensity)

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

        # Depth debug overlay — shows each box's depth score and whether it passed the gate
        if depth_map is not None:
            for label, meta in box_meta.items():
                score = sample_depth(depth_map, meta['x1'], meta['y1'], meta['x2'], meta['y2'])
                passed = score >= DEPTH_THRESHOLD
                pwm = motor_intensity(label, score)
                color = (0, 255, 0) if passed else (0, 100, 255)  # green = firing, orange = blocked
                cv2.putText(annotated, f'{label}: d={score:.2f} pwm={pwm}',
                            (meta['x1'], meta['y2'] + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        # Encode annotated frame to JPEG and push to shared state for the web dashboard
        _, buf = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        shared.latest_frame = buf.tobytes()

        # Encode depth map to JPEG if available
        if depth_map is not None:
            depth_uint8 = (depth_map * 255).astype(np.uint8)
            _, depth_buf = cv2.imencode('.jpg', depth_uint8, [cv2.IMWRITE_JPEG_QUALITY, 70])
            shared.latest_depth_frame = depth_buf.tobytes()

        # Local display windows — skipped when SKIP_DISPLAY is set (e.g. Colab/headless)
        if not os.environ.get('SKIP_DISPLAY'):
            if depth_map is not None:
                cv2.imshow('Depth Map', depth_map)
            cv2.imshow('Echolocation Vest', annotated)
            if cv2.waitKey(1) == ord('q'):
                break

        await asyncio.sleep(0)  # yield to event loop so WebSocket messages process


# ── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    """Start the WebSocket motor server, YOLO loop, and web dashboard concurrently."""
    from frontend import run_frontend_server
    async with websockets.serve(motor_handler, '0.0.0.0', MOTOR_WS_PORT):
        print(f'Motor WebSocket server running on port {MOTOR_WS_PORT}')
        print(f'Dashboard running on http://localhost:{FRONTEND_PORT}')
        await asyncio.gather(run_yolo_loop(), run_frontend_server())

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    if not os.environ.get('SKIP_VOICE'):
        import voice  # noqa: F401 — imported for side effect (starts voice WS thread on port 8766)
    asyncio.run(main())
