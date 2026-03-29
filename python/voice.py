import io
import os
import threading

import numpy as np
import pyaudio
import speech_recognition as sr
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from dotenv import load_dotenv
from openwakeword.model import Model

try:
    from shared import current_detections
except ImportError:
    current_detections: list[str] = []  # TODO: remove once Jaden adds this to shared.py

load_dotenv()

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

r = sr.Recognizer()
r.pause_threshold = 0.5       # seconds of silence before end-of-speech (default 0.8)
r.non_speaking_duration = 0.3 # seconds of silence at start before giving up (default 0.5)

# Set WAKE_WORD_MODEL in .env to path of a custom hey-echo.onnx model.
# If not set, falls back to the built-in "hey_jarvis" model for testing.
_WAKE_WORD_MODEL: str | None = os.environ.get("WAKE_WORD_MODEL")
_WAKE_WORD_THRESHOLD: float = float(os.environ.get("WAKE_WORD_THRESHOLD", "0.5"))

_AUDIO_RATE: int = 16000   # required by openwakeword
_AUDIO_CHUNK: int = 1280   # 80ms frames at 16kHz, recommended by openwakeword


def speak(text: str) -> None:
    """Stream text to ElevenLabs TTS and play audio as it arrives — no wait for full response."""
    audio_stream = elevenlabs_client.text_to_speech.stream(
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_turbo_v2_5",
        text=text,
    )
    stream(audio_stream)


def listen_once() -> str | None:
    """Record one utterance and transcribe it with OpenAI Whisper."""
    with sr.Microphone() as source:
        print("Listening...")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            return None

    # Convert to WAV bytes and send to Whisper
    wav_bytes = io.BytesIO(audio.get_wav_data())
    wav_bytes.name = "audio.wav"
    try:
        result = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=wav_bytes,
            language="en",
        )
        return result.text.strip().lower() or None
    except Exception:
        return None


def ask_openai_streaming(detections: list, question: str) -> str:
    """Stream GPT-4o mini response and return the full text (for logging)."""
    prompt = f"""You help blind people navigate safely. Be extremely brief.
Current detections: {detections}
User asked: '{question}'
Respond in one short sentence, 10 words max."""

    stream_response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        max_tokens=30,
    )

    full_reply = ""
    for chunk in stream_response:
        delta = chunk.choices[0].delta.content or ""
        full_reply += delta

    return full_reply


STOP_PHRASES = {
    "i'm done", "im done", "stop", "stop listening", "goodbye",
    "bye", "shut down", "turn off", "quit", "exit", "that's all",
    "thats all", "i'm finished", "im finished", "never mind", "nevermind",
}


def is_stop_command(text: str) -> bool:
    """Return True if the user's text matches a stop/exit phrase."""
    text = text.strip().lower()
    return any(phrase in text for phrase in STOP_PHRASES)


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
    """Wait for wake word, then transcribe with Whisper, get GPT response, and stream TTS.
    Exits cleanly when the user says a stop phrase."""
    print("Voice assistant ready — say 'Hey Echo' to activate.")
    while True:
        try:
            wait_for_wake_word()
            speak("Hello! How can I help you?")
            text = listen_once()
            if text:
                print(f"You said: {text}")
                if is_stop_command(text):
                    speak("Got it, stopping. Goodbye!")
                    print("Voice loop stopped by user.")
                    break
                reply = ask_openai_streaming(current_detections, text)
                print(f"GPT: {reply}")
                speak(reply)
        except Exception as e:
            print(f"Voice loop error: {e}")


voice_thread = threading.Thread(target=voice_loop, daemon=True)
voice_thread.start()

if __name__ == "__main__":
    voice_thread.join()
