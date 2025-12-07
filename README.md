# LiveKit Intelligent Interruption Handling

This project solves a major conversational issue in real-time voice agents built with LiveKit.

By default, LiveKit’s Voice Activity Detection (VAD) is highly sensitive. When a user speaks
small acknowledgement words like **"okay"**, **"yeah"**, or **"hmm"** while the agent is
talking, the agent mistakenly treats this as an interruption and stops mid-sentence.

This repository implements a **context-aware interruption handling layer** that preserves
natural conversational flow without modifying any LiveKit internal code.

---

## What Problem Does This Solve?

In real conversations, humans frequently use **backchanneling** to show they are listening:
- "okay"
- "yeah"
- "uh-huh"
- "right"

However, LiveKit’s default behavior interrupts the agent as soon as speech is detected,
even if the speech has no intent to interrupt.

This leads to:
- Broken explanations
- Unnatural stop–start audio
- Poor user experience

---

## Goal of This Solution

The goal is to help the agent understand:
- When the user is **just acknowledging**
- When the user **actually wants to interrupt**

This solution achieves that by using **agent state awareness + semantic STT filtering**.

---

## High-Level Design

The solution adds a logic layer around the Speech-to-Text (STT) system.

Key ideas:
- Do **not** touch the VAD kernel
- Let VAD detect speech normally
- Decide *after transcription* whether the input matters

A custom STT wrapper monitors:
- Agent speaking state
- User transcript content
- Whether the transcript should interrupt, be ignored, or be processed

---

## How the Logic Works

### 1. Tracking Agent State

The agent listens to internal session events:

- `agent_state_changed`

If the agent state changes to:
- `speaking` → filtering is enabled
- `listening` / `idle` → filtering is disabled

Filtering **only applies while the agent is speaking**.

---

### 2. Ignore List (Passive Acknowledgements)

A configurable ignore list is defined:

```python
["yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha"]

## How to Run the Agent

This agent uses:

- **Deepgram** for Speech-to-Text (STT)
- **ElevenLabs** for Text-to-Speech (TTS)
- **OpenAI** for language responses (LLM)

You can run the agent in two modes: **console** mode and **development** mode.

---

### 1. Prerequisites

- Python 3.9 or higher
- A working microphone and speakers/headphones
- The following API keys:
  - OpenAI
  - Deepgram
  - ElevenLabs
  - LiveKit (for `dev` mode)

## Environment Setup

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVEN_API_KEY=your_elevenlabs_api_key

# Required only for dev mode
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_URL=wss://your-livekit-server-url


Install dependencies:

pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
pip install python-dotenv




