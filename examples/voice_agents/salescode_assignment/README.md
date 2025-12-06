# Voice Agent with Backchannel Handling

A LiveKit-based voice agent that uses advanced speech processing with intelligent interruption and backchannel handling.

## 🎯 Features

- **Real-time Voice Interaction**: Seamless voice-based conversation with the AI agent
- **Intelligent Backchannel Handling**: Filters out filler words and handles interruptions gracefully
- **Advanced Speech Processing**: Uses industry-leading AI models for STT, LLM, and TTS
- **Interruption Management**: Smart detection and handling of user interruptions

## 🤖 AI Models Used

This project uses the following AI services (all have **free tiers**):

| Service | Provider | Model | Purpose |
|---------|----------|-------|---------|
| **LLM** | Groq | Llama 3.3 70B Versatile | Language Understanding & Generation |
| **STT** | AssemblyAI | Universal Streaming | Speech-to-Text Transcription |
| **TTS** | Deepgram | Aura | Text-to-Speech Synthesis |
| **VAD** | Silero | Multilingual | Voice Activity Detection |

## 📋 Prerequisites

You'll need API keys from the following services (all free to sign up):

1. **Groq API Key** - Get it at: https://console.groq.com/keys
2. **AssemblyAI API Key** - Get it at: https://www.assemblyai.com/dashboard/signup
3. **Deepgram API Key** - Get it at: https://console.deepgram.com/signup
4. **LiveKit Account** - Get it at: https://cloud.livekit.io/

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/agents-assignment.git
cd agents-assignment/examples/voice_agents/salescode_assignment
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `salescode_assignment` directory:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# AI Service API Keys
GROQ_API_KEY=your_groq_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
```

### 4. Get Your LiveKit Credentials

1. Go to https://cloud.livekit.io/
2. Create a new project or select an existing one
3. Navigate to **Settings** → **Keys**
4. Click **"Create API Key"** to generate new credentials
5. Copy the following:
   - Project URL (LIVEKIT_URL)
   - API Key (LIVEKIT_API_KEY)
   - API Secret (LIVEKIT_API_SECRET)

## ▶️ Running the Agent

Start the agent:

```bash
python basic_agent.py start
```

You should see output like:
```
{"level": "INFO", "name": "livekit.agents", "message": "starting worker", "version": "1.3.6"}
{"level": "INFO", "name": "livekit.agents", "message": "registered worker"}
```

## 🎮 Testing on LiveKit Playground

1. Go to your LiveKit Cloud dashboard: https://cloud.livekit.io/
2. Navigate to your project
3. Click on **"Playground"** in the left sidebar
4. Click **"Connect"** to join a test room
5. Your agent will automatically join the room
6. Start speaking to interact with the agent!

## 🎭 Backchannel Handling Approach

The agent implements intelligent backchannel handling through the `InterruptionHandler` class:

### Key Features:

#### 1. **Filler Word Filtering**
The agent ignores common filler words and backchannels to prevent unnecessary responses:
- **Ignored words**: "yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha", "mmm"
- **Benefit**: Agent doesn't interrupt itself when user gives verbal acknowledgments

#### 2. **Interrupt Command Detection**
Recognizes explicit interruption commands during agent speech:
- **Interrupt words**: "stop", "wait", "hold on", "pause"
- **Action**: Queues interruption and stops current speech

#### 3. **State-Based Processing**
The handler maintains agent speaking state to decide how to process user input:

```python
if agent_is_speaking:
    if is_filler_word:
        ignore()  # Don't interrupt for backchannels
    elif is_interrupt_command:
        queue_interruption()  # Stop and listen
    else:
        ignore()  # Ignore other speech during agent turn
else:
    process_normally()  # Process user input when agent is silent
```


### Example Scenarios:

**Scenario 1: Backchannel During Agent Speech**
```
Agent: "So the weather today is..."
User: "yeah"  ← IGNORED (filler word)
Agent: "...going to be sunny and warm."
```

**Scenario 2: Explicit Interruption**
```
Agent: "Let me tell you about..."
User: "wait, stop"  ← INTERRUPTION QUEUED
Agent: [stops speaking]
User: "I have a question first"  ← PROCESSED
```

**Scenario 3: Normal Conversation**
```
Agent: [silent]
User: "What's the weather?"  ← PROCESSED IMMEDIATELY
Agent: "The weather is sunny today."
```

## 🛠️ Customization

### Adding More Filler Words

Edit `backchannel_handle.py`:

```python
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha", "mmm",
    "um", "uh", "er", "ah", "well", "like"  # Add more here
}
```

### Adding More Interrupt Commands

```python
INTERRUPT_WORDS = [
    "stop", "wait", "hold on", "pause",
    "interrupt", "let me speak"  # Add more here
]
```

