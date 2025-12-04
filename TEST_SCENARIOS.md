# Test Scenarios for Intelligent Interruption Handling

This document outlines the test scenarios to validate the intelligent interruption handling implementation.

## Prerequisites

Before testing, ensure:
1. Virtual environment is activated
2. All dependencies are installed
3. `.env` file is configured with valid API keys:
   - `LIVEKIT_URL`
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_API_SECRET`
   - `DEEPGRAM_API_KEY`
   - `OPENAI_API_KEY`
   - `CARTESIA_API_KEY`

## Running the Agent

### Development Mode (with LiveKit Playground)

```bash
cd examples/voice_agents
python intelligent_interruption_agent.py dev
```

Then open the [LiveKit Agents Playground](https://agents-playground.livekit.io/) and connect to your agent.

### Console Mode (Terminal Testing)

```bash
cd examples/voice_agents
python intelligent_interruption_agent.py console
```

This allows you to test with your local microphone and speakers.

## Test Scenarios

### ✅ Scenario 1: Long Explanation Test

**Purpose:** Verify that agent continues speaking when user provides passive acknowledgements.

**Steps:**
1. Start the agent
2. Wait for the greeting
3. Say: "Tell me about artificial intelligence in detail"
4. While the agent is explaining (speaking):
   - Say "okay" (pause)
   - Say "yeah" (pause)
   - Say "uh-huh" (pause)
   - Say "hmm" (pause)
   - Say "right" (pause)

**Expected Result:**
- ✅ Agent CONTINUES speaking without interruption
- ✅ No audible pause or stutter in agent's speech
- ✅ Agent completes the full explanation
- ✅ Filler words are not processed as interruptions

**Log Output to Look For:**
```
DEBUG: User transcript (interim): 'yeah' (agent_was_speaking: True)
DEBUG: Text contains only filler words: 'yeah'
INFO: 🔇 IGNORING interruption - agent continues speaking
INFO: ✅ Resumed agent speech successfully
```

---

### ✅ Scenario 2: Passive Affirmation Test

**Purpose:** Verify that agent responds to filler words when NOT speaking.

**Steps:**
1. Start the agent
2. Wait for the greeting to finish completely (agent goes silent)
3. After silence (agent in "listening" state):
   - Say "yeah"

**Expected Result:**
- ✅ Agent PROCESSES "yeah" as valid input
- ✅ Agent responds (e.g., "Great! What would you like to know?")
- ✅ Normal conversational flow continues

**Log Output to Look For:**
```
DEBUG: User transcript (final): 'yeah' (agent_was_speaking: False)
DEBUG: Agent was not speaking, allowing interruption
INFO: 🛑 ALLOWING interruption - user input: 'yeah'
```

---

### ✅ Scenario 3: Active Correction Test

**Purpose:** Verify that agent stops immediately on interruption keywords.

**Steps:**
1. Start the agent
2. Say: "Count to 20 for me"
3. While the agent is counting (e.g., "One, two, three, four..."):
   - Say "stop" or "wait" or "no"

**Expected Result:**
- ✅ Agent STOPS immediately
- ✅ Agent does NOT resume counting
- ✅ Agent listens for new input

**Log Output to Look For:**
```
DEBUG: User transcript (interim): 'stop' (agent_was_speaking: True)
DEBUG: Found interruption keyword: 'stop'
INFO: 🛑 ALLOWING interruption - user input: 'stop'
```

---

### ✅ Scenario 4: Mixed Input Test

**Purpose:** Verify that mixed filler + interruption keywords trigger interruption.

**Steps:**
1. Start the agent
2. Say: "Explain quantum computing"
3. While the agent is explaining:
   - Say "Yeah okay but wait"

**Expected Result:**
- ✅ Agent STOPS (because "but" and "wait" are interruption keywords)
- ✅ Even though "yeah okay" are filler words, the presence of interruption keywords triggers interruption

**Log Output to Look For:**
```
DEBUG: User transcript (interim): 'yeah okay but wait' (agent_was_speaking: True)
DEBUG: Found interruption keyword: 'but'
DEBUG: Found interruption keyword: 'wait'
INFO: 🛑 ALLOWING interruption - user input: 'yeah okay but wait'
```

---

### ✅ Scenario 5: Multiple Rapid Fillers Test

**Purpose:** Verify agent handles multiple rapid filler words smoothly.

**Steps:**
1. Start the agent
2. Say: "Tell me a long story"
3. While agent is speaking, say rapidly:
   - "yeah" ... "okay" ... "hmm" ... "right" ... "uh-huh"

**Expected Result:**
- ✅ Agent continues speaking throughout
- ✅ No stuttering or repeated pausing
- ✅ Smooth, natural speech flow

---

### ✅ Scenario 6: Interruption After Filler Test

**Purpose:** Verify that real interruptions work after filler words.

**Steps:**
1. Start the agent
2. Say: "Explain machine learning"
3. While agent is speaking:
   - Say "yeah" (should be ignored)
   - Wait 1 second
   - Say "actually, stop" (should interrupt)

**Expected Result:**
- ✅ First "yeah" is ignored, agent continues
- ✅ Second "actually, stop" triggers interruption
- ✅ Agent stops and listens

---

### ✅ Scenario 7: Context Switch Test

**Purpose:** Verify state tracking across speaking/silent transitions.

**Steps:**
1. Start the agent
2. Say "hello" → agent responds and goes silent
3. Say "yeah" → agent should respond (not ignore)
4. Say "tell me about AI" → agent starts explaining
5. While agent explaining, say "okay" → should be ignored
6. Agent finishes, goes silent
7. Say "hmm" → agent should respond

**Expected Result:**
- ✅ "yeah" in step 3: Processed as valid input
- ✅ "okay" in step 5: Ignored (agent continues)
- ✅ "hmm" in step 7: Processed as valid input

---

## Debugging Commands

### Enable Debug Logging

To see detailed logs of the interruption handling logic, the agent is already configured with DEBUG level logging for the interruption handler.

### Monitor Logs

Look for these key log messages:

**Filler Word Detection:**
```
DEBUG: Text contains only filler words: 'yeah'
DEBUG: Found non-filler word: 'wait'
```

**Interruption Decisions:**
```
INFO: 🔇 IGNORING interruption - agent continues speaking
INFO: 🛑 ALLOWING interruption - user input: 'stop'
```

**State Changes:**
```
DEBUG: Agent state changed: listening → speaking
DEBUG: Agent state changed: speaking → listening
```

**Resume Actions:**
```
INFO: ✅ Resumed agent speech successfully
```

## Common Issues & Troubleshooting

### Issue 1: Agent doesn't resume after filler word

**Symptom:** Agent pauses briefly when you say "yeah"

**Possible Causes:**
- Audio output doesn't support pause/resume
- STT latency too high

**Solution:**
Check logs for:
```
WARNING: Audio output does not support pause/resume
```

If you see this, the fallback behavior will allow brief interruptions.

### Issue 2: Agent stops on filler words

**Symptom:** Agent stops even when you say "yeah"

**Possible Causes:**
- STT is producing different text (e.g., "yep" instead of "yeah")
- Word not in filler words list

**Solution:**
1. Check debug logs for actual transcript
2. Add the word to `DEFAULT_FILLER_WORDS` set
3. Restart agent

### Issue 3: Agent doesn't stop on interruption keywords

**Symptom:** Agent continues even when you say "stop"

**Possible Causes:**
- STT confidence is low, producing incorrect text
- Word not in interruption keywords list

**Solution:**
1. Check debug logs for actual transcript
2. Speak more clearly
3. Add variants to `INTERRUPTION_KEYWORDS` set

## Performance Metrics

**Expected Latencies:**

| Metric | Target | Actual |
|--------|--------|--------|
| VAD Detection | < 100ms | ~50-80ms |
| STT Latency | < 500ms | ~200-400ms (Deepgram) |
| Resume Delay | < 100ms | ~50ms |
| **Total Pause Duration** | **< 200ms** | **~150-200ms** |

The total pause duration of ~150-200ms is imperceptible to users and feels like continuous speech.

## Success Criteria

All scenarios must pass with these criteria:

1. **No audible stuttering** when filler words are spoken during agent speech
2. **Immediate response** to interruption keywords (< 500ms)
3. **Proper context awareness** (different behavior when speaking vs silent)
4. **Reliable detection** of mixed inputs (filler + interruption)
5. **Smooth transitions** between states

## Video Recording Tips

When creating a demo video:

1. **Use screen recording** to show both audio waveforms and logs
2. **Narrate clearly** what you're testing: "Now I'll say 'yeah' while the agent is speaking..."
3. **Show log output** split-screen to demonstrate the decision-making
4. **Test all 4 core scenarios** at minimum
5. **Keep video under 5 minutes** for clarity

## Automated Testing (Future Enhancement)

For future work, consider implementing automated tests:

```python
import pytest
from livekit.agents import AgentSession

@pytest.mark.asyncio
async def test_filler_word_ignored_when_speaking():
    """Test that 'yeah' is ignored when agent is speaking"""
    session = AgentSession(...)
    handler = IntelligentInterruptionHandler(session)

    # Simulate agent speaking
    session._update_agent_state("speaking")
    handler._agent_was_speaking_on_interrupt = True

    # Simulate user saying "yeah"
    should_ignore = handler._should_ignore_interruption("yeah", True)

    assert should_ignore == True

@pytest.mark.asyncio
async def test_filler_word_processed_when_silent():
    """Test that 'yeah' is processed when agent is silent"""
    # Similar test for silent state
    ...
```

---

**Happy Testing!** 🎉

For questions or issues, refer to the main documentation: `README_INTERRUPTION_CHALLENGE.md`
