# Intelligent Interruption Handling for LiveKit Agents

This repository implements a **context-aware interruption handling layer** on top of LiveKit Agents, addressing a key limitation in default Voice Activity Detection (VAD): false interruptions caused by user backchanneling (e.g., “yeah”, “ok”, “hmm”) while the agent is speaking.

The solution is designed specifically to satisfy the **LiveKit Intelligent Interruption Handling Assignment** requirements and is implemented entirely at the **agent logic layer**, without modifying LiveKit’s low-level VAD.



## Problem Summary

LiveKit’s default VAD is highly sensitive. When a user says short acknowledgement words like:

* “yeah”
* “ok”
* “hmm”

while the agent is explaining something, the agent incorrectly interprets this as an interruption and **stops speaking mid-sentence**.

This leads to:

* Broken conversational flow
* Unnatural user experience
* Frustrating interruptions during long responses

---

## Goal

Introduce a **context-aware logic layer** that allows the agent to:

* **Ignore passive acknowledgements** when the agent is speaking
* **Immediately stop** when the user gives a real interrupt command
* **Correctly respond** to short answers when the agent is silent

---

## High-Level Solution

Instead of reacting only to audio activity, the agent now reasons about **what the user said** and **when they said it**.

The solution introduces three concepts:

### 1. Intent Classification

User transcripts are classified into simple semantic intents:

* **BACKCHANNEL** → acknowledgements like “yeah”, “ok”, “hmm”
* **INTERRUPT** → commands like “stop”, “wait”, “pause”
* **OTHER** → all other speech

This is done using lightweight text normalization and hash-set lookups (O(1)).

---

### 2. Conversation Context

Decisions are made using context, including:

* Whether the agent is currently speaking
* Whether the transcript is interim or final
* Previous user intent (for future extensibility)

This ensures that the **same word** (e.g., “yeah”) is treated differently depending on agent state.

---

### 3. Context-Aware Policy

A policy layer decides what action to take:

* **IGNORE** → clear the user turn (do not interrupt)
* **INTERRUPT** → immediately stop the agent
* **PASS** → let LiveKit handle normally

This keeps the behavior deterministic, debuggable, and easy to extend.

---

## Modular Design

The logic is split into focused, reusable modules:

```
interrupt_handler/
├── interrupt_words.py          # Configurable ignore & interrupt word lists
├── intent_controller.py        # Stateless intent classification
├── context.py                  # Conversation context object
├── interruption_policy.py      # Context-aware decision rules
└── voice_interrupt_controller.py # Glue layer used by the agent
```

---

## How the Logic Works (Step-by-Step)

1. The agent begins speaking.
2. The user says something.
3. STT emits an interim or final transcript.
4. The transcript is normalized (lowercased, punctuation removed).
5. The text is classified into an intent.
6. The policy evaluates intent + agent state.
7. One of three actions is applied:

   * IGNORE → agent continues speaking
   * INTERRUPT → agent stops immediately
   * PASS → normal LiveKit behavior

This approach prevents false interruptions while keeping true interruptions responsive.

---

## Configurable Ignore & Interrupt Lists

All acknowledgement and interrupt words are defined in one place:

**File:** `interrupt_handler/interrupt_words.py`

```python
IGNORE_WORDS = [
    "ok", "okay", "yeah", "yep", "hmm", "mhm",
    "right", "sure", "got it", "i see"
]

INTERRUPT_WORDS = [
    "stop", "wait", "pause", "hold on",
    "hang on", "never mind", "actually"
]
```

These lists are normalized once and stored in sets for fast lookup.

---

## LiveKit Integration

The solution integrates cleanly with LiveKit’s existing event system:

* `agent_state_changed` → updates speaking state
* `user_input_transcribed` → applies intent + policy logic


---


## Edge Cases Covered

* Punctuation variants: “ok!!!”, “…yeah…”
* Mixed inputs: “yeah okay but wait” → INTERRUPT
* Interim vs final transcripts
* Empty or whitespace-only speech

All required assignment scenarios are handled correctly.

---

## Performance & Latency

* Constant-time checks (O(1))
* No noticeable latency
* Fully real-time compatible

---

## How to Run Locally

1. Install dependencies (inside a virtual environment):

```bash
pip install -e .[dev]
```

or

```bash
uv sync
```

2. Configure API keys in `.env`.

LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=wss://your-livekit-server
DEEPGRAM_API_KEY=your_deepgram_api_key
GEMINI_API_KEY=your_groq_api_key
CARTESIA_API_KEY=your_cartesia_api_key

3. Run the agent:

```bash
python basic_agent.py
```

4. Connect via the LiveKit Agents Playground and test:

* Say “ok / yeah” while agent is speaking → agent continues
* Say “stop / wait” while agent is speaking → agent stops
* Say “yeah” when agent is silent → agent responds

---

-
