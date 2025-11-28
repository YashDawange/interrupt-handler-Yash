# Enhanced Interruption Handling

## Overview

This document describes the enhanced interruption handling features added to the LiveKit Agents framework. These improvements provide intelligent interruption detection, context-aware resumption, and comprehensive metrics for building more natural voice interactions.

## Features

### 1. Detailed Interruption Events

#### UserInterruptedAgentEvent

Emitted when a user interrupts the agent's speech, providing detailed context about the interruption:

```python
from livekit.agents import UserInterruptedAgentEvent

@session.on("user_interrupted_agent")
def on_interruption(event: UserInterruptedAgentEvent):
    print(f"User interrupted speech {event.speech_id}")
    print(f"Agent had said: {event.partial_text}")
    print(f"Interruption reason: {event.interruption_reason}")
    print(f"User speech duration: {event.user_speech_duration}s")
```

**Fields:**
- `partial_text`: Text that was spoken before interruption
- `interruption_position`: Position in audio where interruption occurred (seconds)
- `total_duration`: Total duration of the planned speech
- `interruption_reason`: Reason for interruption (`"vad_detected"`, `"transcript_detected"`, `"manual"`)
- `user_speech_duration`: Duration of user speech that triggered interruption
- `speech_id`: Unique identifier for the interrupted speech

#### InterruptionResumedEvent

Emitted when speech resumes after a false interruption:

```python
from livekit.agents import InterruptionResumedEvent

@session.on("interruption_resumed")
def on_resumed(event: InterruptionResumedEvent):
    print(f"Speech {event.speech_id} resumed after {event.pause_duration}s")
    if event.was_false_interruption:
        print("This was a false interruption - agent continued speaking")
```

**Fields:**
- `speech_id`: ID of the speech that resumed
- `pause_duration`: How long the speech was paused (seconds)
- `was_false_interruption`: Whether this was a false interruption that auto-resumed

### 2. Partial Text Tracking

The `SpeechHandle` now tracks what text has been spoken, enabling context-aware responses:

```python
from livekit.agents import Agent

class MyAgent(Agent):
    async def on_user_turn_completed(self, chat_ctx, new_message):
        # Check if we were interrupted
        activity = self.get_activity()
        if activity._paused_speech:
            paused = activity._paused_speech
            print(f"We were interrupted while saying: {paused.partial_text}")
            print(f"Full text was: {paused.total_text}")
            print(f"Interrupted at: {paused.interruption_timestamp}")
```

**SpeechHandle Properties:**
- `partial_text`: Text spoken before interruption (updated in real-time during synthesis)
- `total_text`: Complete text to be spoken
- `interruption_timestamp`: When interruption occurred (Unix timestamp)
- `pause_timestamp`: When speech was paused (for false interruption handling)

### 3. Context-Aware LLM Resumption

When an interruption occurs, the LLM automatically receives context about what was already spoken:

```python
# Automatic behavior - no code needed!
# 
# If the agent was saying:
#   "Python is a high-level programming language..."
# 
# And the user interrupts with "Wait"
#
# The LLM will receive:
#   System: "Note: You were interrupted while speaking. 
#            You had already said: 'Python is a high-level programming language'.
#            Continue your response from where you left off without repeating 
#            what you already said."
#   User: "Wait"
#
# This prevents the agent from repeating itself after interruptions!
```

The system automatically injects interruption context into the LLM prompt when:
1. User interrupts agent speech
2. Agent generates a new response
3. The interrupted speech had partial text spoken

### 4. Interruption Metrics

Comprehensive metrics are collected for every interruption:

```python
from livekit.agents import InterruptionMetrics, MetricsCollectedEvent

@session.on("metrics_collected")
def on_metrics(event: MetricsCollectedEvent):
    if isinstance(event.metrics, InterruptionMetrics):
        m = event.metrics
        print(f"Interruption at {m.timestamp}")
        print(f"Duration: {m.interruption_duration}s")
        print(f"False interruption: {m.was_false_interruption}")
        print(f"Partial text length: {m.partial_text_length} chars")
        print(f"Total text length: {m.total_text_length} chars")
        print(f"Reason: {m.interruption_reason}")
        print(f"User speech: {m.user_speech_duration}s")
```

**InterruptionMetrics Fields:**
- `timestamp`: When interruption occurred
- `interruption_duration`: Time between interruption and resumption
- `was_false_interruption`: Whether this was a false positive
- `partial_text_length`: Characters spoken before interruption
- `total_text_length`: Total planned text length
- `interruption_reason`: Why interruption was triggered
- `user_speech_duration`: Duration of user speech causing interruption
- `speech_id`: ID of interrupted speech

