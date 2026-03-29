import os
import threading
import time

import speech_recognition as sr
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from dotenv import load_dotenv

try:
    from shared import current_detections
except ImportError:
    current_detections: list[str] = []  # TODO: remove once Jaden adds this to shared.py

load_dotenv()

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

r = sr.Recognizer()
r.pause_threshold = 0.5
r.non_speaking_duration = 0.3
r.dynamic_energy_threshold = True  # auto-adjusts mic sensitivity to background noise


def speak(text: str) -> None:
    """Stream text to ElevenLabs TTS and play audio as it arrives — no wait for full response."""
    try:
        audio_stream = elevenlabs_client.text_to_speech.stream(
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_flash_v2_5",
            text=text,
        )
        stream(audio_stream)
    except Exception as e:
        print(f"[SPEAK ERROR] {type(e).__name__}: {e}")


def listen_once() -> str | None:
    """Record one utterance and transcribe it with Google Speech Recognition."""
    with sr.Microphone() as source:
        print("Listening...")
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=6)
            return r.recognize_google(audio).lower()
        except Exception:
            return None


def ask_and_speak(detections: list, question: str) -> None:
    """Get GPT-4o mini response and speak it via ElevenLabs."""
    prompt = f"""You help blind people navigate safely. Be extremely brief.
Current detections: {detections}
User asked: '{question}'
Respond in one short sentence, 10 words max."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
        )
        reply = response.choices[0].message.content.strip()
        print(f"\n>>> GPT: {reply}\n")
        speak(reply)
    except Exception as e:
        import traceback
        print(f"\n[ASK ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()


STOP_PHRASES = {
    "goodbye", "good bye", "bye", "bye bye",
    "i'm done", "im done", "done", "i am done",
    "finished", "i'm finished", "im finished", "i am finished",
    "stop", "stop listening", "shut down", "turn off",
    "quit", "exit", "that's all", "thats all",
    "never mind", "nevermind", "see you", "see ya",
}


def is_stop_command(text: str) -> bool:
    """Return True if the user's text matches a stop/exit phrase."""
    text = text.strip().lower()
    return any(phrase in text for phrase in STOP_PHRASES)



def voice_loop() -> None:
    """Calibrate mic once, then loop: wait for 'Hey Echo', respond, repeat."""
    print("Voice assistant ready — calibrating mic...")
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1)
    print("Ready — say 'Hey Echo' to activate.")

    while True:
        # ── Wake word ──────────────────────────────────────────
        print("Waiting for wake word 'Hey Echo'...")
        with sr.Microphone() as source:
            while True:
                try:
                    audio = r.listen(source, timeout=2, phrase_time_limit=2)
                    heard = r.recognize_google(audio).lower()
                    print(f"Heard: {heard}")
                    if "hey echo" in heard:
                        print("Wake word detected!")
                        break
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"SR network error: {e}")
                except Exception as e:
                    print(f"Wake word error: {type(e).__name__}: {e}")

        # ── Active conversation loop — keeps listening until stop command ──
        speak("Yes?")
        while True:
            text = listen_once()
            if not text:
                break  # timed out — go back to wake word

            print(f"You said: {text}")
            if is_stop_command(text):
                speak("Goodbye! Say Hey Echo whenever you need me.")
                break  # exit conversation, go back to wake word

            ask_and_speak(current_detections, text)
            time.sleep(0.3)  # tiny pause so mic doesn't catch TTS tail


voice_thread = threading.Thread(target=voice_loop, daemon=True)
voice_thread.start()

if __name__ == "__main__":
    voice_thread.join()
