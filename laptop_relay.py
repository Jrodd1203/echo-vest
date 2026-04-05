"""
laptop_relay.py
Run this on your laptop before starting the Colab notebook.
Streams the local webcam as MJPEG and exposes it publicly via localtunnel
(no account needed, no tunnel limits — keeps ngrok free for Colab).

Usage:
    pip install flask
    npm install -g localtunnel   (one-time)
    python laptop_relay.py
"""
import subprocess
import cv2
from flask import Flask, Response

app = Flask(__name__)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def _generate():
    """Yield MJPEG frames from the local webcam."""
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')


@app.route('/stream')
def stream():
    """MJPEG stream endpoint — Colab reads from this URL."""
    return Response(_generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/health')
def health():
    """Quick liveness check."""
    return 'OK'


if __name__ == '__main__':
    import threading, time

    def _start_tunnel():
        time.sleep(1)  # let Flask start first
        proc = subprocess.Popen(
            ['lt', '--port', '5001'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            if 'your url is' in line.lower() or 'loca.lt' in line.lower():
                url = line.strip().split()[-1]
                print('\n' + '='*60)
                print('  Camera relay is live!')
                print(f'  Relay URL: {url}')
                print(f'  Stream:    {url}/stream')
                print('  Paste the relay URL into the Colab notebook.')
                print('='*60 + '\n')
                break

    threading.Thread(target=_start_tunnel, daemon=True).start()
    app.run(host='0.0.0.0', port=5001, threaded=True)
