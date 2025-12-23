# Project Setup Instructions

Welcome to the **Context-Aware Interrupt Handler** project! This guide will help you set up the environment and run the voice agent.

## 📋 Prerequisites

- Python 3.12 or higher
- A LiveKit Cloud account (or self-hosted server)
- API keys for:
  - LiveKit
  - Groq (LLM)
  - Deepgram (STT)
  - Cartesia (TTS)

## 🛠️ Step-by-Step Setup

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd salescode-assignment
```

### 2. Create Virtual Environment
It is highly recommended to use a virtual environment to avoid dependency conflicts.
```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
We use a specific version of OpenTelemetry to ensure compatibility with the LiveKit framework on Windows.
```bash
pip install -r examples/voice_agents/requirements.txt
pip install "opentelemetry-api==1.35.0" "opentelemetry-sdk==1.35.0" "opentelemetry-exporter-otlp==1.35.0" "opentelemetry-proto==1.35.0"
```

### 4. Configure Environment Variables
Copy the example environment file and fill in your keys.
```bash
cp env.example .env
# Open .env and add your API keys
```

## 🚀 Running the Project

### 1. Verification Tests
Run the standalone test suite to ensure the interruption logic is working correctly:
```bash
python examples/verify_interrupt_handler.py
```

### 2. Start the Voice Agent
Launch the agent in development mode with hot-reloading:
```bash
cd examples/voice_agents
python basic_agent.py dev
```

## 🧪 Interruption Logic
The core logic resides in `salescode_interrupt_handler/controllers.py`. It uses a 3-layer defense system:
1. **VAD Gate**: Blocks single-word fillers at the audio level.
2. **Semantic Filter**: Distinguishes between backchannels ("yeah") and commands ("stop").
3. **Grace Period**: Handles race conditions during state transitions.

