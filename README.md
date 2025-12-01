# Intelligent Interruption Handler for LiveKit Agents

## Submitted by
Atishay Jain

## Overview

This project implements an advanced logic layer to achieve human-like, context-aware interruption handling for a LiveKit voice agent. The system successfully distinguishes between passive feedback (backchannels) and active interruption commands, adapting its behavior based on the agent's current speaking state.

The core challenge—achieving a **guaranteed, silent HARD STOP**—was solved by engineering a custom internal patch that overcomes the default asynchronous behavior of the LiveKit SDK (v1.3.x).

---

## Implementation Logic Matrix

| Behavior | Agent State | User Input Type | Action Taken |
| :--- | :--- | :--- | :--- |
| **Seamless Ignore** | **Speaking** | Backchannel (e.g., "yeah", "ok", "hmm") | Continues audio **without pausing or restarting**. |
| **HARD STOP** | **Speaking** | Interruption (e.g., "stop", "wait", "no") or Normal Input | **Stops instantly** (`interrupt(force=True)`) and **generates no verbal reply.** |
| **Normal Respond** | **Silent** | Any Input (including backchannels) | Message is processed by the LLM, and the agent replies normally. |

---

## Technical Solution: The Dropper Hook

To ensure the "NO reply" requirement is strictly met during a HARD STOP, the default message flow had to be intercepted and suppressed:

1.  **Targeted Patching:** The `AdvancedInterruptionHandler` successfully patches the internal LiveKit method `_user_input_transcribed`, which is responsible for committing the final user transcript to the LLM.
2.  **Guaranteed Suppression:** When a HARD STOP is triggered, a flag (`self._drop_next_user_msg`) is set. The patched method reads this flag and returns immediately, preventing the user's transcript from ever reaching the conversation history or the Groq LLM.
3.  **Stability Fixes:** The patch uses a **synchronous wrapper** (`sync_wrapper`) with `asyncio.create_task` and the **`inspect.isawaitable`** check to overcome timing issues and API compatibility challenges in the SDK, ensuring the dropper works without generating `RuntimeWarning` or `TypeError` errors.
4.  **Seamless Resume:** For backchannels while speaking, the code explicitly calls `session.resume_interrupted_speech()` to quickly restart the agent's interrupted audio stream, achieving a virtually imperceptible pause.
5.  **Clean Session:** The session is configured with `resume_false_interruption=False` to disable LiveKit's default attempt to generate cleanup replies, giving full control to the custom handler.

---

## How to Run

1.  **Prerequisites:** Ensure all required libraries (LiveKit Agents, Groq, AssemblyAI, Cartesia, Silero) are installed and environment variables (`.env` file) are configured.
2.  **Execution:** Run the agent using the LiveKit CLI console mode:

    ```bash
    python <path/to/intelligent_interruption_agent.py> console
    ```

3.  **Testing Scenarios:**
    * **Test 1 (Seamless Ignore):** Let the agent speak its long greeting. Say "yeah... ok" during the speech. **Result:** The agent must continue speaking.
    * **Test 2 (HARD STOP):** While the agent is speaking, say "Stop" or "Hold on." **Result:** The agent must cut off immediately and remain silent.
    * **Test 3 (Normal Respond):** Wait until the agent is silent. Say "Yeah." **Result:** The agent must reply to the acknowledgement (e.g., "Great, let's continue").