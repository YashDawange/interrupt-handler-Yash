# 🚀 Intelligent Interruption Handler for LiveKit Agents

This project implements a **custom intelligent interruption handler** for LiveKit Voice Agents.

Unlike standard Voice Activity Detection (VAD) which interrupts on any sound, this agent intelligently distinguishes between **passive backchannels** (active listening) and **active commands** (intent to speak). This creates a more natural, human-like conversation flow where the user can say "uh-huh" or "right" without cutting off the agent, but can still interrupt immediately with "stop" or "wait".

---

## 🧠 The Logic Matrix

The handler makes decisions based on **what** the user says and **when** they say it:

| User Says... | Agent State | Action Taken | Result |
| :--- | :--- | :--- | :--- |
| **"Yeah / Ok / Hmm"** | 🗣️ **Speaking** | 🔇 **IGNORE** | Agent continues speaking uninterrupted. |
| **"Stop / Wait / No"** | 🗣️ **Speaking** | 🛑 **INTERRUPT** | Agent stops immediately. |
| **"Yeah / Ok / Hmm"** | 😶 **Silent** | ✅ **RESPOND** | Treated as confirmation/acknowledgment. |
| **"Yeah wait..."** | 🗣️ **Speaking** | 🛑 **INTERRUPT** | Compound phrases with commands trigger interruption. |

---

## ✨ Key Features

### 1. Passive Backchannel Filtering
Common active listening cues are filtered out while the agent is speaking.
* **Words:** `yeah`, `ok`, `okay`, `hmm`, `uh-huh`, `right`, `sure`, `yep`, `gotcha`
* **Behavior:** The user can verbally nod along without disrupting the agent's flow.

### 2. Instant Command Interruption
Specific command words trigger an immediate hard stop, utilizing partial transcripts for low latency.
* **Words:** `stop`, `wait`, `hold`, `pause`, `no`, `cancel`, `enough`
* **Behavior:** The agent halts mid-sentence and clears the audio queue.

### 3. Context-Aware Responses
If the agent is **not** speaking (waiting for user input), backchannels like "sure" or "ok" are treated as valid answers to confirm a prompt or continue the dialogue.

---

## 🛠️ Technical Implementation

This solution disables the default indiscriminate interruption policy (`allow_interruptions=False`) and injects a custom logic layer:

### `BackchannelInterruptionHandler`
Located in [`backchannel_handler.py`](./examples/voice_agents/backchannel_handler.py), this class:
1.  **Monitors Transcripts:** Listens to `user_input_transcribed` events.
2.  **Tracks State:** Monitors `agent_state_changed` to know if the agent is `speaking`, `listening`, or `processing`.
3.  **Enforces Logic:**
    * If a **Command** is detected → Calls `session.interrupt(force=True)` and `session.clear_user_turn()`.
    * If a **Backchannel** is detected while speaking → Swallows the event to prevent LLM processing.

### Configuration
In [`basic_agent.py`](./examples/voice_agents/basic_agent.py), the session is initialized with strict controls to allow the handler to take over:

```python
session = AgentSession(
    ...
    allow_interruptions=False,          # Disable built-in auto-interrupt
    discard_audio_if_uninterruptible=False,
    false_interruption_timeout=None,    # Disable auto-resume logic
    resume_false_interruption=False,
)