import io
import logging
import math
import os
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
LOW_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class Word:
    text: str
    confidence: float


@dataclass
class TranscriptionResult:
    text: str
    words: list[Word]


def _get_client() -> ElevenLabs:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is missing. Add it to your .env file.")
    return ElevenLabs(api_key=api_key)


def record_from_mic() -> bytes:
    logger.info("Microphone open. Recording... press Enter to stop.")
    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            logger.warning("stream status: %s", status)
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        input()

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype="int16")
    _log_recording_stats(audio)
    return _to_wav_bytes(audio)


def _log_recording_stats(audio: np.ndarray) -> None:
    seconds = len(audio) / SAMPLE_RATE
    peak = int(np.abs(audio).max()) if len(audio) else 0
    logger.info("Recording stopped. Captured %.1fs, peak amplitude %d (out of 32767).", seconds, peak)
    if peak < 50:
        logger.warning("Audio looks silent. Check mic permissions for your terminal app.")


def _to_wav_bytes(audio: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio.tobytes())
    return buffer.getvalue()


def load_wav(path: str) -> bytes:
    return Path(path).read_bytes()


def transcribe(audio_bytes: bytes, keyterms: list[str] | None = None) -> TranscriptionResult:
    client = _get_client()

    kwargs = {
        "file": io.BytesIO(audio_bytes),
        "model_id": "scribe_v2",
        "language_code": "ar",
    }
    if keyterms:
        kwargs["keyterms"] = keyterms

    logger.info("Sending %d bytes of audio to ElevenLabs (scribe_v2, ar)...", len(audio_bytes))
    start = time.perf_counter()
    response = client.speech_to_text.convert(**kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Got response in %.0fms: language=%s (%.0f%% confidence), %d word entries.",
        elapsed_ms,
        response.language_code,
        response.language_probability * 100,
        len(response.words),
    )

    words = [
        Word(text=w.text, confidence=math.exp(w.logprob))
        for w in response.words
        if w.type == "word" and w.logprob is not None
    ]
    return TranscriptionResult(text=response.text, words=words)


def mark_low_confidence(result: TranscriptionResult) -> str:
    if not result.words:
        return result.text
    return " ".join(
        f"[غير متأكد: {w.text}]" if w.confidence < LOW_CONFIDENCE_THRESHOLD else w.text for w in result.words
    )
