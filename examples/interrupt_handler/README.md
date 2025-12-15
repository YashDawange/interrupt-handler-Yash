# Interrupt Handler for LiveKit Agents (feature/interrupt-handler-veera-pratap-sirra)

This module implements a stateful, semantic interruption filter that prevents the agent from being falsely interrupted by backchannels (e.g. "yeah", "ok", "hmm") while speaking, but still accepts explicit interrupts ("stop", "wait", "no").

This repository contains:
- `agent/speech_manager.py` — tracks speaking state and provides play wrapper.
- `agent/interrupt_filter.py` — ignore / interrupt lists and helper predicates (configurable via ENV).
- `agent/event_loop.py` — core handler to wire VAD + STT with semantic decision logic.
- `demo/run_demo.py` — self-contained demo to reproduce required scenarios for the assignment.

## Key design decisions
- **No modification to VAD**: VAD still fires normally. We intercept VAD events at the application layer.
- **Pending VAD flag**: When VAD fires while speaking, we set `pending_vad` and wait for STT to decide.
- **Low-latency timeout**: A small timeout (default 0.6s) clears pending state if STT never arrives, avoiding permanent locks.
- **Configurable lists**: `INTERRUPT_IGNORE_LIST` and `INTERRUPT_WORDS_LIST` environment variables allow easy tuning.

## How to run demo
1. Ensure python3.8+ installed.
2. From repo root:
   ```bash
   python demo/run_demo.py
