## LiveKit Intelligent Interruption Handler

This folder contains a robust, context–aware solution for the **LiveKit Intelligent Interruption Handling Challenge**.

The goal is to fix the classic **“false start”** problem where default Voice Activity Detection (VAD) aggressively cuts off the AI agent whenever the user makes short backchannel noises like “Yeah”, “Uh‑huh”, or “Mm‑hmm”.  
Instead of a naive keyword filter, this solution implements a **multi‑stage intent engine** that can reliably distinguish between:

- **Passive listening** – e.g. “Yeah”, “Uh‑huh”
- **True interruptions** – e.g. “Stop”, “Thank you”
- **Mixed phrases** – e.g. “Yeah wait”, “Wait… go ahead”, “Yeah wait continue”

All of this is implemented as a lightweight middleware layer around `livekit-agents`, without modifying the core library.

---

## Key Behaviors

The core logic lives in `interrupt_logic.py` and is injected into the `AgentActivity` created by the example `basic_agent.py`.

### 1. Intelligent VAD “Safety Net”

File: `interrupt_logic.py`

- **Config:** `MAX_BACKCHANNEL_DURATION = 1.5` seconds
- **Behavior:**  
  - If VAD detects that the user has been speaking **longer than 1.5 seconds** *while the agent is currently speaking*, the system **immediately interrupts** the agent via `agent_activity._interrupt_by_audio_activity()`.
  - This happens **before** waiting for STT, so the user never has to shout over a talking agent for long sentences or monologues.
- **Effect:**  
  - Short “mm‑hmm / yeah” bursts do *not* stop the agent.  
  - Long speeches (e.g. “Wait, I actually have another question about…”) stop the agent quickly, even if STT is a bit slow.

### 2. Intent‑Aware STT Layer (Fuzzy + Priority‑Based)

The STT side of the logic is implemented in a custom replacement for `AgentActivity.on_interim_transcript`.

- **Backchannel vocabulary (`BACKCHANNELS`)** – e.g. `"yeah", "yep", "yup", "yes", "uh-huh", "mm-hmm", "ok", "right", "sure", "correct", "indeed"`, etc.
- **Continuation phrases (`CONTINUE_PHRASES`)** – e.g. `"go on", "keep going", "continue", "please continue", "move on", "next", "go ahead", "carry on"`, etc.
- **Motion words (`MOTION_WORDS`)** – e.g. `"go", "on", "ahead", "continue", "move", "next"`.
- **Fuzzy similarity** via `rapidfuzz`:
  - Threshold: `FUZZY_SCORE_THRESHOLD = 80`
  - Used to handle STT variants like `"yeh"` vs `"yeah"`.

All logic only activates **when the agent is actually speaking**:

```python
is_agent_speaking = (
    agent_activity._current_speech is not None
    and not agent_activity._current_speech.done()
)
```

Within that window, the STT intent engine runs the following **priority pipeline** on each interim transcript:

1. **Length safety (word count)**  
   - If the cleaned transcript contains **more than `MAX_WORD_COUNT` (5) words**, treat it as an interruption:  
     - Log: `Interruption (Length): '<text>' (Too many words)`  
     - Call `_interrupt_by_audio_activity()`.

2. **Explicit continuation (highest logical override)**  
   - If any phrase from `CONTINUE_PHRASES` appears in the cleaned transcript:
     - **Do NOT interrupt.**
     - Log: `Ignoring (Explicit Continue): '<text>'`.

3. **Simple backchannels (single‑phrase / fuzzy match)**  
   - If the entire cleaned transcript is:
     - in `BACKCHANNELS`, or
     - a fuzzy match to an entry in `BACKCHANNELS` above the threshold
   - Then:
     - **Do NOT interrupt.**
     - Log: `Ignoring (Backchannel): '<text>'`.

4. **Multi‑word intent resolution**

   For short multi‑word utterances (≤ 5 words), we apply more nuanced checks:

   - **Last‑word intent:**  
     - Extract `last_word = words[-1]`.  
     - If the last word is a fuzzy match to `BACKCHANNELS` **or** to `MOTION_WORDS`:
       - Treat as a **continuation / listening** signal.  
       - **Do NOT interrupt.**  
       - Log: `Ignoring (Last-Word Intent): '<text>' -> Ends with '<last_word>'`.

   - **All‑backchannel utterances:**  
     - If **every** word is a direct or fuzzy match to `BACKCHANNELS`:
       - Example: `"yeah yeah"`, `"mm hmm yeah"`.
       - **Do NOT interrupt.**  
       - Log: `Ignoring (All-Backchannel): '<text>'`.

5. **Default – valid interruption**

   - If no safe condition above is met:
     - The utterance is treated as a **valid interruption**.
     - Log: `Valid Interruption: '<text>'`.
     - Call `_interrupt_by_audio_activity()`.

### 3. Metrics & Latency

- Each STT event is timed with `time.perf_counter()`.
- If processing takes more than 0.5 ms, a debug log is emitted:
  - `Logic Latency: X.XXms`
