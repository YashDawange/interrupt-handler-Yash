# Intelligent Interruption Handler – Assignment Submission

This submission implements an intelligent interruption handling layer for the LiveKit voice agent. The goal is to distinguish between passive acknowledgments and active interruption commands without modifying VAD behavior, and to pass all four assignment scenarios.

## Core Logic

### 1. Passive Backchannel (Ignored While Speaking)
Words such as: `yeah`, `ok`, `okay`, `hmm`, `uh-huh`, `right`, `sure`
- Ignored while the agent is speaking
- Do not interrupt or pause the response

### 2. Active Commands (Interrupt Immediately)
Words such as: `stop`, `wait`, `no`, `hold on`, `pause`, `enough`, `cancel`
- Immediately interrupt the agent
- Agent stops mid-sentence and does not resume automatically

### 3. Passive Acknowledgment When Silent
If the agent is silent and user says “yeah/ok/hmm”:
- Treated as confirmation
- Agent continues conversation normally

### 4. Mixed Input Handling
Example: “yeah okay but wait”
- Contains a command word (“wait”)
- Entire input is treated as an interrupt

## Files Added / Modified

### Added:
`examples/voice_agents/backchannel_handler.py`  
Implements:
- Backchannel vs. command word detection
- Transcript normalization
- Speech-state awareness via `agent_state_changed`
- Hard stop using `session.interrupt(force=True)`
- Clearing user turns using `session.clear_user_turn()` to prevent LLM restarts

### Modified:
`examples/voice_agents/basic_agent.py`  
Changes:
- Attached the interruption handler
- Updated AgentSession configuration:

allow_interruptions=False
discard_audio_if_uninterruptible=False
false_interruption_timeout=None
resume_false_interruption=False

These ensure:

Agent does NOT auto-interrupt

Agent still receives user audio while speaking

Only the custom handler decides interruptions

How to Run

1.Create a .env file with:

LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=
DEEPGRAM_API_KEY=
CARTESIA_API_KEY=

2.Run the agent:

cd examples/voice_agents
python basic_agent.py dev

3.Connect via LiveKit Agents Playground to test scenarios.
