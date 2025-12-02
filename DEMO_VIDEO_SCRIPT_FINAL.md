# Demo Video Script (30-60 seconds)

## Overview
This script demonstrates the InterruptHandler integration in a real voice agent scenario.

## Recording Setup
1. Open terminal showing logs
2. Have a voice agent running with InterruptHandler enabled
3. Record screen with console/logs visible
4. Use a microphone to interact with the agent

## Script

### Introduction (5 seconds)
**Narrator**: "The InterruptHandler prevents agents from being cut off by backchannel words while still allowing real interrupts."

**[Show terminal/logs]**

### Scenario 1: Soft Backchannel Ignored (15 seconds)
**Narrator**: "When the agent is speaking and the user says 'yeah', the handler pauses briefly, detects it's a backchannel word, and resumes playback."

**[Agent speaking]**
**[User says "yeah"]**
**[Show logs]**
- Highlight: "[IH] Audio paused for confirmation window"
- Highlight: "STT final: yeah"
- Highlight: "[IH] Audio resumed (soft words only, no interrupt)"
- Highlight: "Agent continues speaking"

**Narrator**: "The agent continues without interruption."

### Scenario 2: Hard Interrupt Detected (15 seconds)
**Narrator**: "When the user says 'stop', the handler immediately interrupts and stops playback."

**[Agent speaking]**
**[User says "stop"]**
**[Show logs]**
- Highlight: "[IH] Hard word detected in partial: stop"
- Highlight: "[IH] Audio stopped due to interrupt"
- Highlight: "Agent speech interrupted"

**Narrator**: "The agent stops immediately and processes the interrupt."

### Scenario 3: Mixed Utterance (10 seconds)
**Narrator**: "Mixed utterances like 'yeah wait' also trigger interrupts because they contain hard words."

**[Agent speaking]**
**[User says "yeah wait"]**
**[Show logs]**
- Highlight: "STT partial: yeah wait"
- Highlight: "[IH] Hard word detected in partial"
- Highlight: "Agent speech interrupted"

**Narrator**: "The handler correctly identifies the hard word and interrupts."

### Scenario 4: Immediate Routing (10 seconds)
**Narrator**: "When the agent is silent, user speech routes immediately without delay."

**[Agent silent]**
**[User speaks]**
**[Show logs]**
- Highlight: "[IH] Agent silent, routing immediate user speech"
- Highlight: "User input transcribed immediately"

**Narrator**: "No confirmation window is needed when the agent is silent."

### Conclusion (5 seconds)
**Narrator**: "The InterruptHandler successfully distinguishes backchannel from real interrupts, improving conversation flow."

**[Show summary]**
- Soft words ignored: ✓
- Hard interrupts detected: ✓
- Mixed utterances handled: ✓
- Immediate routing: ✓

## Tips for Recording
- Keep logs clearly visible
- Use clear, distinct voice for agent and user
- Pause briefly between scenarios
- Focus on the [IH] log messages
- Show the agent's response behavior

## What to Highlight
1. The confirmation window pause/resume cycle
2. The [IH] log prefix for handler messages
3. The difference between soft and hard word handling
4. The immediate routing when agent is silent
5. The seamless integration with existing agent pipeline

## Key Log Messages to Show
- `[IH] Agent speaking, starting confirmation window`
- `[IH] Audio paused for confirmation window`
- `[IH] Audio resumed (soft words only, no interrupt)`
- `[IH] Hard word detected in partial: <word>`
- `[IH] Audio stopped due to interrupt: <transcript>`
- `[IH] Agent silent, routing immediate user speech`

