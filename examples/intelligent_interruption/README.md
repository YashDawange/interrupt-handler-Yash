# Intelligent Interruption Handling

This example demonstrates intelligent interruption handling for LiveKit agents that distinguishes between backchanneling (passive acknowledgements like "yeah", "ok", "hmm") and active interruptions (commands like "stop", "wait", "no") based on whether the agent is currently speaking.

## Overview

The problem: When an AI agent is explaining something important, LiveKit's default Voice Activity Detection (VAD) is too sensitive to user feedback. If the user says "yeah," "ok," or "hmm" to indicate they are listening (backchanneling), the agent interprets this as an interruption and abruptly stops speaking.

The solution: This implementation adds a logic layer that is context-aware. The agent distinguishes between a "passive acknowledgement" and an "active interruption" based on whether the agent is currently speaking or silent.

## Core Logic

The system handles the following logic matrix:

| User Input | Agent State | Desired Behavior |
|------------|-------------|------------------|
| "Yeah / Ok / Hmm" | Agent is Speaking | **IGNORE**: The agent continues speaking without pausing or stopping |
| "Wait / Stop / No" | Agent is Speaking | **INTERRUPT**: The agent stops immediately and listens to the new command |
| "Yeah / Ok / Hmm" | Agent is Silent | **RESPOND**: The agent treats this as valid input (e.g., User: "Yeah." → Agent: "Great, let's continue.") |
| "Start / Hello" | Agent is Silent | **RESPOND**: Normal conversational behavior |

## Features

1. **Configurable Ignore List**: Define a list of words (e.g., ['yeah', 'ok', 'hmm', 'right', 'uh-huh']) that act as "soft" inputs.

2. **State-Based Filtering**: The filter only applies when the agent is actively generating or playing audio.

3. **Semantic Interruption**: If the user says a mixed sentence like "Yeah wait a second," this contains a command ("wait"). The agent must interrupt in this case.

4. **No VAD Modification**: Does not rewrite the low-level VAD kernel. Implements this as a logic handling layer within the agent's event loop.

## Installation

1. Ensure you have the required dependencies installed:
   ```bash
   uv sync --all-extras --dev
   ```

2. Set up your environment variables in a `.env` file (see `.env.example`):
   ```bash
   LIVEKIT_URL="wss://your-project.livekit.cloud"
   LIVEKIT_API_KEY="your_api_key"
   LIVEKIT_API_SECRET="your_api_secret"
   OPENAI_API_KEY="sk-xxx"
   DEEPGRAM_API_KEY="your_deepgram_key"
   CARTESIA_API_KEY="your_cartesia_key"
   ```

3. Optionally configure interruption words:
   ```bash
   INTERRUPTION_IGNORE_WORDS="yeah,ok,hmm,right,uh-huh,yep,okay"
   INTERRUPTION_COMMAND_WORDS="stop,wait,no,hold on"
   ```

## Usage

### Running the Agent

Run the agent in console mode for testing:
```bash
uv run examples/intelligent_interruption/agent_with_interruption.py console
```

Or run in development mode:
```bash
uv run examples/intelligent_interruption/agent_with_interruption.py dev
```

### How It Works

1. **State Tracking**: The handler tracks the agent's speaking state by listening to `agent_state_changed` events.

2. **Transcript Analysis**: When user input is detected, the handler:
   - Normalizes the transcript to lowercase
   - Extracts individual words
   - Checks if ALL words are in the ignore list (if agent is speaking)
   - Checks if ANY word is in the command list (always interrupts)

3. **Interruption Filtering**: The handler intercepts the `_interrupt_by_audio_activity()` method and:
   - If agent is speaking and input is backchanneling → ignores the interruption
   - If agent is speaking and input contains commands → allows interruption
   - If agent is silent → processes all input normally

