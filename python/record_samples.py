"""
Record 25 samples of "Hey Echo" for wake word training.
Run this script, then upload the hey_echo_samples/ folder to the
openwakeword training Colab notebook (github.com/dscripka/openWakeWord).
"""
import os
import wave

import pyaudio

OUTPUT_DIR = "hey_echo_samples"
NUM_SAMPLES = 25
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 2

os.makedirs(OUTPUT_DIR, exist_ok=True)
pa = pyaudio.PyAudio()

print("=== Hey Echo — Sample Recorder ===")
print(f"Recording {NUM_SAMPLES} samples at {RATE}Hz, {RECORD_SECONDS}s each.\n")

for i in range(NUM_SAMPLES):
    input(f"[{i+1}/{NUM_SAMPLES}] Press Enter, then say 'Hey Echo' clearly...")
    stream = pa.open(rate=RATE, channels=1, format=pyaudio.paInt16, input=True)
    frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * RECORD_SECONDS))]
    stream.stop_stream()
    stream.close()

    path = os.path.join(OUTPUT_DIR, f"hey_echo_{i+1:02d}.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    print(f"  Saved → {path}")

pa.terminate()
print(f"\nDone! {NUM_SAMPLES} samples saved to '{OUTPUT_DIR}/'")
print("Next: upload that folder to the openwakeword Colab to train your model.")
