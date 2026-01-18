# Project Structure and Workflow

This document outlines the key components of the `livekit-agents` repository involved in voice interaction and how the new interruption handling fits in.

## Key Files

### `livekit-agents/livekit/agents/voice/`

*   **`agent_session.py`**:
    *   **Role**: Manages the session configuration, connection to LiveKit, and the `Agent` instance.
    *   **Change**: Added `interruption_speech_filter` to options.
*   **`agent_activity.py`**:
    *   **Role**: The core logic engine. It handles the "activity" of an agent (speaking, listening, thinking). It coordinates VAD, STT, and TTS tasks.
    *   **Change**: Modified `_interrupt_by_audio_activity` to implement the filter logic.
*   **`audio_recognition.py`**:
    *   **Role**: Manages the STT and VAD streams. It processes raw audio frames and emits events like `final_transcript` or `start_of_speech`.
    *   **Interaction**: It calls hooks on `AgentActivity` (e.g., `on_final_transcript`), which then calls `_interrupt_by_audio_activity`.

## Workflow: Interruption Handling

1.  **User Speaks**:
    *   `vad_task` in `audio_recognition.py` detects speech start.
    *   Calls `AgentActivity.on_start_of_speech`.

2.  **VAD Trigger**:
    *   `vad_task` detects sufficient speech duration.
    *   Calls `AgentActivity.on_vad_inference_done`.
    *   Calls `_interrupt_by_audio_activity()`.
    *   **New Logic**: If `interruption_speech_filter` is enabled and transcript is empty, `_interrupt_by_audio_activity` returns early. **No Interruption yet.**

3.  **STT Update**:
    *   `stt_task` receives audio and returns transcript (interim or final).
    *   Calls `AgentActivity.on_interim_transcript` / `on_final_transcript`.
    *   Calls `_interrupt_by_audio_activity()`.
    *   **New Logic**:
        *   Get `current_transcript` (e.g., "Yeah").
        *   Normalize: "yeah".
        *   Check against filter: `["yeah", "ok"]`.
        *   Match found -> Return. **No Interruption.** Agent continues speaking.

4.  **Command Handling**:
    *   User says "Stop".
    *   STT returns "Stop".
    *   Check against filter: "stop" not in `["yeah", "ok"]`.
    *   **Result**: Interrupt! Calls `self._current_speech.interrupt()`.

5.  **Silent State**:
    *   Agent is not speaking (`_current_speech` is None).
    *   User says "Yeah".
    *   `_interrupt_by_audio_activity` logic doesn't matter (nothing to interrupt).
    *   Turn detection proceeds normally via `on_end_of_speech` -> `on_end_of_turn` -> `Agent.on_user_turn_completed`.
    *   Agent responds to "Yeah".
