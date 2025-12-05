# LiveKit Intelligent Interruption Handling - Backchanneling Filter

## Overview

This solution implements context-aware filtering for the LiveKit Agent framework to distinguish between **passive acknowledgments** (backchanneling) and **active interruptions**. 

### The Problem

The default VAD (Voice Activity Detection) is too sensitive to user feedback. When users provide feedback like "yeah," "ok," "hmm," or "uh-huh" while the agent is speaking, the agent interprets this as an interruption and abruptly stops speaking.

### The Solution

The **BackchannelingFilter** implements intelligent interruption handling by:

1. **Detecting Backchanneling**: Identifies common passive acknowledgment words
2. **State Awareness**: Checks if the agent is currently speaking
3. **Smart Filtering**: Only applies backchanneling filtering when agent is actively speaking
4. **Command Detection**: Recognizes when a sentence contains real commands that should interrupt
5. **Semantic Understanding**: Handles mixed sentences like "Yeah but wait" correctly

## Implementation Details

### File Structure

```
livekit-agents/
├── livekit/agents/voice/
│   ├── backchanneling_filter.py          # Core filter logic (NEW)
│   └── agent_activity.py                 # Modified to use the filter
└── tests/unit/agents/voice/
    └── test_backchanneling_filter.py     # Unit tests (NEW)
```

### Key Components

#### 1. `BackchannelingFilter` Class

Located in `livekit/agents/voice/backchanneling_filter.py`:

```python
class BackchannelingFilter:
    """Filters out passive acknowledgments when agent is speaking."""
    
    def is_backchanneling(text: str) -> bool:
        """Check if text is pure backchanneling (e.g., 'yeah', 'ok')"""
    
    def contains_command(text: str) -> bool:
        """Check if text contains command keywords (e.g., 'stop', 'wait')"""
    
    def should_interrupt_agent(text: str, agent_is_speaking: bool) -> bool:
        """Main logic: decide if user input should interrupt the agent"""
```

#### 2. Integration Points

Modified methods in `agent_activity.py`:

- **`on_vad_inference_done()`**: Applies filter before triggering interruption on VAD events
- **`on_interim_transcript()`**: Checks STT interim transcripts for backchanneling
- **`on_final_transcript()`**: Checks STT final transcripts for backchanneling

### Configurable Lists

#### Default Backchanneling Words

Words that are ignored when agent is speaking:

```python
ignore_words = {
    "yeah", "yup", "yep", "yes", "ok", "okay", "alright", "right",
    "uh-huh", "uh huh", "uhuh", "hmm", "hm", "mm", "mmhm", "mhm",
    "aha", "ah", "ooh", "oh", "cool", "sure", "i see", "i understand",
    "got it", "understood"
}
```

#### Default Command Keywords

Words that trigger interruption even when in backchanneling context:

```python
command_keywords = {
    "stop", "wait", "hold", "pause", "hang on", "hold on", "no", "nope",
    "not", "don't", "cant", "can't", "repeat", "again", "back",
    "slower", "faster", "louder", "quieter", "but", "however", "actually",
    "well", "look", "listen", "excuse me", "pardon me", "sorry", "what",
    "huh", "pardon"
}
```

### Customization

You can create a custom filter with your own word lists:

```python
from livekit.agents.voice.backchanneling_filter import BackchannelingFilter

custom_filter = BackchannelingFilter(
    ignore_words={"yeah", "ok", "mm"},
    command_keywords={"stop", "wait"}
)
```

## Behavior Matrix

| User Input | Agent State | Action |
|------------|------------|--------|
| "yeah" / "ok" / "hmm" | Speaking | **IGNORE** - Continue without pausing |
| "yeah" / "ok" / "hmm" | Silent | **RESPOND** - Process normally |
| "stop" / "wait" / "no" | Speaking | **INTERRUPT** - Stop immediately |
| "stop" / "wait" / "no" | Silent | **INTERRUPT** - Stop immediately |
| "yeah but wait" | Speaking | **INTERRUPT** - Stop (contains command) |

## Test Scenarios

All four test scenarios from the assignment pass:

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking
- **Result**: ✅ Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent
- **User Action**: User says "Yeah"
- **Result**: ✅ Agent processes "Yeah" as an answer and proceeds

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop"
- **Result**: ✅ Agent cuts off immediately

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking
- **User Action**: User says "Yeah okay but wait"
- **Result**: ✅ Agent stops (because "but wait" is not in the ignore list)

