# Voice Agent Interrupt Handler

## Overview

Intelligent interrupt handler distinguishing **backchannel words** (fillers: "mhmm", "okay", "yeah") from **hard commands** ("stop", "wait", "hold on"). Agent ignores fillers while speaking but stops immediately for commands.

---

## Quick Start

### Install

1. **Install framework libraries:**
```bash
pip install -e ./livekit-agents
pip install -e ./livekit-plugins/livekit-plugins-silero
pip install -e ./livekit-plugins/livekit-plugins-groq
```

2. **Navigate to example and install requirements:**
```bash
cd examples/voice_agents
pip install -r requirements.txt
```

**requirements.txt** contains:
- `livekit-agents` with openai, cartesia, elevenlabs, deepgram, silero, turn-detector, mcp
- `python-dotenv`
- `duckduckgo-search`

### Configure (.env)

```
LIVEKIT_URL=wss://your-server
LIVEKIT_API_KEY=your-key
LIVEKIT_API_SECRET=your-secret
GROQ_API_KEY=your-groq-key
INTERRUPTION_IGNORE_WORDS=yeah,ok,okay,yep,yes,hmm,um,uh,mm-hmm,mm hmm,uh-huh,uh huh,alright,right,sure,mhmm,mhm
INTERRUPTION_COMMAND_WORDS=stop,wait,no,hold on,hold,stop it,wait a second,wait a minute,pause
```

### Run

```bash
cd examples/voice_agents
python basic_agent.py dev
```

### Test (LiveKit Playground)

- "Explain AI" → Agent responds
- Say "mhmm" while speaking → Ignored (continues)
- Say "stop" while speaking → Stops immediately
- "Count to 20" + "stop" at #7 → Stops at #7

---

## Architecture

**Decision Flow:**

- User speech detected (VAD) → Defer 0.6s for STT → Check transcript
- **Backchannel-only?** → Ignore (no interrupt)
- **Has command word?** → Interrupt (stop TTS)
- **Mixed content?** → Interrupt

**Components:**

- VAD (Silero) — Detects speech
- STT (Deepgram) — Transcribes
- Interrupt Filter — Analyzes for backchannels/commands
- LLM (Groq) — Generates responses
- TTS (Cartesia) — Plays audio

---

## Key Changes

| File                | Changes                                                      |
| ------------------- | ------------------------------------------------------------ |
| `agent_activity.py` | Backchannel/command detection, VAD deferral, interrupt logic |
| `agent_session.py`  | VAD state blocking during agent speech                       |
| `traces.py`         | OpenTelemetry 1.34.1 compatibility                           |
| `basic_agent.py`    | Example agent with Groq LLM                                  |

### Core Methods

- `_contains_command_word()` — Detect "stop", "wait"
- `_is_backchannel_only()` — Check if all words are fillers
- `_get_last_clause()` — Extract text after final punctuation

---

## Problems & Solutions

| Issue                     | Root Cause                        | Fix                                            |
| ------------------------- | --------------------------------- | ---------------------------------------------- |
| Fillers cause restarts    | EOU checked entire transcript     | Check only last clause when agent speaking     |
| Commands don't stop agent | TTS finishes before interrupt     | Immediate interrupt in `on_final_transcript()` |
| OpenTelemetry errors      | API mismatch in v1.34.1           | Conditional imports with fallback              |
| Empty STT during speech   | Browser AEC suppresses mic        | Documented headphone requirement               |
| Wrong agent state         | State cleared before TTS finishes | VAD state blocking in agent_session            |

---

## Test Results ✅

- ✅ Fillers ignored during speech ("mhmm", "okay", "yeah")
- ✅ Commands interrupt immediately ("stop", "wait", "hold on")
- ✅ Long responses interrupted mid-stream
- ✅ Command + new request works ("stop count to 5")
- ✅ No false acknowledgments for command-only input
- ✅ Works with Groq LLM and all plugins

---

## Configuration

**Custom ignore words:**

```
INTERRUPTION_IGNORE_WORDS=yeah,yep,ok,mhmm,hmm
```

**Custom command words:**

```
INTERRUPTION_COMMAND_WORDS=stop,wait,pause,abort
```

**VAD-only mode (no EOU):**

```
TURN_DETECTOR_ENABLED=False
```

---

## Performance

- VAD deferral: 0.6s (allows STT interim)
- EOU timeout: 2.0s
- Min interruption words: 0
- TTS latency: ~0.2s TTFB

---

## Dependencies

- `livekit-agents` (editable)
- `livekit-plugins-silero` (VAD)
- `livekit-plugins-groq` (LLM)
- `livekit-plugins-deepgram` (STT)
- `livekit-plugins-cartesia` (TTS)
- `livekit-plugins-turn-detector` (EOU)

---

**Status:** ✅ Complete & Tested  
**Branch:** `feature/interrupt-handler-IshanSingh`
