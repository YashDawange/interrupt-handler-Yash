


#  Intelligent Interruption Handling (Assignment Extension)

This repository includes an added **intelligent interruption-handling layer** for a simulated voice-based AI agent.  
The objective is to classify user speech into **IGNORE**, **RESPOND**, or **INTERRUPT** events based on the agent’s speaking state and the transcript content.

This layer runs on top of simulated VAD/STT/TTS modules and does not modify the core LiveKit framework.  
All added logic resides in `livekit-agents/livekit/`.

---

## Video Submission Link: 
https://drive.google.com/file/d/19zpXJ7nhzcYI2GzBj56XXx_SIypp_ENH/view?usp=sharing

##  Features Added

###  1. Configurable Word Categories

**Soft words (ignored while agent is speaking):**
["yeah", "ok", "okay", "hmm", "right", "uh-huh"]

arduino
Copy code

**Interrupt words (immediately stop the agent):**
["stop", "wait", "no", "hold on"]

yaml
Copy code

Mixed input prioritizes interruption words.  
Example:  
*"yeah okay but wait"* → **INTERRUPT**

---

##  2. Speaking State Tracking

The agent tracks whether it is currently speaking using TTS events:

- `on_tts_start()` → speaking = `True`  
- `on_tts_end()` → speaking = `False`  

This enables context-aware decision-making when user speech occurs.

---

##  3. VAD + STT Synchronization Logic

Because VAD (speech detection) and STT (text) arrive at different times, we apply:

1. **VAD triggers →** mark `pending_vad = True`
2. **STT transcript arrives →** evaluate using interruption filter

This prevents false interruptions caused by early VAD signals.

---

##  4. Interruption Filter Logic

A new module, `interrupt_filter.py`, classifies each user transcript as:

- `IGNORE` — soft words while agent is speaking  
- `RESPOND` — any input while agent is silent  
- `INTERRUPT` — hard words while agent is speaking  

###  Decision Table

| Agent Speaking? | Soft Words | Hard Words | Mixed | Result |
|------------------|------------|------------|-------|--------|
| Yes | ✔ | ✖ | — | IGNORE |
| Yes | ✖ | ✔ | — | INTERRUPT |
| Yes | ✔ | ✔ | BOTH | INTERRUPT |
| No | any | any | — | RESPOND |

---

##  Integration Points

To connect the logic to the simulated audio pipeline:

### In `fake_vad.py`
```
on_vad_detected()  # when user starts speaking
```

### In `fake_stt.py`
```
on_stt_result(transcript)  # when transcript is ready
```

### In `fake_tts.py`
```
on_tts_start()  # when agent speech begins
on_tts_end()    # when agent speech ends
```
These ensure correct state transitions and natural timing.

## Demo Script
Run the included demo
```
python run_demo_in_repo.py
```