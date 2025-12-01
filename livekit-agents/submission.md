# Intelligent Interruption Handling - LiveKit Agents
Demo recording link: https://drive.google.com/file/d/18T0IE-TJ8xvOWW2XJfx9QbLj4M3yUqeU/view?usp=sharing

## Overview

Implemented intelligent interruption filtering to distinguish between passive acknowledgments (backchannel) and active interruptions in voice conversations.

## Key Features

- **Backchannel Detection**: Ignores passive words like "yeah", "okay", "mm-hmm" during agent speech
- **Interruption Recognition**: Responds to active interruption words like "wait", "stop", "but"
- **Context-Aware Processing**: Different behavior when agent is speaking vs silent
- **Comprehensive Testing**: Four key scenarios with unit, automated, and live voice testing

## Core Implementation

### InterruptionFilter Class (`interruption_filter.py`)

- **Backchannel Words**: 25+ words that shouldn't interrupt (yeah, okay, hmm, etc.)
- **Interruption Words**: 15+ words that always interrupt (wait, stop, but, etc.)
- **Logic**: `should_interrupt()` method analyzes transcript + agent state
- **Smart Filtering**: Pure backchannel ignored during speech, mixed content allows interruption

### AgentSession Updates (`agent_session.py`)

- **New Parameter**: Added `interruption_filter: InterruptionFilter | None = None`
- **Default Filter**: Creates default InterruptionFilter if none provided
- **Integration**: Passes filter to AgentActivity via AgentSessionOptions

### AgentActivity Updates (`agent_activity.py`)

- **Audio Interruption**: Modified `_interrupt_by_audio_activity()` to use filter
- **Transcript Processing**: Enhanced `on_final_transcript()` with intelligent filtering
- **Decision Logging**: Added comprehensive logging for debugging filter decisions
- **State Awareness**: Filter receives agent speaking state for context

## Test Scenarios

1. **Backchannel During Speech**: Agent continues speaking when user says "yeah", "okay"
2. **Passive Affirmation**: User input processed normally when agent is silent
3. **Clear Interruption**: "Wait" or "stop" immediately interrupts agent speech
4. **Mixed Input**: "Yeah, but wait" - detects interruption word and interrupts

## Setup & Testing

```bash
cd livekit-agents
python -m venv .venv
venv\Scripts\activate  # Windows
pip install -e ".[deepgram,openai]"

# Run comprehensive tests
python four_scenarios_test.py console   # Live voice testing
python real_interruption_handling_test.py console   # similar real-time testing in console
```

## Technical Architecture

- **Traditional Pipeline**: Uses Deepgram STT + OpenAI LLM/TTS (not Realtime API)
- **Real-time Processing**: Filter decisions in ~1ms for responsive interruption handling
- **Backward Compatible**: Existing agents work unchanged, opt-in filter enhancement
