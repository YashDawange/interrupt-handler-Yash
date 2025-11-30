🚀 Interrupt-Aware Voice Agent (LiveKit Assignment)

This project implements a robust, real-time conversational voice agent using the LiveKit Agents SDK.
The agent correctly distinguishes between:

✔ Backchannel words while the agent is speaking

(e.g., “yeah”, “ok”, “right”) → ignored

✔ Backchannel words while the agent is silent

(e.g., “yeah”, “ok”) → treated as valid answers

✔ Explicit interrupt commands

(e.g., “stop”, “wait”, “hold on”, “pause”) → immediately interrupts TTS

This behavior meets the core requirements of the assignment.

📦 Features Implemented
1. Backchannel Suppression

When the agent is speaking (state = speaking/thinking):

Words like “yeah, ok, hmm, right” are ignored.

Repeated backchannels trigger an interrupt after a threshold.

2. Backchannel Acceptance

When the agent is silent and has recently asked a question:

Same backchannel words are accepted as meaningful user replies.

3. Explicit Interrupt Detection

The agent immediately stops speaking when it hears interrupt keywords:
stop, wait, hold on, stop now, pause, cut, listen, what, why, hello...

4. Echo Suppression

Removes tiny transcriptions caused by TTS echo within 350ms.

5. Confidence-Aware Processing

Low-confidence single-token transcriptions are ignored.

6. Multilingual Turn-Detector (Silero + HuggingFace)

Automatically detects when the user starts or stops speaking.

🏗 Folder Structure (Minimal)
your-repo/
│── test.py           # Your interrupt-aware agent implementation
│── requirements.txt  # Full environment dependency list
└── README.md         # This file

🔧 Installation
Create & activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate      # Windows

Install dependencies
pip install -r requirements.txt

📥 Download Required Model Files

The turn-detector plugin requires HuggingFace model files (model_q8.onnx, languages.json, etc.)

Run:

python test.py download-files


This automatically downloads required multilingual VAD / turn-detector models.

▶️ Running the Agent

Start the real-time voice agent worker:

python test.py start


Your terminal will show:

starting worker...
registered worker...


This means your agent is alive and waiting for jobs from LiveKit.

🎧 Testing in LiveKit Playground

Go to LiveKit Playground

Choose:

STT: deepgram/nova-3

LLM: openai/gpt-4o-mini

TTS: cartesia/sonic-2

Connect to your worker

🔑 Required Environment Variables

Create a .env:

OPENAI_API_KEY=your-key
DEEPGRAM_API_KEY=your-key

LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=xxx
LIVEKIT_API_SECRET=xxx

