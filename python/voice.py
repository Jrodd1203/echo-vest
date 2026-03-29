import os
import threading

import numpy as np
import pyaudio
import speech_recognition as sr
from google import genai
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv
from openwakeword.model import Model

try:
    from shared import current_detections
except ImportError:
    current_detections: list[str] = []  # TODO: remove once Jaden adds this to shared.py

load_dotenv()

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

r = sr.Recognizer()

# Set WAKE_WORD_MODEL in .env to path of a custom hey-echo.onnx model.
# If not set, falls back to the built-in "hey_jarvis" model for testing.
_WAKE_WORD_MODEL: str | None = os.environ.get("WAKE_WORD_MODEL")
_WAKE_WORD_THRESHOLD: float = float(os.environ.get("WAKE_WORD_THRESHOLD", "0.5"))

_AUDIO_RATE: int = 16000   # required by openwakeword
_AUDIO_CHUNK: int = 1280   # 80ms frames at 16kHz, recommended by openwakeword


def speak(text: str) -> None:
    """Convert text to speech using ElevenLabs and play it back."""
    audio = elevenlabs_client.text_to_speech.convert(
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2_5",
        text=text,
    )
    play(audio)


def listen_once() -> str | None:
    """Listen for one spoken utterance from the microphone and return transcribed text."""
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        print("Listening...")
        try:
            audio = r.listen(source, timeout=5)
            return r.recognize_google(audio).lower()
        except Exception:
            return None


def ask_gemini(detections: list, question: str) -> str:
    """Send current detections and user question to Gemini and return a natural response."""
    prompt = f"""
You help blind people navigate safely.
Current detections: {detections}
User asked: '{question}'
Respond in 1-2 natural sentences.
"""
    response = gemini_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def wait_for_wake_word() -> None:
    """Block until the wake word is detected using openwakeword."""
    if _WAKE_WORD_MODEL:
        oww = Model(wakeword_models=[_WAKE_WORD_MODEL], inference_framework="onnx")
        label = "Hey Echo"
    else:
        # Fallback: built-in hey_jarvis model while custom hey-echo.onnx is not yet trained
        oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        label = "Hey Jarvis (test fallback)"

    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=_AUDIO_RATE,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=_AUDIO_CHUNK,
    )
    print(f"Waiting for wake word '{label}'...")
    try:
        while True:
            raw = stream.read(_AUDIO_CHUNK, exception_on_overflow=False)
            audio_chunk = np.frombuffer(raw, dtype=np.int16)
            scores = oww.predict(audio_chunk)
            if any(score >= _WAKE_WORD_THRESHOLD for score in scores.values()):
                print("Wake word detected!")
                break
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def voice_loop() -> None:
    """Wait for 'Hey Echo' wake word, greet the user, listen for a question, then respond."""
    print("Voice assistant ready — say 'Hey Echo' to activate.")
    while True:
        try:
            wait_for_wake_word()
            speak("Hello! How can I help you?")
            text = listen_once()
            if text:
                print(f"You said: {text}")
                reply = ask_gemini(current_detections, text)
                print(f"Gemini: {reply}")
                speak(reply)
        except Exception as e:
            print(f"Voice loop error: {e}")


voice_thread = threading.Thread(target=voice_loop, daemon=True)
voice_thread.start()

if __name__ == "__main__":
    voice_thread.join()
