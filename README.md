## Intelligent Interruption Handling

### Problem
LiveKit’s default VAD interrupts the agent whenever user speech
is detected. This causes the agent to stop even when the user
only provides passive acknowledgements like "yeah" or "ok".

### Solution
A state-aware interruption handler was implemented as a logic
layer above VAD. Interruption decisions are made only after
semantic validation of STT transcripts.

### Behavior
- Agent speaking + "yeah / ok" → ignored
- Agent speaking + "stop / wait" → interrupt
- Agent silent + "yeah" → valid response

### Why VAD Was Not Modified
VAD was intentionally left unchanged to preserve real-time
performance. All logic operates after VAD triggers.

### Testing
The interruption logic was unit-tested using deterministic
test cases covering all required scenarios.
