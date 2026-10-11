import argparse
import json
import logging
import time

from .agent import ToolCallRecord, respond
from .locations import load_branches, load_zones
from .order_state import OrderState
from .restaurant_db import load_menu
from .stt import load_wav, mark_low_confidence, record_from_mic, transcribe
from .tools import CallSession
from .tts import speak, speak_order_id

MAX_KEYTERMS = 100


def _build_keyterms() -> list[str]:
    zone_names = [z.name_ar for z in load_zones()]
    branch_names = [b.name_ar for b in load_branches().values()]

    category_names = []
    dish_names = []
    seen_categories = set()
    for item in load_menu().values():
        if item.category_id not in seen_categories:
            seen_categories.add(item.category_id)
            category_names.append(item.category_ar)
        dish_names.append(item.name_ar)

    keyterms = zone_names + branch_names + category_names + dish_names
    return keyterms[:MAX_KEYTERMS]


def _print_tool_call(record: ToolCallRecord) -> None:
    args_json = json.dumps(record.args, ensure_ascii=False)
    result_json = json.dumps(record.result, ensure_ascii=False)
    print(f"  TOOL {record.name}({args_json}) -> {result_json}")


def _run_turn(
    session: CallSession, history: list[dict[str, str]], user_text: str, speak_reply: bool, stt_ms: float
) -> bool:
    """Runs one turn. Returns False when the call should end."""
    turn_start = time.perf_counter()

    reply = respond(session, history, user_text)

    for record in reply.tool_calls:
        _print_tool_call(record)

    print(f"Order: {json.dumps(session.order.summary(), ensure_ascii=False)}")
    print(f"Agent: {reply.text}")

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply.text})

    tts_ms = speak(reply.text) if speak_reply else 0.0
    confirmed = session.order.status == "confirmed"
    if confirmed and speak_reply:
        speak_order_id(session.order.order_id)

    turn_ms = (time.perf_counter() - turn_start) * 1000
    print(
        f"Timings (ms): STT={stt_ms:.0f} LLM_total={reply.total_ms:.0f} TTS={tts_ms:.0f} Turn={turn_ms:.0f}"
    )

    return not (confirmed or session.transferred)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true", help="type instead of using the mic")
    parser.add_argument("--speak", action="store_true", help="speak replies out loud even in --text mode")
    parser.add_argument("--wav", type=str, default=None, help="run a single turn from a WAV file instead of the mic")
    args = parser.parse_args()

    session = CallSession(order=OrderState())
    history: list[dict[str, str]] = []
    speak_reply = (not args.text) or args.speak
    keyterms = _build_keyterms()

    try:
        while True:
            stt_ms = 0.0
            if args.text:
                user_text = input()
            else:
                audio_bytes = load_wav(args.wav) if args.wav else record_from_mic()
                stt_start = time.perf_counter()
                result = transcribe(audio_bytes, keyterms=keyterms)
                stt_ms = (time.perf_counter() - stt_start) * 1000
                user_text = mark_low_confidence(result)

            print(f"You: {user_text}")

            keep_going = _run_turn(session, history, user_text, speak_reply, stt_ms)
            print()

            if not keep_going or args.wav:
                break
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        main()
    except RuntimeError as e:
        print(f"Error: {e}")
