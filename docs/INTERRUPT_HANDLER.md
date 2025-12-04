LiveKit Intelligent Interruption Handling
======================================

Overview
--------
This change implements a context-aware interruption handler for LiveKit Agents. It prevents the agent from stopping mid-sentence when the user produces backchannel/filler speech (e.g. "yeah", "ok", "uh-huh") while still allowing true commands (e.g. "stop", "wait") to interrupt.

Key features
------------
- Configurable ignore list (env: LIVEKIT_IGNORE_WORDS)
- Configurable command list (env: LIVEKIT_COMMAND_WORDS)
- Short validation window to let fast STT partials disambiguate VAD false starts (env: LIVEKIT_VALIDATION_WINDOW_MS)
- No changes to VAD kernel; logic implemented at the agent event layer

Files changed/added
-------------------
- Modified: `livekit-agents/livekit/agents/voice/agent_activity.py` — consults classifier and defers VAD-based interrupts.
- Added: `livekit-agents/livekit/agents/voice/interrupt_handler.py` — classifier and defer helper.
- Added: `integration_tests/*` — tests + scenario tests for local verification.
- Added: `tools/demo_interrupt_proof.py` — small demo script that generates a proof log for the four scenarios.

Environment variables
---------------------
- LIVEKIT_IGNORE_WORDS (comma-separated) e.g. `yeah,ok,okay,uh-huh`
- LIVEKIT_COMMAND_WORDS (comma-separated) e.g. `stop,wait,hold,cancel`
- LIVEKIT_VALIDATION_WINDOW_MS (int) e.g. `200`

How to run the quick verification locally
-----------------------------------------
1. Activate your venv (you already have one):
   ```powershell
   & C:\Users\anshu\OneDrive\Desktop\SalesCode\venv\Scripts\Activate.ps1
   ```
2. Run the integration tests (we added pytest-asyncio earlier):
   ```powershell
   Set-Location 'c:\Users\anshu\OneDrive\Desktop\SalesCode\agents-assignment'
   pytest -q integration_tests
   ```
3. Run the demo script to produce a proof log:
   ```powershell
   python tools\demo_interrupt_proof.py
   ```
   The script writes `proofs/interrupt_proof.log`.

Notes on trade-offs
-------------------
To guarantee the strict requirement (the agent must NOT pause or stutter on filler while speaking), the handler conservatively treats a VAD event as non-interrupt if no STT partial arrives within the validation window. Lower the validation window to be more aggressive in interrupting, but only if your STT provider is reliably fast.

Submission checklist
--------------------
- [x] Feature implemented in the agent event layer (no VAD kernel edits)
- [x] Integration tests covering the four scenarios (passed locally)
- [x] Demo script and proof log generated

If you want, I can prepare the PR text and open the PR for you, or provide the exact commands to create the PR using the GitHub web UI or `gh` CLI.
