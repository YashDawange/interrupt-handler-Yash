#DEMO LINK 
https://drive.google.com/file/d/1qXB4Zsbv1295qBSalQEbw6QX8w5T_Qv8/view?usp=sharing

# Intelligent Interruption Handling for LiveKit Voice Agent

This project extends a LiveKit-based voice agent with **semantic interruption handling**.

The goal is to fix a common problem with VAD-based systems:

> When the agent is speaking, short backchannel phrases like “yeah”, “ok”, “hmm” should **not** interrupt.  
> But when the user really wants to cut in (“wait”, “no, stop”), the agent should **immediately** stop and listen.

We implement a small, focused layer on top of LiveKit that:

- Tracks whether the **agent is currently speaking or silent**
- Buffers VAD-triggered interruptions until we have **STT text**
- Uses a **pure Python decision engine** to classify user speech as:
  - `IGNORE` – backchannel while agent is speaking  
  - `INTERRUPT` – real interruption while agent is speaking  
  - `RESPOND` – normal user input while agent is silent  

---

## High-Level Architecture

At a high level, the system looks like this:

1. **LiveKit AgentSession** handles:
   - Audio I/O
   - VAD / turn detection
   - STT (Deepgram)
   - LLM (OpenAI)
   - TTS (Cartesia)

2. **Agent state tracking** (`state_manager.py`):
   - Maintains whether the agent is **SPEAKING** or **SILENT**.

3. **Interruption decision engine** (`interruption_handler.py` + `config.py`):
   - Given:
     - the **transcribed text**
     - the **agent state at the time VAD fired**
   - Returns a decision: `IGNORE`, `INTERRUPT`, or `RESPOND`.

4. **Interruption buffer** (`buffer.py` + `LiveKitInterruptionBuffer` in `agents.py`):
   - When VAD fires while the agent is speaking:
     - We **queue** a “potential interruption” instead of interrupting immediately.
     - Wait briefly for STT to arrive.
   - Once STT text arrives, we:
     - Classify the utterance.
     - Either **cancel** the interruption (pure backchannel), or
     - **Interrupt** the agent (hard interrupt or non-trivial phrase).

This approach gives the **speed of VAD** with the **semantic understanding of STT**, without changing any of the low-level VAD code.

---

## Behavior and Design Logic

### 1. Agent state machine

We track just two practical states:

- `SPEAKING` – the agent TTS is currently playing.
- `SILENT` – the agent is not speaking.

The state machine is updated from LiveKit events:

- On `agent_state_changed` and `speech_created`, we mark the agent as **speaking**.
- When speech ends (via LiveKit internals) and the agent state changes away from `"speaking"`, we mark the agent as **silent**.

This is implemented by `AgentStateTracker` in `state_manager.py`.

### 2. Why buffering is needed

VAD fires **fast** but doesn’t know what was said.  
STT is **slower**, but can tell us whether the user said:

- “yeah ok” (backchannel)  
- or “wait stop” (interrupt)  
- or “yeah but wait” (mixed → interrupt)

If we interrupt immediately on VAD, the agent will stutter on every “yeah/ok/hmm”.  
So instead we:

1. On **VAD + user speaking while agent is speaking**:  
   → queue a **pending interruption** in `InterruptionBuffer`.
2. Wait up to `BUFFER_TIMEOUT_MS` for STT text.
3. When STT arrives:
   - Run the decision engine.
   - If `IGNORE` → drop the event, the agent continues talking smoothly.
   - If `INTERRUPT` → call `session.interrupt()` to stop TTS.
   - If `RESPOND` → do not stop TTS (handled as normal input when appropriate).

Timeout behavior is configurable via `TIMEOUT_FALLBACK`.

### 3. Semantic decision rules

Defined in `interruption_handler.py` and `config.py`.

We use two configurable word lists:

- `BACKCHANNEL_WORDS` – short, low-content fillers like:
  - `"yeah", "ok", "okay", "hmm", "mhm", "uh-huh", "right", "sure", "fine", ...`
- `INTERRUPT_WORDS` – clear interruption intents like:
  - `"stop", "wait", "no", "cancel", "enough", "pause", "listen", ...`

The decision logic, simplified:

1. Normalize and tokenize the STT text:
   - Lowercase
   - Extract word-like tokens (robust regex, not just `.split()`)

2. If the agent **was speaking** when VAD fired:
   - If any token is in `INTERRUPT_WORDS` → **`Decision.INTERRUPT`**  
     - e.g. `"no stop"`, `"yeah wait a sec"`, `"stop please"`
   - Else if the text is a **short pure backchannel**:
     - length ≤ 4 tokens  
     - all tokens in `BACKCHANNEL_WORDS`  
     → **`Decision.IGNORE`**  
       - e.g. `"yeah"`, `"ok"`, `"hmm okay"`, `"mhm right"`
   - Else (longer / mixed content) → **`Decision.INTERRUPT`**  
     - e.g. `"yeah but that's wrong"`, `"okay I have a question"`

