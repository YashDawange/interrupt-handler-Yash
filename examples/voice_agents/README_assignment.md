# LiveKit — Intelligent Interruption Handling

## Overview
This project adds a small, state-aware layer on top of a LiveKit voice agent to distinguish passive backchanneling (for example: "yeah", "ok", "uh-huh") from active interruptions ("stop", "wait", "no"). The logic lives in the agent event loop and does not modify the low-level VAD. The result:

- The agent keeps speaking uninterrupted when the user produces filler/backchannel words.
- The agent stops immediately when explicit interrupt words are detected.
- The same short filler word is treated as valid input when the agent is silent.

## Files added 
- `examples/voice_agents/agent_layer.py`  
  Example integration that prewarms VAD, wires STT/LLM/TTS, and attaches the interruption logic. It handles both interim and final transcripts and attempts manual TTS interruption when appropriate.

- `livekit-agents/livekit/agents/voice/interrupt_handler.py`  
  `InterruptHandler` and `InterruptionConfig` responsible for:
  - Loading `interrupt_config.json`
  - Tokenizing STT text
  - Making state-aware decisions (speak vs silent)

- `interrupt_config.json` (project root)  
  Configurable lists for `filler_words`, `interrupt_words`, and `min_words_for_interrupt`.

- `.env` (add a .env inside examples folder)  
  Holds LiveKit, GROQ and DEEPGRAM API credentials needed by the agent_layer file.

## How it works (short)
1. The VAD triggers audio events as usual.
2. STT provides interim and final transcripts.
3. `InterruptHandler` inspects tokens and the current agent state:
   - If the agent is speaking, filler-only utterances are ignored.
   - If the agent is speaking and an explicit interrupt word or a contentful phrase (meeting the configured threshold) appears, the agent is interrupted.
   - If the agent is silent, input is always processed.
4. All logic runs in user-space; VAD is unchanged.

### Setup and how to run 

1. Run this command -> uv sync --all-extras --dev
2. Then run -> uv run examples/voice_agents/agent_layer.py console