# Intelligent Interruption Handling Implementation

## 📝 Overview

This document describes the implementation of intelligent interruption handling for the LiveKit AI agent, which distinguishes between passive acknowledgements (backchanneling) and active interruptions based on conversation context.

## 🎯 Problem Statement

The default Voice Activity Detection (VAD) in LiveKit is too sensitive to user feedback. When the AI agent is speaking and the user says backchannel words like "yeah," "ok," or "hmm" to indicate they're listening, the agent incorrectly interprets this as an interruption and stops speaking abruptly.

## ✅ Solution: Context-Aware Interruption Logic

### Logic Matrix

| User Input | Agent State | Behavior | Implementation |
|------------|-------------|----------|----------------|
| "Yeah / Ok / Hmm" | Agent is Speaking | **IGNORE** - Agent continues seamlessly | ✅ Implemented |
| "Wait / Stop / No" | Agent is Speaking | **INTERRUPT** - Agent stops immediately | ✅ Implemented |
| "Yeah wait" (mixed) | Agent is Speaking | **INTERRUPT** - Semantic detection | ✅ Implemented |
| Any input | Agent is Silent | **RESPOND** - Treat as valid conversation | ✅ Implemented |

## 🔧 Implementation Details

### 1. Word Lists Definition

**Location:** `/livekit-agents/livekit/agents/voice/agent.py`

```python
# Passive backchannel words - short acknowledgments that don't interrupt
PASSIVE_BACKCHANNEL_WORDS = [
    "yeah", "ok", "hmm", "mhmm", "aha", "right", "uh-huh",
    "i see", "got it", "sure", "alright", "uh", "ah", "mm", 
    "mhm", "okay", "yes"
]

# Active interrupt words - always trigger immediate interruption
ACTIVE_INTERRUPT_WORDS = [
    "stop", "wait", "hold on", "hold up", "hang on", "pause",
    "nevermind", "never mind", "cancel", "shut up", "be quiet",
    "enough", "shush", "silence", "quiet", "stop talking"
]
```

### 2. Agent Class Properties

**Location:** `/livekit-agents/livekit/agents/voice/agent.py`

```python
class Agent:
    def __init__(self, ...):
        self._passive_backchannel_words = PASSIVE_BACKCHANNEL_WORDS.copy()
        self._active_interrupt_words = ACTIVE_INTERRUPT_WORDS.copy()
    
    @property
    def passive_backchannel_words(self) -> list[str]:
        return self._passive_backchannel_words

    @property
    def active_interrupt_words(self) -> list[str]:
        return self._active_interrupt_words
```

### 3. Core Interruption Logic

**Location:** `/livekit-agents/livekit/agents/voice/agent_activity.py`

#### A. `_interrupt_by_audio_activity()` Method

This method is called on VAD events and interim transcripts to decide whether to interrupt the agent.

**Key Features:**
- ✅ Checks if agent is currently speaking
- ✅ Analyzes transcript for passive vs active words
- ✅ **Semantic Interruption Detection**: Detects mixed sentences like "yeah wait"
- ✅ **State-based filtering**: Different behavior when agent is speaking vs silent
- ✅ **Partial word handling**: Waits for word completion (e.g., "o" might become "ok")

```python
def _interrupt_by_audio_activity(self) -> None:
    # ... initialization code ...
    
    # Check if agent is currently speaking
    is_agent_speaking = self._current_speech is not None and not self._current_speech.done()
    
    # Analyze the transcript
    has_active_interrupt = any(w in self._agent.active_interrupt_words for w in words)
    all_passive = all(w in self._agent.passive_backchannel_words for w in words)
    
    # LOGIC MATRIX IMPLEMENTATION:
    if is_agent_speaking:
        if all_passive and not has_active_interrupt:
            # Case 1: Pure passive backchannel → IGNORE
            print(f"[IGNORE] Agent speaking, passive backchannel detected: '{cleaned_text}'")
            return  # Don't interrupt!
        elif has_active_interrupt:
            # Case 2: Active interrupt word or mixed sentence → INTERRUPT
            print(f"[INTERRUPT] Active interrupt word detected: '{cleaned_text}'")
            # Continue to interrupt
        else:
            # Case 3: Other words → INTERRUPT
            print(f"[INTERRUPT] Non-backchannel speech detected: '{cleaned_text}'")
    else:
        # Agent is silent - treat all input as valid conversation
        print(f"[RESPOND] Agent silent, treating as valid input: '{cleaned_text}'")
```

#### B. `on_end_of_turn()` Method

This method is called when the user completes their turn (final transcript).

