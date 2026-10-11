import argparse
import json
import logging

from .agent import ToolCallRecord, respond
from .order_state import OrderState
from .stt import load_wav, record_from_mic, transcribe
from .tools import CallSession
from .tts import speak


def _print_tool_call(record: ToolCallRecord) -> None:
    args_json = json.dumps(record.args, ensure_ascii=False)
    result_json = json.dumps(record.result, ensure_ascii=False)
    print(f"  TOOL {record.name}({args_json}) -> {result_json}")


def _run_turn(session: CallSession, history: list[dict[str, str]], user_text: str, speak_reply: bool) -> bool:
    """Runs one turn. Returns False when the call should end."""
    reply = respond(session, history, user_text)

    for record in reply.tool_calls:
        _print_tool_call(record)

    print(f"Order: {json.dumps(session.order.summary(), ensure_ascii=False)}")
    print(f"Agent: {reply.text}")

    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply.text})

    if speak_reply:
        speak(reply.text)

    return not (session.order.status == "confirmed" or session.transferred)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true", help="type instead of using the mic")
    parser.add_argument("--speak", action="store_true", help="speak replies out loud even in --text mode")
    parser.add_argument("--wav", type=str, default=None, help="run a single turn from a WAV file instead of the mic")
    args = parser.parse_args()

    session = CallSession(order=OrderState())
    history: list[dict[str, str]] = []
    speak_reply = (not args.text) or args.speak

    try:
        while True:
            if args.text:
                user_text = input()
            elif args.wav:
                user_text = transcribe(load_wav(args.wav)).text
            else:
                user_text = transcribe(record_from_mic()).text

            print(f"You: {user_text}")

            keep_going = _run_turn(session, history, user_text, speak_reply)
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