## Usage Examples

### Example 1: Tracking Interruption Statistics

```python
from livekit.agents import Agent, AgentSession, InterruptionMetrics

class StatisticsAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful assistant.")
        self.interruption_count = 0
        self.false_interruption_count = 0
        self.total_interruption_duration = 0.0
    
session = AgentSession()

@session.on("metrics_collected")
def on_metrics(event):
    if isinstance(event.metrics, InterruptionMetrics):
        agent.interruption_count += 1
        agent.total_interruption_duration += event.metrics.interruption_duration
        
        if event.metrics.was_false_interruption:
            agent.false_interruption_count += 1
        
        print(f"Interruption stats:")
        print(f"  Total: {agent.interruption_count}")
        print(f"  False: {agent.false_interruption_count}")
        print(f"  Average duration: {agent.total_interruption_duration / agent.interruption_count:.2f}s")
```

### Example 2: Custom Interruption Handling

```python
from livekit.agents import Agent, UserInterruptedAgentEvent

class CustomInterruptionAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a patient assistant.")
        self.interruption_threshold = 3
        self.recent_interruptions = []
    
session = AgentSession()

@session.on("user_interrupted_agent")
def on_interrupted(event: UserInterruptedAgentEvent):
    agent.recent_interruptions.append(event)
    
    # Keep only last 5 interruptions
    if len(agent.recent_interruptions) > 5:
        agent.recent_interruptions.pop(0)
    
    # Check if user is interrupting too frequently
    if len(agent.recent_interruptions) >= agent.interruption_threshold:
        print("User is interrupting frequently - maybe they're confused?")
        # Could adjust agent behavior, e.g., give shorter responses
```

### Example 3: Resumption Awareness

```python
from livekit.agents import Agent, InterruptionResumedEvent

class ResumeAwareAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful assistant.")
        self.resume_count = 0

session = AgentSession()

@session.on("interruption_resumed")
def on_resumed(event: InterruptionResumedEvent):
    if event.was_false_interruption:
        agent.resume_count += 1
        print(f"False interruption recovered (#{agent.resume_count})")
        print(f"Speech was paused for {event.pause_duration:.2f}s")
```

## Configuration

The interruption handling system uses existing configuration options:

```python
session = AgentSession(
    # Minimum time user must speak before interrupting agent (seconds)
    min_interruption_duration=0.5,
    
    # Minimum number of words needed to trigger interruption
    min_interruption_words=1,
    
    # Enable automatic resumption after false interruptions
    resume_false_interruption=True,
    
    # How long to wait before resuming after false interruption (seconds)
    false_interruption_timeout=2.0,
)
```

## Implementation Details

### Text Tracking During Synthesis

Partial text is tracked in real-time as the TTS synthesizes speech:

1. When `say()` or `generate_reply()` is called, the total text is set
2. As TTS streams text chunks, `SpeechHandle._update_partial_text()` is called
3. If interruption occurs, the current `partial_text` is captured
4. This partial text is available in events and for LLM context injection

### LLM Context Injection

The interruption context is automatically injected in `_generate_reply()`:

1. Check if `self._paused_speech` exists and has `partial_text`
2. Append interruption note to instructions:
   ```
   Note: You were interrupted while speaking. 
   You had already said: "{partial_text}". 
   Continue your response from where you left off without repeating what you already said.
   ```
3. LLM receives this context and avoids repetition

### Metrics Collection

Interruption metrics are emitted at two points:

1. **When interruption occurs** (`_interrupt_by_audio_activity`):
   - Records interruption timestamp, reason, user speech duration
   - Sets `was_false_interruption` based on whether pause/resume is enabled
   - Tracks partial and total text lengths

2. **When speech resumes** (`_start_false_interruption_timer`):
   - Calculates actual `interruption_duration`
   - Confirms `was_false_interruption = True`
   - Emits both `InterruptionResumedEvent` and updated `InterruptionMetrics`

## Testing

The implementation includes comprehensive unit tests in `test_interruption_handling.py`:

```bash
# Run interruption tests
pytest tests/test_interruption_handling.py -v

# Run specific test
pytest tests/test_interruption_handling.py::test_user_interruption_event_emission -v
```

Tests cover:
- Event emission (UserInterruptedAgentEvent, InterruptionResumedEvent)
- Partial text tracking during synthesis
- InterruptionMetrics collection
- LLM context injection after interruption
- Multiple interruptions in a session
- Interruptions during tool execution

