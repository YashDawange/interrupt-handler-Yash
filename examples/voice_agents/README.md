# LiveKit Voice Agent with Intelligent Interruption Handler

A voice agent built with LiveKit that features intelligent interruption handling - filtering out filler words ("uh", "umm", "hmm") while still responding to real user commands.

## 🎯 Features

- **Voice-based AI Agent** powered by LiveKit
- **Intelligent Interruption Handling** - Filters filler words during agent speech
- **Multilingual Turn Detection** - Context-aware conversation flow
- **Speech-to-Text** using Deepgram Nova-3
- **Text-to-Speech** using Cartesia Sonic-2
- **LLM** powered by OpenAI GPT-4.1-mini

---

## 📋 Prerequisites

- **Python 3.11+** installed on your system
- **API Keys** for the following services:
  - [Deepgram](https://deepgram.com/) (STT)
  - [OpenAI](https://openai.com/) (LLM)
  - [Cartesia](https://cartesia.ai/) (TTS)
  - [LiveKit Cloud](https://livekit.io/) (optional, for production deployment)

---

## 🚀 Installation Steps

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd livekit-agent-interruption-handler
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install livekit-agents livekit-plugins-silero livekit-plugins-turn-detector livekit-plugins-deepgram livekit-plugins-openai livekit-plugins-cartesia python-dotenv
```

Or if a `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the `examples/voice_agents/` directory:

```bash
cd examples/voice_agents
```

Create a file named `.env` with the following content:

```env
# Deepgram API Key (for Speech-to-Text)
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# OpenAI API Key (for LLM)
OPENAI_API_KEY=your_openai_api_key_here

# Cartesia API Key (for Text-to-Speech)
CARTESIA_API_KEY=your_cartesia_api_key_here

# LiveKit Credentials (optional for console mode, required for production)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
```

### Step 5: Download Required Model Files

Before running the agent, you need to download the turn detection and VAD models:

```bash
python basic_agent.py download-files
```

This will download:
- Silero VAD model
- Multilingual turn detection model

---

## ▶️ Running the Agent

### Console Mode (Local Testing)

This mode allows you to test the agent locally without connecting to LiveKit Cloud:

```bash
cd examples/voice_agents
python basic_agent.py console
```

You should see output like:

```
Agents   Starting console mode 🚀
... INFO   livekit.agents     starting worker
... INFO   livekit.agents     HTTP server listening on :55927
```

### Production Mode (with LiveKit Cloud)

For production deployment with LiveKit Cloud:

```bash
python basic_agent.py start
```

---

## 📁 Project Structure

```
livekit-agent-interruption-handler/
├── livekit_plugins/
│   ├── __init__.py
│   └── livekit_interrupt_handler.py    # Custom interruption handler
├── examples/
│   └── voice_agents/
│       ├── basic_agent.py              # Main agent file
│       ├── .env                         # Environment variables (create this)
│       └── README.md                    # This file
└── venv/                                # Virtual environment
```

---

## 🧩 How the Interruption Handler Works

The custom `InterruptHandler` class in `livekit_plugins/livekit_interrupt_handler.py`:

1. **Filters Filler Words** - When the agent is speaking, filler words like "uh", "umm", "hmm", "haan" are ignored
2. **Detects Real Interruptions** - Non-filler speech during agent playback triggers a real interruption
3. **Processes Normal Input** - When the agent is silent, all user speech is processed normally

### Decision Flow:

```
User speaks while agent is speaking
    ├── Low confidence (< 0.6) → IGNORED
    ├── Filler word only → IGNORED  
    └── Real speech → STOP agent (valid interruption)

User speaks while agent is silent
    └── All speech → PROCESSED normally
```

### Configurable Filler Words:

You can customize the ignored words list when initializing:

```python
interrupt_handler = InterruptHandler(
    ignored_words=["uh", "umm", "hmm", "yeah", "okay", "mhm"]
)
```

---

## 🔧 Customization

### Change the Agent's Personality

Edit the `instructions` in `basic_agent.py`:

```python
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You would interact with users via voice. "
                "Keep your responses concise and to the point. "
                # Add your custom instructions here
            )
        )
```

### Change Voice/LLM Providers

Modify the `AgentSession` configuration:

```python
session = AgentSession(
    stt="deepgram/nova-3",           # Speech-to-Text provider
    llm="openai/gpt-4.1-mini",       # LLM provider
    tts="cartesia/sonic-2:voice-id", # Text-to-Speech provider
    # ...
)
```

---

## ❓ Troubleshooting

### Error: `ModuleNotFoundError: No module named 'livekit'`

Make sure you've activated the virtual environment:

```bash
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
```

### Error: `Could not find file "model_q8.onnx"`

Run the download command:

```bash
python basic_agent.py download-files
```

### Error: `Duplicated timeseries in CollectorRegistry`

This happens when mixing local and installed package versions. Make sure you're using the correct imports from `livekit.agents` and `livekit.plugins.*`.

### Error: `Cannot register an async callback with .on()`

Use a sync callback wrapper with `asyncio.create_task()`:

```python
@session.on("event_name")
def sync_handler(ev):
    async def async_work():
        # your async code here
    asyncio.create_task(async_work())
```

---

## 📚 Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [LiveKit GitHub](https://github.com/livekit/agents)
- [Deepgram API](https://developers.deepgram.com/)
- [OpenAI API](https://platform.openai.com/docs/)
- [Cartesia API](https://docs.cartesia.ai/)

---

## 📄 License

This project is licensed under the Apache License 2.0.
