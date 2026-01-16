# Testing Guide for Intelligent Interruption Filter

## Quick Start

### 0. Quick Unit Test (No Setup Required) ⚡

The fastest way to test the filter logic without any dependencies:

```bash
python test_interruption_filter_standalone.py
```

This will run all unit tests and verify the filter logic works correctly. All tests should pass!

### 1. Prerequisites

Make sure you have the required environment variables set:

```bash
# Required for the agent to work
export LIVEKIT_URL="wss://your-livekit-server.com"
export LIVEKIT_API_KEY="your-api-key"
export LIVEKIT_API_SECRET="your-api-secret"

# Required for STT, LLM, and TTS
export DEEPGRAM_API_KEY="your-deepgram-key"
export OPENAI_API_KEY="your-openai-key"
export CARTESIA_API_KEY="your-cartesia-key"  # or use another TTS provider
```

### 2. Run the Demo Agent

```bash
cd examples/voice_agents
python interruption_filter_demo.py dev
```

Or test in console mode (terminal audio):

```bash
python interruption_filter_demo.py console
```

## Test Scenarios

### Scenario 1: Passive Acknowledgement While Agent is Speaking ✅

**Test**: Agent should continue speaking when user says passive words

1. Start the agent
2. Wait for agent to start speaking (it will give a long explanation)
3. While agent is speaking, say: **"yeah"** or **"ok"** or **"hmm"** or **"uh-huh"**
4. **Expected Result**: Agent continues speaking without any pause, stop, or stutter

**Success Criteria**: 
- ✅ Agent audio continues uninterrupted
- ✅ No pause in agent's speech
- ✅ No stutter or hiccup
- ❌ If agent stops or pauses, the test fails

### Scenario 2: Active Interruption While Agent is Speaking ✅

**Test**: Agent should stop immediately when user says interrupt commands

1. Start the agent
2. Wait for agent to start speaking
3. While agent is speaking, say: **"wait"** or **"stop"** or **"no"**
4. **Expected Result**: Agent stops speaking immediately and listens

**Success Criteria**:
- ✅ Agent stops immediately
- ✅ Agent transitions to listening state
- ✅ Agent is ready to process new input

### Scenario 3: Passive Acknowledgement When Agent is Silent ✅

**Test**: Agent should respond normally to passive words when silent

1. Start the agent
2. Wait for agent to ask "Are you ready?" and go silent
3. Say: **"yeah"** or **"ok"**
4. **Expected Result**: Agent processes "yeah" as valid input and responds (e.g., "Okay, starting now")

**Success Criteria**:
- ✅ Agent treats "yeah" as valid input
- ✅ Agent generates appropriate response
- ✅ Agent does not ignore the input

### Scenario 4: Mixed Input (Passive + Command) ✅

**Test**: Agent should interrupt if passive words are mixed with commands

1. Start the agent
2. Wait for agent to start speaking
3. While agent is speaking, say: **"yeah okay but wait"** or **"ok stop"**
4. **Expected Result**: Agent stops (because it contains interrupt commands)

**Success Criteria**:
- ✅ Agent detects interrupt command in mixed input
- ✅ Agent stops immediately
- ✅ Agent does not ignore because of passive words at the start

## Manual Testing Checklist

Use this checklist to verify all scenarios:

```
[ ] Scenario 1: Agent continues over "yeah" while speaking
[ ] Scenario 1: Agent continues over "ok" while speaking  
[ ] Scenario 1: Agent continues over "hmm" while speaking
[ ] Scenario 1: Agent continues over "uh-huh" while speaking
[ ] Scenario 2: Agent stops on "wait" while speaking
[ ] Scenario 2: Agent stops on "stop" while speaking
[ ] Scenario 2: Agent stops on "no" while speaking
[ ] Scenario 3: Agent responds to "yeah" when silent
[ ] Scenario 3: Agent responds to "ok" when silent
[ ] Scenario 4: Agent stops on "yeah wait" while speaking
[ ] Scenario 4: Agent stops on "ok stop" while speaking
```

## Debugging

### Enable Debug Logging

To see what the filter is doing, enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("livekit.agents.voice.agent_activity").setLevel(logging.DEBUG)
```

You'll see logs like:
```
DEBUG: Interruption filter decision: should_interrupt=False, reason=passive_acknowledgement, transcript='yeah'
DEBUG: Ignoring passive acknowledgement: 'yeah'
```

### Check Filter Configuration

Verify the filter is enabled and using the right words:

```python
from livekit.agents.voice.interruption_filter import get_default_interruption_filter

filter = get_default_interruption_filter()
print(f"Filter enabled: {filter.config.enabled}")
print(f"Passive words: {filter.config.passive_words}")
print(f"Interrupt words: {filter.config.interrupt_words}")
```

### Test Filter Logic Directly

You can test the filter logic programmatically:

```python
from livekit.agents.voice.interruption_filter import InterruptionFilter

filter = InterruptionFilter()

