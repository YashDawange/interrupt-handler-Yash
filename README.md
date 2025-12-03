# Interrupt Handler — LiveKit Agents Assignment

**Branch:** `feature/interrupt-handler-<yourname>`  
**Author:** Krunal Vaghela (`KrunalVaghela62`)  
**Repo / Fork:** your fork of `Dark-Sys-Jenkins/agents-assignment`

---

## Overview

This project improves the real-time interrupt behavior for a LiveKit voice agent. It prevents short "backchannel" words such as _“yeah”_, _“ok”_, or _“hmm”_ from interrupting the agent while it is speaking, but still allows explicit commands like _“stop”_ or _“wait”_ to interrupt immediately.

**Goals achieved**
- Agent ignores soft acknowledgements while speaking (zero audible pause).
- Agent responds to the same soft words when the agent is silent.
- Agent interrupts immediately on hard words (stop/wait/no).
- Configurable ignore/interrupt word lists via environment variables.
- No modification of VAD kernel — logic layer only.

---

## Features

- `SOFT_IGNORE` (default list) — configurable list of filler/backchannel words.
- `HARD_WORDS` (default list) — words that cause immediate interrupt.
- Fast STT handling with a tiny finalize delay to avoid false VAD interruptions.
- Separate interrupt worker that safely calls `session.interrupt()` to avoid blocking STT events.
- README includes instructions to run, test, and record proof for the assignment.

---

## Files changed / added

- `examples/my_agent/agent.py` — main agent implementation with interrupt filter logic.
- (Optional) `README.md` — this file.
- (Optional) demo video and transcript attached to PR.

---

## Requirements

- Python 3.9+ (tested with 3.10)
- Virtualenv (recommended)
- `pip` packages from original repo (use the repo `requirements.txt`)

---

## Setup (local, dev)

1. Clone your fork (if not cloned yet):
   ```bash
   cd ~/projects || mkdir -p ~/projects && cd ~/projects
   git clone https://github.com/<your-username>/agents-assignment.git
   cd agents-assignment
   git checkout -b feature/interrupt-handler-<yourname>
