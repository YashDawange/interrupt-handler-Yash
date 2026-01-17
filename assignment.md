# 🤖 Intelligent Interruption AI Agent

This project features a **real-time AI voice agent** built on the **LiveKit framework**, enhanced to intelligently handle **user backchanneling** (e.g., *"yeah"*, *"ok"*, *"hmm"*).

The core objective is to ensure the agent:

- ✅ Continues speaking seamlessly when a user provides **passive acknowledgements**
- ⛔ Stops immediately for **active interruptions** like *"stop"* or *"wait"*

---

## 🚀 Getting Started

### 1. Environment Configuration

Create a `.env` file in the root directory and add your LiveKit credentials:

```bash
LIVEKIT_URL=<your-project-url>
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-api-secret>
```

---

### 2. Installation

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

---

### 3. Running the Agent

Start the agent in development mode so it automatically joins your LiveKit Sandbox room:

```bash
uv run --active examples/voice_agents/basic_agent.py dev
```

---

## 🧠 Technical Logic & Changes

The implementation introduces a **Semantic Validation Layer** that bridges the gap between:

- ⚡ High-speed **Voice Activity Detection (VAD)**
- 🧾 Accurate **Speech-to-Text (STT)** transcription

This layer ensures that conversational filler words do not prematurely interrupt the agent.

---

## 📂 New Module: `interrupt_handler.py`

This module introduces the `InterruptHandler` class, which manages semantic decision-making.

### Responsibilities

- **State Awareness**  
  Tracks `agent_is_speaking` to apply different logic during active speech versus silent listening.

- **Semantic Filtering**  
  Uses configurable word lists:
  - `IGNORE_WORDS`: `"yeah"`, `"ok"`, `"hmm"`
  - `INTERRUPT_WORDS`: `"stop"`, `"wait"`

- **Decision Matrix**  
  Categorizes transcripts into:
  - `ignore` → Continue speaking
  - `interrupt` → Hard stop
  - `respond` → Normal conversational input

---

## 🛠️ Core Framework Modifications

### `agent_activity.py` — *The VAD Guard*

- Implemented a **HARD BLOCK** on VAD triggers while the agent is speaking.
- When user speech is detected:
  - The agent does **not** stop audio immediately
  - A `pending_ignore` flag is set
  - The system waits for STT results before taking action

---

### `agent_session.py` — *The Decision Resolver*

- Modified `_user_input_transcribed` to resolve pending VAD intents.
- Decision logic uses:
  - Transcript length heuristics
  - Noise detection
  - `InterruptHandler` classification
- Based on the result, the agent:
  - Explicitly **resumes speaking**, or
  - Confirms a **hard interruption**

---

### 🧵 Race Condition Protection

- Added **generation counters** (*Step 3.6*) to prevent:
  - Stale resume signals caused by filler words
  - Interference with new, valid user turns

---

## 🧪 Implementation Verification

The system correctly handles the following logic matrix:

| User Input          | Agent State | Behavior |
|---------------------|-------------|----------|
| "Yeah / Ok / Hmm"   | Speaking    | **IGNORE** → Agent continues speaking |
| "Wait / Stop / No"  | Speaking    | **INTERRUPT** → Agent stops immediately |
| "Yeah / Ok / Hmm"   | Silent      | **RESPOND** → Treated as valid input |

---

## 📹 Proof of Work

```text
https://drive.google.com/file/d/1zrHe1NlLB9OAvRhlvEEM-yyPzl0gs-tk/view?usp=sharing
```

---

## ✅ Summary

This project ensures **natural conversational flow** by combining:

- Voice Activity Detection (VAD)
- Speech-to-Text (STT)
- Semantic intent classification

The result is a **human-like AI voice agent** that understands when to keep talking and when to stop.

