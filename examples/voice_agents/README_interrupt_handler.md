# Interrupt Handler Agent

This example demonstrates an intelligent interruption handling system for LiveKit agents that distinguishes between passive acknowledgments and active interruptions.

## Overview

The agent implements context-aware interruption logic that:

- **Ignores filler words** when the agent is speaking (e.g., "yeah", "ok", "hmm")
- **Interrupts on commands** when the agent is speaking (e.g., "wait", "stop", "no")
- **Responds normally** to filler words when the agent is silent
- **Handles mixed inputs** by checking for non-filler words

## How It Works

### Core Logic

The system modifies the `_interrupt_by_audio_activity` method in `AgentActivity` to check:

1. **Agent State**: Whether the agent is currently speaking or silent
2. **Transcript Content**: Whether the user's speech contains only filler words

### Algorithm

```python
if agent_is_speaking and transcript_exists:
    words = split_transcript_into_words(transcript)
    if all_words_are_filler_words(words):
        # Don't interrupt - continue speaking
        return
    else:
        # Contains commands - proceed with interruption
        proceed_with_interruption()
```

### Configuration

The filler words list is configurable via the `filler_words` parameter in `AgentSession`:

```python
session = AgentSession(
    # ... other options
    filler_words=['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'aha', 'okay', 'alright']
)
```

## Test Scenarios

### Scenario 1: Passive Acknowledgment (No Interruption)

- **Agent**: "The history of computing began with..." (speaking)
- **User**: "Yeah" or "Okay"
- **Result**: Agent continues speaking seamlessly

### Scenario 2: Active Interruption

- **Agent**: "One, two, three..." (speaking)
- **User**: "No stop"
- **Result**: Agent interrupts immediately

### Scenario 3: Mixed Input

- **Agent**: Speaking
- **User**: "Yeah okay but wait"
- **Result**: Agent interrupts because "wait" is not a filler word

### Scenario 4: Silent Agent Response

- **Agent**: Silent, waiting for input
- **User**: "Yeah"
- **Result**: Agent processes "Yeah" as valid input and responds

## Running the Example

1. Set up your environment variables (see `.env.example`)
2. Install dependencies:
   ```bash
   pip install "livekit-agents[openai,silero,deepgram,cartesia]"
   ```
3. Run the agent:
   ```bash
   python examples/voice_agents/interrupt_handler_agent.py
   ```

## Technical Implementation

### Files Modified

- `livekit/agents/voice/agent_session.py`: Added `filler_words` parameter
- `livekit/agents/voice/agent_activity.py`: Modified interruption logic

### Key Changes

1. **AgentSessionOptions**: Added `filler_words` field
2. **AgentSession.**init****: Added `filler_words` parameter with default list
3. **AgentActivity.\_interrupt_by_audio_activity**: Added filler word checking logic

### Timing Considerations

The implementation handles the VAD/STT timing issue by:

- Checking transcripts from both VAD triggers and interim STT updates
- Using current transcript content at decision time
- Allowing interruptions to proceed if transcript contains non-filler words

## Configuration Options

- **filler_words**: List of words considered passive acknowledgments
- **min_interruption_words**: Minimum words required for interruption (existing)
- **false_interruption_timeout**: Timeout for resuming false interruptions (existing)

## Limitations

- Relies on accurate STT transcription
- Word splitting may not handle all languages perfectly
- Case-insensitive matching for filler words
