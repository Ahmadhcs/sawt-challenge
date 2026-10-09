import argparse
import logging

from .stt import load_wav, record_from_mic, transcribe
from .tts import list_arabic_voices, speak


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stt", action="store_true", help="run a speech-to-text test")
    parser.add_argument("--wav", type=str, default=None, help="path to a WAV file instead of recording")
    parser.add_argument("--tts", type=str, default=None, help="Arabic text to speak out loud")
    parser.add_argument("--list-voices", action="store_true", help="list voices that support Arabic")
    args = parser.parse_args()

    if args.list_voices:
        list_arabic_voices()
        return

    if args.tts:
        speak(args.tts)
        return

    if not args.stt:
        parser.print_help()
        return

    audio_bytes = load_wav(args.wav) if args.wav else record_from_mic()
    result = transcribe(audio_bytes)

    print(f"Text: {result.text}")
    for word in result.words:
        print(f"  {word.text}: {word.confidence:.0%}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        _main()
    except RuntimeError as e:
        print(f"Error: {e}")