# Test passive word while agent is speaking
result = filter.should_interrupt("yeah", agent_is_speaking=True)
print(f"Should interrupt 'yeah' while speaking: {result}")  # Should be False

# Test interrupt word while agent is speaking
result = filter.should_interrupt("wait", agent_is_speaking=True)
print(f"Should interrupt 'wait' while speaking: {result}")  # Should be True

# Test passive word while agent is silent
result = filter.should_interrupt("yeah", agent_is_speaking=False)
print(f"Should interrupt 'yeah' while silent: {result}")  # Should be True (normal input)
```

## Automated Testing

### Standalone Test (Recommended for Quick Testing)

The simplest way to test without installing dependencies:

```bash
python test_interruption_filter_standalone.py
```

This test file:
- ✅ Tests all filter logic
- ✅ No external dependencies required
- ✅ Works on Windows, Mac, Linux
- ✅ Shows clear pass/fail results

### Using pytest

Create a test file `test_interruption_filter.py`:

```python
import pytest
from livekit.agents.voice.interruption_filter import InterruptionFilter

def test_passive_words_while_speaking():
    filter = InterruptionFilter()
    
    # Passive words should not interrupt when agent is speaking
    assert filter.should_interrupt("yeah", agent_is_speaking=True) == False
    assert filter.should_interrupt("ok", agent_is_speaking=True) == False
    assert filter.should_interrupt("hmm", agent_is_speaking=True) == False

def test_interrupt_words_while_speaking():
    filter = InterruptionFilter()
    
    # Interrupt words should interrupt when agent is speaking
    assert filter.should_interrupt("wait", agent_is_speaking=True) == True
    assert filter.should_interrupt("stop", agent_is_speaking=True) == True
    assert filter.should_interrupt("no", agent_is_speaking=True) == True

def test_passive_words_while_silent():
    filter = InterruptionFilter()
    
    # Passive words should be processed normally when agent is silent
    assert filter.should_interrupt("yeah", agent_is_speaking=False) == True
    assert filter.should_interrupt("ok", agent_is_speaking=False) == True

def test_mixed_input():
    filter = InterruptionFilter()
    
    # Mixed input with interrupt commands should interrupt
    assert filter.should_interrupt("yeah wait", agent_is_speaking=True) == True
    assert filter.should_interrupt("ok stop", agent_is_speaking=True) == True
    assert filter.should_interrupt("yeah okay but wait", agent_is_speaking=True) == True
```

Run tests:
```bash
pytest test_interruption_filter.py -v
```

## Video/Transcript Proof

As per the requirements, you should record a video or log transcript demonstrating:

1. ✅ Agent ignoring "yeah" while talking
2. ✅ Agent responding to "yeah" when silent
3. ✅ Agent stopping for "stop"

### Recording Tips

- Use screen recording software (OBS, QuickTime, etc.)
- Show the agent console/logs in the recording
- Clearly demonstrate each scenario
- Speak clearly and wait for agent responses

### Log Transcript Example

You can also create a log transcript showing the filter decisions:

```
[2024-01-01 10:00:00] Agent: "Let me explain the history of artificial intelligence..."
[2024-01-01 10:00:05] User: "yeah"
[2024-01-01 10:00:05] Filter: should_interrupt=False, reason=passive_acknowledgement
[2024-01-01 10:00:05] Agent: "...it began in the 1950s with the work of Alan Turing..."
[2024-01-01 10:00:10] User: "wait"
[2024-01-01 10:00:10] Filter: should_interrupt=True, reason=contains_interrupt_command
[2024-01-01 10:00:10] Agent: [STOPS]
[2024-01-01 10:00:11] Agent: "How can I help you?"
```

## Troubleshooting

### Issue: Agent still stops on "yeah"

**Check:**
1. Is the filter enabled? `LIVEKIT_INTERRUPTION_FILTER_ENABLED=true`
2. Is "yeah" in the passive words list?
3. Check debug logs to see filter decision

### Issue: Agent doesn't respond to "yeah" when silent

**Check:**
1. This is expected behavior - when agent is silent, all input is processed normally
2. The filter only applies when agent is speaking
3. Verify agent state is "listening" or "idle" when you speak

### Issue: Filter not working at all

**Check:**
1. Verify the code changes are in place
2. Check that `_interruption_filter` is initialized in AgentActivity
3. Enable debug logging to see filter decisions
4. Verify STT is working and providing transcripts

## Performance Testing

The filter should have minimal latency impact:

- Filter decision should be < 1ms
- No noticeable delay in interruption handling
- Real-time performance maintained

Test with:
```bash
# Monitor response times
python -m cProfile -o profile.stats interruption_filter_demo.py dev
```

## Next Steps

After testing:
1. ✅ Verify all scenarios pass
2. ✅ Record video/log transcript as proof
3. ✅ Create branch: `feature/interrupt-handler-<yourname>`
4. ✅ Commit changes
5. ✅ Submit PR to the forked repository (NOT original LiveKit repo)