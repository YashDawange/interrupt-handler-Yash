# Intelligent Interruption Handling for LiveKit Voice Agents

## Overview

This implementation solves the problem where LiveKit's Voice Activity Detection (VAD) is too sensitive to user backchanneling (filler words like "yeah", "ok", "hmm"). Previously, when users said these words to indicate they're listening, the agent would pause or interrupt its speech, breaking the conversational flow.

## Solution

A **context-aware backchanneling filter** that distinguishes between:
- **Passive acknowledgements** (filler words) → **IGNORED** while agent speaks
- **Active interruptions** (command words) → **INTERRUPT** immediately
- **Valid input** when agent is silent → **RESPOND** normally

## Key Features

### 1. State-Based Filtering
- Only applies filtering when the agent is actively speaking
- When agent is silent, filler words are treated as valid input (e.g., answering "Are you ready?" with "Yeah")

### 2. Configurable Word Lists
- **Filler words** (ignored while speaking): `yeah`, `ok`, `okay`, `hmm`, `right`, `uh-huh`, `got it`, etc.
- **Command words** (always interrupt): `stop`, `wait`, `no`, `help`, `what`, `why`, etc.
- Customizable via environment variables or programmatic configuration

### 3. Complete Transcript Ignoring
- Filler words are **completely ignored** when agent is speaking:
  - No interruption/pause
  - Not added to conversation context
  - No LLM response triggered
  - Seamless continuation of agent speech

### 4. Semantic Interruption Detection
- Mixed inputs like "Yeah wait" correctly trigger interruption (contains command word "wait")
- Punctuation handling (e.g., "Yeah." is recognized as filler)
- Multi-word phrases supported (e.g., "uh huh", "got it")

## Technical Implementation

### Core Components

1. **BackchannelingFilter** (`livekit/agents/voice/backchanneling_filter.py`)
   - Analyzes transcripts and returns: `IGNORE`, `INTERRUPT`, or `RESPOND`
   - Handles punctuation, case sensitivity, and multi-word phrases

2. **Agent Activity Integration** (`livekit/agents/voice/agent_activity.py`)
   - Early detection in `on_interim_transcript` and `on_final_transcript` hooks
   - Signals audio recognition to skip transcript processing entirely

3. **Audio Recognition** (`livekit/agents/voice/audio_recognition.py`)
   - `skip_current_transcript()` method prevents filler words from being added to user turn
   - Ensures no EOU detection or LLM generation for ignored transcripts

### Logic Flow

```
User speaks while agent is talking
    ↓
VAD detects speech → Defers interruption (no transcript yet)
    ↓
STT provides transcript (e.g., "Okay.")
    ↓
BackchannelingFilter analyzes:
    - Agent speaking? ✓
    - Is "okay" a filler word? ✓
    → Result: IGNORE
    ↓
Skip transcript processing:
    - No interruption
    - Not added to chat context
    - No EOU detection
    - Agent continues seamlessly
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install livekit-agents livekit-plugins-google
   ```

2. **Configure Google Cloud credentials**:
   - Download service account JSON from Google Cloud Console
   - Save as `gcloud.json` in project root
   - Set environment variable:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=./gcloud.json
     export GOOGLE_API_KEY=your_gemini_api_key
     ```

3. **Run the agent**:
   ```bash
   python examples/voice_agents/intelligent_interrupt_agent.py dev
   ```

## Usage

The filter is automatically enabled in `intelligent_interrupt_agent.py`. To customize:

```python
from livekit.agents.voice import BackchannelingConfig, BackchannelingFilter, set_global_filter

config = BackchannelingConfig(
    enabled=True,
    filler_words=frozenset(["yeah", "ok", "custom_word"]),
    command_words=frozenset(["stop", "wait", "custom_command"]),
)
set_global_filter(BackchannelingFilter(config))
```

Or via environment variables:
```bash
BACKCHANNELING_ENABLED=true
BACKCHANNELING_FILLER_WORDS=yeah,ok,hmm,right
BACKCHANNELING_COMMAND_WORDS=stop,wait,no,help
```

## Test Scenarios

✅ **Scenario 1: Long Explanation**
- Agent reading long text, user says "Okay... yeah... uh-huh"
- **Result**: Agent continues without any pause or break

✅ **Scenario 2: Passive Affirmation**
- Agent asks "Are you ready?", user says "Yeah"
- **Result**: Agent processes "Yeah" as valid answer

✅ **Scenario 3: Correction**
- Agent counting, user says "No stop"
- **Result**: Agent stops immediately

✅ **Scenario 4: Mixed Input**
- Agent speaking, user says "Yeah okay but wait"
- **Result**: Agent stops (contains command word "wait")

## Video Demonstration

See the implementation in action:
**[Video Demonstration](https://drive.google.com/drive/folders/1d54gpGB3_SyAe5arlJCOWeL5PB6sZ2Cg?usp=drive_link)**

The video demonstrates:
- Agent ignoring "okay", "yeah", "hmm" while speaking (no pause/stutter)
- Agent responding to "yeah" when silent
- Agent stopping immediately for "stop" command

## Files Modified

- `livekit-agents/livekit/agents/voice/backchanneling_filter.py` - Core filter logic
- `livekit-agents/livekit/agents/voice/agent_activity.py` - Hook integration
- `livekit-agents/livekit/agents/voice/audio_recognition.py` - Transcript skipping
- `examples/voice_agents/intelligent_interrupt_agent.py` - Example implementation
- `tests/test_backchanneling_filter.py` - Comprehensive test suite

## Requirements

- Python 3.8+
- LiveKit Agents framework

### Google Cloud Setup

The example agent (`intelligent_interrupt_agent.py`) uses Google Cloud services and requires:

1. **Google Cloud Service Account JSON** (`gcloud.json`)
   - Download from Google Cloud Console
   - Place in project root directory
   - Set environment variable: `GOOGLE_APPLICATION_CREDENTIALS=./gcloud.json`
   - Used for: Google Cloud Speech-to-Text (STT) and Text-to-Speech (TTS)

2. **Google API Key**
   - Set environment variable: `GOOGLE_API_KEY=your_api_key`
   - Used for: Google Gemini LLM

**Note**: You can also use Application Default Credentials instead of the JSON file.

---

**Note**: This implementation ensures the agent continues speaking seamlessly over filler words, with zero pause, stutter, or hiccup, meeting the strict requirements of the challenge.

