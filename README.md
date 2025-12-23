## LiveKit Intelligent Interruption Handler

**Context-Aware Voice Agent with Manual Orchestration**

This project implements a **robust, low-latency interruption handling system** for LiveKit voice agents.
It solves the classic **“false interruption” problem**, where passive listener acknowledgements like **“yeah”* or *“ok”** incorrectly stop the agent mid-sentence.

Instead of relying on default VAD or library-level heuristics, this solution introduces a **Manual Orchestrator** that explicitly reasons about **user intent**, **agent speaking state**, and **semantic meaning of utterances**.

## The Problem

LiveKit’s default interruption behavior is overly sensitive:

* While the agent is speaking…

  * User says **“yeah”** →  agent stops
  * User says **“uh-huh”** →  agent stops
* These are **not interruptions**, they are **backchanneling cues**.

This leads to:

* Broken sentences
* Poor conversational flow
* Unnatural user experience

## The Solution: Manual Orchestrator Pattern

This agent intercepts **speech-to-text events before they reach the LLM**, applies intent classification, and only interrupts when the user **explicitly commands it**.

## Core Principle

> **Interruptions are a semantic decision, not a signal-level decision.**

## Interruption State Matrix

| User Input              | Agent State | Action           | Reason               |
| ----------------------- | ----------- | ---------------- | -------------------- |
| “yeah”, “ok”, “uh-huh”  | Speaking    | **IGNORE**       | Passive listening    |
| “stop”, “wait”, “pause” | Speaking    | **INTERRUPT**    | Explicit command     |
| “yeah”, “ok”            | Silent      | **RESPOND**      | Valid turn           |
| Any normal query        | Silent      | **RESPOND**      | Standard interaction |

## Key Technical Features

### 1. Manual Orchestration (Bypassing Default LLM Flow)

* Speech is intercepted **before** LLM generation
* Prevents false positives from **VAD / STT noise**
* Gives full control over interruption logic

### 2. Dual-Vocabulary Intent Detection

**```python**
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "mhmm", "uh-huh",
    "right", "sure", "yes", "yep", "i see", "go on"
}

STOP_WORDS = {
    "stop", "wait", "hold on", "cancel", "pause",
    "shut up", "quit", "silence", "enough"
}
**```**

* Soft acknowledgements are ignored **only while speaking**
* Hard commands **immediately terminate audio + generation**

### 3. Instant Audio Cut-Off (Zero Latency)

On hard interrupt:

* Ongoing LLM streaming task is **cancelled**
* Audio buffer is **cleared**
* No delayed or trailing speech

**```python**
self.interrupt_flag.set()
self.current_response_task.cancel()
**```**

### 4. Mixed-Intent Detection (Critical Edge Case)

Handles sentences like:

> “Yeah… wait a second”

Because the cleaned input does **not match IGNORE_WORDS**, it is treated as a **hard interrupt**.

✔ Prevents partial sentence continuation
✔ Matches real human intent

### 5. Streaming-Safe TTS Playback

* LLM responses are streamed token-by-token
* Speech is synthesized **sentence-wise**
* Interrupts can occur **mid-sentence or mid-audio**

**```python**
if self.interrupt_flag.is_set():
    break
**```**

## Architecture Overview

Microphone
   ↓
Deepgram STT (Streaming)
   ↓
Manual Orchestrator
   ├─ IGNORE → Do nothing
   ├─ STOP   → Cancel + Clear audio
   └─ VALID  → Send to LLM
               ↓
          Groq LLM (Streaming)
               ↓
          Deepgram TTS
               ↓
           LiveKit Audio Track

##  Tech Stack

| Component               | Purpose                      |
| ----------------------- | ---------------------------- |
| LiveKit                 | Real-time audio transport    |
| Deepgram STT            | Streaming speech recognition |
| Deepgram TTS            | Low-latency speech synthesis |
| Silero VAD              | Voice activity detection     |
| Groq LLM (LLaMA-3.1-8B) | Fast streaming responses     |
| asyncio                 | Precise task cancellation    |

##  How to Run

### 1. Install dependencies

**```bash**
pip install livekit-agents deepgram-sdk silero-vad python-dotenv openai
**```**

### 2. Set environment variables

**```env**
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
GROQ_API_KEY=...
DEEPGRAM_API_KEY=...
**```**

### 3. Start the agent

**```bash**
python manual_agent.py dev
**```**

## How to Test the Interruption Logic

1. Let the agent start speaking
2. Say:

   * **“yeah”** → agent continues 
   * **“ok”** → agent continues 
   * **“stop”** → agent stops instantly 
   * **“yeah wait”** → agent stops 
3. Stay silent → agent waits
4. Ask a question → agent responds

##  Why This Solution Is Correct

✔ Does **not** rely on fragile VAD thresholds
✔ Distinguishes **intent**, not volume
✔ Works with **any LLM provider**
✔ Handles **real human conversational behavior**
✔ Zero-latency interruption
✔ Production-safe task cancellation




