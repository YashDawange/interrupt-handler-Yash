🧠 Intelligent Interruption Handler

This project implements a Real-time Voice AI Agent using LiveKit, Google Gemini 2.0, and Deepgram. The agent plays the role of "Kelly," a whimsical customer service representative for a newly found colony on Mars.

Core Innovation: This agent solves the "Over-Sensitive VAD" challenge by implementing a Deaf Agent Pattern. Instead of relying on standard Voice Activity Detection (which interrupts on any sound), this agent strictly controls the conversation flow, allowing it to ignore passive backchanneling ("yeah", "uh-huh") while respecting explicit stop commands.

🧠 Logic & Architecture

To satisfy the strict interruption requirements, this agent uses a "Manual Flow Control" strategy.

1. The "Deaf Agent" Configuration

Standard LiveKit agents automatically stop speaking when they detect user speech. We disabled this default behavior to gain full control:

turn_detection=None: The agent does not use the default model to decide when the user is done.

allow_interruptions=False: The agent is configured to never stop speaking automatically when audio is detected.

2. The Logic Matrix (on_user_input_transcribed)

We intercept every piece of text transcribed by Deepgram (both interim and final results) and apply the following decision matrix:

User Input

Agent State

Action

Logic

"Stop", "Wait", "Hold on"

Speaking

STOP

Detected via a STOP_PHRASES list.

"Don't stop", "Never stop"

Speaking

IGNORE

Negation detection prevents false positives.

"Yeah", "Uh-huh", [Noise]

Speaking

IGNORE

No stop command found; agent continues seamlessly.

Full Sentence

Listening

REPLY

User finished speaking; input is sent to Gemini LLM.

🛠️ Tech Stack

Framework: LiveKit Agents (Python)

STT (Ears): Deepgram Nova-3 (Optimized for speed & interim results)

LLM (Brain): Google Gemini 2.0 Flash (Fast, Cost-effective & Smart)

TTS (Voice): Deepgram TTS (Low latency)

VAD: Silero (Used for pre-warming only)

🚀 Setup & Installation

1. Prerequisites

Python 3.9+

A LiveKit Cloud project

API Keys for Google (Gemini) and Deepgram

2. Install Dependencies

pip install livekit-agents livekit-plugins-google livekit-plugins-deepgram livekit-plugins-silero python-dotenv


3. Environment Configuration

Create a .env file in the root directory:

# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=API...
LIVEKIT_API_SECRET=Secret...

# AI Model Keys
GOOGLE_API_KEY=AIza...
DEEPGRAM_API_KEY=c3f...


4. Run the Agent

python basic_agent.py dev


🧪 How to Test

Once the agent is running, connect via the LiveKit Playground and perform these tests:

The "Passive Listening" Test:

Ask the agent to explain the weather on Mars (it gives a long answer).

While it speaks, say "Yeah", "Uh-huh", or "Okay".

✅ Result: The agent should NOT stop speaking.

The "Hard Stop" Test:

While the agent is speaking, say "Kelly stop" or "Wait a second".

✅ Result: The agent should STOP immediately.

The "Negation" Test:

Say "Please do not stop talking".

✅ Result: The agent should treat this as normal text, not a stop command.

📂 Project Structure

basic_agent.py: Main entry point containing the manual interruption logic loop.

requirements.txt: List of Python dependencies.

.env: API keys and secrets (not committed).

