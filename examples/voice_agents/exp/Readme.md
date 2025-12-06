# Intelligent Voice Interrupts – LiveKit Agent

## 1. Problem Statement (PS)

The base LiveKit voice agent was responding to **every tiny sound** as an interruption:

- Short backchannel phrases like “yeah”, “ok”, “hmm” caused the agent to pause/stutter.
- Hard commands like **“stop”, “wait”, “pause”** did **not** reliably and immediately stop the TTS.
- Sometimes the interrupt was picked up late, so the agent kept talking even after the user clearly tried to interrupt.

**Goal:**  
Build a voice agent that:

1. **Immediately stops** speaking when the user says a hard command (e.g. _stop, wait, pause, hold on_).
2. **Ignores natural backchanneling** that normally happens in conversation (e.g. _yeah, ok, hmm, right_).
3. Stays simple, observable, and production-friendly.

---

## 2. Solution Overview

### High-level idea

1. Keep the core LiveKit pipeline **unchanged**:

   - STT: `deepgram/nova-3`
   - LLM: `gemini-2.0-flash`
   - TTS: `cartesia/sonic-2`
   - VAD: `silero.VAD`
   - Turn detection: `MultilingualModel` from `livekit.plugins.turn_detector`.

2. Add a **small STT-based hook** that watches every transcript:

   - If the transcript matches a **hard command** (`stop`, `wait`, `pause`, `hold`, `hold on`)  
     → call `session.interrupt()` **immediately**.
   - Otherwise, let LiveKit’s normal VAD + turn detection handle everything.

3. Provide a reusable helper (`IntelligentInterruptionHandler`) that supports:
   - A configurable list of **backchannel words** to ignore.
   - A configurable list of **command words** that must interrupt.
   - Clean, testable logic for “ignore vs allow”.

The final implementation in `main.py` intentionally uses the **simplest stable version**: a regex-based hard interrupt. `interrupt_handler.py` is kept as a more advanced policy layer that can be wired in if needed.

---

## 3. Architecture

### Components

- **AgentServer / AgentSession**

  - Manages the RTC session and orchestrates STT → LLM → TTS.
  - Configured with:
    - `stt="deepgram/nova-3"`
    - `llm=google.LLM(model="gemini-2.0-flash")`
    - `tts="cartesia/sonic-2:…"`
    - `turn_detection=MultilingualModel()`
    - `vad=silero.VAD` (loaded once per worker in `prewarm`).

- **MyAgent**

  - Simple `Agent` subclass:
    - Provides system instructions (voice style, behaviour).
    - Sends a short greeting in `on_enter()` when the session starts.

- **Hard Interrupt Handler (main.py)**

  - Registers a `user_input_transcribed` callback.
  - Uses a **regex** to match `stop|wait|pause|hold on|hold` as **whole words**.
  - Calls `session.interrupt()` on first match (partial or final transcript).

- **IntelligentInterruptionHandler (interrupt_handler.py)**

  - Not currently wired into `main.py`, but available for more advanced use.
  - Encapsulates:
    - List of ignore words (backchannels).
    - List of command words (hard interrupts).
    - Public methods:
      - `set_agent_speaking(is_speaking: bool)`
      - `is_command(transcript: str)`
      - `should_ignore_interruption(transcript: str)`
  - The filler words (backchannels) and hard command words can be easily tweaked via the `INTERRUPTION_IGNORE_WORDS` and `INTERRUPTION_COMMAND_WORDS` environment variables without changing any code.

- **Metrics**
  - Uses `metrics.UsageCollector()` and `metrics.log_metrics(...)`.
  - A shutdown callback logs aggregated usage summary.

---

## 4. Files Added / Modified

| File                   | Location                                         | Description                                                                                     |
| ---------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `main.py`              | `examples/voice_agents/exp/main.py`              | Entrypoint for the voice agent. Adds a simple, robust hard-interrupt handler on STT output.     |
| `interrupt_handler.py` | `examples/voice_agents/exp/interrupt_handler.py` | Reusable interruption policy class (ignore backchannels, allow commands). Not wired by default. |
| `README.md`            | `examples/voice_agents/exp/README.md`            | Documentation for the problem, solution, architecture, and how to run the agent.                |

> Note: Only comments and structure around the interrupt logic were cleaned up.  
> **Core logic and behaviour remained unchanged** as requested.

---

## 5. How the Problem Was Solved

### Original issues

- **Late or unreliable stop:**  
  “Stop” and similar words were sometimes treated like any other content, so the agent finished long chunks before cutting off.
- **Over-sensitive interruptions:**  
  Any noise or filler speech could cause VAD-based interruption and create stutter.

### Design decisions

1. **Use STT text, not just VAD, to decide hard interrupts.**  
   We hook into `UserInputTranscribedEvent` and look at the actual transcript, instead of relying only on voice activity.

2. **Trigger on both partial and final STT results.**  
   The handler checks **partial** transcripts to cut latency: if `"stop"` appears mid-phrase, we interrupt immediately.

3. **Keep the core pipeline unchanged.**  
   We did **not** modify the AgentSession’s internal behaviour, only added a thin listener around it. This:

   - keeps future upgrades easy,
   - avoids deep monkey-patching,
   - makes debugging and logging simpler.

4. **Provide a more general policy class separately.**  
   `IntelligentInterruptionHandler` gives a clear place to:
   - tune ignore/command words via environment variables,
   - write unit tests for “ignore vs allow” behavior,
   - plug into more complex logic later if needed.

---

## 6. How to Run

```bash
git clone <repo-url>
cd agents-assignment

python -m venv venv
venv\Scripts\Activate.ps1

pip install -r examples/voice_agents/exp/requirements.txt

cd examples/voice_agents/exp

python main.py download-files

python main.py dev

```
