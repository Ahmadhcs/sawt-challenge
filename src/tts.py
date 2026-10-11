import logging
import os
import time

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

TTS_MODEL_ID = os.getenv("ELEVEN_TTS_MODEL_ID", "eleven_flash_v2_5")
TTS_VOICE_ID = os.getenv("ELEVEN_TTS_VOICE_ID", "SAz9YHcvj6GT2YYXdXww")


def _get_client() -> ElevenLabs:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is missing. Add it to your .env file.")
    return ElevenLabs(api_key=api_key)


def speak(text: str) -> float:
    client = _get_client()

    logger.info("Sending text to ElevenLabs TTS (%s, voice %s)...", TTS_MODEL_ID, TTS_VOICE_ID)
    start = time.perf_counter()
    audio_chunks = client.text_to_speech.convert(
        text=text,
        voice_id=TTS_VOICE_ID,
        model_id=TTS_MODEL_ID,
        output_format=f"pcm_{SAMPLE_RATE}",
    )
    audio_bytes = b"".join(audio_chunks)
    # This is the full synthesis time (all chunks collected before playback
    # starts), not time-to-first-byte - we don't stream playback.
    synthesis_ms = (time.perf_counter() - start) * 1000
    logger.info("Received %d bytes of audio in %.0fms. Playing...", len(audio_bytes), synthesis_ms)

    samples = np.frombuffer(audio_bytes, dtype=np.int16)
    sd.play(samples, samplerate=SAMPLE_RATE)
    sd.wait()

    return synthesis_ms


ARABIC_DIGIT_WORDS = {
    "0": "صفر",
    "1": "واحد",
    "2": "اثنين",
    "3": "ثلاثة",
    "4": "أربعة",
    "5": "خمسة",
    "6": "ستة",
    "7": "سبعة",
    "8": "ثمانية",
    "9": "تسعة",
}


def speak_order_id(order_id: str) -> None:
    digits_spoken = " ".join(ARABIC_DIGIT_WORDS[d] for d in order_id if d in ARABIC_DIGIT_WORDS)
    speak(f"رقم طلبك: {digits_spoken}")


def list_arabic_voices() -> None:
    client = _get_client()
    response = client.voices.search(language=["ar"], voice_type="default")
    voices = response.voices

    if not voices:
        print("No default voices are tagged 'Arabic' (the tag is accent, not language ability).")
        print("Multilingual models can still speak Arabic text through any voice. Listing all default voices instead:")
        voices = client.voices.search(voice_type="default").voices

    for voice in voices:
        print(f"{voice.voice_id}  {voice.name}  {voice.labels}")
