# Intelligent Interruption Handling

## Overview

This implementation adds intelligent interruption handling to the LiveKit Agents framework. It allows the agent to distinguish between passive acknowledgements (backchanneling) and active interruptions based on whether the agent is currently speaking or silent.

## Problem Statement

Previously, when the AI agent was explaining something important, LiveKit's default Voice Activity Detection (VAD) was too sensitive to user feedback. If the user said "yeah," "ok," "aha," or "hmm" (known as backchanneling) to indicate they are listening, the agent would interpret this as an interruption and abruptly stop speaking.

## Solution

The implementation adds a configurable logic layer that:

1. **Ignores backchanneling when agent is speaking**: If the agent is actively speaking and the user says only backchanneling words (e.g., "yeah", "ok", "hmm"), the agent continues speaking without pausing or stopping.

2. **Processes backchanneling when agent is silent**: When the agent is silent, backchanneling words are processed normally as valid user input.

3. **Interrupts for actual commands**: If the user says a mixed sentence like "yeah wait" or "ok stop", the agent interrupts because it contains non-backchanneling words.

4. **Handles VAD-before-STT race condition**: Since VAD is faster than STT, the implementation handles cases where VAD triggers an interruption before the transcript is available. If the transcript later reveals it was only backchanneling, the agent immediately resumes.

## Implementation Details

### Configuration

The feature is configured via the `backchanneling_ignore_list` parameter in `AgentSession`:

```python
session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini",
    tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    # Configure backchanneling words to ignore when agent is speaking
    backchanneling_ignore_list=["yeah", "ok", "okay", "hmm", "hmmm", "right", "uh-huh", "aha", "mhm", "yep"],
)
```

**Default ignore list**: If not specified, the following words are ignored by default:
- `yeah`, `ok`, `okay`, `hmm`, `hmmm`, `right`, `uh-huh`, `aha`, `mhm`, `yep`

### How It Works

1. **State-Based Filtering**: The filter only applies when the agent is actively generating or playing audio. When the agent is silent, all words (including backchanneling) are processed normally.

2. **Semantic Interruption Detection**: The implementation checks if ALL words in the user's input are in the ignore list. If any word is not in the list (e.g., "yeah wait"), the agent interrupts.

3. **Real-time Processing**: The solution maintains real-time performance by:
   - Checking transcripts as they become available (interim and final)
   - Immediately resuming if backchanneling is detected after a pause
   - Using efficient word matching with normalized text comparison

### Code Structure

The implementation consists of:

1. **Configuration** (`agent_session.py`):
   - Added `backchanneling_ignore_list` to `AgentSessionOptions` dataclass
   - Added parameter to `AgentSession.__init__()` with default values
   - Integrated into session options initialization

2. **Helper Function** (`agent_activity.py`):
   - `_is_only_backchanneling()`: Checks if text contains only backchanneling words
   - Normalizes text (lowercase, removes punctuation) for comparison
   - Only returns `True` when agent is speaking AND all words are in ignore list

3. **Interruption Logic** (`agent_activity.py`):
   - Modified `_interrupt_by_audio_activity()`: Checks for backchanneling before interrupting
   - Modified `on_end_of_turn()`: Filters backchanneling at turn boundaries
   - Handles resume logic when backchanneling is detected after pause

## Example Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history.
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking.
- **Result**: ✅ Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent.
- **User Action**: User says "Yeah."
- **Result**: ✅ Agent processes "Yeah" as an answer and proceeds (e.g., "Okay, starting now").

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop."
- **Result**: ✅ Agent cuts off immediately (because "no" and "stop" are not in ignore list).

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking.
- **User Action**: User says "Yeah okay but wait."
- **Result**: ✅ Agent stops (because "but wait" contains words not in the ignore list).

## Usage Example

```python
from livekit.agents import Agent, AgentSession, JobContext, cli
from livekit.plugins import silero

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    agent = Agent(
        instructions="You are a helpful assistant. Explain things clearly and thoroughly."
    )
    
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        # Customize backchanneling words (optional)
        backchanneling_ignore_list=["yeah", "ok", "hmm", "right", "uh-huh", "mhm"],
        # Enable false interruption resume
        resume_false_interruption=True,
        false_interruption_timeout=2.0,
    )
    
    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(instructions="greet the user and explain a topic")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

## Customization

You can customize the backchanneling ignore list:

```python
# Use default list
session = AgentSession(...)  # Uses default: ["yeah", "ok", "okay", "hmm", ...]

# Use custom list
session = AgentSession(
    ...,
    backchanneling_ignore_list=["yeah", "yep", "sure", "got it"],
)

# Disable feature (empty list)
session = AgentSession(
    ...,
    backchanneling_ignore_list=[],
)
```

## Environment Variable Support

You can also configure the ignore list via environment variable:

```python
import os

backchanneling_words = os.getenv(
    "BACKCHANNELING_IGNORE_LIST",
    "yeah,ok,okay,hmm,right,uh-huh,aha,mhm,yep"
).split(",")

session = AgentSession(
    ...,
    backchanneling_ignore_list=backchanneling_words,
)
```

## Technical Notes

1. **No VAD Modification**: The implementation does not modify the low-level VAD kernel. It works as a logic handling layer within the agent's event loop.

2. **Latency**: The solution maintains real-time performance. The delay to determine if a word is "valid" or "ignored" is imperceptible.

3. **Word Matching**: Words are matched case-insensitively and punctuation is ignored. For example, "Yeah!" matches "yeah" in the ignore list.

4. **Multi-word Handling**: The implementation checks if ALL words in the user's input are in the ignore list. Mixed inputs (e.g., "yeah wait") will trigger an interruption.

5. **Integration with Existing Features**: Works seamlessly with:
   - `min_interruption_words`: Both checks are applied
   - `false_interruption_timeout`: Backchanneling detection can trigger immediate resume
   - `resume_false_interruption`: Enables audio resume when backchanneling is detected

## Testing

To test the implementation:

1. **Test ignoring backchanneling while speaking**:
   - Start agent speaking a long explanation
   - Say "yeah", "ok", "hmm" while agent is speaking
   - Verify agent continues without interruption

2. **Test processing backchanneling when silent**:
   - Wait for agent to finish speaking
   - Say "yeah" when agent asks a question
   - Verify agent processes it as valid input

3. **Test interruption with commands**:
   - Start agent speaking
   - Say "stop" or "wait" or "no"
   - Verify agent interrupts immediately

4. **Test mixed input**:
   - Start agent speaking
   - Say "yeah but wait"
   - Verify agent interrupts (because "but wait" contains non-backchanneling words)

## Files Modified

- `livekit-agents/livekit/agents/voice/agent_session.py`: Added configuration option
- `livekit-agents/livekit/agents/voice/agent_activity.py`: Added filtering logic and helper function

## Future Enhancements

Potential improvements:
- Language-specific backchanneling lists
- Machine learning-based backchanneling detection
- Configurable semantic analysis for interruption commands
- Support for phrase-level backchanneling (e.g., "I see", "got it")

