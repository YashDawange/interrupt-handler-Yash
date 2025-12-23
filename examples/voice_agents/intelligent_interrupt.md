## Intelligent Interruption Demo

This example demonstrates **intelligent interruption handling** for a LiveKit voice agent.

Goal: when the agent is speaking, ignore backchanneling/filler words like “yeah”, “ok”, “uh-huh” so the agent **does not pause or stop**. But if the user says a real command like “stop” or “wait”, the agent must **interrupt immediately**.

### How it works
- The agent enables semantic interruption handling via `AgentSession` options:
  - `semantic_interruption_soft_words` (ignore list)
  - `semantic_interruption_stop_commands` (hard interruption commands)
  - `semantic_interruption_correction_cues` (mid-sentence correction cues)

This logic is implemented inside the LiveKit Agents runtime event loop (no VAD kernel modifications). Since VAD fires faster than STT, the runtime delays interruption decisions until it has enough transcript text to classify the utterance. Soft-only transcripts are ignored while the agent is speaking.

### Run it
```
cd examples/voice_agents
python intelligent_interrupt.py console
# or
python intelligent_interrupt.py dev
```

Environment variables expected (match other examples):
- `GOOGLE_API_KEY` (LLM: Gemini)
- `DEEPGRAM_API_KEY` (Deepgram “secret” goes here)
- `CARTESIA_API_KEY` (TTS)
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### Quick start checklist (for your demo video)
1) Copy `env.sample` → `.env` in `examples/voice_agents/` and fill your keys (OpenAI, Deepgram, Cartesia, LiveKit URL/key/secret).
2) (Optional) Install test dep: `pip install pytest` then run `python -m pytest tests/test_interrupt_logic.py` from repo root.
3) Run the demo from repo root:  
   `python examples/voice_agents/intelligent_interrupt.py console`
4) Record the required scenarios:  
   - Agent speaking; you say “yeah / ok / mm-hmm” → agent keeps talking with no pause.  
   - Agent speaking; you say “stop” or “yeah wait” → agent stops immediately and responds.  
   - Agent silent; you say “yeah” → agent treats it as an answer and continues.  
5) Save the video or transcript for submission.

### Quick validation scenarios
- Agent speaking, user says “yeah / ok / mm-hmm” → agent keeps talking with no pause.
- Agent speaking, user says “yeah wait” or “stop” → agent stops immediately and responds.
- Agent silent, user says “yeah” → agent treats it as an answer and continues the flow.

Files to read:
- `intelligent_interrupt.py` – wiring and defaults (models, session flags).
- `livekit-agents/livekit/agents/voice/semantic_interruptions.py` – classifier used by the runtime.
- `livekit-agents/livekit/agents/voice/agent_activity.py` – where semantic interruption is applied.

