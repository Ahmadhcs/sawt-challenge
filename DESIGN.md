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


## Architecture
 
### Pipeline
 
```mermaid
flowchart LR
    A[Mic or WAV] --> B[Scribe v2 STT]
    B -- text + word confidence --> C[Agent: GPT-4.1]
    C -- tool calls --> D[Tools]
    D --> E[OrderState]
    E --> F[(menu.csv, branches.json, zones.json)]
    D -- result + order summary --> C
    C -- reply text --> G[Flash v2.5 TTS]
    G --> H[Speaker]
```
 
 ## Data
 
**Menu (given).** 144 dishes, 12 categories, 1,728 rows. Each dish spans 8–15 rows, one per option, with the dish-level fields repeated. Two things in the CSV shaped the code:
 
- `item_price_with_option_sar` looks like a final price but only reflects one option at a time. A large pizza with extra cheese needs the base price plus every selected options' deltas, so the code sums them itself.
- Availability is per dish and per branch, while prices are the same at every branch. 111 dishes are available everywhere, the other 33 are missing at one or more branches. This is what makes the location changes after adding items scenario real.
**Branches and delivery zones (mock).** The CSV only covers the menu, so I created:
 
- `branches.json`: the 4 branch IDs from the CSV (3 in Riyadh, 1 in Jeddah), with Arabic names and a pickup prep time.
- `zones.json`: 12 real neighborhoods (8 in Riyadh, 4 in Jeddah), each mapped to a branch with a delivery fee and ETA (20–40 min). Fees and ETAs vary on purpose so changes are visible in the demo. Any location outside these zones gets "we don't deliver there, would you like pickup?"
All money is stored as integer halalas (SAR × 100), makes it easier to avoid floating point rounding errors.

## Order state
 
All order data lives in one `OrderState` object (`src/order_state.py`), split into three groups:
 
- **Inputs**, what the caller told us: service type, delivery zone, pickup branch, and cart lines (item, quantity, size, options, notes).
- **Derived**, what code calculates: branch, delivery fee, ETA, line prices, unavailable lines, subtotal, total.
- **Bookkeeping:** version, read back version, order ID, status.
Five rules keep the order correct:
 
1. **Validate first, then change.** Every change method either rejects the input and changes nothing, or updates the input, increments `version`, and calls `recalculate()`. Validation is menu-aware: the item exists, a required size is given and valid, each option group's min/max selections are respected, and no unknown options slip through.
2. **Rebuild, never patch.** `recalculate()` rebuilds every derived field from the inputs from scratch. Nothing is updated incrementally, so nothing can drift.
3. **Flag, don't delete.** Items the current branch doesn't serve stay in the cart, flagged, so the agent can tell the caller and ask what to do. If no branch is chosen yet, availability is "unknown", not "unavailable".
4. **No math in the LLM.** `summary()` includes ready made SAR strings (`total_sar: "87.50"`) computed in code, so the LLM only ever reads numbers, never computes them.
5. **Safe confirmation.** `get_order_summary()` is the read back and records the current version. `confirm_order()` only succeeds if nothing changed since the read back, the service type and location or branch are set, the cart isn't empty, and nothing is flagged unavailable. Confirming twice returns the same order ID without writing a second record, and every change method refuses once the order is confirmed.

```mermaid
flowchart TD
    A[Tool call] --> B{Input valid?}
    B -- no --> C[Return error, nothing changes]
    B -- yes --> D[Update the input field]
    D --> E[version + 1]
    E --> F["recalculate()"]
    F --> G[Branch, fee, ETA]
    F --> H[Line prices and unavailable flags]
    F --> I[Subtotal and total]
    G --> J[Return result and fresh summary]
    H --> J
    I --> J
```

## Customer journey
 
```mermaid
stateDiagram-v2
    [*] --> Greeting
    Greeting --> ServiceType: wants to order
    Greeting --> Info: menu question
    Info --> ServiceType: decides to order
    ServiceType --> Location: delivery
    ServiceType --> PickupBranch: pickup
    Location --> BuildOrder: zone found (branch, fee, ETA)
    Location --> ServiceType: out of zone, offer pickup
    PickupBranch --> BuildOrder
    BuildOrder --> ReadBack: caller is done
    ReadBack --> Confirmed: clear yes and version matches
    ReadBack --> BuildOrder: change an item
    ReadBack --> Location: change address
    BuildOrder --> ServiceType: switch delivery or pickup
    BuildOrder --> Location: change address
    Confirmed --> [*]
    note right of Greeting: Complaint or human request goes to Transfer from any step
```
 
The steps aren't a fixed script. Nothing in the code directly says "you are now in step 3". The agent looks at what is missing from the order state  and asks for that.

How a read back blocks a stale or duplicate confirmation:
 
```mermaid
sequenceDiagram
    participant C as Caller
    participant A as Agent
    participant O as OrderState
    A->>O: get_order_summary (version 3)
    Note over O: readback_version = 3
    A->>C: reads back the total
    C->>A: "شيل البيبسي"
    A->>O: remove_line (version 4)
    A->>O: confirm_order
    O-->>A: rejected, changed since read-back
    A->>O: get_order_summary
    Note over O: readback_version = 4
    A->>C: reads back the new total
    C->>A: "ايه"
    A->>O: confirm_order
    O-->>A: order 482713
    C->>A: "ايه" again
    A->>O: confirm_order
    O-->>A: same order 482713, no second record
```