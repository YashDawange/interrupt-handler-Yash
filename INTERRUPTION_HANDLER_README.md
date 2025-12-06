# Intelligent Interruption Handler

## Overview

This implementation adds context-aware interruption handling to LiveKit agents, distinguishing between passive acknowledgements (backchanneling) and active interruptions based on the agent's speaking state.

**Important**: This is implemented as a **standalone example agent** using only public APIs. No framework code was modified.

## Problem Statement

Previously, when the AI agent was explaining something important, LiveKit's default Voice Activity Detection (VAD) was too sensitive to user feedback. If the user said "yeah," "ok," "hmm," or other backchanneling words to indicate they were listening, the agent would interpret this as an interruption and abruptly stop speaking.

## Solution

The intelligent interruption handler implements a logic layer that:

1. **Tracks agent state**: Monitors whether the agent is currently speaking or silent
2. **Filters backchanneling**: Ignores passive acknowledgements when the agent is speaking
3. **Allows real interruptions**: Still interrupts for actual commands like "wait," "stop," "no"
4. **Handles mixed inputs**: Detects interruption words even in mixed sentences (e.g., "yeah wait")

## Core Logic Matrix

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah / Ok / Hmm" | Speaking | **IGNORE**: Agent continues speaking (resumes if interrupted) |
| "Wait / Stop / No" | Speaking | **INTERRUPT**: Agent stops immediately and listens |
| "Yeah / Ok / Hmm" | Silent | **RESPOND**: Agent treats this as valid input |
| "Start / Hello" | Silent | **RESPOND**: Normal conversational behavior |

## Implementation Details

### Architecture

The solution is implemented as a **standalone example agent** (`examples/voice_agents/interruption_handler_agent.py`) that uses only public APIs:

1. **`InterruptionHandler` class**: 
   - Tracks agent speaking state via `agent_state_changed` events
   - Maintains configurable lists of backchanneling and interruption words
   - Analyzes transcripts to determine if they are backchanneling
   - Handles mixed inputs and semantic analysis

2. **`IntelligentInterruptionAgent` class**:
   - Listens to `user_input_transcribed` events (both interim and final)
   - Detects backchanneling while agent is speaking
   - Uses `clear_user_turn()` to prevent processing backchanneling input
   - Raises `StopResponse` in `on_user_turn_completed` to skip reply generation
   - Leverages existing `agent_false_interruption` event and resume mechanism

### Key Features

1. **Configurable Ignore List**: 
   - Default backchanneling words: `yeah`, `ok`, `okay`, `hmm`, `uh-huh`, `right`, `sure`, `yep`, `yup`, `mhm`, `aha`, `got it`, `alright`, etc.
   - Configurable via environment variable `LIVEKIT_BACKCHANNELING_WORDS` (comma-separated)

2. **Interruption Words**:
   - Default interruption words: `wait`, `stop`, `no`, `don't`, `halt`, `pause`, `hold on`, `cancel`, etc.
   - Configurable via environment variable `LIVEKIT_INTERRUPTION_WORDS` (comma-separated)

3. **State-Based Filtering**:
   - Filter only applies when agent is actively speaking
   - When agent is silent, all user input is processed normally

4. **Semantic Interruption Detection**:
   - Handles mixed sentences like "Yeah wait a second" - detects "wait" and interrupts
   - Uses word boundary matching to avoid false positives

5. **VAD/STT Race Condition Handling**:
   - VAD can trigger before STT completes transcription
   - Solution handles both interim and final transcripts
   - Uses `clear_user_turn()` when backchanneling is detected
   - Leverages `StopResponse` to prevent reply generation
   - Uses existing false interruption resume mechanism

## Usage

### Running the Example

The interruption handler is implemented as a standalone example agent:

```bash
# Run the example agent
python examples/voice_agents/interruption_handler_agent.py dev
```

### Configuration

You can customize the behavior via environment variables:

