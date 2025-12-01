# Interrupt Handler — Submission (feature/interrupt-handler-VarunSriTeja)

**Short summary**  
This submission implements an interrupt handler for a voice agent that:
- Ignores backchannel words while the agent is speaking (e.g. “yeah”, “ok”).
- Interrupts on explicit commands while speaking (e.g. “stop”, “wait”, “pause”).
- Treats the same short words as user input when the agent is **not** speaking.
- Supports VAD start-of-speech interruption (user starts speaking while agent is speaking).
- Cancels in-progress LLM generation and stops TTS playback on interruption.

This behavior matches the assignment rubric: the difference between *ignoring a word while speaking* vs *accepting it when silent* is the core challenge.

---

## Files changed / added
- `livekit/agents/voice/interrupt_handler.py` — **new** (final interrupt logic)
- `livekit/agents/voice/agent_session.py` — small integration hooks (`_on_interrupt` wired to stop player, cancel LLM, emit state change)
- `livekit/agents/voice/audio_recognition.py` — VAD start hook calls `on_vad_start`
- `test_all.py`, `test_interrupts.py`, `test_vad_interrupt.py`, `test_full_pipeline.py` — local test scripts used for verification

(If you need a one-file diff summary for the PR, I can generate `patch.diff` for you.)

---

## How the logic works (short)
1. **Agent silent** → any transcript is treated as user input (`action: user_input`).
2. **Agent speaking**:
   - If transcript *contains* any configured INTERRUPT phrase → **interrupt** immediately (`action: interrupt`, reason `semantic_interrupt`).
   - Else if tokens are only backchannel/ignore words → **ignore** (agent continues speaking).
   - Else (mixed tokens or other user intent) → **interrupt**.
3. **VAD** start-of-speech while agent is speaking → `action: treat_as_user_turn` so TTS stops immediately and user turn is processed.
4. `_do_interrupt()` is a hook overridden by `AgentSession` to stop the player, cancel LLM tasks and transition agent state to `listening`.

---

## How to change ignore / interrupt words
The arrays live at top of `interrupt_handler.py`:

```py
IGNORE_WORDS = ["yeah","ok","okay", ...]
INTERRUPT_WORDS = ["stop","wait","hold on", ...]
```

To change behavior you can:
- Edit the lists above (simple and explicit), or
- Replace them with configuration/environment parsing (optional); the code is modular so this swap is straightforward.

## Run tests (quick)
Run from the repo root (where test_all.py is located).
```py
# optional: ensure virtualenv / python env used in development
python -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows PowerShell

# install deps if any (no extra packages required for tests)
# pip install -r requirements.txt

# run full verification
python test_all.py
```
 
