🎙️ Intelligent Interruption Handling
Assignment Submission — Maria Helenaa Manickam
📌 Overview

LiveKit’s default Voice Activity Detection (VAD) stops the agent whenever it hears user audio — including harmless backchannel words like “yeah”, “ok”, “hmm” that users say while listening.

This project implements an intelligent context-aware interruption handler that correctly differentiates between:

Soft acknowledgements → ignored if the agent is speaking

Real interruption commands → immediately stop the agent

Mixed inputs → treated as valid interruptions

User input when agent is silent → processed normally

This ensures a smooth, uninterrupted conversational experience.


🚀 Setup Instructions
1️⃣ Clone the Repository
git clone https://github.com/Dark-Sys-Jenkins/agents-assignment.git
cd agents-assignment

2️⃣ Install Requirements
pip install -r requirements.txt
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"

3️⃣ Configure Environment Variables

Create a .env file:

LIVEKIT_URL=wss://your-livekit-server
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
DEEPGRAM_API_KEY=your-deepgram-key
GROQ_API_KEY=your-groq-key

4️⃣ Run the Agent
uv run examples/backchanneling_agent.py console

🧪 Test Scenarios
Scenario	User Says	Agent Should…
Long Explanation	“yeah ok hmm”	Keep speaking (ignore)
Passive Affirmation	“yeah” (silent)	Respond normally
Real Command	“stop / wait / no”	Stop immediately
Mixed Input	“okay but wait”	Stop (contains hard command)
🎥 Log Evidence

A file named log.txt is included showing:

Agent ignores fillers while speaking

Agent responds when silent

Agent stops instantly on “stop/wait/no”

Mixed input correctly triggers interruption
