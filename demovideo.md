# 🎥 LiveKit Voice Agent Demo Video

## 🚀 Voice Agent with Intelligent Interruption Handling

This demo showcases a sophisticated voice agent built with **LiveKit Agents** that demonstrates advanced conversational AI capabilities, including intelligent interruption filtering and real-time voice processing.

### 📹 Demo Video

**Watch the full demonstration:**
[🎬 Voice Agent Demo Video](https://drive.google.com/file/d/1D0TicW6shulFJXD6MIdAsTA9tBIUuSuA/view?usp=sharing)

*Click the link above to view the Google Drive video demonstrating the voice agent in action.*

---

## 🎯 Key Features Demonstrated

### 🧠 **Intelligent Interruption Handling**
- **Backchannel Detection**: Recognizes and ignores casual acknowledgments like "uh-huh", "yeah", "ok" while the agent is speaking
- **Smart Filtering**: Distinguishes between filler words and actual interruption commands
- **Seamless Conversation**: Maintains natural flow without being interrupted by natural speech patterns

### 🎤 **Advanced Voice Processing**
- **Real-time Speech Recognition**: Powered by Deepgram for accurate transcription
- **Natural Text-to-Speech**: Cartesia TTS for human-like voice synthesis
- **Voice Activity Detection**: Silero VAD for precise speech detection
- **OpenAI GPT-4.1-mini**: Advanced language model for intelligent responses

### ⚡ **LiveKit Integration**
- **WebRTC Audio**: High-quality, low-latency voice communication
- **Real-time Processing**: Instant response generation and audio synthesis
- **Scalable Architecture**: Built on LiveKit's robust infrastructure

---

## 🎬 Demo Highlights

The video demonstrates:

1. **Natural Conversation Flow**
   - Agent introduces itself and engages in dialogue
   - Handles multiple conversation topics seamlessly

2. **Interruption Intelligence**
   - Shows how the agent ignores backchannel responses
   - Demonstrates immediate response to stop commands

3. **Real-time Voice Processing**
   - Live speech-to-text transcription
   - Instant text-to-speech synthesis
   - Natural conversation pacing

4. **Error Handling & Recovery**
   - Graceful handling of unclear speech
   - Context-aware response generation

---

## 🛠️ Technical Implementation

### Core Technologies
- **LiveKit Agents**: Voice agent framework
- **Python 3.9+**: Backend implementation
- **OpenAI GPT-4.1-mini**: Language model
- **Deepgram**: Speech-to-text
- **Cartesia**: Text-to-speech
- **Silero**: Voice activity detection

### Custom Features
- **AgentSpeechManager**: Custom interruption filtering logic
- **Word Pattern Recognition**: Regex-based backchannel detection
- **State Management**: Tracks agent speaking vs. listening states
- **Configurable Patterns**: Customizable ignore and stop word lists

---

## 🚀 Quick Start

To run this voice agent yourself:

### Prerequisites
```bash
# Required API Keys
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key

# LiveKit Server (optional, for dev mode)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret
```

### Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Or for minimal setup
pip install -r requirements-minimal.txt
```

### Run the Agent
```bash
# Console mode (recommended for testing)
python examples/voice_agents/action.py console

# Development mode (with UI)
python examples/voice_agents/action.py dev

# Production mode
python examples/voice_agents/action.py start
```

---

## 📋 Demo Script

The video follows this interaction flow:

1. **Agent Introduction**
   - Agent greets and introduces capabilities
   - Explains intelligent interruption handling

2. **Backchannel Testing**
   - Demonstrates ignoring "uh-huh", "yeah", "ok" during speech
   - Shows continued explanation despite acknowledgments

3. **Stop Command Testing**
   - Shows immediate interruption on "stop" command
   - Demonstrates instant response cutoff

4. **Natural Conversation**
   - Handles topic changes seamlessly
   - Maintains context throughout dialogue

---

## 🎯 Use Cases

This voice agent is perfect for:

- **Customer Service**: Intelligent call handling with natural interruptions
- **Virtual Assistants**: Context-aware voice interactions
- **Educational Tools**: Interactive voice-based learning
- **Accessibility**: Voice interfaces for users with different needs
- **Entertainment**: Interactive storytelling and games

---

## 🔗 Resources

- **LiveKit Agents**: [https://docs.livekit.io/agents/](https://docs.livekit.io/agents/)
- **LiveKit Playground**: [https://agents-playground.livekit.io/](https://agents-playground.livekit.io/)
- **OpenAI API**: [https://platform.openai.com/](https://platform.openai.com/)
- **Deepgram**: [https://deepgram.com/](https://deepgram.com/)
- **Cartesia**: [https://cartesia.ai/](https://cartesia.ai/)

---

## 📞 Contact & Support

For questions about this voice agent implementation:
- Check the [LiveKit Community](https://livekit.io/join-slack)
- Review the [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- Explore the [GitHub Repository](https://github.com/livekit/agents)

---

