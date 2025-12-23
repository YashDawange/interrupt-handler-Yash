
# Setup

This document describes how to set up the development environment for running
the LiveKit voice agent examples in this repository.

---

## 🐍 Python & Virtual Environment

- Python **3.10 – 3.12** recommended
- Create and activate a virtual environment from the project root:

```bash
# for mac use python3 and for linux/windows use python
python3 -m venv .venv
source .venv/bin/activate
````
Ctrl + Shift + P -> Select correct python interpreter

---

## 📦 Install Dependencies

Install all required dependencies using `requirements.txt`:

Goto the following directory for voice-agents:
```bash
cd ./examples/voice_agents
```
```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Create a `.env` file at the project root:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=lk_api_xxxxx
LIVEKIT_API_SECRET=lk_secret_xxxxx

OPENAI_API_KEY=sk-xxxxxxxx
```

**Notes:**

* `LIVEKIT_URL` must start with `wss://` (LiveKit Cloud) or `ws://` (local server)
* Do not wrap values in quotes
* Do not use `export`

---

## 🔌 LiveKit Server

A running LiveKit server is required.

### Option A — LiveKit Cloud (Recommended)

1. Create a project at [https://cloud.livekit.io](https://cloud.livekit.io)
2. Copy the credentials into `.env`

### Option B — Run Locally

```bash
brew install livekit
livekit-server --dev --bind 127.0.0.1
```

Use the following values in `.env`:

```env
DEEPGRAM_API_KEY=5xxxxxx
ELEVENLABS_API_KEY=sk_xxxxxxxx
OPENAI_API_KEY=sk-proj-xxxxxx
LIVEKIT_URL=wss://127.0.0.1:7880
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=Dpauxxxxxxxx
```

---

## ⚠️ Required: Load `.env` Explicitly

LiveKit spawns worker processes, so environment variables must be loaded
explicitly inside each agent file.


Failing to do this will result in errors such as:

```
ValueError: ws_url is required, or add LIVEKIT_URL in your environment
```

---

## ▶️ Running an Agent

From the `examples/voice_agents` directory:

```bash
python3 realtime_interrupt_handling_agent.py dev
```

A successful startup will show logs similar to:

```text
Watching ./voice_agents
connected to livekit
worker registered
waiting for room
```

---

## ⚠️ Known Warnings

You may see warnings like:

```text
Field "model_name" has conflict with protected namespace "model_"
```

These are internal Pydantic warnings and can be safely ignored.