## Example Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history.
- **User Action**: User says "Okay... yeah... uh-huh" while Agent is talking.
- **Result**: Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent.
- **User Action**: User says "Yeah."
- **Result**: Agent processes "Yeah" as an answer and proceeds (e.g., "Okay, starting now").

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop."
- **Result**: Agent cuts off immediately.

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking.
- **User Action**: User says "Yeah okay but wait."
- **Result**: Agent stops (because "but wait" contains "wait" which is a command word).

## Configuration

### Environment Variables

- `INTERRUPTION_IGNORE_WORDS`: Comma-separated list of backchanneling words to ignore when agent is speaking.
  - Default: `"yeah,ok,hmm,right,uh-huh,uh huh,yep,yeah yeah,okay,uh,um,mm-hmm,mm hmm"`

- `INTERRUPTION_COMMAND_WORDS`: Comma-separated list of command words that should always interrupt.
  - Default: `"stop,wait,no,hold on,hold,stop it,wait a second,wait a minute"`

### Programmatic Configuration

You can also configure the handler programmatically:

```python
from interruption_handler import IntelligentInterruptionHandler

handler = IntelligentInterruptionHandler(
    ignore_words=["yeah", "ok", "hmm", "right"],
    command_words=["stop", "wait", "no"]
)
```

## Implementation Details

### Architecture

The implementation consists of two main components:

1. **`interruption_handler.py`**: Core filtering logic that analyzes transcripts and determines if interruptions should be ignored.

2. **`agent_with_interruption.py`**: Example agent that integrates the interruption handler by:
   - Tracking agent speaking state via events
   - Intercepting interruption calls via monkey-patching
   - Applying filtering logic before allowing interruptions

### Interception Method

Since `AgentActivity` is not part of the public API, the implementation uses monkey-patching to intercept the `_interrupt_by_audio_activity()` method. This allows us to:

- Check the interruption handler before allowing interruptions
- Maintain compatibility with the existing framework
- Avoid modifying core framework code

### State Management

The handler tracks agent state by:
- Listening to `agent_state_changed` events
- Updating internal state when agent transitions to/from "speaking"
- Using this state to determine if filtering should be applied

## Testing

To test the implementation, try the following scenarios:

1. **Backchanneling while speaking**: Start the agent explaining something, then say "yeah" or "ok" - the agent should continue speaking.

2. **Command while speaking**: Start the agent explaining something, then say "stop" - the agent should interrupt immediately.

3. **Backchanneling while silent**: Wait for the agent to finish speaking and ask a question, then say "yeah" - the agent should respond to "yeah" as valid input.

4. **Mixed input**: Start the agent speaking, then say "yeah but wait" - the agent should interrupt because "wait" is a command word.

## Limitations

1. **VAD Timing**: VAD may trigger before STT provides a transcript. The implementation uses the most recent transcript available, but there may be edge cases where VAD triggers on very short utterances before STT can process them.

2. **Language Support**: The current implementation is optimized for English. Multi-language support would require language-specific word lists.

3. **Context Awareness**: The implementation is based on word matching, not semantic understanding. More sophisticated implementations could use NLP to better understand intent.

## Troubleshooting

### Agent still interrupts on "yeah"
- Check that the agent state is being tracked correctly (look for "Agent state changed" logs)
- Verify that `INTERRUPTION_IGNORE_WORDS` includes the word you're testing
- Check logs to see if the interruption handler is being called

### Agent doesn't respond to "yeah" when silent
- This is expected behavior - when the agent is silent, all input is processed normally
- The handler only filters when the agent is speaking

### Import errors
- Ensure you're running from the repository root
- Check that `sys.path` modifications in the agent file are correct
- Verify that all dependencies are installed

## Contributing

This is an example implementation for the LiveKit Agents assignment. To extend it:

1. Add more sophisticated semantic analysis
2. Support multiple languages
3. Add configuration for different conversation contexts
4. Implement learning from user behavior

## License

This example follows the same license as the LiveKit Agents framework.

