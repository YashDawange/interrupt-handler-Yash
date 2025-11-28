# Intelligent Interruption Handling

## Problem
When users say "yeah," "ok," or "hmm" (passive listening cues), the agent would incorrectly stop speaking.

## Solution
Implemented a pattern-based filter that distinguishes between:
- **Soft interruptions** (yeah, ok, hmm) → Ignored when agent is speaking
- **Hard interruptions** (stop, wait, no) → Always interrupt the agent
- **Mixed inputs** (yeah but wait) → Treated as hard interruptions

## Implementation Approach

### 1. Created Filter Class
**File**: `livekit-agents/livekit/agents/voice/soft_interruption_filter.py`
- Uses regex patterns to match soft interruption words
- Provides `should_suppress_interruption()` method
- Configurable pattern list

### 2. Modified AgentSession
**File**: `livekit-agents/livekit/agents/voice/agent_session.py`
- Added `enable_soft_interrupt_filtering` parameter (default: True)
- Added `soft_interrupt_patterns` parameter for custom patterns
- Creates `SoftInterruptionFilter` instance

### 3. Modified AgentActivity
**File**: `livekit-agents/livekit/agents/voice/agent_activity.py`
- Added `_should_filter_soft_interruption()` helper method
- Modified `on_interim_transcript()` - filters soft interruptions before processing
- Modified `on_final_transcript()` - filters soft interruptions before processing
- Modified `on_vad_inference_done()` - skips VAD when using STT + filtering
- Modified `_interrupt_by_audio_activity()` - checks filter before interrupting

### 4. Created Demo Agent
**File**: `examples/voice_agents/smart_interruption_demo.py`
- Agent named "Alex" for testing
- Includes function tools: `explain_topic()`, `pose_question()`, `enumerate_items()`

## How It Works

```
User speaks → STT transcribes → Check if agent is speaking
                                          ↓
                              YES: Is text soft interruption?
                                   YES → Ignore, continue speaking
                                   NO → Stop immediately
                                          ↓
                              NO: Process as normal input
```

## Setup

### 1. Install Dependencies

```bash
cd /Users/parvathanenimokshith/Downloads/Aparna/agents-assignment

# Install required packages
pip install -e livekit-agents
pip install livekit-plugins-deepgram
pip install livekit-plugins-openai
pip install livekit-plugins-cartesia
pip install livekit-plugins-silero
pip install livekit-plugins-turn-detector
pip install python-dotenv
```

Or use the requirements file:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file in `examples/voice_agents/`:

```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
DEEPGRAM_API_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
```

### 3. Run the Agent

```bash
cd examples/voice_agents
python smart_interruption_demo.py dev
```

### 4. Connect and Test

Connect via: https://agents-playground.livekit.io/

## Test Scenarios

**Scenario 1 - Long Explanation:**
1. Say: "Explain quantum physics"
2. While agent talks, say "yeah" multiple times
3. Expected: Agent continues without stopping

**Scenario 2 - Question Response:**
1. Say: "Ask me if I'm ready"
2. Agent asks and waits
3. Say: "yeah"
4. Expected: Agent responds to your answer

**Scenario 3 - Real Interruption:**
1. Say: "Count to 20"
2. While counting, say: "stop"
3. Expected: Agent stops immediately

**Scenario 4 - Mixed Input:**
1. While agent is speaking
2. Say: "okay but wait"
3. Expected: Agent stops (contains "wait")

## Configuration

### Default Soft Words
- yeah, yep
- ok, okay
- hmm, mhm
- uh-huh
- right, sure, alright
- aha
- got it

### Custom Configuration

```python
from livekit.agents import AgentSession

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4o-mini",
    tts="cartesia/sonic-2",
    turn_detection="stt",  # Required
    enable_soft_interrupt_filtering=True,
    soft_interrupt_patterns=[  # Optional custom patterns
        r"^yeah\.?$",
        r"^ok(ay)?\.?$",
        r"^I\s+see\.?$",
    ],
)
```

## Key Requirements

- Must use `turn_detection="stt"` for transcript-based filtering
- Set `enable_soft_interrupt_filtering=True` to enable the feature
- VAD is still used for turn detection, but interruptions rely on transcripts

## Troubleshooting

**Problem**: Agent still stops on "yeah"
- Check logs for "Filtering soft interruption"
- Verify `enable_soft_interrupt_filtering=True`
- Verify `turn_detection="stt"`

**Problem**: Agent doesn't stop on "stop"
- Check that "stop" is NOT in soft patterns
- Default patterns don't include command words

**Problem**: Agent ignores "yeah" when you answer a question
- This is working correctly! Filter only applies when agent is speaking
- When agent is silent, "yeah" is processed normally

## Files Modified Summary

- ✅ `livekit-agents/livekit/agents/voice/soft_interruption_filter.py` (NEW)
- ✅ `livekit-agents/livekit/agents/voice/agent_session.py` (modified)
- ✅ `livekit-agents/livekit/agents/voice/agent_activity.py` (modified)
- ✅ `examples/voice_agents/smart_interruption_demo.py` (NEW)