```bash
# Custom backchanneling words (comma-separated)
export LIVEKIT_BACKCHANNELING_WORDS="yeah,ok,hmm,right,sure"

# Custom interruption words (comma-separated)
export LIVEKIT_INTERRUPTION_WORDS="wait,stop,no,halt"
```

### Key Session Settings

The example agent uses these important session settings:

```python
session = AgentSession(
    # ... other settings ...
    # Enable false interruption resume - this is key for handling backchanneling
    resume_false_interruption=True,
    false_interruption_timeout=0.5,  # Short timeout for quick resume
)
```

### How It Works

1. **State Tracking**: The handler listens to `agent_state_changed` events to track when the agent is speaking vs. listening.

2. **Transcript Monitoring**: When `user_input_transcribed` events fire (both interim and final):
   - If agent is speaking and transcript is backchanneling → mark for handling
   - If final transcript is backchanneling → call `clear_user_turn()` to prevent processing

3. **Turn Completion**: In `on_user_turn_completed`:
   - If the transcript is backchanneling and agent was speaking → raise `StopResponse` to skip reply generation
   - This prevents the agent from generating a response to backchanneling

4. **False Interruption Resume**: 
   - The existing `resume_false_interruption` mechanism handles resuming speech
   - When backchanneling is detected, the agent resumes its previous speech seamlessly

## Test Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking
- **Expected Result**: Agent audio resumes quickly. Backchanneling is ignored.

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
- **Expected Result**: Agent stops (because "but wait" contains an interruption word).

## Technical Details

### Public APIs Used

The implementation uses only public APIs:

- `AgentSession.on("agent_state_changed")` - Track agent state
- `AgentSession.on("user_input_transcribed")` - Monitor user transcripts
- `AgentSession.on("agent_false_interruption")` - Handle false interruptions
- `AgentSession.clear_user_turn()` - Clear backchanneling input
- `Agent.on_user_turn_completed()` - Skip processing backchanneling
- `StopResponse` exception - Prevent reply generation

### Code Structure

```
examples/voice_agents/
└── interruption_handler_agent.py    # Standalone example agent
    ├── InterruptionHandler          # Utility class for filtering logic
    └── IntelligentInterruptionAgent # Agent with interruption handling
```

### Limitations

1. **VAD Timing**: Since VAD triggers before STT completes, there may be a brief pause before resume. The `false_interruption_timeout` is set to 0.5s to minimize this.

2. **Language Support**: Currently optimized for English. Multi-language support would require language-specific backchanneling word lists.

3. **STT Accuracy**: Relies on accurate transcription. Very poor STT quality might affect filtering accuracy.

4. **Resume Mechanism**: Uses the existing false interruption resume mechanism, which may have a brief pause. This is the best achievable with public APIs without modifying the framework.

## Why This Approach?

This implementation follows the assignment requirements:

✅ **No Framework Modification**: All logic is in a standalone example agent  
✅ **Public APIs Only**: Uses only documented public APIs  
✅ **Logic Layer**: Implements filtering as a logic handling layer in the agent's event loop  
✅ **Configurable**: Word lists can be customized via environment variables  
✅ **Non-Breaking**: Doesn't affect other agents or framework behavior  

## Future Enhancements

Potential improvements:

1. **Language-specific word lists**: Support for multiple languages
2. **Context-aware filtering**: Use LLM to determine if input is backchanneling
3. **Confidence thresholds**: Only ignore high-confidence backchanneling detections
4. **Customizable sensitivity**: Allow fine-tuning of filtering aggressiveness

## Testing

To test the implementation:

1. Run the example agent: `python examples/voice_agents/interruption_handler_agent.py dev`
2. While the agent is speaking, say backchanneling words ("yeah", "ok", "hmm")
3. Verify the agent resumes quickly without generating a reply
4. While the agent is speaking, say interruption words ("wait", "stop")
5. Verify the agent stops immediately
6. When the agent is silent, say "yeah" and verify it responds appropriately

## License

This implementation is part of the LiveKit agents examples and follows the same license terms.
