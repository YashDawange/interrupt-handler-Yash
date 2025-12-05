# LiveKit – Intelligent Interruption Handling

This project implements an advanced, context-aware interruption system for LiveKit agents. Its purpose is to distinguish between meaningful interruptions and small “backchannel” responses (e.g., *yeah*, *ok*, *hmm*) so that the agent is not unnecessarily stopped while speaking. When the agent is silent, these same words are treated as valid input.

---

## 📌 Behavior Overview

| User Input          | Agent State | Expected Behavior                       | Status |
|--------------------|-------------|-------------------------------------------|---------|
| “Yeah / Ok / Hmm”  | Speaking    | Ignore — agent continues speaking         | ✅ Done |
| “Wait / Stop / No” | Speaking    | Interrupt — agent stops immediately       | ✅ Done |
| “Yeah / Ok / Hmm”  | Silent      | Respond — handled as normal input         | ✅ Done |
| “Hello / Start”    | Silent      | Respond — standard behavior               | ✅ Done |

---

## ✅ Test Summary

| Test File                         | Test Name                       | Result | Progress |
|----------------------------------|----------------------------------|--------|-----------|
| `tests/test_interruption.py`     | `test_ignored_interruption`      | PASS   | 20%       |
| `tests/test_interruption.py`     | `test_valid_interruption`        | PASS   | 40%       |
| `tests/test_interruption.py`     | `test_silent_response`           | PASS   | 60%       |
| `tests/test_mixed_interruption.py` | `test_mixed_input_interruption` | PASS   | 80%       |
| `tests/test_mixed_interruption.py` | `test_all_ignored_words`        | PASS   | 100%     |

All tests required by the assignment are fully implemented and validated.

---

## 🌟 Key Features

- **Customizable ignore list** for backchannel/filler words  
- **State-aware logic** — filtering applies only when the agent is speaking  
- **Mixed input detection** — e.g., “yeah wait” still triggers an interruption  
- **No modifications to VAD** — logic is entirely within agent event lifecycle  
- **Real-time behavior** with zero perceptible delay  
- **Smooth speech output** — ignored words never cause stuttering or pauses  

---

## 🧠 How It Works

The interruption handling logic functions at multiple points within the LiveKit agent pipeline.

### 1. Final Transcript Filtering (`on_final_transcript`)
When STT produces a final transcript:
- If the agent is currently speaking:
  - Normalize words  
  - If **all words** are in the ignore list → transcript is discarded  
  - If **any word** is meaningful → treated as a valid interruption  

### 2. Turn Management (`on_end_of_turn`)
Ensures:
- Ignored words never interrupt  
- Ignored transcripts are not stored in conversation history  

### 3. Commit-Turn Protection (`audio_recognition`)
- Maintains an internal set of ignored transcripts  
- Prevents them from resurfacing during buffer flush operations  

### ⚠️ Important Note

The agent’s TTS output **never pauses** when ignored words are detected.  
Filtering happens *before* interruption logic, guaranteeing seamless speech flow.

---

## ⚙️ Configuration

Ignored words can be set when creating the `AgentSession`:

```python
session = AgentSession(
    vad=silero.VAD.load(),
    stt=deepgram.STT(),
    llm=openai.LLM(),
    tts=elevenlabs.TTS(),
    ignored_words=["yeah", "ok", "okay", "hmm", "right", "uh"],
)
