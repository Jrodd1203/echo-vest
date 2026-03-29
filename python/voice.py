import os
import threading
import time

import speech_recognition as sr
from deepgram import DeepgramClient
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from dotenv import load_dotenv

try:
    import shared
    from shared import current_detections
except ImportError:
    import types
    shared = types.SimpleNamespace(voice_status='idle', chat_messages=[])
    current_detections: list[str] = []

load_dotenv()

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
deepgram_client = DeepgramClient(api_key=os.environ["DEEPGRAM_API_KEY"])

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
        import traceback
        print(f"[SPEAK ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()


def listen_once(source: sr.AudioSource) -> str | None:
    """Record one utterance from an already-open microphone and transcribe with Deepgram.

    Accepts a persistent microphone source so we avoid the cold-start delay that
    clips the first syllable when opening a new Microphone() each call.
    """
    print("Listening...")
    try:
        audio = r.listen(source, timeout=5, phrase_time_limit=6)
    except sr.WaitTimeoutError:
        return None

    try:
        response = deepgram_client.listen.v1.media.transcribe_file(
            request=audio.get_wav_data(),
            model="nova-2",
            language="en",
        )
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript.strip().lower() or None
    except Exception as e:
        print(f"[DEEPGRAM ERROR] {e}")
        return None


def ask_and_speak(detections: list, question: str) -> None:
    """Get GPT-4o mini response, speak it, and log both sides to shared chat."""
    shared.chat_messages.append({'role': 'user', 'text': question, 'timestamp': time.time()})
    shared.voice_status = 'processing'

    prompt = f"Blind navigation assistant. Detections: {detections}. Question: {question}. Reply in 8 words max."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
        )
        reply = response.choices[0].message.content.strip()
        print(f"\n>>> GPT: {reply}\n")
        shared.chat_messages.append({'role': 'assistant', 'text': reply, 'timestamp': time.time()})
        speak(reply)
    except Exception as e:
        import traceback
        print(f"\n[ASK ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        shared.voice_status = 'listening'


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
        shared.voice_status = 'idle'
        print("Waiting for wake word 'Hey Echo'...")
        with sr.Microphone() as source:
            while True:
                try:
                    audio = r.listen(source, timeout=2, phrase_time_limit=2)
                    heard = r.recognize_google(audio).lower()
                    print(f"Heard: {heard}")
                    if any(w in heard for w in ("hey echo", "hi echo", "hello echo", "hi", "hello")):
                        print("Wake word detected!")
                        break
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"SR network error: {e}")
                except Exception as e:
                    print(f"Wake word error: {type(e).__name__}: {e}")

        # ── Active conversation loop — mic stays open to avoid cold-start clipping ──
        speak("Yes?")
        time.sleep(0.8)  # let TTS finish fully before opening mic
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.2)  # recalibrate after TTS
            while True:
                shared.voice_status = 'listening'
                text = listen_once(source)
                if not text:
                    break  # timed out — go back to wake word

                print(f"You said: {text}")
                if is_stop_command(text):
                    print("Saying goodbye...")
                    speak("Goodbye!")
                    print("Goodbye spoken.")
                    break  # exit conversation, go back to wake word

                ask_and_speak(current_detections, text)
                time.sleep(0.8)  # wait for TTS to fully finish before listening again


voice_thread = threading.Thread(target=voice_loop, daemon=True)
voice_thread.start()

if __name__ == "__main__":
    voice_thread.join()
