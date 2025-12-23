# Intelligent Interruption Handling

This project implements context-aware interruption handling for a LiveKit voice agent.
It ensures that short acknowledgement words like "yeah" or "ok" do not interrupt the
agent while it is speaking, but are still processed normally when the agent is silent.

---

## What Problem This Solves

LiveKit’s default Voice Activity Detection (VAD) is very sensitive.
If a user says short filler words while the agent is speaking, the agent
often stops speaking incorrectly.

This implementation fixes that behavior without modifying the VAD kernel.

---

## How the Logic Works

- When the agent is speaking:
  - Passive acknowledgements ("yeah", "ok", "hmm") are ignored
  - Explicit commands ("stop", "wait", "no") interrupt immediately
  - Mixed input ("yeah okay but wait") interrupts correctly

- When the agent is silent:
  - All inputs, including short words like "yeah", are processed normally

The solution uses STT-based semantic validation to decide whether an
interruption is real or should be ignored.

---

## Configuration

Ignore and interrupt words are defined in:

config/interrupt_policy.py

This allows the behavior to be adjusted easily without changing agent code.

---

## How to Run

1. Create ,activate a virtual environment and Set API KEYs

   python -m venv venv  
   source venv/bin/activate   (Windows: venv\Scripts\activate)
   Set required API keys using environment variables

2. Install dependencies

    pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"

3. Run the agent from the repository root

   python examples/voice_agents/interrupt_handler_agent.py dev

Connect using the LiveKit Playground.

---

## Demo Video

The following video demonstrates all required scenarios:

- Agent continues speaking over "yeah" and "ok"
- Agent responds to "yeah" when silent
- Agent stops immediately on "stop"
- Agent interrupts on mixed input ("yeah okay but wait")

Demo link:https://drive.google.com/file/d/1bbTH3RrPbCwS1FPll-F5ggqxJ6UgYJnJ/view?usp=sharing

---

## Author

Yogesh Goutam

Branch:feature/interrupt-handler-yogeshgoutam
