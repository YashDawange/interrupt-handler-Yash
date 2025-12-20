# Intelligent Interruption Handling (Assignment)

A focused explanation of the “intelligent interruption” work added on top of LiveKit Agents. The goal: reduce false interruptions by ignoring real-time acknowledgements like “ok”, “yeah”, “sure” while the agent is speaking — just as a human speaker would not stop when the listener briefly affirms.

## Why This Matters

- Human-inspired: People don’t stop speaking when the listener says “yes/ok/yeah”. We replicate that behavior.
- Real-time friendly: Works directly on streaming transcripts (Deepgram/Whisper/etc.).
- Low overhead: No extra model, no added pipeline — just lightweight, normalized text checks.

## What Was Implemented

- Ignore-word list extracted to a separate, reusable module: `intelligent_interuption.py`.
- Session-level option to pass the list: `AgentSession(..., ignore_words=...)`.
- Runtime filtering inside `AgentActivity` during agent speech: If the user’s interim/final transcript is only acknowledgements/fillers, we do not treat it as an interruption.
- Robust normalization: Lowercasing, punctuation removal, and whitespace compaction to handle edge cases like "ok!!!", "...yeah...", etc.

## Modular Design

- Separate module: `examples/voice_agents/intelligent_interuption.py` exposes `INTERRUPT_IGNORE_WORDS`.
- Example wiring: `examples/voice_agents/basic_agent.py` imports the list and provides it to `AgentSession` via `ignore_words`.
- Core behavior: Implemented in LiveKit voice runtime (`agent_activity.py`) using the session’s `ignore_words`. This keeps configuration separate from behavior and makes swapping or extending lists trivial.

## How It Works (Flow)

1. User speaks while the agent is speaking.
2. STT emits interim/final text (real-time).
3. We normalize the text and split into words.
4. If the set of words is a subset of the configured `ignore_words` set, we ignore it (no interruption triggered).
5. Otherwise, normal interruption logic proceeds.

This preserves responsiveness while avoiding needless agent cut-offs.

## Configuration

- File: [examples/voice_agents/intelligent_interuption.py](./intelligent_interuption.py)
- Add or remove words/phrases in `INTERRUPT_IGNORE_WORDS`.
- In your agent setup, pass them as a set or list:

```python
from intelligent_interuption import INTERRUPT_IGNORE_WORDS
ignore_set = {w.lower() for w in INTERRUPT_IGNORE_WORDS}

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini",
    tts="cartesia/sonic-2:...",
    turn_detection=MultilingualModel(),
    vad=ctx.proc.userdata["vad"],
    preemptive_generation=True,
    resume_false_interruption=True,
    false_interruption_timeout=1.0,
    ignore_words=ignore_set,
)
```

## Edge Cases Handled

- Punctuation and spacing variants: "ok!!!", "...yeah...", "ok?".
- Multi-word phrases: "sounds good", "tell me more" (when configured).
- Empty or whitespace-only transcripts are ignored by default.

## Performance Notes

- O(1) checks on normalized words using a prebuilt set.
- No additional model calls or pipelines.
- Works seamlessly with existing turn detection (VAD, STT, or real-time LLM).

## Changes Summary (Important Files)

- [examples/voice_agents/intelligent_interuption.py](./intelligent_interuption.py): Acknowledgement/filler word list (modular config).
- [examples/voice_agents/basic_agent.py](./basic_agent.py): Imports the list and passes `ignore_words` to `AgentSession`.
- [livekit-agents/livekit/agents/voice/agent_activity.py](../../livekit-agents/livekit/agents/voice/agent_activity.py): Uses `session.options.ignore_words` to suppress false interruptions when only acknowledgements are heard.

## How To Run (Local)

1. Install dependencies (preferably in a venv):

```bash
python -m pip install -e .[dev]
```
or 
```bash
uv sync
```

2. Set environment (keys, models) in `.env.local` as per your provider setup.

3. Run the example server:

```bash
uv run python examples/voice_agents/basic_agent.py dev 
```
open ,connect and test at : https://agents-playground.livekit.io/

or
```bash
python examples/voice_agents/basic_agent.py
```

Connect your client to the LiveKit room and speak while the agent is talking. Try saying “ok”, “yeah”, “sure” — the agent should keep speaking unless you say non-acknowledgement content (e.g., “stop”).

## Limitations & Next Steps

- Language coverage: The provided list is English-focused. Add language-specific files/lists or detect language to swap lists dynamically.
- Contextual acknowledgements: Some phrases may be acknowledgements in some contexts but not others. A future improvement could use lightweight heuristics (e.g., single-token + prosody duration) without adding heavy models.
- Per-agent control: Expose `ignore_words` per agent if different agents need distinct policies.

## Why This Approach Is Strong

- Human-inspired and intuitive.
- Minimal complexity and compute cost.
- Modular and easily extensible.
- Preserves responsiveness without harming interruption handling for meaningful inputs.
- Faster than adding new models or pipelines.
