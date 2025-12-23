# Intelligent Interruption Handling (Voice)

This document explains the logic-layer interruption filter that prevents filler words from interrupting the agent mid‑utterance, while preserving normal behavior for real commands and when the agent is silent.

## Assignment Overview
- Problem: VAD can be too sensitive; backchannels like “yeah/ok/hmm/right/uh‑huh” cause unintended barge‑in.
- Goal: Add a context‑aware logic layer that distinguishes passive acknowledgements from active interruptions.
- Strict requirement: If the agent is speaking and the user says a filler word, the agent must not stop or stutter.

## Goals
- Ignore soft acknowledgements (e.g., “yeah”, “ok”, “hmm”, “right”, “uh‑huh”) while the agent is speaking — no pause, no stutter.
- Interrupt immediately on hard commands (e.g., “stop”, “wait”, “no”, “cancel”, “hold on”, “pause”).
- Respond normally when the agent is silent (short answers should be processed).
- Do NOT modify VAD kernels; implement in the agent’s event loop using STT.
- Keep latency imperceptible.

## Core Logic & Objectives (Matrix)
- Agent speaking + “yeah/ok/hmm/right/uh‑huh” → IGNORE (continue TTS seamlessly).
- Agent speaking + “stop/wait/no” → INTERRUPT (stop immediately).
- Agent silent + “yeah/ok/hmm” → RESPOND (treat as valid answer).
- Agent silent + “start/hello” → RESPOND (normal behavior).
- Mixed input (e.g., “yeah … but wait”) → INTERRUPT (hard token present).

## Where it lives
- Policy and configuration:
  - `livekit/agents/voice/interrupt_policy.py`
- Event‑loop integration:
  - `livekit/agents/voice/agent_activity.py`

No changes were made to VAD implementations or plugins.

## Technical Expectations Mapping
- Integration: Implemented entirely inside the existing Agents framework (policy module + `AgentActivity` hooks).
- Transcription Logic: Uses STT interim text; decisions rely on the latest STT delta during speech.
- False start handling: Short “ack grace” re‑check when VAD fires before STT arrives, avoiding premature pauses.
- Latency: All checks are O(1); grace is tiny (~180 ms by default) and configurable; behavior is real‑time.

## Configuration
The soft/hard lists and grace window are configurable via environment variables:

```bash
export LIVEKIT_SOFT_ACKS="yeah,ok,okay,hmm,uh-huh,uhhuh,mm-hmm,mmhmm,mhm,mhmm,mm,mmm,right,aha"
export LIVEKIT_HARD_INTERRUPTS="stop,wait,no,cancel,hold on,pause"
export LIVEKIT_ACK_GRACE_MS=180
```

Tip for demos: set a minimum word count to reduce accidental one‑word turns:

```python
# in your example session constructor
session = AgentSession(
  # ... models ...
  min_interruption_words=2,
)
```

## How it works

1) Latest STT delta while speaking
- In `on_interim_transcript`, we compute the delta (newly added text) and use only that for classification during active agent speech. This avoids misclassifying older words in the full transcript.

2) Small “ack grace” re‑check after VAD
- If VAD fires before any STT text is available, a short timer (~180 ms, configurable) defers the decision until the first STT token arrives. If it’s a soft‑ack, we ignore; if it’s a hard command, we interrupt.

3) Central interruption gate
- In `_interrupt_by_audio_activity`, when the agent is speaking (or has an active speech handle):
  - Soft‑acks → ignored (no pause or stutter).
  - Hard words → immediate interrupt.
  - Too‑short utterances (if `min_interruption_words` > 0) → ignored.

4) Preemptive and end‑of‑turn suppression for soft‑acks
- `on_preemptive_generation`: soft‑ack during active speech does not trigger a speculative reply.
- `on_end_of_turn`: soft‑ack during active speech does not commit a new turn.

5) Zero VAD changes
- The approach uses STT interim text and event‑loop gates; the VAD kernel/stream remains unchanged.

## Diagram
![Interruption Handling Diagram](https://drive.google.com/thumbnail?id=1dGzglspWZj0UPBY85jeHPXVxLr0lQnSO&sz=w1000)


## Run and test
From the repo root:

```bash
python examples/voice_agents/basic_agent.py console
```

Test scenarios:
- Agent speaking + “yeah/ok/hmm/right/uh‑huh” → agent continues seamlessly (ignored).
- Agent speaking + “stop/wait/no” → immediate interrupt.
- Agent silent + “yeah/right” → processed as a valid answer.

Console logs will include:
- “soft acknowledgement detected while speaking; ignoring”
- “hard interruption keyword detected while speaking”
- “ack grace scheduled … / ack grace recheck fired”
- “preemptive generation suppressed … / end_of_turn suppressed …”

## Troubleshooting
- If a filler still interrupts, check the exact STT transcript in logs and add the variant to `LIVEKIT_SOFT_ACKS` (e.g., “mm”, “okey”, “uh huh”). You can lower `LIVEKIT_ACK_GRACE_MS` (e.g., 120) for faster STT.
- For noisy environments during demos, keep `min_interruption_words=2` in `AgentSession(...)`.

## Evaluation Criteria Mapping
- Strict functionality: Soft acks are ignored during speech; hard words interrupt; no pause/stutter on “yeah/ok”.
- State awareness: When silent, “yeah/right” are processed as valid short answers.
- Code quality: Modular policy module; env‑configurable lists; minimal edits in one logic file with clear logs.
- Documentation: This doc explains how to run, configure, and how the logic works.

