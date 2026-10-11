# Sawt Challenge — Arabic Restaurant Voice Agent

A Python CLI that takes a restaurant order over voice or text, in Saudi Arabic. Speech goes in, an llm driven agent manages the order through validated tools against a real menu/branch/zone dataset, and a spoken reply comes back out.

## Requirements

- Python 3.12
- A microphone, you can use text mode if not available. 

## Setup

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

You'll need a `.env` file in the project root with:

```
OPENAI_API_KEY=...
ELEVENLABS_API_KEY=...
```

(`.env` will be sent separately, as a one time link alongside the email submission)

## Running it

**Voice mode** (records from your mic, transcribes, speaks the reply back):

```
.venv/bin/python -m src.main
```

Press Enter after speaking each turn. The call ends when the order is confirmed (it reads the order ID back digit by digit) or you ask for a human.

**Text mode** (type instead of using the mic; no TTS unless you pass `--speak`):

```
.venv/bin/python -m src.main --text
```

Every turn prints the caller's text, each tool call with its arguments and result, the full order state, and the agent's reply.

## Tests

**Unit tests** (fast, free, no API calls):

```
.venv/bin/python -m pytest
```

**Scenario tests** (slow, real GPT-4.1 calls — costs API usage, skipped by default):

```
RUN_SCENARIOS=1 .venv/bin/python -m pytest tests/scenarios/
```

These run scripted multi turn conversations through the real agent and assert on the final order state and tool calls made, never on exact reply wording.

## More detail

See [DESIGN.md](DESIGN.md) for the architecture, journey diagram, and design decisions.
