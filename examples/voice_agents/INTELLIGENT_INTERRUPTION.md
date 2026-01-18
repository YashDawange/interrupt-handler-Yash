# Intelligent Interruption Handling

## Overview

The Intelligent Interruption Handling feature provides context-aware interruption management for LiveKit voice agents. It distinguishes between **passive acknowledgements** (backchanneling) and **active interruptions** based on whether the agent is currently speaking.

## Problem Statement

Previously, when the AI agent was explaining something important, LiveKit's default Voice Activity Detection (VAD) was too sensitive to user feedback. If the user said "yeah," "ok," "aha," or "hmm" (known as backchanneling) to indicate they are listening, the agent would interpret this as an interruption and abruptly stop speaking.

## Solution

The Intelligent Interruption Handler implements a logic layer that:

1. **Ignores backchanneling when agent is speaking**: If the agent is speaking and the user says "yeah", "ok", "hmm", etc., the agent continues speaking without pausing or stopping.

2. **Allows interruptions for commands**: If the user says "wait", "stop", "no" while the agent is speaking, the agent stops immediately.

3. **Responds to backchanneling when agent is silent**: When the agent is silent and the user says "yeah" or "ok", the agent treats this as valid input and responds normally.

4. **Handles mixed inputs**: If the user says "yeah wait" while the agent is speaking, the agent stops because "wait" is an interrupt command.

## Behavior Matrix

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah / Ok / Hmm" | Speaking | **IGNORE**: Agent continues speaking |
| "Wait / Stop / No" | Speaking | **INTERRUPT**: Agent stops immediately |
| "Yeah / Ok / Hmm" | Silent | **RESPOND**: Agent treats as valid input |
| "Start / Hello" | Silent | **RESPOND**: Normal conversational behavior |
| "Yeah wait" | Speaking | **INTERRUPT**: Contains interrupt command |

## Configuration

The interruption handler is **enabled by default**. You can configure it using environment variables:

### Enable/Disable

```bash
# Enable intelligent interruption (default: true)
export LIVEKIT_AGENTS_INTELLIGENT_INTERRUPTION=true
```

### Customize Backchannel Words

```bash
# Comma-separated list of words to ignore when agent is speaking
export LIVEKIT_AGENTS_BACKCHANNEL_WORDS=yeah,ok,okay,hmm,uh-huh,right,yep,sure,mhm,aha
```

### Customize Interrupt Commands

```bash
# Comma-separated list of words that always trigger interruption
export LIVEKIT_AGENTS_INTERRUPT_COMMANDS=wait,stop,no,dont,halt,pause,cancel,abort
```

## Default Words

### Backchannel Words (Ignored when agent is speaking)
- yeah, ok, okay, hmm, uh-huh, uh huh, right, yep, yup, sure, mhm, mm-hmm, mm hmm, aha, ah, mhm, uh, um

### Interrupt Commands (Always interrupt)
- wait, stop, no, don't, dont, halt, pause, cancel, abort

## Technical Implementation

### Architecture

The interruption handler is implemented as a logic layer within the agent's event loop:

1. **VAD Detection**: When VAD detects speech, it triggers an interruption check.
2. **STT Validation**: The handler waits for STT transcript to validate the interruption.
3. **State-Aware Filtering**: The handler checks:
   - Is the agent currently speaking?
   - Does the transcript contain only backchanneling words?
   - Does the transcript contain interrupt commands?
4. **Decision**: Based on the above, the handler either ignores the interruption or allows it.

### Race Condition Handling

Since VAD fires faster than STT, the handler implements a delay mechanism:
- When VAD detects speech, the interruption is queued but not executed immediately.
- The handler waits for STT transcript (with a timeout).
- Once transcript is available, it checks if the interruption should be ignored.
- If no transcript arrives within the timeout, the interruption proceeds (to avoid blocking real interruptions).

## Example Usage

See `examples/voice_agents/intelligent_interruption_agent.py` for a complete example.

```python
from livekit.agents import AgentSession

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    vad=silero.VAD.load(),
    allow_interruptions=True,  # Required for intelligent interruption
    resume_false_interruption=True,
    false_interruption_timeout=1.0,
)
```

## Test Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history.
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking.
- **Expected Result**: Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent.
- **User Action**: User says "Yeah."
- **Expected Result**: Agent processes "Yeah" as an answer and proceeds (e.g., "Okay, starting now").

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop."
- **Expected Result**: Agent cuts off immediately.

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking.
- **User Action**: User says "Yeah okay but wait."
- **Expected Result**: Agent stops (because "but wait" contains an interrupt command).

## Requirements

- `allow_interruptions=True` must be set on the AgentSession
- STT (Speech-to-Text) must be enabled for transcript validation
- VAD (Voice Activity Detection) must be enabled

## Limitations

- The handler works best with English language input. Multi-language support may require customization.
- Very short utterances (< 0.5s) may not have transcripts available in time.
- The handler relies on STT accuracy for proper classification of backchanneling vs. commands.

## Troubleshooting

### Agent still stops on "yeah"
- Check that `LIVEKIT_AGENTS_INTELLIGENT_INTERRUPTION` is set to `true`
- Verify STT is enabled and working
- Check logs for "Ignoring interruption due to backchanneling" messages

### Agent doesn't respond to "yeah" when silent
- This is expected behavior - the handler only ignores backchanneling when agent is speaking
- When agent is silent, all input is treated as valid

### Mixed inputs not working correctly
- Ensure interrupt commands are properly configured
- Check that the transcript contains the interrupt command word

## Code Location

- Handler implementation: `livekit-agents/livekit/agents/voice/interruption_handler.py`
- Integration: `livekit-agents/livekit/agents/voice/agent_activity.py`
- Example: `examples/voice_agents/intelligent_interruption_agent.py`

