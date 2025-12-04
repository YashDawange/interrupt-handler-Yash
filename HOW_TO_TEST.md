# How to Test

Testing with LiveKit Playground is the easiest way since Windows console has encoding issues with emojis.

## Quick Start

### 1. Start the Agent

```bash
cd agents-assignment/examples/voice_agents
../../venv/Scripts/python.exe intelligent_interruption_agent.py dev
```

You should see logs saying the agent is ready and registered with LiveKit.

**Note:** All logs automatically save to `PROOF_LOGS.log` in the root directory.

### 2. Connect via LiveKit Playground

Open https://agents-playground.livekit.io/ in your browser and connect to the agent.

### 3. Test Scenarios

**Test 1: Agent Ignores Fillers**
- Ask agent: "Tell me about artificial intelligence"
- While agent is speaking, say: "yeah" or "okay" or "hmm"
- Expected: Agent continues speaking without stopping

**Test 2: Agent Responds to Fillers When Silent**
- Wait for agent to finish speaking
- Say: "yeah"
- Expected: Agent responds to you

**Test 3: Agent Stops for Real Interruptions**
- Ask agent: "Count to 20"
- While counting, say: "stop"
- Expected: Agent stops immediately

**Test 4: Mixed Input**
- Ask agent a question
- While agent is speaking, say: "yeah but wait"
- Expected: Agent stops (because "but" and "wait" are interruption keywords)

### 4. Check the Logs

Look at the terminal output or `PROOF_LOGS.log` file. You'll see:
- `🔇 IGNORING interruption` - when filler words are ignored
- `🛑 ALLOWING interruption` - when real interruptions occur
- Agent state changes
- Transcript events with timing

## What You Should See

When working correctly, the logs will show something like:

```
📝 User transcript: 'Yeah.' (agent_was_speaking: True)
🔍 Evaluating: agent_was_speaking=True, text='Yeah.'
✅ Agent WAS speaking → checking transcript content
🔇 Only filler words → IGNORING interruption
🔇 IGNORING interruption - agent continues speaking
✅ Resumed agent speech successfully
```

## Alternative Testing Methods

If you can't use LiveKit Playground right now, you can:

1. **Code Walkthrough** - Record a video explaining how the code works
2. **Simulated Logs** - Show what the logs would look like for each scenario
3. **Code Review** - Walk through the decision logic step by step

But LiveKit Playground testing is preferred because it shows real behavior.

## Troubleshooting

**Agent not connecting?**
- Check your .env file has all required API keys
- Make sure LiveKit URL and credentials are correct

**Emojis showing as ?**
- This is a Windows console encoding issue
- Use dev mode instead of console mode
- Check PROOF_LOGS.log file for complete logs

**Agent not ignoring fillers?**
- Make sure you say the filler word WHILE agent is actively speaking
- Check the logs to see if agent_was_speaking was True
- Timing matters - say it during speech, not after