3. If the agent **was silent**:
   - Any non-empty utterance → **`Decision.RESPOND`**  
   - Even pure backchannels are treated as valid user input when the agent is not speaking:
     - e.g.:
       - Agent: “Are you ready?” (silent afterward)
       - User: “Yeah.”  
       - Decision: `RESPOND` (the agent should answer and continue)

This exactly matches the assignment requirements:
- Backchannel while speaking → ignored.
- Same phrase while silent → responded to.

---

## File-by-File Overview

### `agents.py`

Entry point and LiveKit integration.

Key responsibilities:

- Defines `MyAgent`, a simple voice assistant with concise, flirty responses.
- Creates an `AgentSession` with:
  - STT: `deepgram/nova-3`
  - LLM: `openai/gpt-4.1-mini`
  - TTS: `cartesia/sonic-2:...`
  - VAD: `silero.VAD`
  - Turn detection: `MultilingualModel`
- Disables LiveKit’s built-in interruption behavior by:
  - `min_interruption_words=999`
  - Enabling `preemptive_generation`, `resume_false_interruption`, etc.
- Wires metrics collection (unchanged from base example).
- Instantiates the **interruption handling stack**:
  - `AgentStateTracker`
  - `InterruptionHandler`
  - `LiveKitInterruptionBuffer` (subclass of `InterruptionBuffer`)

Event wiring:

- `agent_state_changed`  
  → Updates `AgentStateTracker` to `SPEAKING` or `SILENT`.

- `speech_created`  
  → Marks the agent as `SPEAKING` when a new TTS utterance starts.

- `user_state_changed`  
  → When the **user starts speaking while the agent is speaking**:
    - Queue a potential interruption in `LiveKitInterruptionBuffer` instead of immediately interrupting.

- `user_input_transcribed`  
  → When a **final STT transcript** arrives:
    - Pass the text to `buffer.on_stt_transcription`, which triggers the decision engine.

`LiveKitInterruptionBuffer` overrides `_execute_pending_locked()` to actually call `session.interrupt()` when the final decision is `Decision.INTERRUPT`.

---

### `buffer.py`

Defines the **generic buffering layer** that sits between VAD and interruption.

- `InterruptionEvent`  
  - Stores:
    - `timestamp`
    - `agent_state_when_queued` (string, e.g. `"speaking"`)
    - `event_data` (raw info from VAD / user state change)
    - `stt_text` (filled in when transcript arrives)
    - `decision` (filled in by `InterruptionHandler`)

- `InterruptionBuffer`  
  Core logic:
  - `queue_interruption(event_data)`:
    - Stores a new `InterruptionEvent` with the current agent state.
    - Logs that a potential interruption has been queued.
    - Waits (with timeout) for STT text to arrive.
  - `_wait_for_stt()`:
    - Simple polling loop waiting until `stt_text` is set or the event is cleared.
  - `on_stt_transcription(text)`:
    - Attaches the STT text to the pending event.
    - Calls `handler.analyze_input(text, agent_state_when_queued)`.
    - If decision is `IGNORE`:
      - Cancels the pending event (no interruption).
    - Otherwise:
      - Calls `_execute_pending_locked()` to let the subclass perform the actual side-effect.
  - `_handle_timeout()`:
    - Handles the case where STT doesn’t arrive before `BUFFER_TIMEOUT_MS`.
    - Behavior depends on:
      - Agent’s current state
      - `TIMEOUT_FALLBACK` (ignore vs interrupt).

`LiveKitInterruptionBuffer` (in `agents.py`) extends this to physically call `session.interrupt()` on a `Decision.INTERRUPT`. For `RESPOND`, it does nothing special; LiveKit continues with its normal user-turn handling.

---

### `config.py`

Central configuration for interruption behavior:

- `TimeoutFallback` enum:
  - `IGNORE` – drop pending interruptions on timeout while speaking.
  - `INTERRUPT` – go ahead and interrupt if no STT arrives in time.

- `BACKCHANNEL_WORDS`:
  - List of short acknowledgements treated as “soft” backchannels while speaking.

- `INTERRUPT_WORDS`:
  - List of words that signal a real interruption.

- `BUFFER_TIMEOUT_MS`:
  - Maximum time to wait for STT after VAD fires.

- `MIN_PHRASE_LENGTH`:
  - Threshold for distinguishing very short phrases vs longer content (used conceptually by the decision logic).

- `TIMEOUT_FALLBACK`:
  - Default timeout behavior (`TimeoutFallback.INTERRUPT` in this implementation).

These lists are intentionally **small and focused**. They are easy to tweak to match different languages or UX preferences.

---

### `interruption_handler.py`

Contains the **pure decision engine**. It’s completely framework-agnostic.

- `Decision` enum:
  - `IGNORE`
  - `INTERRUPT`
  - `RESPOND`

