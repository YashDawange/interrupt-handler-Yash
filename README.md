

# Intelligent Interruption Handling Agent

## Overview

This project was created for the LiveKit Intelligent Interruption Handling Challenge. The objective was to improve the conversational experience of a real-time voice agent by preventing unintended interruptions caused by natural backchannel cues.

Many Voice Activity Detection (VAD) systems mistake filler words such as "yeah" or "okay" as user attempts to interrupt. This results in the agent stopping mid-sentence even when the user is simply acknowledging.
To address this, a context-aware interruption layer was designed to distinguish between genuine interruptions and passive listener feedback.

---

## Problem

LiveKit’s default interruption behavior activates whenever VAD or STT detects user speech. This is often too sensitive. Natural listener cues such as short acknowledgements or filler words are misinterpreted as interruptions.

This leads to abrupt, unnatural conversational flow and disrupts the agent’s response generation.

---

## Solution

A context-driven filtering layer was developed to identify the intent behind the user’s input during agent speech.

The system separates:

* **Active Interruptions**: Commands like "stop", "wait", "repeat", which should stop the agent.
* **Passive Acknowledgements**: Backchannel cues like "yeah", "mhmm", "okay", which should not interrupt the agent.

This ensures that the agent only stops when the user actually intends to interrupt.

---

## Features

### 1. Smart Interruption Logic

The agent filters out specific filler words while speaking, preventing unnecessary cutoff.

### 2. State-Aware Processing

The handling logic depends on agent state:

* When the agent is silent, all user inputs are processed normally.
* When the agent is speaking, only meaningful user inputs can interrupt.

### 3. Configurable Ignore List

The ignored backchannel words are passed dynamically to the session and can be updated without modifying internal logic.

---

## Technical Implementation

### 1. Session Configuration

Defined an `IGNORE_WORDS` set inside `examples/voice_agents/basic_agent.py`:

```python
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "mhmm", "aha", "uh-huh", "right",
    "sure", "yep", "yup", "cool", "gotcha", "i see", "yo"
}
```

These words are passed to the agent session through the `userdata` parameter.

---

### 2. Logic Layer

Implemented in:

```
livekit-agents/.../agent_activity.py
```

Modified the method:

```
_interrupt_by_audio_activity
```

**Logic Flow**

1. Detect audio via VAD or STT transcript.
2. Check if agent is speaking or listening.
3. If speaking:

   * If VAD fires but STT text is not available yet, wait to avoid false positives.
   * Clean and normalize the transcript.
   * If the transcript matches an item in `IGNORE_WORDS`, block the interruption.
   * Otherwise, allow interruption.
4. If listening, process normally.

This approach ensures only intentional user interventions break the agent’s speech.

---

## How to Run

### Install Dependencies

```
pip install -r examples/voice_agents/requirements.txt
```

### Environment Setup

Create a `.env` file in `examples/voice_agents/`:

```
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

### Start the Agent

```
python examples/voice_agents/basic_agent.py dev
```

---

## Verification

The following scenarios were tested:

| Scenario   | Agent State | User Input  | Result            | Explanation            |
| ---------- | ----------- | ----------- | ----------------- | ---------------------- |
| Ignore     | Speaking    | "Yeah"      | Continues         | Word is in ignore list |
| Respond    | Silent      | "Yeah"      | Responds normally | Agent listening        |
| Correction | Speaking    | "Stop"      | Interrupts        | Not in ignore list     |
| Mixed      | Speaking    | "Yeah wait" | Interrupts        | Phrase not ignored     |

Logs confirming these outcomes are included in the proof file.

---

## Proof of Work

See `proof_of_work.txt` for terminal logs demonstrating correct behavior for all scenarios.

---
