# Smart Interruption Management for LiveKit Voice Agents

This project implements intelligent interruption filtering for LiveKit voice agents, allowing them to distinguish between passive acknowledgments (like "yeah", "mhmm") and active interruptions during conversations.

## 🎯 Problem Solved

Traditional voice agents interrupt their speech immediately upon detecting any user input through Voice Activity Detection (VAD). This creates awkward pauses even for simple backchannel feedback like "mhmm" or "yeah". This system prevents such false interruptions while still allowing legitimate interruptions.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- LiveKit account and API keys
- API keys for chosen STT/LLM/TTS providers

### Installation

1. **Navigate to the project directory:**
   ```bash
   cd examples/voice_agents/Interrup_handling
   ```

2. **Install dependencies:**
   ```bash
   pip install -r ../requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file or set environment variables:
   ```bash
   # Required for LiveKit
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret

   # Required for Deepgram STT (or use alternative STT provider)
   DEEPGRAM_API_KEY=your_deepgram_api_key

   # Required for OpenAI LLM
   OPENAI_API_KEY=your_openai_api_key

   # Required for Cartesia TTS
   CARTESIA_API_KEY=your_cartesia_api_key
   ```

4. **Run the agent:**
   ```bash
   python basic_agent.py dev
   ```

5. **Connect to LiveKit Playground:**
   - Open [LiveKit Playground](https://playground.livekit.io)
   - Join a room and start conversing with "Kelly"

## 🧠 How It Works

### Core Logic

The system uses a **runtime monkey patch** to intercept LiveKit's interruption detection and inject intelligent filtering. Here's the decision flow:

```
User Speaks → VAD Detects Audio → STT Transcribes → Filter Checks Content → Decision
```

### Key Components

#### 1. InterruptionFilter Class (`interrupt_handler.py`)
- **Purpose:** Analyzes transcript content to determine interruption intent
- **Logic:**
  - **Directive Words** (always interrupt): "stop", "wait", "no", "don't"
  - **Acknowledgment Words** (block interruption): "yeah", "mhmm", "okay", "uh-huh"
  - **Smart Threshold:** If transcript has >5 words and isn't pure acknowledgment, allow interruption

#### 2. Runtime Patch (`helper.py`)
- **Injection Point:** Overrides `AgentActivity` methods
- **Delta Calculation:** Compares current transcript with previous to identify new words
- **Blocking Logic:** Prevents audio pause for acknowledgment-only inputs

#### 3. Agent Integration (`basic_agent.py`)
- **State Tracking:** Monitors agent speaking state via events
- **Event Handling:** Processes transcription events with filtering
- **Fallback Protection:** Clears user turns for blocked interruptions

### Decision Matrix

| Agent State | Input Type | Action |
|-------------|------------|--------|
| Speaking | Acknowledgment ("mhmm") | Continue speaking |
| Speaking | Directive ("stop") | Interrupt immediately |
| Speaking | Substantial input | Interrupt |
| Not speaking | Any input | Process normally |

## 🧪 Testing & Verification

### Test Scenarios

1. **Backchannel Test:**
   - Ask agent to tell a long story
   - Say "mhmm" or "yeah" during speech
   - **Expected:** Agent continues speaking uninterrupted

2. **Directive Test:**
   - During agent speech, say "Wait, stop"
   - **Expected:** Agent halts immediately

3. **Mixed Input Test:**
   - Say "Yeah but wait"
   - **Expected:** Agent interrupts (detects "wait")

4. **Substantial Input Test:**
   - During speech, say "Actually, I prefer a different story"
   - **Expected:** Agent interrupts for meaningful input

## ⚙️ Configuration

### Word Sets (`config.py`)

#### Acknowledgment Words
Words that should NOT interrupt when agent is speaking:
```python
DEFAULT_ACKNOWLEDGMENT_WORDS = {
    "yeah", "yea", "yes", "yep", "yup",
    "ok", "okay", "alright", "aight",
    "hmm", "hm", "mhm", "mmhmm", "uh-huh", "uhuh",
    "right", "sure", "gotcha", "got it",
    "aha", "ah", "oh", "ooh",
    "mm", "mhmm", "huh"
}
```

#### Directive Words
Words that should ALWAYS interrupt:
```python
DEFAULT_DIRECTIVE_WORDS = {
    "stop", "wait", "hold", "pause",
    "no", "nope", "don't",
    "hold on", "wait a second", "wait a minute",
    "hang on", "one second", "one minute"
}
```

### Customization

#### Adding Words
```python
filter = InterruptionFilter()
filter.add_acknowledgment_word("totally")
filter.add_directive_word("cancel")
```

#### Adjusting Threshold
```python
filter = InterruptionFilter(min_word_threshold=3)  # More sensitive
```

## 🏗️ Architecture Details

### File Structure
```
Interrup_handling/
├── README.md              # This file
├── basic_agent.py         # Main agent with interruption handling
├── interrupt_handler.py   # Core filtering logic
├── helper.py              # Runtime patching system
└── config.py              # Word sets and configuration
```

### Event Flow
1. **Agent State Change:** Tracks when agent starts/stops speaking
2. **User Transcription:** STT produces interim and final transcripts
3. **Filter Analysis:** Checks content against word sets
4. **Decision:** Allow/block interruption based on context
5. **Action:** Clear user turn or allow normal processing

### Technical Implementation
- **Runtime Patching:** Modifies LiveKit internals without source changes
- **Delta Processing:** Only analyzes new words since last turn
- **State Awareness:** Considers agent speaking state for decisions
- **Latency Optimization:** Processes interim transcripts for early blocking

## 🔧 Troubleshooting

### Common Issues

1. **Agent doesn't respond to interruptions:**
   - Check that `min_interruption_words=1` is set
   - Verify STT is working properly

2. **False interruptions still occur:**
   - Add more acknowledgment words to config
   - Increase `min_word_threshold`

3. **Agent ignores all input:**
   - Check that directive words are properly configured
   - Verify agent state tracking is working

4. **STT errors (429 rate limit):**
   - Set `DEEPGRAM_API_KEY` environment variable
   - Or change STT provider in `basic_agent.py`

### Debug Logging
Enable detailed logging to see filtering decisions:
```python
import logging
logging.getLogger("acknowledgment-patch").setLevel(logging.DEBUG)
logging.getLogger("basic-agent").setLevel(logging.DEBUG)
```

## 📈 Performance & Metrics

The system adds minimal latency (~150ms buffer) while significantly improving conversation flow. Metrics are automatically collected and logged, including:
- Interruption events blocked
- False positive rate
- Response times

## 🤝 Contributing

To extend the system:
1. Add new word categories in `config.py`
2. Implement custom filtering logic in `InterruptionFilter`
3. Test with various conversation scenarios
4. Update documentation

## 📄 License

This project follows the same license as the parent LiveKit Agents repository.</content>
<filePath>c:\Users\Prithvi Ahuja\OneDrive\Desktop\GenAi assignment\agents-assignment\examples\voice_agents\Interrup_handling\README.md
