# SalesCode.ai Assessment: LiveKit - A powerful framework for building realtime voice AI agents

This repository contains my implementation of a **filler-aware, interruption-safe voice assistant** built using the **LiveKit Agents** framework.  
The goal of this work was to create a more natural and intelligent voice interaction system that understands the difference between *filler noise* and *real user interruptions* — something real conversational AI systems must handle correctly.

I have demonstrated my work in examples/voice_agents/basic_agent.py.

---
## Problem Statement

LiveKit’s default Voice Activity Detection (VAD) is highly sensitive.  
When a user says short backchannel words like "yeah", "ok", or "hmm" while the agent is speaking, the agent incorrectly treats them as interruptions and stops mid-sentence.

This results in a poor conversational experience during long explanations.
## Solution Summary

This solution introduces a semantic interruption filter based on:
- Agent speaking state
- Speech-to-text transcription
- Keyword-based intent detection

The low-level VAD is not modified.  
All logic is implemented inside the agent’s event loop.
## Core Logic Matrix

| User Input | Agent State | Behavior |
|-----------|------------|----------|
| yeah / ok / hmm | Speaking | IGNORE |
| stop / wait / no | Speaking | INTERRUPT |
| yeah / ok | Silent | RESPOND |
| hello / start | Silent | RESPOND |
| yeah wait | Speaking | INTERRUPT |

## How It Works

### Agent State Awareness

The agent tracks whether it is speaking using `AgentStateChangedEvent`.

Filtering logic is applied only when the agent is actively speaking.

### Manual Interruption Control

Automatic VAD-based interruptions are effectively disabled by increasing the interruption thresholds.

This ensures the agent is not interrupted before transcript-based validation occurs.
### Transcript-Based Interruption Decision

Interruption decisions are handled inside the `user_input_transcribed` event.

Only interim transcripts are evaluated while the agent is speaking, ensuring real-time behavior without stutter.
### Semantic Filtering Logic

The interruption logic classifies user speech into:
- Passive acknowledgements (ignored while speaking)
- Explicit commands (interrupt immediately)

Ignored filler words include:
uh, umm, hmm, haan, um, ah, er, like, yeah, mhm, mm, mhmm, uh-huh

Command words include:
stop, wait, holdon

Mixed inputs such as "yeah wait a second" correctly trigger an interruption.
## Example Scenarios

**Scenario 1: Passive Listening**  
User says "yeah… ok… uh-huh" while the agent is speaking  
→ Agent continues speaking without interruption

**Scenario 2: Silent Confirmation**  
Agent is silent, user says "yeah"  
→ Agent responds normally

**Scenario 3: Correction**  
User says "no stop" while the agent is speaking  
→ Agent stops immediately

**Scenario 4: Mixed Input**  
User says "yeah okay but wait"  
→ Agent interrupts
## Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

DEEPGRAM_API_KEY=

OPENAI_API_KEY=

CARTESIA_API_KEY=

LIVEKIT_REMOTE_INFERENCE_URL=


```





## Installation

This project uses `uv` for dependency management.

Install dependencies using the lockfile:

```bash
uv sync
```

---




## Running the Agent

After installing dependencies and configuring the `.env` file, run:

```bash
python examples/voice_agents/basic_agent.py console
```

---




## Configuration

The interruption behavior can be customized by modifying:
- Ignored filler words
- Command (stop) words

All logic is centralized inside the interruption decision function.

## Proof of Correctness

Logs demonstrate:
- Passive acknowledgements are ignored while the agent is speaking
- Explicit commands interrupt immediately
- Short confirmations are processed when the agent is silent

## Compliance Checklist

| Requirement | Status |
|------------|--------|
Ignore filler words while speaking | ✅ |
Interrupt on semantic commands | ✅ |
Respond when silent | ✅ |
No VAD modification | ✅ |
Real-time behavior | ✅ |
Configurable logic | ✅ |
## Conclusion

This implementation provides a clean, modular, and real-time solution to intelligent interruption handling, ensuring natural conversational flow without sacrificing responsiveness.
