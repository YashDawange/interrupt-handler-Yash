# Voice Agent with Smart Backchannel Filtering

## Overview

DEMO VIDEO LINK : https://drive.google.com/file/d/188CbGFTb83_mCfHiFg2UYD-384joQ76f/view?usp=sharing

This implementation provides a voice agent with intelligent interruption handling that distinguishes between acknowledgment sounds (like "yeah", "okay") and meaningful interruptions.

## Files

- **`basic_agent.py`** - Main voice agent with backchannel filtering
- **`backchannel_agent.py`** - Contains the `BackchannelFilter` class
- **`gen_token.py`** - Generates authentication tokens for testing

## How It Works

### Backchannel Filtering Logic

The agent intelligently handles user input based on three categories:

#### 1. **Acknowledgment Words** (Ignored)
```
Words: yeah, okay, hmm, mm, uh, mhm, right, sure, yep, yup
Action: Agent continues speaking without interruption
```

#### 2. **Interrupt Words** (Immediate Stop)
```
Words: stop, wait, hold, no, nope
Action: Agent stops immediately and listens
```

#### 3. **Real Content** (Smart Interruption)
```
Words: Any meaningful input
Action: Agent interrupts only if currently speaking
```

### Processing Flow

```
User speaks → Transcription → Tokenize words
                ↓
    Is agent speaking? → NO → Normal turn-taking
                ↓ YES
    Contains interrupt word? → YES → Stop immediately
                ↓ NO
    Only acknowledgment words? → YES → Continue speaking
                ↓ NO
    Real content → Interrupt and listen
```

## Setup

### 1. Environment Variables

Create `.env` file in `examples/` directory:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
```

### 2. Optional Customization

Add custom words to `.env`:

```env
BACKCHANNEL_IGNORE_WORDS=gotcha,understood,cool
BACKCHANNEL_INTERRUPT_WORDS=pause,quit,enough
```

## Running the Agent

### Development Mode (with UI)

```bash
cd agents-assignment/examples/voice_agents
python basic_agent.py dev
```

Then connect via [Agents Playground](https://agents-playground.livekit.io/)

### Console Mode (local testing)

```bash
python basic_agent.py console
```

Uses your computer's microphone/speakers directly.

## Testing

### Generate Token

```bash
python gen_token.py
```

Copy the JWT token and use it to connect in the Agents Playground.

### Test Scenarios

1. **Acknowledgment Test**: While agent is speaking, say "yeah" or "hmm" - agent should continue
2. **Interrupt Test**: While agent is speaking, say "stop" - agent should stop immediately  
3. **Real Content Test**: While agent is speaking, ask a question - agent should interrupt and respond

## Key Features

- **Smart Interruption**: Distinguishes between acknowledgments and real input
- **Configurable Word Lists**: Customize via environment variables
- **State Tracking**: Monitors agent speech state for context-aware filtering
- **Token-based Analysis**: Handles elongated words (e.g., "stoppp")

## Architecture

```
basic_agent.py
    ├── MyAgent (Agent logic)
    ├── AgentSession (STT/LLM/TTS pipeline)
    └── BackchannelFilter (imported from backchannel_agent.py)
            ├── attach() - Hooks into session events
            ├── _on_user_input_transcribed() - Main event handler
            ├── _tokenize() - Text processing
            ├── _contains_interrupt_word() - Interrupt detection
            ├── _is_only_acknowledgement() - Acknowledgment detection
            └── _background_validate() - Async decision logic
```

## Technical Details

- **VAD**: Silero Voice Activity Detection
- **STT**: Deepgram Nova-3
- **LLM**: OpenAI GPT-4.1-mini
- **TTS**: Cartesia Sonic-2
- **Turn Detection**: Multilingual model

## Troubleshooting

### KeyError warnings
Non-fatal SDK warnings - agent will still work normally.

### Rate limit (429 errors)
- Check API key quotas
- Ensure all API keys are valid in `.env`

### Agent not responding
- Verify all API keys are set correctly
- Check microphone permissions in browser
- Try console mode for local testing

