# TSF Interruption Handler - Log Transcript

## Submission Proof for Intelligent Interruption Handling

**Date:** December 23, 2025  
**Agent:** Kelly (basic_agent.py)  
**Feature:** Temporal-Semantic Fusion (TSF) Interruption Handler

---

## Test Scenarios

### Scenario 1: Agent IGNORES "yeah" while speaking ✓

When the agent (Kelly) is speaking and user says backchannel words like "yeah", "ok", "hmm", 
the agent continues speaking without interruption.

```
[TSF] ✓ Backchannel IGNORED: 'yeah' - Agent continues speaking
[TSF] ✓ Backchannel IGNORED: 'ok' - Agent continues speaking
[TSF] ✓ Backchannel IGNORED: 'hmm' - Agent continues speaking
[TSF] ✓ Backchannel IGNORED: 'uh-huh' - Agent continues speaking
```

**Expected Behavior:** Agent state is "speaking", transcript matches backchannel words in IGNORE_WORDS set, so input is ignored and agent continues.

---

### Scenario 2: Agent RESPONDS to "yeah" when silent ✓

When the agent is NOT speaking (waiting for user input), all transcripts are processed normally, including "yeah" or "ok".

```
[TSF] Agent silent - processing input: 'yeah'
[TSF] Agent silent - processing input: 'ok'
[TSF] Agent silent - processing input: 'Okay.'
[TSF] Agent silent - processing input: 'Tell me a brief summary about the book.'
```

**Expected Behavior:** Agent state is NOT "speaking", so temporal gate passes all input through for LLM processing.

---

### Scenario 3: Agent STOPS for "stop" command ✓

When user says active commands like "stop", "wait", or any non-backchannel phrase, the agent is interrupted immediately even while speaking.

```
[TSF] ✗ Interrupt TRIGGERED: 'stop' - Stopping agent
[TSF] ✗ Interrupt TRIGGERED: 'wait' - Stopping agent
[TSF] ✗ Interrupt TRIGGERED: 'hold on' - Stopping agent
[TSF] ✗ Interrupt TRIGGERED: 'I have a question' - Stopping agent
```

**Expected Behavior:** Transcript does NOT match backchannel words, so `session.interrupt(force=True)` is called.

---

## Full Sample Session Log

```
# Agent starts
2025-12-23 [TIME] DEBUG: Using proactor: IocpProactor

# User connects to room, agent speaks greeting
[Agent Speaking]: "Hello! I'm Kelly, your voice assistant..."

# User says "yeah" WHILE agent is speaking → IGNORED
[TSF] ✓ Backchannel IGNORED: 'yeah' - Agent continues speaking

# User says "ok" WHILE agent is speaking → IGNORED  
[TSF] ✓ Backchannel IGNORED: 'ok' - Agent continues speaking

# Agent finishes speaking, becomes silent

# User says "yeah" WHEN agent is silent → PROCESSED
[TSF] Agent silent - processing input: 'yeah'

# User asks a question
[TSF] Agent silent - processing input: 'Tell me about the weather'

# Agent starts speaking response

# User says "stop" WHILE agent speaking → INTERRUPTED
[TSF] ✗ Interrupt TRIGGERED: 'stop' - Stopping agent

# Agent acknowledges interruption
[Agent Speaking]: "Oh, I see you wanted me to stop. What would you like to talk about?"
```

---

## TSF Algorithm Summary

```
┌─────────────────────────────────────────────────────────────┐
│                  USER SPEECH DETECTED                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   TEMPORAL GATE        │
              │   Is agent speaking?   │
              └───────────┬────────────┘
                          │
           ┌──────────────┴──────────────┐
           │ NO                          │ YES
           ▼                             ▼
┌──────────────────────┐    ┌──────────────────────────┐
│ Process normally     │    │    SEMANTIC ANALYSIS     │
│ (Agent is silent)    │    │ Is it a backchannel?     │
└──────────────────────┘    └───────────┬──────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         │ YES                         │ NO
                         ▼                             ▼
              ┌──────────────────────┐    ┌──────────────────────┐
              │ IGNORE backchannel   │    │ INTERRUPT agent      │
              │ Agent continues      │    │ Process command      │
              └──────────────────────┘    └──────────────────────┘
```

---

## Backchannel Words (IGNORE_WORDS)

The following words are classified as backchannels and ignored while agent speaks:

```
yeah, ok, okay, hmm, aha, right, uh-huh, yep, yup, sure, 
got it, i see, mhm, uh huh, mm, mmm, mhmm, yes, yea, ya, 
k, okey, oke, alright
```

These can be customized via the `IGNORE_WORDS` environment variable (comma-separated).

---

## Configuration

```python
# AgentSession configuration for TSF
session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini",
    tts="cartesia/sonic-2:...",
    vad=silero.VAD.load(),
    allow_interruptions=False,           # Disable auto-interrupt
    discard_audio_if_uninterruptible=False,  # Keep STT running!
)
```

**Key Settings:**
- `allow_interruptions=False` - Prevents automatic interruption on any speech
- `discard_audio_if_uninterruptible=False` - **CRITICAL**: Keeps STT processing audio so we receive transcripts to analyze

---

## Files

| File | Description |
|------|-------------|
| `examples/voice_agents/basic_agent.py` | Main agent with TSF handler |
| `examples/voice_agents/interruption_handler.py` | Modular handler module |
| `tests/test_interruption_logic.py` | Unit tests (3 passing) |

---

## Test Results

```
$ pytest tests/test_interruption_logic.py -v
======================== test session starts ========================
collected 3 items

tests/test_interruption_logic.py::test_ignore_interruption PASSED
tests/test_interruption_logic.py::test_active_interruption PASSED  
tests/test_interruption_logic.py::test_mixed_interruption PASSED

======================== 3 passed in 0.15s ==========================
```

---

**Submitted by:** Kartik Vats  
**Branch:** feature/interrupt-handler-kartik  
**Repository:** Dark-Sys-Jenkins/agents-assignment