- `_tokenize(text)`:
  - Uses a regex to extract word-like tokens.
  - Lowercases everything, strips punctuation.
  - More robust than a simple `.split()`.

- `_contains_any(words, vocab)`:
  - Helper to test for membership in a set of tokens.

- `InterruptionHandler`:
  - Stores a reference to `AgentStateTracker` (for auxiliary checks, if needed).
  - Main method: `analyze_input(text, agent_state_when_queued) -> (Decision, reason)`
    - Implements the decision rules described above.
  - `is_backchannel(text)`:
    - Quick helper to detect very short pure backchannels.

This file is the heart of the **semantics** of interruption.

---

### `state_manager.py`

Tracks the agent’s speaking state over time.

- `AgentState` enum:
  - `SPEAKING`
  - `SILENT`
  - `TRANSITIONING` (reserved / available if needed later)

- `AgentStateTracker`:
  - Internally holds:
    - `_current_state`
    - `_speaking_start_time`
  - Methods:
    - `get_state()`
    - `is_speaking()`
    - `set_speaking()`
    - `set_silent()`
  - Both `set_speaking()` and `set_silent()` are async and protected by a lock for safety.
  - Logs transitions, including how long the agent was speaking for each utterance.

This abstraction keeps the rest of the code decoupled from the specifics of LiveKit events.

---

## Example Scenarios (What the User Experiences)

### Scenario 1 – Pure backchannel while agent is speaking

- Agent: reading a long answer…
- User: “yeah”, “ok”, “hmm”, “uh-huh” **during** the speech.

Flow:

1. VAD detects user speech → `user_state_changed` fires.
2. Since agent is speaking, we **queue** an interruption in `InterruptionBuffer`.
3. STT returns `"yeah"` (or similar).
4. `InterruptionHandler.analyze_input(...)`:
   - Agent state was `"speaking"`.
   - Tokens all in `BACKCHANNEL_WORDS`.
   - Short phrase → `Decision.IGNORE`.
5. Buffer cancels the pending event.
6. Agent audio **continues uninterrupted** (no stutter, no pause).

### Scenario 2 – Backchannel while agent is silent

- Agent: “Are you ready to continue?” (then silent)
- User: “Yeah.”

Flow:

1. Agent is in `SILENT` state.
2. STT returns `"yeah"`.
3. `InterruptionHandler` sees agent was silent → `Decision.RESPOND`.
4. LiveKit treats this as a normal user input; the agent responds:
   - “Great, let’s continue.”

### Scenario 3 – Hard interruption

- Agent: explaining something.
- User: “No, stop.” (while agent is speaking)

Flow:

1. VAD → pending interruption queued.
2. STT returns `"no stop"`.
3. Decision:
   - Agent was speaking.
   - Contains `"stop"` in `INTERRUPT_WORDS`.
   - → `Decision.INTERRUPT`.
4. `LiveKitInterruptionBuffer` calls `session.interrupt()`.
5. Agent TTS stops immediately, and the system processes the user’s correction.

### Scenario 4 – Mixed phrase

- Agent: explaining something.
- User: “Yeah okay but wait…” (while agent is speaking)

Flow:

1. Pending interruption is queued.
2. STT returns `"yeah okay but wait"`.
3. Contains `"wait"` → `Decision.INTERRUPT`.
4. Agent is interrupted, as expected.

---

## Configuration and Tuning

All key knobs are in `config.py`:

- **Backchannel words**
  ```python
  BACKCHANNEL_WORDS = [
      "yeah", "yep", "yup", "yes",
      "ok", "okay", "alright", "right",
      "sure", "fine", "cool", "nice",
      "great", "gotcha", "gotit",
      "hmm", "mhm", "mmhmm", "uh-huh", "uhhuh",
      "uh", "huh",
      "understood", "okaythen",
  ]

INTERRUPT_WORDS = [
    "stop", "wait", "no", "nope",
    "cancel", "enough", "quiet", "silence",
    "hold", "pause", "hang", "listen", "excuse",
]
BUFFER_TIMEOUT_MS = 2000  # 200 seconds (adjust as needed)
TIMEOUT_FALLBACK = TimeoutFallback.INTERRUPT

STEPS TO RUN:

1) Clone the repo
2) Go to examples/voice_agents and run
3) pip install -r requirements.txt  #run in terminal
#to download dependencies like
 	•	livekit-agents
	•	livekit-plugins-silero
	•	python-dotenv
4) Then cd.. back to the root of repo and run 

from dotenv import load_dotenv
load_dotenv()

#in terminal to load your api keys like
	•	LIVEKIT_API_KEY
	•	LIVEKIT_API_SECRET
	•	LIVEKIT_URL

…and any keys required for:
	•	Deepgram STT
	•	OpenAI LLM
	•	Cartesia TTS

5)run th agent via
python3 agents.py console #or dev instead of a console if cloud is accessible

