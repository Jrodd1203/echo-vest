import asyncio
import os
import threading

import websockets
import speech_recognition as sr
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv

from shared import current_detections

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

r = sr.Recognizer()


def speak(text: str) -> None:
    """Convert text to speech using ElevenLabs and play it back."""
    audio = elevenlabs_client.text_to_speech.convert(
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # Rachel — swap voice_id as needed
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
    response = gemini_model.generate_content(prompt)
    return response.text


async def voice_handler(ws: websockets.ServerConnection) -> None:
    """Handle incoming WebSocket messages — fires mic + Gemini + TTS when ESP32 sends 'LISTEN'."""
    async for message in ws:
        if message == "LISTEN":
            text = listen_once()
            if text:
                reply = ask_gemini(current_detections, text)
                speak(reply)


def voice_thread_fn() -> None:
    """Entry point for the background voice thread — runs the WebSocket server on port 8766."""
    asyncio.run(websockets.serve(voice_handler, "0.0.0.0", 8766))


voice_thread = threading.Thread(target=voice_thread_fn, daemon=True)
voice_thread.start()
