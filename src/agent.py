import logging
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

MODEL_ID = os.getenv("OPENAI_MODEL_ID", "gpt-4.1")

SYSTEM_PROMPT = (
    "أنت موظف استقبال طلبات في مطعم سعودي عبر الهاتف. "
    "رد باللهجة السعودية الطبيعية، بإيجاز شديد (جملة أو جملتين)، وكأنك في مكالمة هاتفية حقيقية."
)


@dataclass
class AgentReply:
    text: str
    time_to_first_token_ms: float
    total_ms: float


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your .env file.")
    return OpenAI(api_key=api_key)


def respond(history: list[dict[str, str]], user_text: str) -> AgentReply:
    client = _get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_text}]

    start = time.perf_counter()
    first_token_time = None
    chunks = []

    stream = client.chat.completions.create(model=MODEL_ID, messages=messages, stream=True)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            chunks.append(delta)

    total_ms = (time.perf_counter() - start) * 1000
    ttft_ms = (first_token_time - start) * 1000 if first_token_time else total_ms
    text = "".join(chunks)

    logger.info("LLM reply in %.0fms (first token %.0fms).", total_ms, ttft_ms)
    return AgentReply(text=text, time_to_first_token_ms=ttft_ms, total_ms=total_ms)
