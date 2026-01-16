# Intelligent Interruption Filter

## Overview

The Intelligent Interruption Filter is a context-aware logic layer that enables voice agents to distinguish between passive acknowledgements (backchanneling) and active interruptions. This solves the problem where LiveKit's default Voice Activity Detection (VAD) is too sensitive and misinterprets user feedback like "yeah," "ok," or "hmm" as interruptions when the agent is speaking.

## Key Features

1. **Configurable Ignore List**: Define words/phrases that act as "soft" inputs (e.g., 'yeah', 'ok', 'hmm', 'right', 'uh-huh')
2. **State-Based Filtering**: The filter only applies when the agent is actively generating or playing audio
3. **Semantic Interruption**: If the user says a mixed sentence like "Yeah wait a second," the agent will interrupt because it contains a command ("wait")
4. **No VAD Modification**: Implemented as a logic handling layer within the agent's event loop, without modifying the low-level VAD kernel

## How It Works

The interruption filter uses the following logic matrix:

| User Input | Agent State | Action |
|------------|-------------|--------|
| "Yeah" / "Ok" / "Hmm" | Agent is Speaking | **IGNORE**: Agent continues speaking without pausing or stopping |
| "Wait" / "Stop" / "No" | Agent is Speaking | **INTERRUPT**: Agent stops immediately and listens to the new command |
| "Yeah" / "Ok" / "Hmm" | Agent is Silent | **RESPOND**: Agent treats this as valid input (e.g., User: "Yeah." → Agent: "Great, let's continue.") |
| "Start" / "Hello" | Agent is Silent | **RESPOND**: Normal conversational behavior |

## Technical Implementation

### Architecture

The filter is integrated into the `AgentActivity` class and operates at the following points:

1. **VAD Events**: When VAD detects speech, the filter checks if a transcript is available. If not, it queues the check for when the transcript arrives.
2. **STT Transcripts**: When interim or final transcripts arrive, the filter evaluates whether to interrupt based on:
   - Whether the agent is currently speaking
   - Whether the transcript contains interrupt commands
   - Whether the transcript is only passive words

### Handling VAD/STT Latency

Since VAD is faster than STT, the filter handles "false start" interruptions by:
- Queuing interruption checks when VAD triggers before STT transcript is available
- Validating transcripts when they arrive from STT
- Only interrupting if the transcript contains actual interrupt commands

### Key Methods

- `_interrupt_by_audio_activity(transcript)`: Main interruption handler that uses the filter
- `should_interrupt(transcript, agent_is_speaking)`: Filter logic that determines if interruption should occur
- `_is_only_passive(text)`: Checks if text contains only passive acknowledgement words
- `_contains_interrupt_command(text)`: Checks if text contains interrupt command words

## Configuration

The interruption filter is enabled by default and can be configured via environment variables:

```bash
# Enable/disable the filter (default: true)
LIVEKIT_INTERRUPTION_FILTER_ENABLED=true

# Comma-separated list of passive words (default: yeah,ok,hmm,right,uh-huh,etc.)
LIVEKIT_PASSIVE_WORDS=yeah,ok,hmm,right,uh-huh,yep,yup,sure,got it

# Comma-separated list of interrupt words (default: wait,stop,no,hold on,etc.)
LIVEKIT_INTERRUPT_WORDS=wait,stop,no,hold on,pause,hang on
```

### Programmatic Configuration

You can also configure the filter programmatically:

```python
from livekit.agents.voice.interruption_filter import (
    InterruptionFilter,
    InterruptionFilterConfig,
    set_default_interruption_filter,
)

# Create custom config
config = InterruptionFilterConfig(
    passive_words=["yeah", "ok", "hmm", "right"],
    interrupt_words=["wait", "stop", "no"],
    enabled=True,
)

# Set as default
filter_instance = InterruptionFilter(config)
set_default_interruption_filter(filter_instance)
```

## Example Usage

See [`examples/voice_agents/interruption_filter_demo.py`](../examples/voice_agents/interruption_filter_demo.py) for a complete example.

```python
from livekit.agents import Agent, AgentSession, JobContext, cli
from livekit.plugins import silero

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        allow_interruptions=True,
    )

    await session.start(agent=MyAgent(), room=ctx.room)
```

## Test Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking
- **Expected Result**: Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent
- **User Action**: User says "Yeah."
- **Expected Result**: Agent processes "Yeah" as an answer and proceeds (e.g., "Okay, starting now").

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop."
- **Expected Result**: Agent cuts off immediately.

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking
- **User Action**: User says "Yeah okay but wait."
- **Expected Result**: Agent stops (because "but wait" is not in the ignore list).

## Evaluation Criteria

The implementation is evaluated on:

1. **Strict Functionality (70%)**: Does the agent continue speaking over "yeah/ok"?
   - **Fail Condition**: If the agent stops, pauses, or hiccups on "yeah" while speaking, the submission is rejected.

2. **State Awareness (10%)**: Does the agent correctly respond to "yeah" when it is *not* speaking?
   - The agent should not ignore valid short answers when silent.

3. **Code Quality (10%)**: Is the logic modular?
   - Can the list of ignored words be changed easily (e.g., environment variable or config array)?

4. **Documentation (10%)**: Clear documentation explaining how to run the agent and how the logic works.

## Implementation Details

### Default Passive Words
- yeah, yea, yes, yep, yup
- ok, okay
- hmm, hm, mm, mhm, mmhmm, mm-hmm
- uh-huh, uh huh, uhuh
- right, aha, ah, oh
- sure, got it, i see
- alright, all right

### Default Interrupt Words
- wait, stop, no
- hold on, hold up, pause, hang on
- one moment, one second
- actually, but, however
- excuse me, sorry
- question, can i, let me, i have
- what about, how about

## Debugging

The filter provides debug logging to help understand its decisions:

```python
# Enable debug logging
import logging
logging.getLogger("livekit.agents.voice.agent_activity").setLevel(logging.DEBUG)
```

The logs will show:
- Filter decision (should_interrupt: true/false)
- Filter reason (passive_acknowledgement, contains_interrupt_command, etc.)
- Transcript being evaluated

## Limitations

1. The filter relies on STT transcripts, so there may be a small delay between VAD detection and filter evaluation
2. The filter uses word-boundary matching, so variations in pronunciation may affect matching
3. The filter is language-dependent (currently optimized for English)

## Future Enhancements

Potential improvements:
- Multi-language support
- Machine learning-based classification
- Context-aware word detection (considering conversation history)
- Customizable matching strategies (fuzzy matching, phonetic matching)