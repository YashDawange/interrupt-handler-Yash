Hi, I’m here. How can I help?


### ✔ Smooth Audio Output  
Uses preemptive_generation=True for clear, non-choppy TTS.

---

# 2. Requirements

requirements.txt



livekit-agents~=1.0.0
livekit-plugins-google
livekit-plugins-deepgram
livekit-plugins-silero
python-dotenv


---

# 3. Installation

### Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

Install Dependencies
pip install -r requirements.txt

Add Environment Variables

Create .env:

LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

DEEPGRAM_API_KEY=...
GOOGLE_API_KEY=...

4. Project Files
my_agent.py      # Main agent logic
logic.py         # Interruption + filler decision rules
README.md
requirements.txt

5. How to Run
python my_agent.py


You should see:

>>> STARTING AGENT
>>> Connected to room <room>


Join from LiveKit Playground or your client device.

6. Behavior Breakdown
6.1 Filler Words (Ignored)

Examples:

mhmm
hmm
yeah
ok
right
uhhuh


Behavior:

Agent speaking? → Ignored (no interruption)

Agent silent? → Ignored (no response triggered)

6.2 Interrupt Commands

Examples:

stop
wait
no
hello?
what?
question
again


Behavior:

Interrupts immediately

Agent cancels TTS and listens

6.3 Greetings (Special Case)

Input:

Hello?
Hey
Hi


Behavior (only when agent is silent):

Hi, I’m here. How can I help?

6.4 Real User Queries

Examples:

Tell me about the French Revolution.
Explain how LLMs work.
Who was Isaac Newton?


Behavior:

Agent responds with a short, complete, 1–2 sentence answer

No follow-up questions unless explicitly asked

7. Testing Scenarios
Test 1 — Filler While Speaking
Agent: "... France faced economic hardship ..."
User: mhmm
Agent: (continues speaking normally)

Test 2 — Interrupt While Speaking
User: stop
Agent: immediately stops talking

Test 3 — Greeting While Silent
User: Hello?
Agent: Hi, I’m here. How can I help?

Test 4 — Real Question While Silent
User: Can you explain LLMs?
Agent: LLMs are neural networks trained on large datasets.

Test 5 — Partial STT Protection

User whispers or breathes:

m
mh
mm
hm


Behavior:

Ignored

No interruption

No response

8. Troubleshooting
Agent responds to “mhmm”

Ensure on_stt_update checks:

Silence mode filler ignore

Speaking mode filler ignore

Partial STT ignore

Agent sounds choppy

Enabled automatically via:

preemptive_generation=True


Ensure:

Stable network

LLM responds with short sentences

9. Architecture Summary
Event Flow:
User Speech → VAD → STT → on_stt_update
    ↓
Interruption or ignore logic
    ↓
LLM (if needed)
    ↓
TTS → Playback