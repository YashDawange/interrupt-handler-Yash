# Intelligent Interruption Handling for LiveKit Agents

## Overview

This feature implements context-aware interruption handling that distinguishes between **passive acknowledgment** (backchannel feedback) and **active interruption** based on whether the agent is currently speaking or silent.

### The Problem

By default, LiveKit's Voice Activity Detection (VAD) is highly sensitive. When a user provides backchannel feedback like "yeah," "ok," or "hmm" to indicate they're listening, the VAD interprets this as an interruption and stops the agent mid-sentence. This breaks the natural flow of conversation.

### The Solution

The intelligent interruption handling system:
1. **Ignores backchannel words when agent is speaking** - Agent continues seamlessly
2. **Respects command words** - Agent stops immediately on "stop", "wait", "no"
3. **Treats backchannel as valid input when agent is silent** - Normal conversational behavior
4. **Handles mixed inputs** - "Yeah wait a second" triggers interruption because it contains a command

---

## Features

### 1. Configurable Ignore List
Define a list of words that act as "soft" inputs when the agent is speaking.

**Default backchannel words:**
- yeah, ok, okay
- hmm, mm-hmm, uh-huh
- right, aha, ah, mhm
- yep, yup, sure
- gotcha, alright

### 2. State-Based Filtering
The filter only applies when the agent is actively generating or playing audio.

**Logic Matrix:**

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "yeah" / "ok" / "hmm" | Speaking | **IGNORE** - Agent continues without pausing |
| "wait" / "stop" / "no" | Speaking | **INTERRUPT** - Agent stops immediately |
| "yeah" / "ok" / "hmm" | Silent | **RESPOND** - Treated as valid input |
| "yeah wait" (mixed) | Speaking | **INTERRUPT** - Contains command word |

### 3. Semantic Interruption Detection
Mixed sentences like "Yeah wait a second" are correctly identified as interruptions because they contain non-backchannel words.

### 4. No VAD Modification
Implemented as a logic layer within the agent's event loop - no low-level VAD changes required.

---

## Usage

### Basic Setup

```python
from livekit.agents import AgentSession

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2",
    vad=your_vad,
    # Enable intelligent interruption handling with default words
    # (This is optional - defaults to a sensible list)
)
```

### Custom Backchannel Words

```python
session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2",
    vad=your_vad,
    # Customize the backchannel words list
    backchannel_words=["yeah", "ok", "hmm", "right", "uh-huh", "gotcha"],
)
```

### Disable Feature (Use Empty List)

```python
session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2",
    vad=your_vad,
    # Disable intelligent interruption by providing empty list
    backchannel_words=[],
)
```

---

## Test Scenarios

### Scenario 1: The Long Explanation
- **Context:** Agent is reading a long paragraph about history
- **User Action:** User says "Okay... yeah... uh-huh" while agent is talking
- **Result:** ✅ Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context:** Agent asks "Are you ready?" and goes silent
- **User Action:** User says "Yeah."
- **Result:** ✅ Agent processes "Yeah" as an answer and proceeds

### Scenario 3: The Correction
- **Context:** Agent is counting "One, two, three..."
- **User Action:** User says "No stop."
- **Result:** ✅ Agent cuts off immediately

### Scenario 4: The Mixed Input
- **Context:** Agent is speaking
- **User Action:** User says "Yeah okay but wait."
- **Result:** ✅ Agent stops (because "but wait" contains non-backchannel words)

---

## Implementation Details

### Architecture

The implementation consists of three main components:

#### 1. Configuration Layer (`agent_session.py`)
- Adds `backchannel_words` parameter to `AgentSessionOptions`
- Default list: `DEFAULT_BACKCHANNEL_WORDS`
- Passed to agent activity for runtime use

#### 2. Interruption Logic (`agent_activity.py`)
Located in `_interrupt_by_audio_activity()` method:
```python
# Check if agent is speaking AND transcript contains ONLY backchannel words
if agent_is_speaking and is_all_backchannel(transcript):
    logger.debug("Ignoring backchannel input")
    return  # Don't interrupt
```

#### 3. Text Analysis
- Extracts words from STT transcript using `split_words()`
- Normalizes words (lowercase, strip punctuation)
- Checks if ALL words are in the backchannel set
- If any word is NOT backchannel → proceed with normal interruption

### Key Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Default backchannel words | `agent_session.py` | 135-151 |
| Configuration option | `agent_session.py` | 92, 163, 314-318 |
| Interruption logic | `agent_activity.py` | 1188-1225 |

### Latency Considerations

The solution remains real-time:
- Text analysis is performed on already-transcribed STT output
- Simple word matching using a set (O(1) lookup)
- Decision made before any audio pipeline changes
- No perceptible delay introduced

---

## Testing

### Run the Demo Agent

```bash
cd examples/voice_agents
python intelligent_interruption_demo.py dev
```

### Manual Test Cases

1. **Test 1: Backchannel while speaking**
   - Wait for agent to start a long explanation
   - Say "yeah", "ok", "hmm" multiple times
   - ✅ Agent should continue without interruption

2. **Test 2: Command while speaking**
   - Wait for agent to start speaking
   - Say "stop" or "wait"
   - ✅ Agent should stop immediately

3. **Test 3: Backchannel when silent**
   - Wait for agent to finish and go silent
   - Say "yeah"
   - ✅ Agent should respond to your input

4. **Test 4: Mixed input**
   - Wait for agent to start speaking
   - Say "yeah but wait"
   - ✅ Agent should stop (mixed input detected)

