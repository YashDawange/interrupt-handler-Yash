# Intelligent Interruption Handler (LiveKit)

This example adds a small logic layer on top of LiveKit Agents so the assistant does not get interrupted by filler words like “yeah” or “ok”, but still stops immediately on real commands like “stop” or “wait”.

---

## Behaviour

| Situation                                 | Result                                          |
|-------------------------------------------|-------------------------------------------------|
| Agent is speaking + user says “yeah/ok/hmm” | Ignored, agent continues smoothly               |
| Agent is speaking + user says “stop/wait/no” | Agent audio is interrupted immediately          |
| Agent is silent + user says “yeah/ok”       | Treated as a normal answer and processed        |
| Agent is speaking + “yeah okay but wait”    | Interrupts (because “wait” is a command word)   |

---

## How it works

- All speech is produced with `allow_interruptions=False`, so VAD alone cannot pause or cut the agent.
- We listen to `user_input_transcribed` events.
- While the agent is speaking:
  - If the text is only backchannel words → it is ignored.
  - If the text contains any interrupt word (`stop`, `wait`, `no`, `hold on`, `cancel`) → `session.interrupt()` is called.
- When the agent is silent, the logic does nothing and the normal LiveKit agent flow handles the text.

The ignore and interrupt word lists can be changed with environment variables:

```bash
export INTERRUPT_IGNORE_WORDS="yeah,ok,okay,hmm,uh-huh,right"
export INTERRUPT_COMMAND_WORDS="stop,wait,hold on,no,cancel"
