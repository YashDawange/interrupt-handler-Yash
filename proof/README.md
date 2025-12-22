# Interrupt Handler Agent

A voice agent that intelligently handles user interruptions by distinguishing between backchannel responses (like "yeah", "okay") and actual interruptions.
Link of the Video of the working agent : [Link](https://drive.google.com/file/d/15naq3rqyoY802elCvcMnRM1OabXnWAnS/view?usp=share_link)

## Features

- **Backchannel Suppression**: Ignores acknowledgment words like "yeah", "okay", "hmm" when the agent is speaking
- **Smart Interruption Detection**: Responds to actual interruptions and commands like "stop", "wait", "hold on"
- **State-Aware Processing**: Different behavior based on whether the agent is speaking or listening
- **Comprehensive Logging**: Detailed logs showing when backchannels are suppressed

## How It Works

The agent uses an `InterruptionManager` that:

1. **Classifies user speech** into three categories:
   - **Backchannel**: Acknowledgments like "yeah", "okay", "uh-huh"
   - **Command**: Interrupt commands like "stop", "wait", "pause"
   - **Normal**: Regular conversation

2. **Tracks agent state**: Knows when the agent is speaking vs. listening

3. **Filters transcripts**: Suppresses backchannel words only when the agent is speaking

## Requirements

- Python >= 3.11, < 3.13
- LiveKit account with API credentials
- Google API key (for LLM) or OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/<your-username>/agents-assignment
cd agents-assignment
```

2. Install dependencies using uv:
```bash
uv add \
  "livekit-agents[silero,turn-detector,assemblyai,google]~=1.3" \
  "livekit-plugins-noise-cancellation~=0.2" \
  "python-dotenv"
```

3. Set up environment variables:
Run the following command to create your `.env.local` file:
```bash
lk app env -w
```

The file should look like this:
```bash
LIVEKIT_API_KEY=<your API Key>
LIVEKIT_API_SECRET=<your API Secret>
LIVEKIT_URL=<your LiveKit server URL>
GOOGLE_API_KEY=<your Google API key>
```

## Running the Agent

### 1. Download Model Files (First Time Only)

Before running the agent, download the required model files:

```bash
uv run examples/voice_agents/interrupt_handler.py download-files
```

### 2. Development Mode (Recommended for Testing)

```bash
uv run examples/voice_agents/interrupt_handler.py dev
```

This will:
- Start the agent in development mode
- Open a web interface in your browser
- Allow you to test the voice interaction

### 3. Console Mode (Terminal Only)

```bash
uv run examples/voice_agents/interrupt_handler.py console
```

### 4. Connect to a Specific Room

```bash
uv run examples/voice_agents/interrupt_handler.py connect --room <room-name>
```

## Testing the Features

Once the agent is running, you can test:

1. **Backchannel Suppression**:
   - Let the agent speak
   - Say "yeah" or "okay" while it's talking
   - The agent should continue without reacting
   - Check logs: `✓ Suppressing backchannel: 'yeah' (agent speaking)`

2. **Response When Silent**:
   - Wait for the agent to stop speaking
   - Say "yeah" or "okay"
   - The agent should respond
   - Check logs: `Agent silent - processing: 'yeah'`

3. **Interrupt Commands**:
   - While agent is speaking, say "stop" or "wait"
   - The agent should stop and acknowledge
   - Check logs: `✓ Processing interrupt command: 'stop'`

## Configuration

You can customize the backchannel and interrupt words in the `InterruptionConfig` class:

```python
@dataclass
class InterruptionConfig:
    backchannel_words: Set[str] = field(default_factory=lambda: {
        "yeah", "ok", "okay", "hmm", "uh-huh", "aha", "right",
        # Add more words here
    })

    interrupt_words: Set[str] = field(default_factory=lambda: {
        "wait", "stop", "no", "pause", "hold on",
        # Add more words here
    })
```

## Architecture

```
┌─────────────────────┐
│  User Speech (STT)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ InterruptionManager │
│  - Classify speech  │
│  - Check agent state│
│  - Decide suppress  │
└──────────┬──────────┘
           │
           ▼
    ┌──────────┐
    │ Suppress?│
    └─┬────┬───┘
  Yes │    │ No
      │    │
      ▼    ▼
   [Skip] [Process with LLM]
```


## Contributing

This agent was created as part of the LiveKit agents assignment. For the full assignment repository, see: https://github.com/Dark-Sys-Jenkins/agents-assignment

## License

See the main repository LICENSE file.