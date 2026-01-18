# Changes Implemented

## 1. `AgentSessionOptions` and `AgentSession`
- **File**: `livekit-agents/livekit/agents/voice/agent_session.py`
- **Change**: Added `interruption_speech_filter: list[str]` to `AgentSessionOptions` and `AgentSession.__init__`.
- **Why**: To provide a configurable list of words (e.g., "yeah", "ok", "hmm") that should be ignored by the interruption logic. This allows the user to backchannel without stopping the agent's speech.

## 2. `AgentActivity` Interruption Logic
- **File**: `livekit-agents/livekit/agents/voice/agent_activity.py`
- **Change**: Modified `_interrupt_by_audio_activity` method.
- **Why**: The default behavior was to interrupt immediately upon VAD activity or any STT transcript.
- **How**:
    - The new logic checks if `interruption_speech_filter` is configured.
    - If configured, it ignores VAD-only triggers (empty transcript).
    - When STT transcript is available, it normalizes the text (lowercase, removing punctuation but keeping hyphens).
    - It checks if *all* words in the transcript are present in the `interruption_speech_filter`.
    - If all words are in the filter, the interruption is ignored.
    - If any word is not in the filter (e.g., "Stop"), the agent interrupts immediately.

## 3. Example Agent
- **File**: `examples/voice_agents/interrupt_handler_agent.py`
- **Change**: Created a new example agent.
- **Why**: To demonstrate how to use the `interruption_speech_filter` feature.

## 4. Testing
- **File**: `tests/verify_interruption.py`
- **Change**: Created a unit test script.
- **Why**: To verify the logic correctness without relying on real-time audio streams. It mocks the `AgentActivity` and simulates various scenarios (ignored words, commands, mixed input).
