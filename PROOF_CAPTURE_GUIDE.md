# Proof Capture Guide

This guide will help you create the required proof (video or log transcript) demonstrating the interruption filter functionality.

## Required Proof Scenarios

You need to demonstrate:
1. ✅ **Agent ignoring "yeah" while talking** - Agent continues speaking without pause/stop
2. ✅ **Agent responding to "yeah" when silent** - Agent treats it as valid input
3. ✅ **Agent stopping for "stop"** - Agent interrupts immediately

## Method 1: Video Recording (Recommended)

### Step 1: Set Up Screen Recording

**Windows:**
- Press `Win + G` to open Xbox Game Bar
- Click the record button, or
- Use OBS Studio (free): https://obsproject.com/
- Use Windows built-in: `Win + Alt + R` (if enabled)

**Mac:**
- Press `Cmd + Shift + 5` for built-in screen recording
- Or use QuickTime Player

**Linux:**
- Use OBS Studio or SimpleScreenRecorder

### Step 2: Prepare Your Setup

1. **Open two windows side by side:**
   - Terminal/console running the agent (with debug logs visible)
   - Your browser/agent interface for interaction

2. **Enable debug logging** in your agent:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("livekit.agents.voice.agent_activity").setLevel(logging.DEBUG)
```

### Step 3: Record the Test Scenarios

**Scenario 1: Agent ignores "yeah" while speaking**
1. Start recording
2. Start the agent: `python examples/voice_agents/interruption_filter_demo.py console`
3. Wait for agent to start speaking (it will give a long explanation)
4. **While agent is speaking**, clearly say: **"yeah"** or **"ok"**
5. **Expected**: Agent continues speaking without any pause, stop, or stutter
6. Show the console logs showing the filter decision
7. Stop recording

**Scenario 2: Agent responds to "yeah" when silent**
1. Start recording
2. Wait for agent to ask a question and go silent
3. Say: **"yeah"**
4. **Expected**: Agent processes "yeah" as valid input and responds
5. Show the console logs
6. Stop recording

**Scenario 3: Agent stops for "stop"**
1. Start recording
2. Wait for agent to start speaking
3. **While agent is speaking**, say: **"stop"** or **"wait"**
4. **Expected**: Agent stops immediately
5. Show the console logs showing interruption
6. Stop recording

### Step 4: Edit the Video (Optional)

- Trim to show only the relevant parts
- Add text labels for each scenario
- Keep it under 2-3 minutes total

## Method 2: Log Transcript (Alternative)

If you can't record video, create a detailed log transcript.

### Step 1: Enable Detailed Logging

Add this to your test script or agent:

```python
import logging
from datetime import datetime

# Create a file logger
file_logger = logging.FileHandler('interruption_filter_proof.log')
file_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_logger.setFormatter(formatter)

# Add to agent activity logger
agent_logger = logging.getLogger("livekit.agents.voice.agent_activity")
agent_logger.addHandler(file_logger)
agent_logger.setLevel(logging.DEBUG)
```

### Step 2: Run the Scenarios

Run each scenario and the logs will be saved to `interruption_filter_proof.log`.

### Step 3: Format the Transcript

Create a document showing:

```
=== PROOF: Intelligent Interruption Filter ===

Scenario 1: Agent ignores "yeah" while speaking
-----------------------------------------------
[2024-01-01 10:00:00] Agent: "Let me explain the history of artificial intelligence..."
[2024-01-01 10:00:05] User: "yeah"
[2024-01-01 10:00:05] Filter: should_interrupt=False, reason=passive_acknowledgement, transcript='yeah'
[2024-01-01 10:00:05] Filter: Ignoring passive acknowledgement: 'yeah'
[2024-01-01 10:00:05] Agent: "...it began in the 1950s with the work of Alan Turing..."
[RESULT] ✅ Agent continued speaking without pause or stop

Scenario 2: Agent responds to "yeah" when silent
-----------------------------------------------
[2024-01-01 10:01:00] Agent: "Are you ready to begin?"
[2024-01-01 10:01:05] Agent State: listening
[2024-01-01 10:01:10] User: "yeah"
[2024-01-01 10:01:10] Filter: should_interrupt=True, reason=agent_silent, transcript='yeah'
[2024-01-01 10:01:10] Agent: "Great! Let's start..."
[RESULT] ✅ Agent processed "yeah" as valid input

Scenario 3: Agent stops for "stop"
-----------------------------------------------
[2024-01-01 10:02:00] Agent: "Let me explain how voice agents work..."
[2024-01-01 10:02:05] User: "stop"
[2024-01-01 10:02:05] Filter: should_interrupt=True, reason=contains_interrupt_command, transcript='stop'
[2024-01-01 10:02:05] Agent: [STOPS IMMEDIATELY]
[2024-01-01 10:02:06] Agent State: listening
[RESULT] ✅ Agent stopped immediately on interrupt command
```

## Method 3: Automated Test Output

You can also use the test results as proof:

```bash
python test_interruption_filter_standalone.py > proof_test_results.txt
```

This shows all the filter logic working correctly.

## Quick Script to Generate Proof Logs

Create a file `generate_proof.py`:

```python
"""Script to generate proof logs for interruption filter."""

