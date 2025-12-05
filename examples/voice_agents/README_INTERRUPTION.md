# Running the Intelligent Interruption Agent Locally

This guide explains how to run the intelligent interruption agent on your local machine.

## Prerequisites

1. **Python 3.9+** installed
2. **OpenAI API Key** (used for STT, LLM, and TTS)

## Setup

### 1. Install Dependencies

From the repository root, install the project:

```bash
# Using uv (recommended for this workspace)
uv sync --extra openai --extra silero

# Activate the virtual environment
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Windows CMD:
.venv\Scripts\activate.bat
# On Linux/Mac:
source .venv/bin/activate
```

**Note:** This is a `uv` workspace project. If you don't have `uv` installed:
- Install uv: `pip install uv` or see https://github.com/astral-sh/uv
- Or see [INSTALL.md](INSTALL.md) for alternative installation methods

### 2. Set Up Environment Variables

Create a `.env` file in the repository root or set environment variables:

```bash
# Required API Key (used for STT, LLM, and TTS)
OPENAI_API_KEY=your_openai_api_key

# Optional: Customize interruption handling
LIVEKIT_AGENT_IGNORE_WORDS="yeah,ok,hmm,right,sure,uh-huh"
LIVEKIT_AGENT_INTERRUPTION_COMMANDS="wait,stop,no,hold on,pause"
```

## Running the Agent

### Option 1: Console Mode (Recommended for Testing)

Console mode runs the agent locally with your microphone and speakers. This is the easiest way to test the interruption handling.

```bash
cd examples/voice_agents
python intelligent_interruption_agent.py console
```

**First time?** List available audio devices:
```bash
python intelligent_interruption_agent.py console --list-devices
```

**Specify audio devices:**
```bash
python intelligent_interruption_agent.py console --input-device "Microphone" --output-device "Speakers"
```

**Text mode (no audio):**
```bash
python intelligent_interruption_agent.py console --text
```

### Option 2: Dev Mode (With LiveKit Server)

For connecting to a LiveKit server (cloud or self-hosted):

```bash
cd examples/voice_agents
python intelligent_interruption_agent.py dev
```

**Required environment variables for dev mode:**
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

Then connect using:
- [Agents Playground](https://agents-playground.livekit.io/)
- Any LiveKit client SDK
- Telephony integration

## Testing the Interruption Handling

Once the agent is running:

1. **Test Backchanneling Ignore:**
   - Let the agent start speaking (it will give a long explanation)
   - While it's speaking, say: "yeah", "ok", "hmm", or "uh-huh"
   - ✅ **Expected:** Agent continues speaking without interruption

2. **Test Interruption Commands:**
   - Let the agent start speaking
   - While it's speaking, say: "wait", "stop", or "no"
   - ✅ **Expected:** Agent stops immediately

3. **Test Valid Input When Silent:**
   - Wait for the agent to finish speaking and ask a question
   - When the agent is silent, say: "yeah" or "ok"
   - ✅ **Expected:** Agent responds normally (treats it as valid input)

4. **Test Mixed Input:**
   - Let the agent start speaking
   - Say: "Yeah wait a second"
   - ✅ **Expected:** Agent stops (contains interruption command)

## Troubleshooting

### Audio Issues

If you can't hear audio or the microphone isn't working:

1. **Check audio devices:**
   ```bash
   python intelligent_interruption_agent.py console --list-devices
   ```

2. **Try specifying devices explicitly:**
   ```bash
   python intelligent_interruption_agent.py console --input-device 0 --output-device 0
   ```

### API Key Issues

Make sure the OpenAI API key is set:
```bash
echo $OPENAI_API_KEY
```

### Import Errors

If you get import errors, make sure you're in the repository root and have installed dependencies:
```bash
cd /path/to/agents-assignment
uv sync
```

## Customization

You can customize the interruption handling by modifying the environment variables:

```bash
# Add more words to ignore
export LIVEKIT_AGENT_IGNORE_WORDS="yeah,ok,hmm,right,sure,uh-huh,yep,alright"

# Add more interruption commands
export LIVEKIT_AGENT_INTERRUPTION_COMMANDS="wait,stop,no,hold on,pause,cancel"
```

Or modify the code directly in `livekit-agents/livekit/agents/voice/interruption_handler.py`.