**Key Features:**
- ✅ Same semantic interruption logic as above
- ✅ Only ignores **pure** passive backchannels when agent is speaking
- ✅ Returns `False` to prevent new turn processing for ignored backchannels
- ✅ Returns `True` to allow turn processing for interruptions or when agent is silent

```python
def on_end_of_turn(self, info: _EndOfTurnInfo) -> bool:
    # ... initialization code ...
    
    # Semantic interruption logic for end of turn
    if final_words:
        has_active_interrupt = any(w in self._agent.active_interrupt_words for w in final_words)
        all_passive = all(w in self._agent.passive_backchannel_words for w in final_words)
        
        # If agent is speaking and user says ONLY passive words
        if is_agent_speaking and all_passive and not has_active_interrupt:
            print(f"[IGNORE - EOT] Agent speaking, pure passive backchannel: '{info.new_transcript}'")
            return False  # Don't process this as a new turn
        elif is_agent_speaking and has_active_interrupt:
            print(f"[INTERRUPT - EOT] Active interrupt in final transcript: '{info.new_transcript}'")
            # Continue to process as interruption
```

## 🧪 Test Scenarios

### Scenario 1: Pure Passive Backchanneling (Agent Speaking)
**Input:** "yeah", "ok", "hmm"  
**Expected:** `[IGNORE]` - Agent continues speaking without pause  
**Status:** ✅ Working

### Scenario 2: Active Interrupt (Agent Speaking)
**Input:** "stop", "wait", "hold on"  
**Expected:** `[INTERRUPT]` - Agent stops immediately  
**Status:** ✅ Working

### Scenario 3: Mixed Sentence (Agent Speaking)
**Input:** "yeah wait a second"  
**Expected:** `[INTERRUPT]` - Detects "wait" and interrupts  
**Status:** ✅ Working

### Scenario 4: Any Input (Agent Silent)
**Input:** "yeah", "stop", "hello"  
**Expected:** `[RESPOND]` - All treated as valid conversation  
**Status:** ✅ Working

### Scenario 5: Partial Word Completion (Agent Speaking)
**Input:** "yeah o..." (being typed/spoken)  
**Expected:** `[WAIT]` - System waits as "o" might complete to "ok"  
**Status:** ✅ Working

## 📊 Logging Output

The system provides clear logging for debugging:

```
[IGNORE] Agent speaking, passive backchannel detected: 'yeah'
[INTERRUPT] Active interrupt word detected: 'wait'
[INTERRUPT] Non-backchannel speech detected: 'tell me more about that'
[RESPOND] Agent silent, treating as valid input: 'hmm'
[WAIT] Potential incomplete passive word: 'o' (might be 'ok')
[IGNORE - EOT] Agent speaking, pure passive backchannel: 'Yeah.'
[INTERRUPT - EOT] Active interrupt in final transcript: 'Yeah wait.'
```

## 🎨 Key Design Principles

1. **No VAD Modification**: Implemented as a logic layer, not by changing VAD
2. **Seamless Continue**: When ignoring passive backchannels, agent continues without pause or stutter
3. **Semantic Awareness**: Analyzes entire sentences, not just individual words
4. **State-Based**: Behavior changes based on whether agent is speaking or silent
5. **Configurable**: Word lists can be easily modified at module level

## 🔍 Code Locations

| Component | File Path | Lines |
|-----------|-----------|-------|
| Word Lists | `/livekit-agents/livekit/agents/voice/agent.py` | 26-38 |
| Agent Properties | `/livekit-agents/livekit/agents/voice/agent.py` | 83-84, 122-129 |
| Interruption Logic | `/livekit-agents/livekit/agents/voice/agent_activity.py` | 1170-1235 |
| Turn Detection Logic | `/livekit-agents/livekit/agents/voice/agent_activity.py` | 1403-1453 |

## ✨ Benefits

1. **Natural Conversation Flow**: Agent doesn't stop for simple acknowledgments
2. **Immediate Response**: Agent stops instantly when user genuinely wants to interrupt
3. **Context-Aware**: Different behavior based on conversation state
4. **Robust**: Handles mixed sentences and partial words correctly
5. **Maintainable**: Clear separation of concerns, easy to modify word lists

## 🚀 Usage

The system works automatically once the agent is started:

```bash
python _agent.py console
```

No additional configuration needed - the intelligent interruption logic is built into the agent's event loop.

## 📝 Notes

- The system uses transcript cleaning (removing punctuation, lowercasing) for reliable word matching
- Partial word detection only applies when last word is ≤4 characters
- Both interim transcripts and final transcripts are processed with the same logic
- The agent state check (`is_agent_speaking`) is performed at the time of transcript processing for accurate state detection

---

**Implementation Date:** December 1, 2025  
**Status:** ✅ Complete and Tested  
**Author:** AI Assistant with User Requirements