- In the validation run, latency was consistently in the **1–3 ms** range and added **negligible overhead**.

---

## Architecture & Injection Strategy

### Non‑Invasive Monkey Patch

The logic is injected into LiveKit’s `AgentActivity` **after** the session is started, so we never modify the `livekit-agents` package itself.

File: `examples/voice_agents/basic_agent.py`

- After `AgentSession.start(...)` is awaited, we access the underlying activity:

```python
if session._activity:
    setup_interrupt_logic(session._activity)
elif session._agent._activity:
    setup_interrupt_logic(session._agent._activity)
```

- `setup_interrupt_logic` in `interrupt_logic.py`:
  - Captures original handlers:
    - `original_on_vad = agent_activity.on_vad_inference_done`
    - `original_on_interim = agent_activity.on_interim_transcript`
  - Replaces them with:
    - `custom_on_vad` – implements the **VAD Safety Net** and suppresses the default “interrupt on any sound” behavior.
    - `custom_on_interim` – implements the **intent‑aware STT priority logic** described above.
  - At the end of `custom_on_interim`, it forwards events to the original handler:

```python
original_on_interim(ev, speaking=speaking)
```

This keeps the LiveKit agent behavior intact, while layering the interruption intelligence on top.

---

## How to Run

### 1. Install Dependencies

From the repository root:

```bash
pip install -e livekit-agents
pip install -r examples/voice_agents/requirements.txt
```

`requirements.txt` (for reference):

- `livekit-agents[openai, cartesia, elevenlabs, deepgram, silero, turn-detector, mcp]>=1.0`
- `python-dotenv>=1.0`
- `duckduckgo-search>=8.0`
- `rapidfuzz==3.9.0`

### 2. Configure Environment

Create a `.env` file at the project root with your credentials:

```ini
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

### 3. Start the Agent

From the repository root:

```bash
python examples/voice_agents/basic_agent.py dev
```

Then connect to the room specified by the job request (e.g. via the LiveKit Playground) and talk to the agent.

---

## How to Manually Test the Logic

Use these sample phrases while the agent is speaking:

- **Backchannel (should NOT interrupt)**
  - `"Yeah."`, `"Uh-huh."`, `"Mm-hmm."`, `"Right."`, `"Sure."`
  - Variants like `"Yeh"` or `"Yea"` should still be ignored due to fuzzy matching.

- **Clear interruption (should interrupt)**
  - `"Stop."`, `"Wait."`, `"Thank you."`, or a longer sentence (> 5 words).

- **Continuation overrides**
  - `"Wait. Go ahead."`
  - `"Yeah, continue."`
  - `"Yeah wait continue."`
  - These should **not** interrupt; the final continuation intent wins.

- **VAD Safety Net**
  - Speak over the agent for more than ~1.5 seconds with a full sentence.  
  - The agent should stop **before** the full STT transcript is ready, driven purely by VAD duration.

For a fully annotated run, see `log-transcript.md` in this folder.

---

## Customization Notes

All configuration currently lives directly in `interrupt_logic.py`:

- **Timing & thresholds**
  - `MAX_BACKCHANNEL_DURATION` – controls how long VAD will wait before treating speech as a guaranteed interruption.
  - `MAX_WORD_COUNT` – maximum number of words for which nuanced intent logic is applied before defaulting to interruption.
  - `FUZZY_SCORE_THRESHOLD` – similarity threshold for RapidFuzz.

- **Vocabulary**
  - `BACKCHANNELS` – add or remove terms to tune what should be considered “listening” behavior.
  - `CONTINUE_PHRASES` – extend with your own forms of “keep going”.
  - `MOTION_WORDS` – tweak which verbs/particles count as forward‑motion intents.

If you want to externalize configuration (e.g. via environment variables or a config file), the current constants are clean, centralized entry points to do so.

---

## Evaluation Checklist (Mapped to `interrupt_logic.py`)

- **Strict functionality**
  - Agent **ignores backchannels** like “Yeah” while speaking.
  - Agent **stops immediately** on real interruptions like “Stop.” or “Thank you.”.

- **State awareness**
  - Logic only runs interruption checks when `is_agent_speaking` is `True`.  
  - When the agent is silent, user speech is processed normally.

- **Code quality**
  - Clear separation in `interrupt_logic.py`:
    - VAD Safety Net (`custom_on_vad`)
    - Intent Analysis (`custom_on_interim`)
  - Well‑named constants and helper functions (`clean_text`, `is_fuzzy_match`, `check_phrase_in_text`).

- **Configurability**
  - Single, centralized sets for `BACKCHANNELS`, `CONTINUE_PHRASES`, `MOTION_WORDS`, and tunable thresholds.

- **Novelty**
  - Adds a **hybrid VAD + STT** strategy (VAD Safety Net) instead of using STT alone.
  - Uses **RapidFuzz** for robust fuzzy backchannel detection.
  - Implements a clear **priority hierarchy** to handle tricky phrases like:
    - “Yeah wait”
    - “Wait… go on”
    - “Yeah wait continue”


