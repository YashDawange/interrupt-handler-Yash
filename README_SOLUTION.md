## Solution

The core idea is simple: wait for the transcript before deciding whether to interrupt.

VAD fires fast (~50ms) but STT takes a bit longer (~200ms). So instead of letting VAD immediately stop the agent, I hold that interruption and wait for the STT. Then I check:

1. Is the agent currently speaking?
2. Is what the user said just a backchannel word like yeah or ok?

If it's just a backchannel while the agent is talking, I completely ignore it no transcript added, no LLM call, nothing. The agent just keeps going.

## Why This Works

The key insight is that backchannels should be ignored at the deepest level possible. Not just hiding them from the user, but preventing them from entering the chat context, triggering EOU detection, or generating LLM responses.

By returning False from `on_final_transcript`, the entire pipeline stops right there
