🚀 LiveKit Intelligent Interruption Handling – Enhanced Conversational Control

This project enhances the conversational flow of a real-time AI agent built using the LiveKit Agent framework by implementing context-aware intelligent interruption handling.
This assignment is based on the challenge description in the provided document 

GEN AI Assignment Campus (New) …

.

🧠 Problem Statement

In natural conversations, humans use filler responses such as “yeah,” “hmm,” “ok,” “right” to signal active listening.
However, LiveKit’s default VAD (Voice Activity Detection) treats these as interruptions, causing the agent to abruptly stop speaking mid-sentence.

This results in:

Broken responses

Poor user experience

Conversation that feels robotic and unnatural 

GEN AI Assignment Campus (New) …

🎯 Project Goal

Implement a logic layer that protects the agent's speech output from being interrupted by passive acknowledgements, while still allowing real interruptions like “stop,” “wait,” or “no.”
The agent must be semantic-aware, state-aware, and have real-time response capability with no noticeable delay 

GEN AI Assignment Campus (New) …

.

🔧 Core Logic & Behaviors
User Input	Agent State	Behavior
“yeah / ok / hmm”	Speaking	Ignore – continue speaking
“stop / wait / no”	Speaking	Interrupt immediately
“yeah / ok”	Silent	Respond normally
Any valid input	Silent	Normal conversational behavior

The logic also detects mixed input such as:
👉 “Yeah, okay but wait” → Agent must interrupt 

GEN AI Assignment Campus (New) …

.

🛠️ Key Features Implemented
Feature	Description
Configurable Soft-Ignore Word List	Dynamically adjustable list such as [“yeah”, “ok”, “hmm”]
State-Based Filtering	Logic activates only when agent is actively speaking
Semantic Interruption Detection	Stops output if sentence contains any “hard interruption” command
STT + VAD Coordination	Handles early VAD triggers before STT completes
Real-Time Handling	No delay or stutter when ignoring filler words
📁 Project Setup
1️⃣ Clone This Repository
git clone <your-fork-url>
cd agents-assignment

2️⃣ Install Dependencies
pip install -r requirements.txt

3️⃣ Add Your LiveKit Keys

Create a .env file:

LIVEKIT_URL=<your-url>
LIVEKIT_API_KEY=<your-key>
LIVEKIT_API_SECRET=<your-secret>

▶️ Running the Agent
python -m examples.drive_thru.agent start \
  --url <LIVEKIT URL> \
  --api-key <KEY> \
  --api-secret <SECRET>

🔍 How The Interruption Handler Works

1️⃣ When STT transcript arrives →
2️⃣ System checks current agent state (speaking / silent)
3️⃣ If speaking →

If word ∈ ignore list → Continue speaking

If contains command → Stop immediately
4️⃣ If silent → Respond normally

No modifications were made to the VAD kernel.
Filter layer is implemented at logic level, as required. 

GEN AI Assignment Campus (New) …

🧪 Test Coverage (Examples)
Scenario	Expected
User says "yeah" while agent reading	Agent continues
User says "yeah" while silent	Agent replies “Great, let’s continue”
User says “stop” mid-speech	Agent stops
User says “yeah but wait”	Agent stops
🧾 Submission Requirements Fulfilled

✔ Feature implementation
✔ Documentation (this README)
✔ Demonstration logs/screenshots/video
✔ Custom branch naming - feature/interrupt-handler-<yourname> 

GEN AI Assignment Campus (New) …

📌 Future Enhancements

AI-based sentiment layer to detect uncertain vs emphatic “yeah”

ML model to detect backchannels without static word lists

Dynamic interruption threshold based on topic priority