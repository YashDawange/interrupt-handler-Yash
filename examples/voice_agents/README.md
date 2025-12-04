https://drive.google.com/file/d/1hbb5Ey05NhCqU78sk9U7CeUe7LVdI5Oe/view?usp=drive_link - demo video link
How to Run the Agent

Follow these steps to set up, configure, and run the intelligent interruption-enabled LiveKit agent.

1. Clone Your Forked Repository
git clone https://github.com/<your-username>/agents-assignment
cd agents-assignment



2. Create & Activate Python Environment
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows

3. Install Dependencies
pip install -r requirements.txt

# LiveKit Agent Dependencies
livekit-agents>=0.8.0
livekit-plugins-deepgram>=0.6.0
livekit-plugins-openai>=0.7.0
livekit-plugins-silero>=0.6.0
livekit-plugins-cartesia>=0.2.0

# Core dependencies
python-dotenv>=1.0.0
aiohttp>=3.9.0

# Optional: For development and testing
pytest>=7.4.0
pytest-asyncio>=0.21.0


4. Add Your LiveKit Credentials

Create a .env file:

LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_secret
LIVEKIT_WS_URL=wss://your-livekit-url
OPENAI_API_KEY=

5. Run the Agent
python basic_agent.py dev


This starts a LiveKit agent with:

Deepgram Nova-3 speech-to-text

GPT-4o-mini LLM

Cartesia Sonic-2 text-to-speech

Silero VAD

Intelligent Interruption Handler

How the Logic Works (Core Explanation)

our system introduces a semantic logic layer between LiveKit’s VAD and the agent’s reply generation.

This layer ensures human-like conversational flow by distinguishing between:

✔ Backchannel cues

Examples: “yeah”, “ok”, “hmm”, “uh-huh”, “right”
→ These should NOT interrupt the agent when it is speaking.
→ These SHOULD be treated as valid input when agent is silent.

✔ True interruption commands

Examples: “stop”, “wait”, “hold on”, “no”, “pause”
→ These must immediately interrupt the agent.

✔ Mixed-intent sentences

Example: “yeah okay but wait”
→ Although it starts with soft cues, it contains an interruption command.
→ The agent correctly stops.

 How the IntelligentInterruptionHandler Works

Inside interrupt_handler.py, your handler executes a four-step decision pipeline whenever the user speaks:
1. Normalize the Transcription
normalized = self._normalize_text(text)


Removes punctuation, lowercases, handles hyphens (e.g., “uh-huh”).

2. Detect Interruption Keywords
self._contains_interrupt_word(text)


This checks for:

Single words → “stop”, “wait”, “no”

Multi-word phrases → “hang on”, “hold on”

Embedded commands → “yeah but wait a second”

If found → IMMEDIATE INTERRUPT

3. Detect Pure Backchannel Input
self._is_only_backchannel(text)


Checks if every word is soft filler.

Examples considered backchannel:

yeah, ok, hmmm, mm-hmm, uh-huh, sure, right, mhmm, uh


If backchannel ONLY + agent speaking → IGNORE

4. Evaluate Agent Speaking State

The agent updates its speaking state:

agent.interrupt_handler.set_agent_speaking_state(True/False)


Final decision:

Agent Speaking?	Input Type	Action
Yes	Backchannel	Ignore
Yes	Real content	Interrupt
No	Anything	Respond normally
🧩 Why This Logic Works

Your implementation satisfies all required behaviors:

🟢 Agent reading long text

User: “yeah ok uh-huh” → no interruption

🟢 Agent silent

User: “yeah” → agent responds properly

🔴 User overrides agent

User: “stop / wait / no” → agent instantly stops

🔥 Mixed intention

User: “yeah okay but wait” → agent interrupts
