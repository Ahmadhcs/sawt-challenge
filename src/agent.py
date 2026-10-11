import json
import logging
import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

from .restaurant_db import list_categories
from .tools import CallSession, get_openai_tool_schemas, llm_summary, run_tool

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_ID = os.getenv("OPENAI_MODEL_ID", "gpt-4.1")
MAX_TOOL_ROUNDS = 5
APOLOGY_TEXT = "عذرًا، واجهت مشكلة في معالجة طلبك، ممكن تعيد كلامك؟"

SYSTEM_PROMPT = f"""ROLE: You are a phone order agent for a Saudi restaurant. Reply in short, natural Saudi Arabic - one or two sentences per reply, like a real phone call.

GOALS (a checklist, not a script - ask for whatever is still missing, in any order the caller gives it):
- service type (delivery or pickup)
- delivery area, or pickup branch
- items, with all required options chosen
- a read-back of the order
- clear agreement ("yes") before confirming

Accept information the caller gives early or out of order. If the caller changes an earlier answer (location, service type, an item), call the matching tool again - don't just acknowledge it in words.

HARD RULES:
- Only change the order through tools. Never state a price, fee, or total that didn't come from a tool result.
- Call search_menu before add_item. Use get_item_details to see valid option IDs before adding an item with options.
- If search results are ambiguous, ask the caller which one they mean instead of guessing.
- If a search result already has a detected_size or detected_options, use it instead of asking again.
- Before confirming, call get_order_summary and read back the items, fee, and total to the caller.
- Only call confirm_order after the caller clearly agrees ("yes"/"اوكي"/"تمام") to the read-back.
- If a line is flagged unavailable, tell the caller and ask what they'd like to do about it.
- If set_location returns an error for an area that's not covered, ask the caller to repeat the area, then offer pickup as an alternative.
- A complaint or a request for a human, at any point in the call, means call transfer_to_human.

Menu categories: {", ".join(list_categories())}
"""


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: dict


@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your .env file.")
    return OpenAI(api_key=api_key)


def respond(session: CallSession, history: list[dict[str, str]], user_text: str) -> AgentReply:
    client = _get_client()
    tool_schemas = get_openai_tool_schemas()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current order state: {json.dumps(llm_summary(session.order), ensure_ascii=False)}"},
        *history,
        {"role": "user", "content": user_text},
    ]

    tool_call_records: list[ToolCallRecord] = []
    seen_calls: dict[tuple[str, str], dict] = {}

    start = time.perf_counter()
    for _round in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(model=MODEL_ID, messages=messages, tools=tool_schemas)
        message = response.choices[0].message

        if not message.tool_calls:
            total_ms = (time.perf_counter() - start) * 1000
            logger.info("LLM turn finished in %.0fms with %d tool call(s).", total_ms, len(tool_call_records))
            return AgentReply(text=message.content or "", tool_calls=tool_call_records)

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            dedupe_key = (name, json.dumps(args, sort_keys=True))
            if dedupe_key in seen_calls:
                result = seen_calls[dedupe_key]
            else:
                result = run_tool(session, name, args)
                seen_calls[dedupe_key] = result

            tool_call_records.append(ToolCallRecord(name=name, args=args, result=result))
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result, ensure_ascii=False)}
            )

    logger.info("Hit MAX_TOOL_ROUNDS (%d) without a final reply.", MAX_TOOL_ROUNDS)
    return AgentReply(text=APOLOGY_TEXT, tool_calls=tool_call_records)
