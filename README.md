# Context-Aware Interruption Handling for LiveKit Agents

## Overview

This project implements **intelligent interruption handling** for a real-time AI agent.
The goal is to prevent the agent from stopping mid-sentence when the user provides **passive acknowledgements**
like “yeah”, “ok”, or “hmm”, while still allowing **explicit interruption commands** like “stop” or “wait” to
interrupt immediately.

The solution is **context-aware**, distinguishing between user inputs based on whether the agent is
**currently speaking or silent**, without modifying LiveKit’s low-level Voice Activity Detection (VAD).

---

## Problem Statement

LiveKit’s default VAD is highly sensitive.
When the agent is speaking and the user says short filler words such as:
- yeah
- ok
- hmm

the agent incorrectly interprets this as an interruption and stops speaking.

This breaks conversational flow and leads to a poor user experience.

---

## Solution Approach

A **logic layer** is introduced above VAD that determines whether a user input should be ignored,
processed, or treated as an interruption.

Key idea:
> **VAD detects sound, but STT determines intent.**

---

## Core Logic

| User Input | Agent State | Behavior |
|-----------|------------|----------|
| yeah / ok / hmm | Speaking | Ignored |
| stop / wait / no | Speaking | Interrupt |
| yeah / ok | Silent | Respond |
| yeah wait | Speaking | Interrupt |

---

## Key Features

- Configurable ignore list
- State-based filtering
- Semantic interruption detection
- No VAD modification
- Modular and testable logic

---

## Project Structure

agents-assignment/
├── agent.py
├── config.py
├── requirements.txt
└── README.md

---

## Configuration

### config.py

IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha"}
INTERRUPT_WORDS = {"stop", "wait", "no", "cancel", "hold"}

---

## How to Run

```bash
python agent.py
```

### Commands
- /speak   → Agent starts speaking
- /silent  → Agent stops speaking
- /exit    → Quit
- Any other input simulates user speech

---

## 🧪 Example

/speak
yeah
→ IGNORE

/speak
wait
→ INTERRUPT

/silent
yeah
→ RESPOND: yeah

---

## LiveKit Integration

In production, this logic plugs into LiveKit STT and TTS callbacks without modifying VAD.

---

## Conclusion

This project ensures smooth conversational flow by intelligently handling interruptions
based on **context and intent**.
