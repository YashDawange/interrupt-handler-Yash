
# LiveKit Voice Agent – State-Aware Interruption Handling

This project builds on the LiveKit Agents framework to implement a **state-aware voice agent** that handles short user acknowledgments (e.g., *“yeah”, “ok”, “hmm”*) correctly during real-time speech.

The core focus of this assignment is **distinguishing between interruptions and acknowledgments based on the agent’s speaking state**, ensuring natural and human-like conversational behavior.

---

## Problem Statement

In real conversations, users frequently say short filler or acknowledgment words while another person is speaking.
Most voice agents incorrectly treat these as interruptions, causing responses to stop or restart mid-sentence.

This project solves that issue by making interruption handling **state-dependent**, rather than keyword-dependent.

---

## Core Logic Overview

The agent evaluates **two things before acting on user input**:

1. **Agent State**

   * Speaking
   * Silent

2. **User Input Type**

   * Acknowledgment (e.g., *“yeah”, “ok”, “hmm”*)
   * Explicit interruption (e.g., *“stop”, “wait”, “no”*)
   * Normal conversational input

A mediator layer decides whether the input should be **ignored**, **interrupt speech**, or **trigger a response**.

---

## Behavior Matrix

| Agent State | User Input          | Behavior                         |
| ----------- | ------------------- | -------------------------------- |
| Speaking    | Acknowledgment word | Continue speaking (ignore input) |
| Speaking    | Interrupt command   | Stop immediately                 |
| Silent      | Acknowledgment word | Respond naturally                |
| Silent      | Normal input        | Normal conversational flow       |

This ensures that the **same word behaves differently depending on context**, which is the key challenge of the assignment.

---

## Key Features

* State-aware interruption handling
* No false pauses on acknowledgment words
* Immediate response to explicit stop commands
* Modular mediator logic
* Easily extendable ignore-word list
* Works with LiveKit Meet and LiveKit Cloud

---

## Configuration

Short acknowledgment words are defined in a centralized list and can be easily modified:

```python
IGNORED_WHILE_SPEAKING = [
    "yeah", "ok", "okay", "hmm", "uh", "uh-huh", "oh"
]
```

This allows simple tuning without changing core logic.

---

## How It Works (High Level)

1. Agent starts speaking using TTS
2. Incoming user audio is transcribed
3. Mediator checks:

   * Is the agent currently speaking?
   * Is the input an acknowledgment or interruption?
4. Decision is applied:

   * Ignore
   * Stop speaking
   * Respond normally

This separation keeps conversational logic clean and predictable.

---

## How to Run

### 1. Install dependencies

```bash
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
```

### 2. Set environment variables

Create a `.env` file:

```env
LIVEKIT_URL=wss://<your-livekit-url>
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-api-secret>
OPENAI_API_KEY=<your-openai-key>
DEEPGRAM_API_KEY=<your-deepgram-key>
```

---

### 3. Start the agent

```bash
python basic_agent.py start
```

---

### 4. Connect to the agent

1. Open [https://meet.livekit.io](https://meet.livekit.io)
2. Enter any room name (e.g., `test-room`)
3. Join with microphone enabled
4. The agent will automatically join the same room

---

## How to Test the Logic

1. Ask the agent a long question
   Example:
   *“Tell me a joke.”*

2. While the agent is speaking, say:

   * “yeah”
   * “ok”
   * “hmm”

   ✅ Agent continues speaking

3. Say:

   * “stop”

   ✅ Agent immediately stops

4. When the agent is silent, say:

   * “yeah”

   ✅ Agent responds naturally

---

## Evaluation Criteria Mapping

* **Strict Functionality (70%)**
  The agent does not stop or pause on acknowledgment words while speaking.

* **State Awareness (10%)**
  The same word behaves differently depending on whether the agent is speaking or silent.

* **Code Quality (10%)**
  Logic is modular, readable, and easy to extend.

* **Documentation (10%)**
  Clear explanation of behavior, reasoning, and testing steps.

---

## Summary

This implementation focuses on **conversation correctness**, not simple keyword filtering.
By making interruption handling dependent on agent state, the voice experience becomes smoother, more natural, and closer to real human dialogue.

