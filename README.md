# Context-Aware Interruption Detection for LiveKit Agents

This repository contains the implementation of a context-aware interruption logic for LiveKit Agents. The goal is to distinguish between passive acknowledgements (backchanneling) and active interruptions.

## The Problem
Standard VAD (Voice Activity Detection) is sensitive and interrupts the agent on any user noise. This is undesirable for "filler words" like "yeah", "ok", "hmm", which indicate listening rather than an intent to speak.

## The Solution
We implemented a logic layer within the `AgentActivity` event loop that filters interruptions based on:
1.  **Agent State**: Only active when the agent is speaking.
2.  **Semantic Analysis**: Checks the user's spoken text against a configurable `ignore_words` list.
3.  **STT Validation**: Delays the VAD-triggered interruption until valid Speech-to-Text data confirms the intent, effectively handling "false starts".

## Key Features

1.  **Configurable Ignore List**:
    *   Added `ignore_words` to `AgentSessionOptions`.
    *   Default: `("yeah", "ok", "hmm", "right", "uh-huh", "uh huh")`.
    
2.  **Seamless Continuation**:
    *   If the user says a word in the ignore list, the agent **does not stop**.
    *   The agent does not process the "yeah" as a conversational turn (it is ignored).

3.  **Context-Aware**:
    *   Mixed sentences like "Yeah wait" **DO** interrupt (because "yeah wait" is not in the ignore list).
    *   If the agent is silent, "yeah" is processed normally as a response.

## Implementation Details

### `livekit/agents/voice/agent_session.py`
Modified `AgentSession` and `AgentSessionOptions` to accept a sequence of `ignore_words`.

### `livekit/agents/voice/agent_activity.py`
Modified `_interrupt_by_audio_activity` and `on_end_of_turn`:
*   **_interrupt_by_audio_activity**:
    *   Before interrupting, it checks if `current_transcript` is available.
    *   If transcript is empty (VAD only), it returns (ignores interruption), waiting for STT.
    *   If transcript matches `ignore_words`, it returns (ignores interruption).
*   **on_end_of_turn**:
    *   Checks if the completed turn text matches `ignore_words` while the agent was speaking.
    *   If so, it discards the turn (`returns False`) prevents the LLM from responding to "yeah".

## How to Run

1.  **Install Dependencies**:
    ```bash
    pip install -e .
    ```

2.  **Run an Example Agent**:
    You can run the basic agent to test the logic.
    ```bash
    python examples/voice_agents/basic_agent.py dev
    ```

3.  **Test the Interruption**:
    *   Let the agent speak a long sentence (e.g., ask it to tell a story).
    *   Say "yeah", "ok", "hmm" — **The agent should continue speaking.**
    *   Say "Stop" or "Wait" — **The agent should stop immediately (after STT latency).**
    *   Say "Yeah wait" — **The agent should stop.**

## Configuration

To customize the ignore list in your own agent:

```python
session = AgentSession(
    # ...
    ignore_words=("aye", "correct", "continue"),
)
```

## Original Documentation
See [README_ORIGINAL.md](README_ORIGINAL.md) for the original LiveKit Agents framework documentation.
