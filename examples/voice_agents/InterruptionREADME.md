# Intelligent Speech Interruption Manager for Voice Agents

**Overview:**  
This project improves the natural flow of conversations in voice AI agents by differentiating between **passive acknowledgments** (like “yeah” or “uh-huh”) and **active commands** (like “stop” or “wait”) that require immediate agent attention.

---

## Why This Matters

Many voice agents interrupt themselves **every time a user speaks**, leading to:

- **Mistaken interruptions** caused by short acknowledgments  
- **Unnecessary UI indicators** flashing for minor speech  
- **Disjointed conversation flow** for the user  

**Example Scenario:**  

Agent: "Next, open your browser and go to settings..."
User: "Uh-huh" ← Should be ignored
Agent: [Stops] ❌ Bad UX

Agent: "Next, open your browser and go to settings..."
User: "Wait, I have a question" ← Should interrupt
Agent: [Stops] ✅ Correct behavior

---

## Solution Summary

We built a **Smart Interruption Manager** with these capabilities:

- **Skip passive phrases** while the agent is speaking  
- **React immediately** to command words  
- **Reduce start-of-speech flicker** in the UI  
- **Dual-path processing**: Fast for partial speech, robust for complete sentences  

---

## System Flow

User Audio → Voice Activity Detection → Speech-to-Text → Interruption Manager → LLM → Text-to-Speech → Agent Voice
↑
│
stt_node() Override
│
┌──────────────────────────┼─────────────────────────┐
↓ ↓ ↓
INTERIM_TRANSCRIPT FINAL_TRANSCRIPT START_OF_SPEECH
(Quick) (Accurate) (Suppressed)

### Two-Tiered Processing

| Mode | Event Type | Purpose | Typical Delay |
|------|------------|---------|---------------|
| Quick | INTERIM_TRANSCRIPT | React to commands instantly | ~100ms |
| Full | FINAL_TRANSCRIPT | Evaluate complete input | ~500ms |

---

## Key Modules

### 1. Interruption Filter (`interruption_filter.py`)

Contains the logic for classifying speech:

| Function | Role |
|----------|------|
| `should_interrupt_optimistic(text)` | Fast detection on partial text |
| `should_interrupt_agent(text, is_speaking)` | Detailed check for final transcript |
| `clean_text(text)` | Standardizes text for comparison |

### 2. Agent Logic (`basic_agent.py`)

- Overrides `stt_node()` to process all speech events  
- Filters input before sending it to the LLM  
- Controls which phrases are ignored vs. processed  

---

## How the Filter Works

```python
async def stt_node(self, audio, model_settings):
    async for event in Agent.default.stt_node(self, audio, model_settings):
        is_speaking = self.session.agent_state == "speaking"

        if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
            if is_speaking and should_interrupt_optimistic(partial_text):
                self.session.interrupt()
            yield event

        elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
            if should_interrupt_agent(text, is_speaking):
                if is_speaking:
                    self.session.interrupt()
                yield event
            else:
                continue

        elif event.type == SpeechEventType.START_OF_SPEECH:
            if is_speaking:
                continue
            yield event
            
Action Table           

| User Input      | Agent Talking? | Contains Command? | Outcome                       |
| --------------- | -------------- | ----------------- | ----------------------------- |
| "Yeah"          | ✅              | ❌                 | Ignored                       |
| "Yeah"          | ❌              | ❌                 | Processed normally            |
| "Stop"          | ✅              | ✅                 | Interrupt immediately         |
| "Yeah but wait" | ✅              | ✅                 | Interrupt (command overrides) |
| "Tell me more"  | ✅              | ❌                 | Interrupt (user query)        |


Customization & Configuration
Passive Words (Ignored while agent speaks)
PASSIVE_WORDS = {"yeah", "yep", "uh-huh", "ok", "mhmm", "sure", "got it"}
Active Commands (Always trigger interruption)
ACTIVE_WORDS = {"stop", "wait", "hold", "pause", "cancel", "actually"}
Agent Session Settings Example
session = AgentSession(
    allow_interruptions=True,
    resume_false_interruption=True,
    false_interruption_timeout=1.5,
    min_interruption_words=2
)
Installation & Running
Requirements

Python 3.9 or higher

LiveKit Agents SDK

API keys for Deepgram, OpenAI, Cartesia

Environment Variables

Create a .env file in your project directory:
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
CARTESIA_API_KEY=your_cartesia_key
Start the Agent
cd examples/voice_agents
python basic_agent.py dev

Usage

Connect to the LiveKit room
Speak naturally to the agent
Passive words like "yeah" → ignored
Commands like "stop" → interrupt immediately
Check logs for filter actions:

⚡ FAST INTERRUPT: Heard partial 'sto...'
🛑 FINAL INTERRUPT: Heard 'wait a moment'
🔇 IGNORING BACKCHANNEL: 'yeah'

| Scenario | User Says                     | Expected Result                |
| -------- | ----------------------------- | ------------------------------ |
| 1        | "Uh-huh"                      | Agent continues                |
| 2        | "Stop"                        | Agent interrupts immediately   |
| 3        | "Actually, I have a question" | Agent interrupts and processes |
| 4        | "Yeah okay cool"              | Ignored                        |
| 5        | "Yeah but wait"               | Agent interrupts               |

Edge Cases:

Mixed phrases: "Yeah, but actually..." → Interrupt

Long acknowledgments: "Oh yeah okay sure" → Ignore

Unknown sentences: "My cat is orange" → Interrupt

Notes on Implementation

stt_node() intercepts speech before LLM sees it

Filters events based on agent state

Keeps conversation flow natural

Event Handling
Event	Description	Handling
START_OF_SPEECH	User started talking	Suppress if agent is speaking
INTERIM_TRANSCRIPT	Partial speech	Fast command detection
FINAL_TRANSCRIPT	Complete sentence	Full classification
END_OF_SPEECH	User finished	Passed to LLM unchanged

Project Layout
examples/voice_agents/
├── basic_agent.py            # Agent with smart stt_node() override
├── interruption_filter.py    # Command/backchannel logic
├── .env                      # API credentials
├── README.md                 # Project documentation
