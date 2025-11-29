# LiveKit Intelligent Interruption Handling Agent

A context-aware voice agent that intelligently handles user interruptions by distinguishing between passive acknowledgements (backchanneling) and active interruptions based on the agent's current speaking state.

This project is a voice cascading model built using:

--> Deepgram STT for real-time speech recognition

--> Google Gemini Flash as the language model

--> Cartesia TTS for natural text-to-speech generation

## Problem Statement

Voice agents treat all user input as interruptions, causing the agent to stop speaking even when users provide simple feedback like "yeah," "okay," or "hmm" while actively listening. This creates an unnatural conversational flow.

## Solution Overview

This implementation adds a sophisticated logic layer that:
- **Ignores backchanneling** (e.g., "yeah", "ok", "hmm") when the agent is speaking
- **Processes commands** (e.g., "stop", "wait", "no") immediately, even during agent speech
- **Responds to all input** when the agent is silent, including simple acknowledgements
- **Maintains natural conversation flow** without stuttering or awkward pauses

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
│                    (LiveKit Session)                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├──► TranscriptBuffer (duplicate detection)
                       │
                       ├──► InputClassifier (categorize user input)
                       │         ├─► BACKCHANNEL ("yeah", "ok")
                       │         ├─► COMMAND ("stop", "wait")
                       │         └─► QUERY (meaningful input)
                       │
                       └──► ConversationAnalyzer (handling strategy)
                                 ├─► IGNORE
                                 ├─► INTERRUPT
                                 ├─► INTERRUPT_AND_RESPOND
                                 ├─► RESPOND
                                 └─► WAIT
```

### File Structure

- **`main.py`**: LiveKit agent entry point and event handling
- **`classifier.py`**: Categorizes user input into types (backchannel, command, query)
- **`analyzer.py`**: Determines handling strategy based on input type and agent state
- **`transcript_buffer.py`**: Prevents duplicate processing of transcripts
- **`logger.py`**: Event logging for debugging and monitoring
- **`settings.py`**: Configuration management
- **`agent_types.py`**: Type definitions and enums
- **`utils.py`**: Helper functions

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# LiveKit Credentials
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Service API Keys
DEEPGRAM_API_KEY=your-deepgram-key
GOOGLE_API_KEY=your-google-key
CARTESIA_API_KEY=your-cartesia-key

# Model Configuration
DEEPGRAM_MODEL=nova-3
GOOGLE_LLM_MODEL=gemini-2.5-flash


```

### Configurable Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `COOLDOWN_MS` | 300 | Milliseconds between allowed interruptions |
| `BUFFER_CAP` | 20 | Maximum transcript entries to track |
| `DUP_WINDOW_S` | 0.75 | Time window for duplicate detection |
| `INTERRUPT_SETTLE_S` | 0.25 | Delay after interrupt before responding |
| `BACKCHANNEL_WORDS` | (see above) | Words to ignore during agent speech |
| `COMMAND_WORDS` | (see above) | Words that trigger immediate interrupt |

