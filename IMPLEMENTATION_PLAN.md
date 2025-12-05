# LiveKit Intelligent Interruption Handling - Implementation Plan

## Overview
This document outlines the implementation strategy for adding intelligent interruption handling to the LiveKit agents framework.

## Problem Analysis
Currently, the agent stops speaking whenever VAD detects user speech, even for backchannel words like "yeah", "ok", "hmm". We need to:
1. Track agent speaking state
2. Filter backchannel words when agent is speaking
3. Allow real interruptions (commands like "stop", "wait")
4. Process backchannel words normally when agent is silent

## Key Files to Modify

### 1. `livekit-agents/livekit/agents/voice/agent_session.py`
- Add agent speaking state tracking
- Implement interruption filtering logic
- Add configurable backchannel word list

### 2. `livekit-agents/livekit/agents/voice/audio_recognition.py`
- Modify `_on_stt_event` to check if input should be ignored
- Add logic to distinguish between backchannel and command words

### 3. `livekit-agents/livekit/agents/voice/agent.py`
- Add configuration parameter for backchannel words list
- Pass configuration to agent session

## Implementation Strategy

### Phase 1: Add Configuration
1. Add `backchannel_words` parameter to `Agent.__init__`
2. Add `backchannel_words` parameter to `AgentSession.__init__`
3. Create default list: `['yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 'aha', 'mhm', 'uh', 'ah']`

### Phase 2: Track Agent Speaking State
1. Add `_is_agent_speaking` flag to `AgentSession`
2. Update flag when TTS starts/stops playback
3. Ensure flag is accessible to audio recognition module

### Phase 3: Implement Filtering Logic
1. Create function to check if transcript contains only backchannel words
2. Create function to check if transcript contains command words
3. Modify interruption logic to:
   - If agent is speaking AND transcript is only backchannel → ignore
   - If agent is speaking AND transcript contains commands → interrupt
   - If agent is silent → process normally

### Phase 4: Handle Mixed Input
1. Parse transcripts for command words like "wait", "stop", "no", "hold on"
2. If mixed input detected (e.g., "yeah wait"), treat as interruption

## Technical Approach

### Timing Challenge
Since VAD triggers before STT completes:
1. Buffer the interruption event briefly
2. Wait for STT transcription (with timeout ~200-500ms)
3. Decide whether to actually interrupt based on transcript content
4. If ignored, continue playback seamlessly

### State Machine
```
Agent State: SPEAKING | SILENT
User Input: BACKCHANNEL | COMMAND | MIXED | OTHER

Decision Matrix:
- SPEAKING + BACKCHANNEL → IGNORE
- SPEAKING + COMMAND → INTERRUPT
- SPEAKING + MIXED → INTERRUPT
- SPEAKING + OTHER → INTERRUPT
- SILENT + ANY → PROCESS
```

## Configuration Example

```python
agent = Agent(
    instructions="You are a helpful assistant",
    backchannel_words=['yeah', 'ok', 'hmm', 'right', 'uh-huh'],
    command_words=['stop', 'wait', 'no', 'hold on', 'pause'],
)
```

## Testing Strategy

### Test Cases
1. **Scenario 1**: Agent speaking + user says "yeah" → No interruption
2. **Scenario 2**: Agent silent + user says "yeah" → Process as input
3. **Scenario 3**: Agent speaking + user says "stop" → Interrupt
4. **Scenario 4**: Agent speaking + user says "yeah wait" → Interrupt
5. **Scenario 5**: Agent speaking + user says "tell me more" → Interrupt

## Next Steps
1. Implement configuration parameters
2. Add speaking state tracking
3. Implement filtering logic
4. Test with various scenarios
5. Create demo video
6. Document changes in README
