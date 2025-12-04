Title: feat: Intelligent Interruption Handler (Assignment Submission)

Summary
-------
This PR implements a context-aware interruption handling layer for LiveKit AI agents, ensuring:
- Backchannels such as "yeah", "ok", "uh-huh" do NOT interrupt the agent while speaking.
- Commands such as "stop", "wait", "no" interrupt immediately.
- When the agent is silent, short confirmations ("yeah") are processed as normal responses.
- Mixed utterances ("yeah okay but wait") correctly trigger interruption.

What I implemented
-------------------
1) Interruption Logic Module
   - File: livekit_agents/interrupt_handler.py
   - Implements tokenization, soft-word ignore rules, command-word detection, and state-aware decision logic (IGNORE / INTERRUPT / RESPOND).

2) Validation-Window Mechanism
   - When the agent is speaking and VAD fires, wait a short validation window (default 0.25s) for STT.
   - If STT arrives and is soft-only → IGNORE.
   - If STT contains commands → INTERRUPT.
   - If no STT arrives → IGNORE (VAD false-start).

3) Integration Adapter
   - Provided sample adapter code (suggested location: livekit-agents/interrupt_adapter.py) demonstrating how to integrate the logic into the LiveKit event loop.

4) Unit Tests
   - File: unit_tests/test_interrupt_handler.py
   - All tests pass (5 passing): covers the four assignment scenarios and edge cases.

5) Simulator Proof
   - A Colab-friendly simulator was used to demonstrate VAD early-firing / STT latency handling.
   - Log file produced: logs/sim_log.txt (committed or available in branch).

Why this meets the assignment
------------------------------
- The solution is a logic-layer on top of VAD; no VAD kernel changes.
- The validation-window prevents false interruptions and avoids pauses/stutters on soft backchannels.
- The ignore list is configurable.
- Real-time: validation window is short (0.15–0.35s recommended); default 0.25s.

How to test locally / in Colab
------------------------------
- Run isolated tests:
  - pytest unit_tests
- Run the simulator (Colab):
  - Run the provided simulator cell; inspect logs/sim_log.txt for timestamped decisions.

Files to review
---------------
- livekit_agents/interrupt_handler.py
- unit_tests/test_interrupt_handler.py
- logs/sim_log.txt
- (optional) livekit-agents/interrupt_adapter.py (integration example)

Demo video / proof
------------------
I will attach or link a short screen recording (10–30s) showing the simulator run and the log demonstrating PASS for each required scenario.

Notes
-----
- Branch: feature/interrupt-handler-ashutosh
- This PR is intended to be merged into the assignment repo: Dark-Sys-Jenkins/agents-assignment

