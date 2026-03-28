import os
import threading

import speech_recognition as sr
from google import genai
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv

try:
    from shared import current_detections
except ImportError:
    current_detections: list[str] = []  # TODO: remove once Jaden adds this to shared.py

load_dotenv()

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

r = sr.Recognizer()


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


def voice_loop() -> None:
    """Continuously listen for speech, ask Gemini, and speak the response."""
    print("Voice loop started — listening for speech...")
    while True:
        try:
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
