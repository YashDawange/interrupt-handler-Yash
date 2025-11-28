# Changes by Gundeti Manoj

**Date:** November 28, 2025  
**Author:** Gundeti Manoj  


## Summary

Implemented an **intelligent interruption handling system** with backchanneling support for LiveKit voice agents. This feature allows agents to differentiate between passive acknowledgments (like "yeah", "ok", "hmm") and real interruptions, creating more natural conversational experiences.

### Key Features Added:
1. **Backchanneling Detection** - Agent continues speaking when users provide passive acknowledgments
2. **Context-Aware Interruption** - Different behavior based on whether agent is speaking or silent
3. **Configurable Word List** - Customizable list of backchanneling words
4. **Test Agent Example** - Comprehensive example demonstrating the feature with multiple test scenarios

---

## Code Changes

### Commit 1: `1f86698c` - "Changes By Gundeti Manoj"

#### 1. New File: `examples/voice_agents/interruption_test_agent.py` (170 lines)

Created a comprehensive test agent to demonstrate and validate the backchanneling feature:

**Features:**
- Three function tools for testing different interruption scenarios:
  - `tell_long_story()` - Tests backchanneling during long agent speech
  - `ask_question()` - Tests how "yeah" is treated as a valid answer when agent is silent
  - `count_slowly()` - Tests interruption timing

**Test Scenarios:**
1. **Long Explanation**: Agent speaks continuously (30-45 seconds), user says "yeah" → agent continues
2. **Passive Affirmation**: Agent asks question and waits, user says "yeah" → agent responds (treats it as answer)
3. **Real Interruption**: Agent speaks, user says "stop" → agent stops immediately
4. **Mixed Input**: Agent speaks, user says "yeah wait" → agent stops (contains non-backchanneling words)

**Configuration Used:**
```python
custom_backchanneling_words = [
    "yeah", "ok", "okay", "hmm", "uh-huh", 
    "right", "aha", "mhmm", "yep", "yup", 
    "sure", "alright"
]

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    turn_detection="stt",
    preemptive_generation=True,
    resume_false_interruption=False,
    backchanneling_words=custom_backchanneling_words,
    min_interruption_duration=0.5,
    min_interruption_words=0,
)
```

#### 2. Modified: `livekit-agents/livekit/agents/voice/agent_activity.py`

**Key Changes:**

a. **New Method: `_is_only_backchanneling(text: str) -> bool`** (35 lines)
   - Checks if user input contains ONLY backchanneling words
   - Ignores punctuation characters (., !, ?, ;, :)
   - Returns `True` only if ALL words in the text are in the backchanneling list
   - Used to prevent interruptions during agent speech

b. **Enhanced: `_interrupt_by_audio_activity()` method**
   - Added backchanneling check BEFORE interrupting agent speech
   - Logic:
     ```python
     if agent_is_speaking and is_only_backchanneling:
         logger.info("✓ IGNORING backchanneling during agent speech")
         return  # Don't interrupt
     elif text:
         logger.info("✗ ALLOWING interruption (not backchanneling)")
         # Continue with interruption
     ```
   - Added detailed debug logging for troubleshooting

c. **Enhanced: `on_final_transcript()` method**
   - Added intelligent backchanneling handling BEFORE emitting transcript
   - **Critical Logic:**
     ```python
     agent_is_speaking = (self._current_speech is not None 
                          and not self._current_speech.interrupted)
     
     if agent_is_speaking and is_backchanneling:
         # Agent IS speaking → ignore backchanneling
         self._audio_recognition.clear_user_turn()
         return  # Don't emit transcript, don't trigger EOU
     
     elif not agent_is_speaking and is_backchanneling:
         # Agent NOT speaking → treat as valid response (e.g., answering "yeah")
         # Fall through to emit transcript
     ```

d. **Enhanced: `on_interim_transcript()` method**
   - Same intelligent backchanneling logic as `on_final_transcript()`
   - Ensures consistent behavior for both interim and final transcripts
   - Prevents premature end-of-utterance (EOU) triggering

e. **Updated: `on_vad_inference_done()` method**
   - Added "stt" to the list of turn_detection modes that skip VAD inference

f. **Code Cleanup:**
   - Removed outdated comments
   - Improved code formatting
   - Removed unused comparison logic for tool outputs

#### 3. Modified: `livekit-agents/livekit/agents/voice/agent_session.py`

**Key Changes:**

a. **New Parameter: `backchanneling_words`**
   - Added to `AgentSessionOptions` dataclass
   - Added to `AgentSession.__init__()` signature with default value
   - Comprehensive docstring explaining the feature:
     ```
     backchanneling_words (list[str], optional): List of words to treat as backchanneling
         (passive acknowledgments like "yeah", "ok", "hmm"). When the agent is speaking,
         these words will NOT interrupt the agent. When the agent is silent, these words
         are treated as normal user input. Set to ``None`` to use default list.
     ```

b. **New Constant: `DEFAULT_BACKCHANNELING_WORDS`**
   ```python
   DEFAULT_BACKCHANNELING_WORDS: list[str] = [
       "yeah", "ok", "okay", "hmm", "uh-huh", 
       "right", "aha", "mhmm"
   ]
   ```

c. **Updated Initialization:**
   - Sets `backchanneling_words` in options using provided value or default
   - Properly integrates with existing session options

d. **Code Cleanup:**
   - Removed unnecessary commented-out code for tracing
   - Removed obsolete comments
   - Improved code formatting consistency

#### 4. Modified: `livekit-agents/livekit/agents/version.py`
   - Updated version from `1.3.3` → `1.3.5`

