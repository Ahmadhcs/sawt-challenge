# Design

## Overview

The agent is a Python CLI that runs one voice ordering phone call in Saudi Arabic: record or load audio, transcribe it, let an LLM understand the caller and decide what to do, then speak the reply back. The one idea behind the design is a hybrid split: the LLM understands speech and phrases replies, but it never touches the order directly, code owns the order state, and the LLM can only change it by calling validated tools.

## Why Python

I haven't written much Python recently (my day to day has been Node.js with TypeScript), but it was the clear choice for this project:

- every STT, LLM and TTS provider I considered ships a first class Python SDK
- the open-source Arabic models I recommend in EVALUATION.md run on the Python ecosystem (Hugging Face / PyTorch), so a self hosted model could later replace a hosted one without changing languages

## Demo stack

- **STT:** ElevenLabs Scribe v2: lowest WER (13.2%) among five commercial  providers on an independent Saudi Arabic (Najdi & Hijazi)–English code switching benchmark. Returns a log probability per word, which the agent converts to a confidence score to decide when to confirm an address, quantity, or size with the caller. Also supports keyterm biasing, used to pass menu item names.
- **LLM:** GPT-4.1: a fast, non reasoning model with reliable tool calling, which the hybrid design depends on since the LLM can only act through tools. Natural conversation needs ~1.5s voice to voice, about 700ms time to first token for the LLM, the most accurate tool calling models in that benchmark were too slow for live voice. Tool calling accuracy also drops 5–10% when users speak Arabic, so all tool inputs are validated in code.
- **TTS:** ElevenLabs Flash v2.5 : the lowest latency ElevenLabs model (~75ms) that still lists Arabic in its supported languages, their other low latency models dropped Arabic support. Same provider account as stt to keep the demo stack simple. Requests raw PCM output instead of mp3, so playback doesn't need an extra audio decoder.
  - First choice was a shared library voice tagged with an Arabic accent, since that's closest to what a Saudi caller would expect to hear. ElevenLabs blocks free tier accounts from using shared library voices via the API (kept running into a 402 :/ ), so the demo falls back to the free tier default voice instead. None of the default voices are labeled Arabic, but flash v2.5 can still speak Arabic text through an english accented default voice. Worth a real Arabic voice before any production use.

Sources: 
- Benchmark of commercial ASR on saudi arabic-english code switching (https://benchmarklist.com/models/elevenlabs-scribe-v2/)
- ElevenLabs speech to text API reference (https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- Best LLM for AI voice agents (https://murf.ai/blog/best-llm-for-voice-ai)
- Arabic Prompts with english tools (https://arxiv.org/html/2601.05101v1)
- Best LLMs for voice agents (https://benchlm.ai/best/voice-ai-agents)
- ElevenLabs models reference, language/latency per model (https://elevenlabs.io/docs/models)

