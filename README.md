# Intelligent Interruption Handling

<<<<<<< Updated upstream
Demo Video - [https://drive.google.com/file/d/1fSCWHF4F6WUgtLt2yAQAg7kh9mBni8CD/view?usp=sharing](Demo)

This implementation adds context-aware interruption handling to LiveKit agents, allowing them to distinguish between passive acknowledgements (backchanneling) and active interruptions based on whether the agent is currently speaking or silent.

## Problem

LiveKit's default Voice Activity Detection (VAD) is too sensitive. When the AI agent is explaining something important, user feedback like "yeah," "ok," "aha," or "hmm" (known as backchanneling) is misinterpreted as an interruption, causing the agent to abruptly stop speaking.


=======
This implementation adds context-aware interruption handling to LiveKit agents, allowing them to distinguish between passive acknowledgements (backchanneling) and active interruptions based on whether the agent is currently speaking or silent.

## Problem

LiveKit's default Voice Activity Detection (VAD) is too sensitive. When the AI agent is explaining something important, user feedback like "yeah," "ok," "aha," or "hmm" (known as backchanneling) is misinterpreted as an interruption, causing the agent to abruptly stop speaking.


>>>>>>> Stashed changes
## Running the Example
1. Clone the repository and install the dependencies

```bash
git clone https://github.com/Dark-Sys-Jenkins/agents-assignment.git
cd agents-assignment
uv sync --all-extras --dev
```
2. Set up environment variables and update the .env file with your LiveKit credentials and model provider API keys.
```bash
cp .env.example .env
```

3. Run the example agent
```bash
uv run python examples/voice_agents/intelligent_interruption_agent.py console
```

## Solution

The intelligent interruption handler implements a logic layer that:

1. **Ignores backchanneling words when agent is speaking**: Words like "yeah", "ok", "hmm" are filtered out when the agent is actively generating or playing audio.

2. **Responds to backchanneling when agent is silent**: The same words are treated as valid input when the agent is not speaking, allowing natural conversation flow.

3. **Always interrupts for commands**: Words like "stop", "wait", "no" always interrupt the agent, regardless of state.

4. **Handles mixed inputs**: If the user says something like "yeah okay but wait", the agent will interrupt because "wait" is a command word.

## Implementation Details

### Core Components

1. **InterruptionHandler** (`livekit/agents/voice/interruption_handler.py`):
   - Configurable list of ignore words (backchanneling)
   - Configurable list of interrupt words (commands)
   - State-aware filtering logic
   - Word extraction and normalization
   - **Embedding-based semantic similarity checking** (optional, using OpenAI embeddings)
   - Hybrid approach: embeddings first, word matching as fallback

2. **AgentActivity Integration** (`livekit/agents/voice/agent_activity.py`):
   - Integrated into the `_interrupt_by_audio_activity` method
   - Handles false start interruptions (VAD triggers before STT confirms)
   - Processes interim and final transcripts with intelligent filtering

### Key Features

- **Configurable Ignore List**: Define words to ignore when agent is speaking (default: "yeah", "ok", "hmm", "uh-huh", "right", etc.)
- **Configurable Interrupt List**: Define words that always interrupt (default: "stop", "wait", "no", "halt", "cancel", "pause")
- **State-Based Filtering**: Only applies ignore logic when agent is actively speaking
- **False Start Handling**: Handles cases where VAD triggers before STT confirms the word is ignorable
- **Environment Variable Support**: Configure ignore/interrupt words via environment variables
- **Embedding-Based Semantic Checking**: Optional OpenAI embedding-based detection for more robust backchanneling identification
- **Hybrid Approach**: Uses embeddings when available, falls back to word matching for reliability

## Configuration

### Environment Variables

You can configure the ignore and interrupt words using environment variables:

```bash
# Comma-separated list of words to ignore when agent is speaking
LIVEKIT_AGENT_IGNORE_WORDS="yeah,ok,okay,hmm,uh-huh,right,sure,yep,mhm,aha"

# Comma-separated list of words that should always interrupt
LIVEKIT_AGENT_INTERRUPT_WORDS="stop,wait,no,halt,cancel,pause"

# Enable embedding-based semantic similarity checking (optional)
LIVEKIT_AGENT_USE_EMBEDDINGS=true

# Set similarity threshold for embeddings (0.0-1.0, higher = more strict)
# Default: 0.75
LIVEKIT_AGENT_EMBEDDING_THRESHOLD=0.75

# Set OpenAI embedding model to use
# Default: text-embedding-3-small
LIVEKIT_AGENT_EMBEDDING_MODEL=text-embedding-3-small

# OpenAI API key (required if using embeddings)
OPENAI_API_KEY=your_openai_api_key_here
```

### Embedding-Based Semantic Checking

The interruption handler now supports **embedding-based semantic similarity checking** using OpenAI embeddings. This provides a more robust way to detect backchanneling by understanding the semantic meaning of user input, not just exact word matches.

#### Benefits of Embedding-Based Checking

- **Handles Variations**: Recognizes semantic equivalents like "gotcha", "I understand", "makes sense" as backchanneling
- **More Robust**: Understands context and meaning, not just exact word matches
- **Handles Paraphrases**: Catches variations like "that's right", "exactly", "absolutely" as backchanneling
- **Hybrid Approach**: Falls back to word-based matching if embeddings fail or are unavailable

#### How It Works

1. When embeddings are enabled, the handler:
   - Generates embeddings for the user's transcript using OpenAI's embedding API
   - Compares it against cached embeddings of known backchanneling phrases
   - Uses cosine similarity to determine if the transcript is semantically similar to backchanneling
   - If similarity exceeds the threshold (default: 0.75), treats it as backchanneling

2. **Caching**: 
   - Backchanneling embeddings are initialized once and cached
   - Transcript embeddings are cached for 1 hour to reduce API calls
   - Significantly improves performance and reduces costs

3. **Fallback**:
   - If embeddings fail or are disabled, automatically falls back to word-based matching
   - Ensures reliability even if the OpenAI API is unavailable

#### Performance Considerations

- **First Use**: Initial embedding generation for backchanneling phrases happens on first use (one-time cost)
- **Subsequent Uses**: Transcript embeddings are cached, making subsequent checks fast
- **API Costs**: Minimal - embeddings are cached and only generated once per unique transcript
- **Latency**: Embedding checks add ~50-200ms latency on first use, then use cached results

#### When to Use Embeddings

- **Recommended for**: Production environments where you want maximum accuracy
- **Not needed for**: Simple use cases where word-based matching is sufficient
- **Requires**: OpenAI API key and internet connection

### Programmatic Configuration

The `InterruptionHandler` can also be configured programmatically:

```python
from livekit.agents.voice.interruption_handler import InterruptionHandler

handler = InterruptionHandler(
    ignore_words=["yeah", "ok", "hmm"],
    interrupt_words=["stop", "wait"],
    use_embeddings=True,
    embedding_similarity_threshold=0.75,
    embedding_model="text-embedding-3-small"
)
```

Note: The handler is automatically initialized in `AgentActivity`. For custom configurations, you would need to modify the `AgentActivity.__init__` method.

## Usage

The intelligent interruption handler is **automatically enabled** for all agents. No additional configuration is required - it works out of the box with the existing LiveKit agent framework.

### Example Agent

See `examples/voice_agents/intelligent_interruption_agent.py` for a complete example.

```python
from livekit.agents import voice_assistant

assistant = voice_assistant.VoiceAssistant(
    vad=vad.VAD.load(),
    stt=stt.STT.load(),
    llm=llm.LLM.load(),
    tts=tts.TTS.load(),
)
```

The interruption handler is automatically integrated and will:
- Ignore "yeah", "ok", "hmm" when the agent is speaking
- Respond to these words when the agent is silent
- Always interrupt for "stop", "wait", "no"

## Behavior Matrix

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah" / "Ok" / "Hmm" | Agent is Speaking | **IGNORE** - Agent continues speaking |
| "Wait" / "Stop" / "No" | Agent is Speaking | **INTERRUPT** - Agent stops immediately |
| "Yeah" / "Ok" / "Hmm" | Agent is Silent | **RESPOND** - Agent processes as valid input |
| "Start" / "Hello" | Agent is Silent | **RESPOND** - Normal conversational behavior |
| "Yeah okay but wait" | Agent is Speaking | **INTERRUPT** - Contains interrupt word |

## Test Scenarios

### Scenario 1: The Long Explanation
- **Context**: Agent is reading a long paragraph about history
- **User Action**: User says "Okay... yeah... uh-huh" while the agent is talking
- **Result**: Agent audio does not break. It ignores the user input completely.

### Scenario 2: The Passive Affirmation
- **Context**: Agent asks "Are you ready?" and goes silent
- **User Action**: User says "Yeah."
- **Result**: Agent processes "Yeah" as an answer and proceeds (e.g., "Okay, starting now")

### Scenario 3: The Correction
- **Context**: Agent is counting "One, two, three..."
- **User Action**: User says "No stop."
- **Result**: Agent cuts off immediately.

### Scenario 4: The Mixed Input
- **Context**: Agent is speaking
- **User Action**: User says "Yeah okay but wait."
- **Result**: Agent stops (because "but wait" contains interrupt words).

## Technical Details

### Detection Methods

The interruption handler uses a **hybrid approach** with two detection methods:

#### 1. Word-Based Matching (Default)
- Fast and lightweight
- Exact word matching with fuzzy variations (e.g., "mhmm" → "mhm")
- No external dependencies
- Works offline

<<<<<<< Updated upstream
#### 2. Embedding-Based Semantic Similarity
=======
#### 2. Embedding-Based Semantic Similarity (Optional)
>>>>>>> Stashed changes
- More robust and accurate
- Understands semantic meaning, not just exact words
- Handles variations and paraphrases
- Requires OpenAI API key
- Uses cosine similarity to compare embeddings
- Falls back to word matching if unavailable

The handler tries embedding-based checking first (if enabled), then falls back to word-based matching for reliability.

### False Start Interruption Handling

One challenge is that VAD (Voice Activity Detection) can trigger before STT (Speech-to-Text) confirms what the user said. The implementation handles this by:

1. When VAD triggers but no transcript is available yet, the interruption is marked as "pending"
2. A timer (800ms) is set to wait for STT confirmation
3. When STT provides the transcript:
   - If it's an ignorable word (via word matching or embeddings), the pending interruption is cancelled
   - If it's a command word, the interruption proceeds
   - If no transcript arrives within the timeout, the interruption proceeds (handles STT failures)

### State Detection

The agent determines if it's speaking by checking:
- `_current_speech` is not None and not interrupted
- `_current_speech.allow_interruptions` is True
- `_session.agent_state == "speaking"`



## Files Modified
<<<<<<< Updated upstream
=======

1. `livekit/agents/voice/interruption_handler.py` - New module for interruption logic
2. `livekit/agents/voice/agent_activity.py` - Integrated interruption handler into agent activity

## Files Added

1. `examples/voice_agents/intelligent_interruption_agent.py` - Example agent demonstrating the functionality
2. `.env.example` - Example environment variables
>>>>>>> Stashed changes

1. `livekit/agents/voice/interruption_handler.py` - New module for interruption logic
2. `livekit/agents/voice/agent_activity.py` - Integrated interruption handler into agent activity

<<<<<<< Updated upstream
## Files Added

1. `examples/voice_agents/intelligent_interruption_agent.py` - Example agent demonstrating the functionality
2. `.env.example` - Example environment variables

=======


## Notes

- The interruption handler does not modify the low-level VAD kernel
- It operates as a logic handling layer within the agent's event loop
- The solution handles real-time constraints with minimal latency
- Works with both streaming and non-streaming STT implementations
- Embedding-based checking is optional and falls back to word matching if unavailable
- Embeddings are cached to minimize API calls and improve performance
- Requires `numpy` for optimal performance (falls back to manual cosine similarity if unavailable)

>>>>>>> Stashed changes
