# Intelligent Interruption Handling for LiveKit Agents

## Overview

This project implements a **context-aware interruption handling logic** for a LiveKit voice agent.  
The goal is to prevent the agent from being interrupted by **passive acknowledgements**
(e.g., “yeah”, “ok”, “hmm”) while it is speaking, while still allowing **explicit commands**
(e.g., “stop”, “wait”, “no”) to interrupt immediately.

The solution is implemented as a **logic layer** based on agent state and user transcript
semantics. No changes are made to LiveKit’s low-level VAD implementation.

---

## Problem Statement

LiveKit’s default Voice Activity Detection (VAD) reacts to any detected sound.
As a result, when a user says short filler words like “yeah” or “ok” while the agent is
speaking, the agent incorrectly interprets this as an interruption and stops speaking.

This leads to a poor conversational experience.

---

## Solution Approach

A **state-aware logic layer** is introduced that classifies user input based on:

1. **Agent Speaking State**
   - Whether the agent is currently speaking or silent
2. **Semantic Meaning of User Transcript**
   - Passive acknowledgements vs. active interruption commands

This logic determines whether the agent should:
- Ignore the input
- Interrupt immediately
- Respond normally

---

## Core Logic

The core logic is implemented in the function:

```python
classify_user_input(text: str, agent_is_speaking: bool) -> str
# Context-Aware Semantic Interruption Handling for Voice Agents

This project implements **context-aware interruption logic** for voice agents, ensuring that user utterances like *"yeah"* or *"wait"* are handled correctly depending on whether the agent is currently speaking or silent.

The solution is designed to be **modular, readable, and production-ready**, and can be directly integrated into a LiveKit-based voice agent system.

---

## 📌 Problem Overview

In voice-based AI systems, **not all user speech should interrupt the agent**.

For example:
- A passive acknowledgment like *"yeah"* while the agent is speaking should **not** stop the agent.
- A command like *"stop"* or *"wait"* should **immediately interrupt** the agent.
- The same word can mean different things depending on **context**.

This project addresses that challenge.

---

## 🧠 Decision Rules

| Agent State | User Input        | Action     |
|------------|-------------------|------------|
| Speaking   | "yeah", "ok"      | IGNORE     |
| Speaking   | "yeah wait"       | INTERRUPT  |
| Speaking   | "stop", "wait"    | INTERRUPT  |
| Silent    | "yeah"            | RESPOND    |
| Silent    | "hello"           | RESPOND    |

🔹 This ensures the **same input** (e.g., *"yeah"*) is handled **differently depending on context**.

---

## 🧩 Semantic Interruption Handling

Mixed inputs such as:yeah wait

are correctly classified as **INTERRUPT**, because:
- They contain a **semantic command** (`wait`)
- Even though they also include filler words (`yeah`)

This allows the system to behave naturally, similar to human conversations.

---

## 🔌 Integration with LiveKit (Conceptual)

In a full LiveKit runtime environment, this logic would be invoked:

- **After receiving the STT transcript**
- **Before allowing any VAD-triggered interruption** to cancel agent audio

### Based on the classification result:

- **IGNORE** → Agent continues speaking seamlessly  
- **INTERRUPT** → Agent speech stops immediately  
- **RESPOND** → Normal conversational flow  

The logic is intentionally **isolated and modular**, making it easy to plug into the agent’s event loop.

---

## 🧪 Testing & Validation

Running a full voice agent requires **paid APIs** (STT, LLM, TTS).

To avoid this, the solution was validated using a **logic-only simulation**.

### Example Output
text='yeah', speaking=True -> IGNORE
text='yeah wait', speaking=True -> INTERRUPT
text='yeah', speaking=False -> RESPOND
text='stop', speaking=True -> INTERRUPT

## 📁 File Structure
examples/
└── voice_agents/
├── basic_agent.py
└── interrupt_handler_agent.py

