# Interrupt Handling Assignment

## Overview
This submission improves agent interruption handling by validating user input
at the **final STT transcript stage**. The goal is to ensure that soft
acknowledgements such as **"yeah"** or **"ok"** do **not** interrupt the agent
while it is speaking, while still allowing valid responses and hard interrupts
when appropriate.

The change specifically addresses edge cases where Voice Activity Detection
(VAD) may fail to emit interruption signals during intermediate speech.

---

## Files Modified

### 1. `speech_handle.py`

This file manages the lifecycle and state of agent speech playback.

**What was changed**
- Added support for validating a **pending interrupt** when a final STT
  transcript is received.
- Ensures that interruption decisions are not lost when speech recognition
  completes after VAD has failed to trigger.

**Why this matters**
`speech_handle.py` is the source of truth for whether the agent is currently
speaking and whether it is safe to interrupt ongoing speech.

---

### 2. `agent_activity.py`

This file coordinates STT, VAD, and agent speech behavior.

**What was changed**
- Updated the final STT transcript handling flow to re-evaluate interruption
  conditions.
- When the agent is speaking:
  - Soft acknowledgements (e.g. "yeah", "ok") are ignored.
  - Hard interrupts (e.g. "stop") immediately cancel speech.
- When the agent is silent:
  - Short acknowledgements are treated as valid input.
- The list of soft acknowledgement words is configurable via the
  `AGENT_SOFT_ACK_WORDS` environment variable.

**Why this matters**
`agent_activity.py` determines whether user input should affect the agent based
on the agent’s current speaking state.

---

## Expected Behavior

| Scenario | Result |
|--------|--------|
| User says "yeah" while agent is speaking | Ignored |
| User says "yeah" while agent is silent | Processed as valid input |
| User says "stop" while agent is speaking | Agent stops immediately |
| User says "yeah okay but wait" | Agent interrupts |

---

## How the Logic Works

1. The agent begins speaking and a `SpeechHandle` is created.
2. User audio is processed through STT and VAD.
3. If VAD fails to emit an interruption during speech:
   - The **final STT transcript** is still received.
4. In `agent_activity.py`, the final transcript is evaluated:
   - If the agent is speaking and the transcript is a soft acknowledgement
     (as defined in `AGENT_SOFT_ACK_WORDS`), the input is ignored.
   - Otherwise, the transcript is treated as a valid interrupt or response.
5. `speech_handle.py` finalizes whether the speech should continue or be
   cancelled.

This ensures that interruptions are handled correctly even in VAD edge cases.

---

## How to Run (Execution Context)

This repository does **not** provide a standalone entrypoint.

The agent logic is executed as part of a **LiveKit agent session**, where:
- Audio input is streamed to STT
- Agent state is managed by `AgentActivity`
- Speech playback is controlled by `SpeechHandle`

No additional runner files are required for this assignment. The focus of this
submission is the correctness and robustness of the interruption-handling logic.

---

## Verification

The behavior introduced in this PR can be verified through logs during a LiveKit
session:

- Soft acknowledgements ("yeah", "ok") do not interrupt ongoing speech
- Explicit interrupt phrases ("stop", "wait") immediately cancel speech
- When the agent is silent, short acknowledgements are processed normally

Representative log excerpts demonstrating this behavior are included in the pull
request description.

---

## Notes
This submission focuses on deterministic, state-aware interruption handling
logic. The changes are isolated, modular, and designed to be easily extended or
configured in future iterations.