### Commit 2: `63d7524a` - "Update version.py"

- Reverted version from `1.3.5` back to `1.3.3`
- Likely to maintain compatibility with main branch

---

## Installation & Testing Commands

### 1. Install Core Package (Editable Mode)
```bash
pip install -e livekit-agents
```

### 2. Install Required Plugins
```bash
pip install livekit-plugins-deepgram
pip install livekit-plugins-openai
pip install livekit-plugins-cartesia
pip install livekit-plugins-silero
pip install livekit-plugins-turn-detector
pip install python-dotenv
```

Or use the `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3. Run the Test Agent

**Development Mode:**
```bash
python examples/voice_agents/interruption_test_agent.py dev
```

**Download Required Models:**
```bash
python examples/voice_agents/interruption_test_agent.py download-files
```

---

## How the Feature Works

### Backchanneling Detection Algorithm

1. **Text Analysis:**
   - Splits user input into words using the `split_words()` utility
   - Ignores punctuation characters (., !, ?, ;, :)
   - Checks if ALL words are in the backchanneling word list

2. **Context-Aware Behavior:**
   ```
   IF agent is speaking AND user says ONLY backchanneling words:
       → Ignore the input completely (don't interrupt)
       → Clear audio buffer
       → Log: "✓ IGNORING backchanneling during agent speech"
   
   ELSE IF agent is silent AND user says backchanneling words:
       → Treat as normal user input
       → Emit transcript
       → Log: "✓ Processing backchanneling as response"
   
   ELSE IF user input contains non-backchanneling words:
       → Allow interruption
       → Log: "✗ ALLOWING interruption (not backchanneling)"
   ```

3. **Integration Points:**
   - Checked in `_interrupt_by_audio_activity()` - prevents audio-based interruptions
   - Checked in `on_final_transcript()` - prevents transcript from triggering EOU
   - Checked in `on_interim_transcript()` - prevents premature interruptions

### Example Scenarios

**Scenario 1: Long Story Test**
```
Agent: "Let me tell you about the history of computers... [speaking for 30 seconds]"
User: "yeah" (while agent is speaking)
Result: Agent continues speaking ✓
```

**Scenario 2: Question Response Test**
```
Agent: "Would you like to hear more?"
[Agent stops and waits]
User: "yeah"
Result: Agent processes "yeah" as affirmative answer ✓
```

**Scenario 3: Real Interruption Test**
```
Agent: "Let me explain quantum computing... [speaking]"
User: "wait, stop"
Result: Agent stops immediately (contains "wait" and "stop", not just backchanneling) ✓
```

---

## Technical Details

### Modified Files Summary

| File | Lines Changed | Description |
|------|---------------|-------------|
| `examples/voice_agents/interruption_test_agent.py` | +170 | New test agent example |
| `livekit-agents/livekit/agents/voice/agent_activity.py` | +140, -28 | Core backchanneling logic |
| `livekit-agents/livekit/agents/voice/agent_session.py` | +40, -13 | API additions and configuration |
| `livekit-agents/livekit/agents/version.py` | ±2 | Version updates |
| **Total** | **+350, -41** | **Net: +309 lines** |

### Configuration Options

```python
AgentSession(
    # ... other options ...
    backchanneling_words=[
        "yeah", "ok", "okay", "hmm", "uh-huh",
        "right", "aha", "mhmm", "yep", "yup",
        "sure", "alright"
    ],
    min_interruption_duration=0.5,  # Minimum audio duration for interruption
    min_interruption_words=0,       # Minimum word count (0 = disabled)
    resume_false_interruption=False, # Don't resume after false interruptions
)
```

---

## Benefits

1. **More Natural Conversations:** Users can provide feedback without disrupting agent flow
2. **Improved User Experience:** Agent feels more conversational and less robotic
3. **Flexible Configuration:** Developers can customize backchanneling words per use case
4. **Context Awareness:** Same words have different meanings based on conversation state
5. **Backward Compatible:** Feature is opt-in via configuration parameter

---

## Testing & Validation

The `interruption_test_agent.py` includes three function tools to validate all aspects:

- ✅ `tell_long_story()` - Validates backchanneling during continuous speech
- ✅ `ask_question()` - Validates response detection when agent is silent
- ✅ `count_slowly()` - Validates interruption timing and mixed inputs

### Logging

The implementation includes extensive debug logging:
- `✓ IGNORING backchanneling during agent speech: 'yeah'`
- `✓ Processing backchanneling as response (agent NOT speaking): 'yeah'`
- `✗ ALLOWING interruption (not backchanneling): 'wait stop'`

---

## Future Enhancements (Potential)

- [ ] Add support for multi-word backchanneling phrases ("I see", "got it")
- [ ] Machine learning-based detection instead of rule-based
- [ ] Configurable interruption sensitivity per backchanneling word
- [ ] Audio prosody analysis (tone, pitch) to better detect intent
- [ ] Language-specific backchanneling word sets

---

## Repository Structure

```
agents-assignment/
├── examples/voice_agents/
│   ├── interruption_test_agent.py          # ← NEW: Test agent
│   └── requirements.txt
├── livekit-agents/
│   └── livekit/agents/
│       ├── voice/
│       │   ├── agent_activity.py           # ← MODIFIED: Core logic
│       │   └── agent_session.py            # ← MODIFIED: API additions
│       └── version.py                       # ← MODIFIED: Version tracking
├── requirements.txt                         # ← NEW: Top-level dependencies
└── Gundeti_Manoj_changes.md                 # ← THIS FILE
```