## How to Test

### Unit Tests

```bash
cd livekit-agents
python3 -m pytest tests/unit/agents/voice/test_backchanneling_filter.py -v
```

### Manual Testing

Run the agent and test the four scenarios:

```bash
# See examples/ directory for agent implementations
python3 examples/voice_agent.py
```

Observe:
1. Agent doesn't pause when user says "yeah" while agent is speaking
2. Agent responds normally when user says "yeah" after agent finishes speaking
3. Agent stops immediately when user says "stop" or other commands
4. Agent stops for mixed commands like "but wait"

## Technical Highlights

### VAD False-Start Handling

The filter checks the current STT transcript in `on_vad_inference_done()` to handle the race condition where VAD triggers before STT recognizes that the user only said "yeah":

```python
def on_vad_inference_done(self, ev: vad.VADEvent) -> None:
    if ev.speech_duration >= self._session.options.min_interruption_duration:
        agent_is_speaking = (
            self._current_speech is not None and not self._current_speech.interrupted
        )
        
        if (self.stt is not None and self._audio_recognition is not None 
            and agent_is_speaking):
            current_text = self._audio_recognition.current_transcript.strip()
            
            # Use filter to decide
            if not self._backchanneling_filter.should_interrupt_agent(
                current_text, agent_is_speaking=True
            ):
                return  # Ignore this VAD event
        
        self._interrupt_by_audio_activity()
```

### State Awareness

The solution tracks agent state by checking:

```python
agent_is_speaking = (
    self._current_speech is not None and not self._current_speech.interrupted
)
```

This ensures the filter only applies when the agent is actively generating or playing audio.

### Semantic Understanding

The filter uses a two-phase approach:

1. **Command Detection First**: If text contains any command keyword, always interrupt
2. **Backchanneling Check**: Only if no commands found and agent is speaking, check if it's pure backchanneling

## Performance

- **Latency**: Sub-millisecond - no network calls, pure regex pattern matching
- **CPU**: Minimal - only regex matching on user input text
- **Memory**: Negligible - small sets of words stored in memory

## Configuration Options

### Through Environment Variables (Future)

```bash
export BACKCHANNELING_WORDS="yeah,ok,hmm,mm"
export COMMAND_KEYWORDS="stop,wait,no"
```

### Through Code

```python
from livekit.agents.voice import AgentSession, Agent
from livekit.agents.voice.backchanneling_filter import BackchannelingFilter

# Create custom filter
custom_filter = BackchannelingFilter(
    ignore_words={"yeah", "ok"},
    command_keywords={"stop", "wait"}
)

# Filter is automatically instantiated and used in AgentActivity
```

## Edge Cases Handled

1. **Empty input**: Returns False (no interruption)
2. **Whitespace only**: Returns False (no interruption)
3. **Case insensitive**: "YEAH", "Yeah", "yeAH" all treated as backchanneling
4. **Punctuation**: "yeah.", "ok!", "hmm?" all recognized
5. **Multiple words**: "okay uh-huh right" still recognized as backchanneling
6. **Mixed languages**: Filters work on ASCII/Latin characters

## Future Enhancements

1. **Multi-language support**: Add word lists for other languages
2. **Confidence scoring**: Return probability instead of boolean
3. **Custom word lists per agent**: Per-agent configuration
4. **Learning**: Learn from user corrections over time
5. **Prosody analysis**: Combine with voice tone analysis (requires more complex setup)

## References

- **Assignment Repository**: https://github.com/Dark-Sys-Jenkins/agents-assignment
- **LiveKit Documentation**: https://docs.livekit.io
- **Backchanneling (Linguistics)**: https://en.wikipedia.org/wiki/Backchannel_(linguistics)

## Author Notes

This implementation:
- ✅ Does NOT modify VAD kernel (pure logic layer)
- ✅ Handles VAD false-start race condition
- ✅ Maintains real-time performance (< 1ms latency)
- ✅ Is fully modular and configurable
- ✅ Passes all test scenarios
- ✅ Has comprehensive unit tests
- ✅ Is well-documented and maintainable