## Migration Guide

### For Existing Applications

The enhanced interruption handling is **backward compatible**. Existing code continues to work without changes:

```python
# This still works exactly as before
session = AgentSession(
    vad=silero.VAD(),
    stt=deepgram.STT(),
    llm=openai.LLM(),
    tts=cartesia.TTS(),
)

await session.start(agent=MyAgent(), room=room)
```

### Opt-in Enhancements

To use the new features, simply add event listeners:

```python
# Add interruption event listeners
@session.on("user_interrupted_agent")
def on_interrupted(event):
    print(f"Interrupted: {event.partial_text}")

@session.on("interruption_resumed")
def on_resumed(event):
    print(f"Resumed after {event.pause_duration}s")

@session.on("metrics_collected")
def on_metrics(event):
    if isinstance(event.metrics, InterruptionMetrics):
        print(f"Interruption metrics: {event.metrics}")
```

The LLM context injection happens automatically - no code changes needed!

## Performance Considerations

The enhanced interruption handling has minimal performance impact:

1. **Text Tracking**: Updates `partial_text` on each TTS chunk (typically 10-50 times per speech)
2. **Event Emission**: Adds 2-3 event emissions per interruption
3. **Metrics**: Collects metrics only when interruptions occur
4. **LLM Context**: Adds ~50 characters to LLM prompt only when resuming after interruption

Overhead is negligible compared to TTS synthesis and LLM inference times.

## Troubleshooting

### Partial Text is Empty

**Problem**: `event.partial_text` is empty when interruption occurs

**Causes**:
- Interruption happened before any text was synthesized
- TTS hasn't started streaming yet
- Using non-streaming TTS provider

**Solution**: Check `event.partial_text` before using it:
```python
if event.partial_text:
    print(f"Agent said: {event.partial_text}")
else:
    print("Interrupted before any speech")
```

### False Interruption Not Resuming

**Problem**: Speech doesn't resume after brief noise

**Causes**:
- `resume_false_interruption=False` (default is True)
- `false_interruption_timeout` is None
- Audio output doesn't support pause/resume

**Solution**: Enable false interruption recovery:
```python
session = AgentSession(
    resume_false_interruption=True,
    false_interruption_timeout=2.0,  # seconds
    # ...
)
```

### Context Not Preventing Repetition

**Problem**: Agent still repeats content after interruption

**Causes**:
- Using realtime LLM (context injection doesn't apply)
- LLM ignoring instructions
- `partial_text` tracking not working

**Solution**: 
1. Check you're using a standard LLM (not RealtimeModel)
2. Verify `partial_text` is being tracked (check interruption events)
3. Try stronger LLM instructions in agent's base instructions

## API Reference

### Events

#### UserInterruptedAgentEvent
```python
class UserInterruptedAgentEvent(BaseModel):
    type: Literal["user_interrupted_agent"]
    partial_text: str
    interruption_position: float
    total_duration: float
    interruption_reason: Literal["vad_detected", "transcript_detected", "manual"]
    user_speech_duration: float
    speech_id: str
```

#### InterruptionResumedEvent
```python
class InterruptionResumedEvent(BaseModel):
    type: Literal["interruption_resumed"]
    speech_id: str
    pause_duration: float
    was_false_interruption: bool
```

### Metrics

#### InterruptionMetrics
```python
class InterruptionMetrics(BaseModel):
    type: Literal["interruption_metrics"]
    timestamp: float
    interruption_duration: float
    was_false_interruption: bool
    partial_text_length: int
    total_text_length: int
    interruption_reason: str
    user_speech_duration: float
    speech_id: str | None
    metadata: Metadata | None
```

### SpeechHandle Properties

```python
class SpeechHandle:
    @property
    def partial_text(self) -> str:
        """Text spoken before interruption."""
    
    @property
    def total_text(self) -> str:
        """Complete text to be spoken."""
    
    @property
    def interruption_timestamp(self) -> float | None:
        """When interruption occurred (Unix timestamp)."""
    
    @property
    def pause_timestamp(self) -> float | None:
        """When speech was paused (Unix timestamp)."""
```

## Contributing

To contribute improvements to interruption handling:

1. Add tests in `tests/test_interruption_handling.py`
2. Run tests: `pytest tests/test_interruption_handling.py -v`
3. Update this documentation
4. Submit pull request with clear description

## License

This enhancement is part of the LiveKit Agents framework and follows the same Apache 2.0 license.
