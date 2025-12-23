# Intelligent Voice Interruption Management System

## 🌟 Overview

The **Intelligent Interruption Handler** is a sophisticated middleware designed for LiveKit-powered voice agents. It solves the "stuttering agent" problem by distinguishing between passive user backchannels (like "uh-huh" or "yeah") and active interruptions (like "stop" or "wait").

## 📺 Demo Video

Check out the Intelligent Interruption Handler in action on the LiveKit Playground:

[![LiveKit Agent Demo]](https://drive.google.com/file/d/1_Bys1ryr2iHB9c2q4F1jGAC4omqEK6Q5/view?usp=sharing)
*Note: Click the image above to watch the demonstration of backchannel filtering and command-driven interruptions.*

## 🛡️ Multilevel Guard Architecture

We protect the agent's flow through three distinct stages of analysis:

### 1. The Signal Guard (VAD Level)
- **What it does**: Filters out short, single-word audio bursts before they even reach the processing stage.
- **Impact**: Prevents momentary audio "hiccups" caused by simple noises or brief acknowledgments.

### 2. The Semantic Guard (Context-Aware Controller)
- **What it does**: Analyzes the *meaning* of the user's words in relation to the agent's current activity.
- **Logic**:
    - **Backchannel Detection**: If the user says "yeah" while the agent is talking, it's flagged as an acknowledgment and ignored.
    - **Intent Prioritization**: Commands like "pause" or "hold on" trigger an immediate stop, regardless of the agent's state.
    - **Passive Agreement**: Recognizes agreement when the agent is silent, allowing the conversation to proceed naturally.

### 3. The Action Guard (Dispatcher)
- **What it does**: Executes precise commands based on the controller's decision.
- **Result**: Either "clears" the user's turn (deleting filler words from the LLM history) or "interrupts" the agent instantly for a snappy response.

---

## 🚀 Performance & Reliability Features

- **Blazing Fast Matching**: Utilizes O(1) Set-based lookups to ensure the filtering logic adds zero detectable latency.
- **Smart Text Normalization**: A custom regex engine handles phonetic variations and punctuation (e.g., "mm-hmm" vs "mm hmm") to catch fillers that standard matching misses.
- **State-Aware Buffer**: Implements a **500ms grace period** after the agent stops speaking to resolve race conditions where user commands arrive slightly "late."
- **Noise Suppression**: Interim transcripts that look like fillers are pre-filtered to reduce unnecessary LLM calls and CPU overhead.
- **Windows-Optimized Logging**: Replaced problematic Unicode characters with stable text tags, ensuring error-free operation on Windows systems.

---

## 🛠️ Getting Started

### Installation
Activate your environment and install the optimized dependency stack:
```bash
pip install -r examples/voice_agents/requirements.txt
pip install "opentelemetry-api==1.35.0" "opentelemetry-sdk==1.35.0" "opentelemetry-exporter-otlp==1.35.0" "opentelemetry-proto==1.35.0"
```

### Configuration
1. Locate `env.example` in the root directory.
2. Create a `.env` file and populate it with your LiveKit, Groq, Deepgram, and Cartesia credentials.

### Execution & Testing
- **To launch the agent**: `cd examples/voice_agents` then `python basic_agent.py dev`
- **To run logic tests**: `python examples/verify_interrupt_handler.py`

## 📁 Repository Map
- `salescode_interrupt_handler/controllers.py` - The brain of the interruption logic.
- `examples/voice_agents/basic_agent.py` - Implementation of the production-ready agent.
- `examples/verify_interrupt_handler.py` - Automated test suite for logic verification.
- `instructions.md` - Deep-dive setup guide for new developers.