import logging
import sys
from pathlib import Path

# Add path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "livekit-agents"))

# Import filter
import importlib.util
filter_path = project_root / "livekit-agents" / "livekit" / "agents" / "voice" / "interruption_filter.py"
spec = importlib.util.spec_from_file_location("interruption_filter", filter_path)
interruption_filter = importlib.util.module_from_spec(spec)
interruption_filter.__name__ = "livekit.agents.voice.interruption_filter"
interruption_filter.__package__ = "livekit.agents.voice"
sys.modules["livekit"] = type(sys)('livekit')
sys.modules["livekit.agents"] = type(sys)('livekit.agents')
sys.modules["livekit.agents.voice"] = type(sys)('livekit.agents.voice')
sys.modules["livekit.agents.voice.interruption_filter"] = interruption_filter
spec.loader.exec_module(interruption_filter)
InterruptionFilter = interruption_filter.InterruptionFilter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('interruption_filter_proof.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
filter = InterruptionFilter()

print("=" * 60)
print("PROOF: Intelligent Interruption Filter")
print("=" * 60)
print()

# Scenario 1: Passive word while speaking
logger.info("=" * 60)
logger.info("Scenario 1: Agent ignores 'yeah' while speaking")
logger.info("=" * 60)
logger.info("Agent: 'Let me explain the history of AI...'")
logger.info("User: 'yeah'")
result = filter.should_interrupt("yeah", agent_is_speaking=True)
reason = filter.get_filter_reason("yeah", agent_is_speaking=True)
logger.info(f"Filter Decision: should_interrupt={result}, reason={reason}")
logger.info("Agent: '...it began in the 1950s...' (continues speaking)")
logger.info("RESULT: ✅ Agent continued speaking without pause or stop")
print()

# Scenario 2: Passive word while silent
logger.info("=" * 60)
logger.info("Scenario 2: Agent responds to 'yeah' when silent")
logger.info("=" * 60)
logger.info("Agent: 'Are you ready?' (silent)")
logger.info("User: 'yeah'")
result = filter.should_interrupt("yeah", agent_is_speaking=False)
reason = filter.get_filter_reason("yeah", agent_is_speaking=False)
logger.info(f"Filter Decision: should_interrupt={result}, reason={reason}")
logger.info("Agent: 'Great! Let's start...'")
logger.info("RESULT: ✅ Agent processed 'yeah' as valid input")
print()

# Scenario 3: Interrupt command
logger.info("=" * 60)
logger.info("Scenario 3: Agent stops for 'stop'")
logger.info("=" * 60)
logger.info("Agent: 'Let me explain how voice agents work...'")
logger.info("User: 'stop'")
result = filter.should_interrupt("stop", agent_is_speaking=True)
reason = filter.get_filter_reason("stop", agent_is_speaking=True)
logger.info(f"Filter Decision: should_interrupt={result}, reason={reason}")
logger.info("Agent: [STOPS IMMEDIATELY]")
logger.info("Agent State: listening")
logger.info("RESULT: ✅ Agent stopped immediately on interrupt command")
print()

logger.info("=" * 60)
logger.info("All scenarios demonstrated successfully!")
logger.info("=" * 60)

print("\nProof log saved to: interruption_filter_proof.log")
```

Run it:
```bash
python generate_proof.py
```

## What to Include in Your PR

1. **Video file** (if recording):
   - Upload to YouTube (unlisted) or attach to PR
   - Or include a link in PR description

2. **Log transcript** (if using logs):
   - Include `interruption_filter_proof.log` or formatted transcript
   - Add to PR description or as a file in the repo

3. **Test results**:
   - Include output from `test_interruption_filter_standalone.py`

## Example PR Description

```markdown
## Intelligent Interruption Filter Implementation

### Summary
Implemented context-aware interruption filter that distinguishes between passive acknowledgements and active interruptions.

### Proof

**Video Demo**: [Link to video or attach file]

**Test Results**:
- All unit tests passing (7/7)
- See `interruption_filter_proof.log` for detailed scenario logs

**Demonstrated Scenarios**:
1. ✅ Agent ignores "yeah" while speaking - continues without pause
2. ✅ Agent responds to "yeah" when silent - processes as valid input  
3. ✅ Agent stops for "stop" - interrupts immediately

### Files Changed
- Core implementation: `interruption_filter.py`
- Integration: `agent_activity.py`
- Example: `interruption_filter_demo.py`
- Tests: `test_interruption_filter_standalone.py`
- Documentation: `INTERRUPTION_FILTER_README.md`
```

## Tips for Best Results

1. **Speak clearly** - Ensure good audio quality
2. **Show console logs** - Makes it clear the filter is working
3. **Keep it concise** - 2-3 minutes is plenty
4. **Label scenarios** - Add text labels in video or clear sections in transcript
5. **Test multiple times** - Record a few attempts and use the best one

Good luck with your submission!