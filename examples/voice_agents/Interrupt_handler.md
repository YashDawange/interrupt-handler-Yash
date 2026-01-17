## Author

**Nikhil Sharma (23BPH029)** 
**NITH** 




# Context-Aware Interruption Handling for Voice Agents

## Overview

This implementation adds a context-aware interruption logic layer to a LiveKit voice agent.
The agent distinguishes between passive acknowledgements (e.g. "yeah", "ok", "hmm") and
active interruptions (e.g. "wait", "stop", mixed intent sentences) based on whether the
agent is currently speaking or silent.

The primary goal is to guarantee uninterrupted agent speech when the user provides
filler acknowledgements, while still allowing decisive user interruptions when intent
is clear.

---

## Core Behavior

### When the agent is speaking

* Passive acknowledgements are ignored
* Agent speech continues seamlessly
* No pause, resume, or stutter occurs
* Audio is interrupted only after semantic confirmation of an active interruption

### When the agent is silent

* User input is handled normally
* No special filtering is applied

---

## Design Decisions

* Interruption handling is driven by **STT events**, not VAD
* Audio is never paused or resumed speculatively
* A small, stable set of passive acknowledgements is explicitly whitelisted
* All other utterances during agent speech are conservatively treated as interruptions

This approach prioritizes audio continuity and deterministic behavior in real-time
voice interactions.

---

## Files Added / Modified

* `examples/voice_agents/interrupt_handler.py`
  Implements semantic classification for passive vs active interruption

* `examples/voice_agents/basic_agent.py`
  Integrates interruption logic using agent speech state and transcription events

---

## Local Validation

Interruption logic was validated using a lightweight mock agent to simulate speaking
and listening states before integrating with LiveKit's real-time audio pipeline.
This ensured zero-stutter behavior for passive acknowledgements.

---

## CI Note

Some CI jobs related to LiveKit plugins (OpenAI, Deepgram, Cartesia, etc.) may fail on
forked repositories due to missing API secrets. This is expected behavior and unrelated
to the interruption-handling logic implemented here.



## Alignment with Assignment Requirements

- Uses a configurable ignore list for passive acknowledgements
- Applies filtering only while the agent is speaking
- Treats mixed or command-containing utterances as interruptions
- Implements logic at the agent event layer without modifying VAD
- Uses STT-based semantic validation to avoid false interruptions






## Proof of Correctness

The following test output demonstrates that the agent:
- ignores filler words while speaking
- responds to short answers when silent
- interrupts immediately on semantic commands

![Interruption logic test output](docs\Interrupt_testing_results.jpeg)
