# Custom Voice Agent — Interrupt-Aware Realtime Assistant

This project implements a custom LiveKit based voice agent that supports
**semantic interruption**, **backchannel suppression**, and **real-time TTS/STT
coordination** using the `WeatherAgent` class in `custom_agent.py`.

## Features Implemented

### 1. Semantic Interrupt Handling

The agent interrupts its speech **only when the user says meaningful or command-like phrases**:

- If user says **“stop”, “wait”, “no”, “pause”, “hold on”**, etc.
    
    → Agent immediately stops TTS and starts a new turn.
    
- If user says **“yeah”, “ok”, “hmm”, “uh-huh”**, etc. *while the agent is speaking*
    
    → These are ignored (no interruption).
    

This is implemented by:

- Tracking `_is_speaking` inside a wrapped `tts_node`
- Filtering STT events inside a custom `stt_node`

### 2. Backchannel Suppression

When the agent is speaking:

- If all detected tokens belong to `INTERRUPT_IGNORE_WORDS`
→ Event is swallowed and does **not** interrupt TTS.

### 3. Command Word Prioritization

If the input contains any word from `INTERRUPT_COMMAND_WORDS`:

- The event is passed untouched to LiveKit’s interruption pipeline.
- TTS stops immediately.
- A new LLM response begins.

### 4. Robust STT Parsing

Text is extracted safely regardless of STT provider using:

- `event.text`
- `event.alternatives[0].text`
- raw string events

### 5. Configurable Word Lists

Using environment variables:

INTERRUPT_IGNORE_WORDS="yeah,ok,hmm"
INTERRUPT_COMMAND_WORDS="stop,wait,no,hold on"

Defaults exist if env vars are not provided.

---

## Modified File

### `custom_agent.py`

Contains the full implementation of:

- `WeatherAgent`
- custom `tts_node` (speaker state tracking)
- custom `stt_node` (backchannel filtering + semantic interruption)
- helper parsing functions
- `get_weather` tool
- agent server entrypoint

This is the only file required for the assignment.

Flow :

Step 1 -> Using Docker
docker run -it \\
  -p 7880:7880 \\
  -e LIVEKIT_KEYS="devkey: secret" \\
  livekit/livekit-server:latest \\
  --dev

Output :

starting LiveKit server
portHttp: 7880
worker registered

Step 2 —> Activate Python Environment & Start Agent

cd examples/voice_agents
source ../../.venv/bin/activate

python custom_agent.py start \\
  --url ws://127.0.0.1:7880 \\
  --api-key devkey \\
  --api-secret secret

starting worker
process initialized
registered worker

Step 3 —> Connect Any LiveKit Client
Here I have Used
LiveKit Cloud room

Upon connecting, agent greets the user

Hello! How can I help you?

The behaviours observed are as follows:

1. Backchannel Ignored During TTS
User :
“yeah”

Agent behavior:
Speech event recognized

Words match ignore list
→ Ignored
→ TTS continues smoothly

Console log:
Agent speaking; ignoring backchannel STT text: yeah

2. Semantic Interrupt
User :
“stop” or “wait, hold on”

Agent behavior:
Contains a command word
→ Interrupt allowed
→ TTS stops immediately
→ Agent begins fresh LLM response

Log:
Agent speaking; received COMMAND text -> allowing interrupt: stop

3. Meaningful User Correction Interrupts TTS
User :
“Actually, tell me the weather in Mumbai.”

Behavior:
Not a backchannel phrase
Not a command word
→ Treated as meaningful input
→ Interrupts TTS
→ Agent responds accordingly

4. When Agent Is Silent
User :
“yeah”

Behavior:
Agent is silent → no filtering

Even backchannels become actual input

Log:
Agent silent; passing STT text through: yeah


This project implements:
a. Per-token semantic filtering
b. Backchannel suppression
c. Command word driven interruption
d. Real time speech aware STT routing
e. Configurable behavior via environment variables
f. A functioning agent entrypoint