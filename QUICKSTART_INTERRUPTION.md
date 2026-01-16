# Quick Start Guide: Intelligent Interruption Handling

This guide will help you quickly get started with the Intelligent Interruption Handling feature.

## Installation

The feature is built into the LiveKit Agents framework. Simply install the package:

```bash
cd agents-assignment/livekit-agents
pip install -e .
```

## Basic Usage

The intelligent interruption handling is **automatically enabled** when you create an `AgentSession` with `allow_interruptions=True`. No additional configuration is needed for basic usage.

```python
from livekit.agents import Agent, AgentSession
from livekit.plugins import deepgram, openai, silero

# Create agent
agent = Agent(
    instructions="You are a helpful assistant.",
)

# Create session with interruption handling enabled
session = AgentSession(
    stt=deepgram.STT(),
    llm=openai.LLM(model="gpt-4o-mini"),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    allow_interruptions=True,  # Intelligent handling is active
)
```

That's it! The agent will now:
- ✅ Continue speaking when user says "yeah", "ok", "hmm"
- ✅ Stop immediately when user says "stop", "wait", "no"
- ✅ Stop when user says mixed input like "yeah but wait"
- ✅ Process filler words normally when agent is silent

## Configuration (Optional)

### Custom Word Lists via Environment Variables

Create a `.env` file in your project:

```bash
# .env
LIVEKIT_IGNORE_WORDS=yeah,ok,hmm,uh-huh,right
LIVEKIT_COMMAND_WORDS=stop,wait,no,pause
```

### Custom Word Lists in Code

```python
from livekit.agents.voice import create_interruption_handler

# Create custom handler
handler = create_interruption_handler(
    ignore_words=["yeah", "ok", "hmm"],
    command_words=["stop", "halt"],
    enable_env_config=False
)

# The handler is automatically integrated into AgentActivity
```

## Running the Demo

```bash
# 1. Navigate to the repository
cd agents-assignment

# 2. Install dependencies
pip install -e ./livekit-agents
pip install livekit-plugins-deepgram livekit-plugins-openai livekit-plugins-silero

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your LiveKit credentials

# 4. Run the demo
python examples/intelligent_interruption_demo.py
```

## Testing Scenarios

### Scenario 1: Ignore Filler While Speaking

1. Start the agent
2. Ask: "Tell me about the weather"
3. While agent is speaking, say: "yeah" or "ok"
4. **Expected**: Agent continues speaking without pause

### Scenario 2: Command Interrupts

1. Start the agent
2. Ask: "Count from 1 to 20"
3. While agent is counting, say: "stop" or "wait"
4. **Expected**: Agent stops immediately

### Scenario 3: Mixed Input Interrupts

1. Start the agent
2. Ask: "Explain how this works"
3. While agent is speaking, say: "yeah but wait"
4. **Expected**: Agent stops (mixed input contains command)

### Scenario 4: Filler When Silent

1. Start the agent
2. Wait for agent to finish speaking
3. Say: "yeah"
4. **Expected**: Agent processes it as normal input and responds

## Logging

Enable detailed logging to see interruption decisions:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

You'll see logs like:

```
INFO - Interruption handler initialized with 12 ignore words and 7 command words
INFO - Pending interrupt triggered - waiting for STT confirmation
INFO - Ignore filler while speaking: 'yeah'
INFO - Command detected - interrupting agent: 'stop'
```

## Troubleshooting

### Issue: Filler words are still interrupting

**Solution**: 
- Check that STT is producing accurate transcripts
- Verify environment variables are loaded correctly
- Enable debug logging to see decision logic

### Issue: Commands are not interrupting

**Solution**:
- Verify `allow_interruptions=True` in AgentSession
- Check that command words are in the list
- Review logs for decision reasoning

### Issue: Audio gaps when ignoring fillers

**Solution**: This should NOT happen. If it does:
- File a bug report with detailed logs
- Check TTS output pipeline
- Verify speaking state is properly tracked

## Next Steps

- Read the [full documentation](INTELLIGENT_INTERRUPTION.md)
- Explore the [example code](examples/intelligent_interruption_demo.py)
- Run the [unit tests](tests/test_interruption_handler.py)
- Customize word lists for your use case

## Support

For questions or issues:
1. Check the [full documentation](INTELLIGENT_INTERRUPTION.md)
2. Review the [test cases](tests/test_interruption_handler.py)
3. Join the [LiveKit Slack community](https://livekit.io/join-slack)
