# Demo Video Script (30-60 seconds)

## Overview
This script is for recording a 30-60 second demo video showing the InterruptHandler in action.

## Recording Setup
1. Open terminal/console
2. Navigate to project directory
3. Have the demo script ready to run
4. Record screen with console output visible

## Script

### Introduction (5 seconds)
**Narrator**: "Voice agents often get cut off by backchannel words like 'yeah' or 'ok'. This InterruptHandler distinguishes backchannel from real interrupts."

**[Show terminal/console]**

### Scenario 1: Immediate Routing (10 seconds)
**Narrator**: "When the agent is silent, user speech routes immediately."

**[Run demo, show Scenario 1 output]**
```bash
python scripts/run_demo.py
```

**[Highlight console output showing]**
- "Agent is silent (not playing)"
- "on_immediate_user_speech called: True"
- "✓ PASS: User speech routed immediately"

### Scenario 2: Soft Backchannel (15 seconds)
**Narrator**: "When the agent is speaking and the user says 'yeah', the handler pauses briefly, detects it's a backchannel word, and resumes playback."

**[Show Scenario 2 output]**
**[Highlight]**
- "User says 'yeah' (backchannel)..."
- "[AUDIO] Paused"
- "[AUDIO] Resumed"
- "Interrupts triggered: 0"
- "✓ PASS: Soft backchannel words ignored, audio resumed"

### Scenario 3: Hard Interrupt (15 seconds)
**Narrator**: "When the user says 'stop', the handler immediately interrupts and stops playback."

**[Show Scenario 3 output]**
**[Highlight]**
- "User says 'stop' (hard interrupt)..."
- "[AUDIO] Paused"
- "[AUDIO] Stopped"
- "Interrupts triggered: 1"
- "✓ PASS: Hard interrupt word triggered stop"

### Scenario 4: Mixed Utterance (10 seconds)
**Narrator**: "Mixed utterances like 'yeah wait' also trigger interrupts because they contain hard words."

**[Show Scenario 4 output]**
**[Highlight]**
- "User says 'yeah wait' (mixed: soft + hard)..."
- "[AUDIO] Stopped"
- "✓ PASS: Mixed utterance triggered interrupt"

### Conclusion (5 seconds)
**Narrator**: "The InterruptHandler successfully prevents false interrupts from backchannel words while allowing real interrupts."

**[Show final summary]**
- "ALL SCENARIOS PASSED ✓"
- List of successful behaviors

## Tips for Recording
- Keep console output clearly visible
- Pause briefly between scenarios for clarity
- Use screen recording software (OBS, QuickTime, etc.)
- Keep total video length to 30-60 seconds
- Focus on the console output and pass/fail messages

## What to Highlight
1. The different behaviors for each scenario
2. The pause/resume/stop audio actions
3. The interrupt count (0 for soft words, 1+ for hard words)
4. The final "ALL SCENARIOS PASSED" message

