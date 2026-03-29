"""
frontend.py — Jaden only
FastAPI server: MJPEG streams, WebSocket status, serves React build.
"""
import asyncio
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import shared
from config import FRONTEND_PORT, DEPTH_ENABLED

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

_FRONTEND_DIST = Path(__file__).parent.parent / 'frontend' / 'dist'


async def _mjpeg_generator(attr: str):
    """Yield MJPEG boundary frames from a shared bytes attribute."""
    while True:
        frame = getattr(shared, attr)
        if frame:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n'
                + frame +
                b'\r\n'
            )
        await asyncio.sleep(0.033)


@app.get('/stream')
async def video_stream() -> StreamingResponse:
    """Stream annotated YOLO frames as MJPEG."""
    return StreamingResponse(
        _mjpeg_generator('latest_frame'),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )


@app.get('/raw')
async def raw_stream() -> StreamingResponse:
    """Stream raw (unannotated) camera frames as MJPEG."""
    return StreamingResponse(
        _mjpeg_generator('latest_raw_frame'),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )


@app.get('/depth')
async def depth_stream() -> StreamingResponse:
    """Stream the MiDaS depth map as MJPEG."""
    return StreamingResponse(
        _mjpeg_generator('latest_depth_frame'),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )


@app.websocket('/ws')
async def status_ws(ws: WebSocket) -> None:
    """Push live status JSON at 10 Hz."""
    await ws.accept()
    try:
        while True:
            await ws.send_text(json.dumps({
                'detections': shared.current_detections,
                'motor_connected': shared.motor_connected,
                'cam_connected': shared.cam_connected,
                'voice_status': shared.voice_status,
                'depth_enabled': DEPTH_ENABLED,
                'chat_messages': list(shared.chat_messages),
            }))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass


# Serve the built React app — mount last so API routes take priority
if _FRONTEND_DIST.exists():
    app.mount('/', StaticFiles(directory=str(_FRONTEND_DIST), html=True), name='static')


async def run_frontend_server() -> None:
    """Run uvicorn inside the existing asyncio event loop."""
    config = uvicorn.Config(app, host='0.0.0.0', port=FRONTEND_PORT, log_level='warning')
    server = uvicorn.Server(config)
    await server.serve()