### Expected Log Output

When backchannel is detected:
```
DEBUG:agent_activity:Ignoring backchannel input while agent is speaking: 'yeah'
```

---

## Configuration Reference

### `AgentSession` Parameters

```python
backchannel_words: NotGivenOr[list[str]] = NOT_GIVEN
```

**Description:** List of words considered as backchannel feedback. When the agent is speaking and the user says ONLY these words, the agent will continue speaking without interruption.

**Default:** See `DEFAULT_BACKCHANNEL_WORDS` in `agent_session.py`

**Type:** `list[str]`

**Example:**
```python
backchannel_words=["yeah", "ok", "hmm", "right", "uh-huh"]
```

### Default Backchannel Words List

```python
DEFAULT_BACKCHANNEL_WORDS = [
    "yeah",     # Common affirmation
    "ok",       # Acknowledgment
    "okay",     # Alternative spelling
    "hmm",      # Thinking sound
    "mm-hmm",   # Verbal nod
    "uh-huh",   # Agreement
    "right",    # Confirmation
    "aha",      # Understanding
    "ah",       # Recognition
    "mhm",      # Short acknowledgment
    "yep",      # Informal yes
    "yup",      # Informal yes
    "sure",     # Agreement
    "gotcha",   # Understanding
    "alright",  # Acceptance
]
```

---

## How It Works: Technical Deep Dive

### 1. Transcript Acquisition
When STT produces a transcript (interim or final), the system captures the text via `self._audio_recognition.current_transcript`.

### 2. Agent State Detection
The system checks if the agent is currently speaking:
```python
if (
    self._current_speech is not None
    and not self._current_speech.interrupted
):
    # Agent is speaking
```

### 3. Word Tokenization & Normalization
```python
words = split_words(transcript, split_character=True)
normalized_words = [
    word.lower().strip(".,!?;:'\"")
    for word in words
]
```

### 4. Backchannel Detection
```python
backchannel_set = set(word.lower() for word in opt.backchannel_words)
is_all_backchannel = all(
    word in backchannel_set
    for word in normalized_words
)
```

### 5. Decision
- If `is_all_backchannel` is `True` AND agent is speaking → **Return early** (don't interrupt)
- Otherwise → **Continue with normal interruption logic**

### Timing: VAD vs STT

**Challenge:** VAD triggers faster than STT transcription is available.

**Solution:** The check happens in `_interrupt_by_audio_activity()`, which is called by both:
- `on_vad_inference_done()` - After VAD detects speech
- `on_interim_transcript()` - After STT produces text
- `on_final_transcript()` - After STT finalizes text

When transcript is not yet available, the system proceeds with normal logic (using `min_interruption_duration` and `min_interruption_words` thresholds).

---

## Troubleshooting

### Agent Still Gets Interrupted

**Possible causes:**
1. STT transcript not available yet when interruption triggered
   - **Solution:** Adjust `min_interruption_duration` to give STT more time
2. User's word not in backchannel list
   - **Solution:** Add the word to your custom `backchannel_words` list
3. Transcript contains mixed input ("yeah but...")
   - **Expected behavior:** This should interrupt

### Agent Doesn't Respond to Backchannel When Silent

This is expected behavior! When the agent is silent:
- Backchannel words like "yeah" are treated as **valid user input**
- The agent will generate a response (e.g., "Great, let's continue")

### How to Debug

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Look for these log messages:
```
DEBUG:agent_activity:Ignoring backchannel input while agent is speaking: 'yeah'
```

---

## Examples

### Full Working Example

See [`examples/voice_agents/intelligent_interruption_demo.py`](examples/voice_agents/intelligent_interruption_demo.py) for a complete working example.

### Minimal Example

```python
from livekit.agents import AgentSession, Agent

class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a friendly assistant."
        )

    async def on_enter(self):
        self.session.generate_reply()

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2",
    vad=vad,
    backchannel_words=["yeah", "ok", "hmm"],  # Custom list
)

await session.start(agent=MyAgent(), room=room)
```

---

## Frequently Asked Questions

### Q: Does this work with all STT providers?
**A:** Yes, as long as the STT provider produces transcripts, the feature will work.

### Q: What if I want different behavior for different languages?
**A:** You can provide language-specific backchannel words:
```python
# Japanese backchannel words
backchannel_words=["はい", "うん", "そう", "なるほど"]

# Spanish backchannel words
backchannel_words=["sí", "vale", "ok", "claro"]
```

### Q: Can I disable this feature entirely?
**A:** Yes, provide an empty list:
```python
backchannel_words=[]
```

### Q: Does this increase latency?
**A:** No. The text analysis is extremely fast (set lookup is O(1)) and happens after STT transcription is already complete.

### Q: What about false positives (VAD triggers before STT)?
**A:** This is handled by the existing `false_interruption_timeout` and `resume_false_interruption` mechanisms. Our feature integrates seamlessly with these.

---

## Contributing

When modifying this feature:

1. **Maintain backward compatibility** - Default behavior should work out of the box
2. **Test all scenarios** - See "Test Scenarios" section
3. **Update documentation** - If adding new backchannel words or behavior
4. **Performance** - Keep word matching efficient (use sets)

---

## License

This implementation is part of the LiveKit Agents framework and follows the same license.

---

## Credits

**Implementation:** Intelligent Interruption Handling Challenge Assignment
**Date:** 2025-11-27
**Framework:** LiveKit Agents Python SDK
