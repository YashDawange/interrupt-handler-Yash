# LiveKit Intelligent Interruption Handler

## Overview
This project implements a context-aware logic layer for LiveKit Voice Agents. It solves the common issue of "sensitive VAD" by distinguishing between **passive acknowledgements** (backchanneling) and **active interruptions**.

This solution ensures the agent flows naturally during conversation, ignoring filler words like "yeah" or "ok" while the agent is speaking, but responding to them appropriately when the agent is silent.

## Problem Statement
Standard Voice Activity Detection (VAD) is often too sensitive. If a user says "yeah" or "uh-huh" to signal they are listening, the agent interprets this as an interruption and cuts off its audio stream.

**The Goal:** Implement a logic layer that:
1.  **Ignores** backchanneling words when the agent is speaking.
2.  **Respects** true interruptions (commands or mixed sentences).
3.  **Responds** to short words normally when the agent is silent.

## Logic Matrix
[cite_start]This implementation strictly adheres to the required logic matrix[cite: 16]:

| User Input | Agent State | Behavior | Logic Applied |
| :--- | :--- | :--- | :--- |
| **"Yeah / Ok / Hmm"** | **Speaking** | **IGNORE** | Agent continues speaking seamlessly. |
| **"Wait / Stop / No"** | **Speaking** | **INTERRUPT** | Agent stops immediately and processes command. |
| **"Yeah / Ok / Hmm"** | **Silent** | **RESPOND** | Agent treats this as a valid turn (e.g., "Great, let's continue"). |
| **"Start / Hello"** | **Silent** | **RESPOND** | Standard conversational flow. |

## Technical Implementation

### Architecture
The solution is implemented as a standalone module `InterruptionHandler` integrated into the agent's event loop. It relies on **Public APIs** only and does not modify the low-level VAD kernel.

### Handling the VAD/STT Race Condition
A core challenge is that VAD (audio detection) is faster than STT (transcription). The system handles the "false start" where VAD pauses audio before the code realizes the user only said "yeah":

1.  **Interim Transcript Analysis:** The handler monitors `user_input_transcribed` events. If "pure backchanneling" is detected while the agent is speaking, the system flags the turn.
2.  **Turn Clearing:** The system calls `session.clear_user_turn()` to discard the backchanneling input prevents the LLM from processing it.
3.  **False Interruption Resume:** The session is configured with `resume_false_interruption=True`. When the system identifies the input as backchanneling, it triggers a resume event, effectively "un-pausing" the agent's speech with minimal latency.
4.  **Semantic Filtering:** Mixed inputs (e.g., "Yeah wait") are detected via word boundary analysis. If an interruption word is found, the filter is bypassed, allowing the interruption to proceed.

### Configuration
[cite_start]The logic is modular and configurable via environment variables[cite: 37, 78]:

```bash
# Define words to ignore while speaking
export LIVEKIT_BACKCHANNELING_WORDS="yeah,ok,hmm,right,sure,uh-huh"

# Define words that always trigger a stop
export LIVEKIT_INTERRUPTION_WORDS="wait,stop,no,halt,cancel"

###Running the Agent


# Run the intelligent interruption agent
python examples/voice_agents/interruption_handler_agent.py dev

# Run the test suite
python3 tests/run_interruption_tests.py