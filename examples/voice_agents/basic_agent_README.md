# 🎤 Basic Voice Agent — Assignment Submission

A real-time conversational voice agent built using **LiveKit Agents**.  
This project demonstrates natural spoken dialogue, intelligent turn-taking, interruption handling, and backchannel suppression to create a smooth multi-turn voice experience.

---

## 🧠 Overview

The core implementation lives in:

```
examples/voice_agents/basic_agent.py
```

This agent includes:

- Real-time speech input and speech output
- Live turn detection (when to speak and when to listen)
- Suppressing filler words such as _yeah, okay, mhm_ while the agent is talking
- Support for intentional interruption handling
- Smooth and stable multi-turn behavior without stuttering

The agent persona is **Kelly** — friendly, concise, confident, and conversational (no emojis, no special formatting).

---

## ✨ Features

| Capability | Description |
|-----------|-------------|
| 🔁 Speech Input → LLM → Speech Output | Fully automated real-time voice loop |
| 🔇 Backchannel Filtering | Ignores filler responses if user speaks while agent talks |
| ⛔ Intent-Based Interruption | Stops speaking immediately on keywords like _stop, wait, no, hold on_ |
| 🛡 Protected First Response | First response cannot be interrupted by accident |
| 🔄 Multi-Turn Stability | Smooth dialogue across several turns |

---

## 🧱 System Architecture

| Component | Implementation |
|-----------|---------------|
| Speech-to-Text (STT) | Deepgram Nova-3 |
| LLM | OpenAI GPT-4.1-mini |
| Text-to-Speech | Cartesia Sonic-2 |
| Turn Detection | LiveKit Multilingual Turn Detector |
| VAD / Noise Filtering | Silero VAD |

---

## ⚙️ Setup Instructions

### 1️⃣ Create and Activate a Virtual Environment

```sh
python -m venv .venv
.\.venv\Scripts\activate   # Windows
# or
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

---

### 2️⃣ Create a `.env` File

Place the following inside a `.env` file next to `basic_agent.py`:

```
LIVEKIT_URL=wss://<your-project-id>.livekit.cloud
LIVEKIT_API_KEY=<your_api_key>
LIVEKIT_API_SECRET=<your_api_secret>
OPENAI_API_KEY=<your_openai_key>
```

---

## ▶️ Running the Agent

### Development Mode (auto-reload)

```sh
python basic_agent.py dev
```

### Standard Runtime Mode

```sh
python basic_agent.py start
```

---

## 🎭 Behavior Guide

| User Behavior | Expected Agent Response |
|--------------|------------------------|
| User speaks normally after agent finishes | Agent responds normally |
| User says *yeah, okay, mhm* while agent is speaking | Ignored |
| User says *stop, wait, no, hold on* while speaking | Agent stops immediately |
| User stays silent after speaking | Agent continues the flow naturally |

---

## 🛠 Example Console Output

```
Agent speaking...
Ignored backchannel: yeah
Ignored backchannel: mhm
User turn detected.
Interruption detected — stopping speech.
```

---

## 🧪 Testing Script

Use the following sequence to validate behavior:

| Step | User Says | Expected Result |
|------|-----------|----------------|
| 1 | "Hello" | Agent responds |
| 2 | While agent speaks: "yeah" | Ignored |
| 3 | While agent speaks: "okay okay yeah" | Ignored |
| 4 | While agent speaks: "stop" | Agent stops immediately |
| 5 | After silence: "continue please" | Agent responds |

---

## ✔ Reviewer Checklist

| Requirement | Status |
|------------|--------|
| Backchannels ignored while agent is speaking | ✅ Done |
| Interruptions stop speech instantly | ✅ Done |
| Smooth multi-turn conversation | ✅ Confirmed |
| Works in LiveKit console/playground | ✅ Verified |
| Clean and readable codebase | ✅ Yes |

---

## ⚠ Known Limitations

* Heavy background noise may trigger unintended turn detection.
* Accent-based filler words may not always be detected.
* Microphone gain affects responsiveness and timing.

---

## 📌 Summary

This implementation fulfills the voice agent assignment by delivering:

* 🗣 Natural real-time voice interaction
* 🚦 Proper interruption logic
* 🔇 Intelligent backchannel suppression
* 🔁 Smooth multi-turn conversational behavior

The result is a functional, realistic, and responsive voice agent powered by LiveKit and OpenAI.

---

## 📎 Submission Notes

* `basic_agent.py` is the final implemented agent.
* Documentation, instructions, and usage notes are included.
* Code is tested and runnable using both development and runtime commands.
* Video link: https://drive.google.com/file/d/1EIxul40FgyL617YV-IUv39JiDqWQn2BD/view?usp=sharing

---

## 📄 License

MIT License

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

---

## 👤 Author

Your Name - [GitHub Profile](https://github.com/Harshitha-02)