## Installation & Setup

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/Dark-Sys-Jenkins/agents-assignment.git
cd agents-assignment/examples/voice_agents/interruption_handling_agents

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the agent
python main.py start
```

## Logic Matrix

| User Input | Agent State | Action | Result |
|------------|-------------|--------|--------|
| "Yeah/Ok/Hmm" | Speaking | **IGNORE** | Agent continues without pause |
| "Wait/Stop/No" | Speaking | **INTERRUPT** | Agent stops immediately |
| "Yeah/Ok/Hmm" | Silent | **RESPOND** | Agent processes as valid input |
| "Hello/Question" | Silent | **RESPOND** | Normal conversation flow |
| Interim transcript | Either | **WAIT** | Wait for final transcript |

## Test Scenarios

### Scenario 1: Long Explanation (Backchannel Ignore)
```
Agent: "In 1492, Christopher Columbus sailed across the Atlantic Ocean..."
User: "Yeah... okay... uh-huh"
Result: ✓ Agent continues speaking without interruption
```

### Scenario 2: Passive Affirmation Response
```
Agent: "Are you ready?"
User: "Yeah"
Result: ✓ Agent responds: "Great, let's continue."
```

### Scenario 3: Command Interruption
```
Agent: "Let me count for you. One, two, three..."
User: "Stop"
Result: ✓ Agent stops immediately
```

### Scenario 4: Mixed Input Detection
```
Agent: "Here's how it works..."
User: "Yeah okay but wait"
Result: ✓ Agent stops (contains command "wait")
```

## How It Works

### 1. Input Classification

The `InputClassifier` categorizes user input:

```python
BACKCHANNEL: "yeah", "ok", "hmm", "right", "uh-huh"
COMMAND: "stop", "wait", "no", "cancel", "pause"
QUERY: Any meaningful question or statement
```

### 2. Strategy Determination

The `ConversationAnalyzer` decides the handling strategy:

```python
if agent_is_speaking:
    if input == BACKCHANNEL:
        return "IGNORE"  # Continue speaking
    if input == COMMAND:
        return "INTERRUPT"  # Stop immediately
    if is_final:
        return "INTERRUPT_AND_RESPOND"  # Stop and reply
else:
    if is_final:
        return "RESPOND"  # Process input
```

### 3. Duplicate Prevention

The `TranscriptBuffer` prevents processing the same transcript multiple times within a configurable window (default: 0.75s).

### 4. Cooldown Management

A cooldown period (default: 300ms) prevents rapid-fire interruptions from causing agent instability.

## Logging

The agent provides detailed event logging:

```
[INPUT] utterance='yeah' status=final agent=speaking
[CLASSIFY] utterance='yeah' → backchannel
[DECIDE] IGNORE: Backchannel while agent speaking
```

Log categories:
- `[INPUT]`: User transcription events
- `[CLASSIFY]`: Input classification results
- `[DECIDE]`: Handling strategy decisions
- `[EXECUTE]`: Actions taken
- `[LIFECYCLE]`: Agent state changes
- `[ERROR]`: Error events

## Demo

[link to demo : https://drive.google.com/file/d/1UNeM_ZqdPozMytJq4tH3fjNsguLYdRhd/view?usp=sharing ]
1. Agent ignoring "yeah" while speaking
2. Agent responding to "yeah" when silent
3. Agent stopping for "stop" command
4. Mixed input handling



### Handling STT-VAD Latency

Since VAD triggers faster than Speech-to-Text transcription:
1. We process both interim and final transcripts
2. We maintain state tracking for agent speech status
3. We use a cooldown period to prevent race conditions
4. We buffer transcripts to prevent duplicate processing

### State Management

The agent maintains precise state tracking:
- `agent_is_speaking`: Tracks current audio output
- `is_processing_reply`: Prevents duplicate response generation
- `last_interrupt_time`: Enforces cooldown period

## Customization

### Adding Custom Backchannel Words

```bash
# In classifier.py file 
BACKCHANNEL_WORDS=yeah,yep,ok,okay,hmm,sure,right,got it,sounds good
```

### Adding Custom Command Words

```bash
# In classifier.py 
COMMAND_WORDS=stop,wait,hold on,pause,cancel,nevermind,hold up
```

### Adjusting Response Timing

```bash
# Increase cooldown for slower conversations
COOLDOWN_MS=500

# Adjust settle delay before responding after interrupt
INTERRUPT_SETTLE_S=0.3
```

## Troubleshooting

### Agent Stops on Backchannels
- Check that words are in `BACKCHANNEL_WORDS` environment variable
- Verify agent state is correctly tracked in logs
- Increase `COOLDOWN_MS` if interrupts are too frequent

### Agent Doesn't Respond to Commands
- Ensure command words are in `COMMAND_WORDS`
- Check classification logs to verify detection
- Verify `is_final` status in transcript events

### Duplicate Processing
- Adjust `DUP_WINDOW_S` to wider window
- Check `BUFFER_CAP` is sufficient
- Review transcript buffer logs



## Contact

Konakalla Shanmukha Sahith 
shanmukhasahith@gmail.com

---
