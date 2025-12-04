LiveKit Intelligent Interruption Handling
=====================================

Overview
--------
This change adds a state-aware interruption handler that distinguishes between
soft backchannels ("yeah", "ok", "hmm", etc.) and real interruption commands
("wait", "stop", "no") when the agent is speaking.

Key behavior
------------
- If the *agent is speaking* and the user says a pure filler/backchannel (e.g., "yeah"),
  the agent will NOT stop or pause — it continues seamlessly.
- If the *agent is speaking* and the user says an explicit interrupt (e.g., "stop") or
  a mixed sentence containing a command ("yeah wait a second"), the agent will
  interrupt immediately.
- If the *agent is silent*, short replies like "yeah" are treated as valid input
  and will be handled normally.

Configuration
-------------
You can tune the behavior using environment variables (comma-separated lists):

- `AGENT_IGNORE_WORDS` (default: `"yeah,ok,hmm,right,uh-huh,uh,mmhmm,mhm"`)
- `AGENT_INTERRUPT_WORDS` (default: `"wait,stop,no"`)
- `AGENT_DEFER_INTERRUPT_DELAY` (default: `0.15`) — small delay (seconds) to wait
  for a quick STT interim result after a VAD event before forcing an interruption.

Files changed
-------------
- `livekit-agents/livekit/agents/voice/agent_activity.py` — core logic that
  defers VAD-driven interrupts while the agent is speaking and uses STT
  transcripts to discriminate filler vs interrupts.

Demo
----
See `scripts/interrupt_demo.py` for an offline demo that simulates the four
required scenarios and prints the outcome expected from the new logic.

Notes
-----
- This change intentionally avoids modifying low-level VAD. It implements the
  logic in the agent event loop as a state-aware filter.
- For live verification, run the demo or start an `AgentSession` in a room and
  set the env vars as desired.
