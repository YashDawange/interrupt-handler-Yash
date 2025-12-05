# LiveKit Intelligent Interruption Handling

This project implements a context-aware interruption handling logic for LiveKit agents. It allows the agent to ignore "backchannel" words (like "yeah", "ok", "hmm") while speaking, preventing unnecessary interruptions, while still responding to them when silent.

### Logic Matrix

| User Input | Agent State | Desired Behavior | Status |
|------------|-------------|------------------|---------|
| "Yeah/Ok/Hmm" | Speaking | IGNORE - Agent continues | ✅ Implemented & Tested |
| "Wait/Stop/No" | Speaking | INTERRUPT - Agent stops | ✅ Implemented & Tested |
| "Yeah/Ok/Hmm" | Silent | RESPOND - Treated as input | ✅ Implemented & Tested |
| "Start/Hello" | Silent | RESPOND - Normal behavior | ✅ Implemented & Tested |

### Test Results

| Test File                         | Test Name                       | Result | Progress |
|----------------------------------|----------------------------------|--------|----------|
| tests/test_interruption.py       | test_ignored_interruption        | PASSED | 20%      |
| tests/test_interruption.py       | test_valid_interruption          | PASSED | 40%      |
| tests/test_interruption.py       | test_silent_response             | PASSED | 60%      |
| tests/test_mixed_interruption.py | test_mixed_input_interruption    | PASSED | 80%      |
| tests/test_mixed_interruption.py | test_all_ignored_words           | PASSED | 100%     |


### Key Features Implemented

1. **Configurable Ignore List**: Define words via `ignored_words` parameter
2. **State-Based Filtering**: Only applies when agent is actively speaking
3. **Semantic Interruption**: Mixed input like "Yeah wait" triggers interruption
4. **No VAD Modification**: Logic layer within agent event loop
5. **Real-time Performance**: Zero perceptible latency
6. **No Agent Stuttering**: Agent continues seamlessly over ignored words

## How it Works

The solution implements filtering at multiple points in the LiveKit agent pipeline:

## How it Works

The solution implements filtering at multiple points in the LiveKit agent pipeline:

### 1. Transcript Filtering (`on_final_transcript`)
When a transcript arrives:
- Checks if agent is in "speaking" state
- Extracts and normalizes words from transcript
- If ALL words are in `ignored_words` list → Ignore transcript
- If ANY word is not ignored → Process normally (interrupt)

### 2. End-of-Turn Filtering (`on_end_of_turn`)
Prevents ignored transcripts from being added to conversation:
- Checks during turn completion
- Prevents messages from being added during session closing
- Ensures ignored words don't appear in chat history

### 3. Commit-Turn Protection (`audio_recognition`)
Tracks ignored transcripts to prevent re-emission:
- Maintains `_ignored_transcripts` set
- Prevents duplicate processing when flushing buffers

### Critical Implementation Detail

**No Agent Pausing**: The agent's audio output is never paused or stopped when an ignored word is detected. The filtering happens at the transcript level BEFORE any interruption logic is triggered. This ensures seamless continuation of speech.

## Configuration

Configure `ignored_words` when creating an `AgentSession`:

```python
session = AgentSession(
    vad=silero.VAD.load(),
    stt=deepgram.STT(),
    llm=openai.LLM(),
    tts=elevenlabs.TTS(),
    ignored_words=["yeah", "ok", "okay", "hmm", "right", "uh"],  # Customize here
)
```

### Lists of Ignore Words
```python
ignored_words=["yeah", "ok", "okay", "hmm", "right"]
```

## Test Coverage

All assignment scenarios are covered with automated tests:

### Test Suite 1: Core Scenarios (`test_interruption.py`)

1. **test_ignored_interruption** - Scenario 1: Long Explanation
   - Agent speaks, user says "Yeah"
   - Expected: Agent continues, "Yeah" NOT in conversation
   - Status: ✅ PASSING

2. **test_valid_interruption** - Scenario 3: The Correction
   - Agent speaks, user says "Stop"
   - Expected: Agent interrupts immediately, "Stop" in conversation
   - Status: ✅ PASSING

3. **test_silent_response** - Scenario 2: Passive Affirmation
   - Agent silent, user says "Yeah"
   - Expected: Agent processes "Yeah" as valid input
   - Status: ✅ PASSING

### Test Suite 2: Mixed Input (`test_mixed_interruption.py`)

4. **test_mixed_input_interruption** - Scenario 4: The Mixed Input
   - Agent speaks, user says "Yeah okay but wait"
   - Expected: Agent interrupts (contains non-ignored words)
   - Status: ✅ PASSING

5. **test_all_ignored_words**
   - Agent speaks, user says "Yeah okay hmm" (all ignored)
   - Expected: Completely ignored
   - Status: ✅ PASSING

### Running Tests

```bash
# Run all interruption tests
pytest tests/test_interruption.py tests/test_mixed_interruption.py -v

# Expected output: 5 passed
```

## Running the Example Agent

1. Install dependencies:
## Running the Example Agent

1. Install dependencies:
    ```bash
    cd agents-assignment
    pip install -e livekit-agents
    pip install -e "livekit-plugins/livekit-plugins-openai"
    pip install -e "livekit-plugins/livekit-plugins-deepgram"
    pip install -e "livekit-plugins/livekit-plugins-elevenlabs"
    pip install -e "livekit-plugins/livekit-plugins-silero"
    pip install pytest pytest-asyncio
    ```

2. Set up environment variables:
    ```bash
    export LIVEKIT_URL=<your-livekit-url>
    export LIVEKIT_API_KEY=<your-api-key>
    export LIVEKIT_API_SECRET=<your-api-secret>
    export OPENAI_API_KEY=<your-openai-key>
    export DEEPGRAM_API_KEY=<your-deepgram-key>
    export ELEVENLABS_API_KEY=<your-elevenlabs-key>
    ```

3. Run an example agent:
    ```bash
    python examples/voice_agents/interrupt_test_agent.py dev
    ```

4. Connect using the LiveKit Playground or your frontend

## Files Modified

The implementation touches the following core files:

- **`livekit-agents/livekit/agents/voice/agent_activity.py`**
  - Added ignore logic in `on_final_transcript()`
  - Added ignore logic in `on_end_of_turn()`
  - Added ignore logic in `_interrupt_by_audio_activity()` (original location)

- **`livekit-agents/livekit/agents/voice/audio_recognition.py`**
  - Added `_ignored_transcripts` tracking set
  - Modified `commit_user_turn()` to check ignored transcripts
  - Modified `clear_user_turn()` to reset ignored transcripts

- **`tests/test_interruption.py`** (NEW)
  - Core test scenarios covering the logic matrix

- **`tests/test_mixed_interruption.py`** (NEW)
  - Mixed input and edge case scenarios