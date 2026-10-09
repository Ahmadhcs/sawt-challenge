import argparse
import logging
import time

from .agent import respond
from .stt import load_wav, record_from_mic, transcribe
from .tts import speak

# placeholder for testing, makes it easier for me to end call 
END_PHRASE = "خلاص"


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _print_averages(turns: dict[str, list[float]]) -> None:
    print("\n--- Session averages (ms) ---")
    print(f"STT:              {_average(turns['stt']):.0f}")
    print(f"LLM first token:  {_average(turns['llm_ttft']):.0f}")
    print(f"LLM total:        {_average(turns['llm_total']):.0f}")
    print(f"TTS:              {_average(turns['tts']):.0f}")
    print(f"Full turn:        {_average(turns['turn']):.0f}")


def _run_turn(history: list[dict[str, str]], audio_bytes: bytes) -> tuple[bool, dict[str, float]]:
    turn_start = time.perf_counter()

    stt_start = time.perf_counter()
    result = transcribe(audio_bytes)
    stt_ms = (time.perf_counter() - stt_start) * 1000

    transcript = result.text
    print(f"You: {transcript}")

    if END_PHRASE in transcript:
        print("Caller ended the call.")
        return False, {}

    reply = respond(history, transcript)
    history.append({"role": "user", "content": transcript})
    history.append({"role": "assistant", "content": reply.text})
    print(f"Agent: {reply.text}")

    tts_ms = speak(reply.text)

    turn_ms = (time.perf_counter() - turn_start) * 1000
    print(
        f"Timings (ms): STT={stt_ms:.0f} "
        f"LLM_first_token={reply.time_to_first_token_ms:.0f} LLM_total={reply.total_ms:.0f} "
        f"TTS={tts_ms:.0f} Turn={turn_ms:.0f}"
    )

    return True, {
        "stt": stt_ms,
        "llm_ttft": reply.time_to_first_token_ms,
        "llm_total": reply.total_ms,
        "tts": tts_ms,
        "turn": turn_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=str, default=None, help="run a single turn from a WAV file instead of the mic")
    args = parser.parse_args()

    history: list[dict[str, str]] = []
    timings: dict[str, list[float]] = {"stt": [], "llm_ttft": [], "llm_total": [], "tts": [], "turn": []}

    try:
        while True:
            audio_bytes = load_wav(args.wav) if args.wav else record_from_mic()
            keep_going, turn_timings = _run_turn(history, audio_bytes)

            for key, value in turn_timings.items():
                timings[key].append(value)

            if not keep_going or args.wav:
                break
    except KeyboardInterrupt:
        print("\nStopped.")

    _print_averages(timings)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        main()
    except RuntimeError as e:
        print(f"Error: {e}")
