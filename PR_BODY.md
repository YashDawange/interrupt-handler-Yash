Title: feature: Context-aware interrupt handler (ignore backchannels while speaking)

Summary
-------
This branch implements a context-aware interruption handler for LiveKit agents that:

- Ignores backchannel/filler words while the agent is actively speaking (no pauses or stutters).
- Interrupts immediately on explicit commands (e.g., stop, wait, no, cancel).
- Uses a short STT validation and classifier layer to avoid false VAD-triggered interruptions.

Notable changes
---------------
- livekit-agents/livekit/agents/voice/interrupt_handler.py  - classifier + short validation window
- livekit-agents/livekit/agents/voice/agent_activity.py    - consults classifier for interim/final transcripts and defers VAD-triggered interrupts
- integration_tests/                                      - focused integration tests for scenarios
- tools/live_tts_autostop.ps1                              - Windows demo script that speaks sentence-by-sentence and supports deterministic pause/resume/stop for recording proofs
- docs/INTERRUPT_HANDLER.md                                - design notes and run instructions
- proofs/interrupt_proof.log                                - sample proof log

Why
---
This addresses the LiveKit Intelligent Interruption Handling challenge: prevent filler/backchannels from interrupting an agent while allowing genuine commands to interrupt. The sentence-chunk playback in the demo ensures deterministic resume behavior on Windows and produces reproducible proofs.

How to review / test
--------------------
1. Open the PR UI using the compare page (replace `main` with the upstream default branch if necessary):
   https://github.com/Dark-Sys-Jenkins/agents-assignment/compare/main...anshuiitb:feature/interrupt-handler-anshu?expand=1

2. Run the demo on Windows to validate behavior:
   - powershell -ExecutionPolicy Bypass -File .\tools\live_tts_autostop.ps1
   - While the agent speaks: say filler words ("yeah", "uh-huh") — playback continues uninterrupted.
   - While the agent speaks: say command words ("wait", "stop") — playback pauses or stops immediately.

3. Run the integration tests included under `integration_tests/` (they're standalone to avoid project conftest):
   - pytest integration_tests

Notes & limitations
-------------------
- The demo uses sentence-level chunking to guarantee deterministic resume semantics on Windows SAPI. If sample-accurate resume is required, a WAV-buffer plus playback engine is recommended (can be provided as follow-up).
- Environment variables (e.g., LIVEKIT_IGNORE_WORDS) can be configured in the runtime environment; see `docs/INTERRUPT_HANDLER.md`.

Contact
-------
If you'd like, I can create the PR for you with this body, but I need gh CLI or API credentials to do that here. Otherwise this `PR_BODY.md` is ready to paste into the PR form.
