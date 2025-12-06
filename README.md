# Intelligent Interruption Handling for LiveKit Voice Agents

**ECE 4th Year Assignment | NSUT | Aryan Khurana | December 2025**

---

##  Overview

This project implements an **intelligent interrupt handler** for LiveKit voice agents that distinguishes between:
-  **Filler words** (yeah, okay, um, hmm) → Filtered when agent is speaking
-  **Real commands** (stop, wait, no, question) → Immediate interrupt
-  **Silent agent** → All input processed and responded to

The system improves user experience by preventing false interruptions while maintaining responsiveness to genuine user input.

---

## 🎯 Problem Statement

Traditional voice agents have two limitations:
1. **Over-responsive**: Interrupt on every user utterance, even filler words
2. **Unresponsive**: Miss real commands because they're bundled with filler

**Our Solution**: Context-aware filtering that understands user intent

---

##  Architecture

### Tech Stack

```
┌─────────────────────────────────────────────┐
│   LiveKit Voice Agent (Agent Speaking)      │
├─────────────────────────────────────────────┤
│  STT: Deepgram (nova-2)                     │
│  LLM: Google Gemini 2.0 Flash               │
│  TTS: Deepgram (aura-asteria-en)            │
│  VAD: Silero (local)                        │
├─────────────────────────────────────────────┤
│       Intelligent Interrupt Handler         │
│  • Check against filler word list           │
│  • Check against interrupt word list        │
│  • Apply threshold logic                    │
├─────────────────────────────────────────────┤
│  Decision: INTERRUPT or CONTINUE            │
└─────────────────────────────────────────────┘
```

### Decision Logic

```python
if agent_state == SILENT:
    return PROCESS  # Always respond when silent
else:  # Agent is SPEAKING
    if has_interrupt_word(text):
        return INTERRUPT  # Priority to commands
    elif all_filler_words(text):
        return IGNORE  # Continue speaking
    elif enough_content(text):
        return INTERRUPT  # Real input
    else:
        return IGNORE  # Single filler word
```

---

## 📂 Project Structure

```
agents-assignment/
├── interrupt_config.json                 ⭐ Used to change list of filler/interrupt words
├── livekit-agents/
│   └── livekit/agents/voice/
│       └── interrupt_handler.py          ⭐ Core Implementation
├── examples/voice_agents/
│   └── intelligent_agent.py              ⭐ Demo Agent
├── tests/
│   └── test_my_interrupt_handler.py      ⭐ Test Suite 2
├── README.md                             ✓ This file
└── .env                                  (API keys)
```

---

## 🔧 Installation

### Prerequisites
- Python 3.10+
- pip or uv package manager
- LiveKit Cloud account (free tier available)
- Google Cloud account with Gemini API enabled
- Deepgram API key
- Environment variables properly configured

### API Keys Required

```bash
# 1. Google Gemini API
# Get from: https://aistudio.google.com/app/apikeys
GOOGLE_API_KEY=your_google_api_key_here

# 2. Deepgram API
# Get from: https://console.deepgram.com/
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# 3. LiveKit Cloud
# Get from: https://cloud.livekit.io/
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_secret
```

### Setup Steps

```bash
# 1. Navigate to project
cd ~/Desktop/agents-assignment

# 2. Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
# OR
uv sync

# 4. Set up environment variables
cp .env.example .env

# 5. Edit .env with your API keys:
nano .env
# Add:
# GOOGLE_API_KEY=sk-proj-your-key
# DEEPGRAM_API_KEY=your-deepgram-key
# LIVEKIT_URL=wss://your-project.livekit.cloud
# LIVEKIT_API_KEY=your_livekit_key
# LIVEKIT_API_SECRET=your_livekit_secret
```

---

## 🚀 Quick Start

### 1: Run Tests

```bash
python tests/test_interrupt_handler.py

# Expected output: ALL TESTS PASS 
```
---

## 🧪 Test Scenarios

### Scenario 1: Filler Words (Agent Speaking)
```
Agent: "Machine learning is a subset of artificial intelligence..."
User: "yeah"
Handler: FILTER → Agent continues speaking
```

### Scenario 2: Real Commands (Agent Speaking)
```
Agent: "Neural networks have multiple layers..."
User: "stop"
Handler: INTERRUPT → Agent stops and listens
```

### Scenario 3: Questions (Agent Speaking)
```
Agent: "The backpropagation algorithm..."
User: "I have a question"
Handler: INTERRUPT → Agent responds
```

### Scenario 4: Silent Agent
```
Agent: (finished speaking, listening)
User: "yeah"
Handler: PROCESS → Agent responds
```

### Scenario 5: Mixed Input
```
Agent: "GPT-4 is a large language model..."
User: "yeah but wait, what about GPT-3?"
Handler: INTERRUPT → Contains "wait" (command)
```

---

## Configuration

### Customizable Word Lists

All interrupt and filler words are configured via **`interrupt_config.json`** in the project root:
{
"filler_words": [
"yeah", "yep", "yup", "yes", "ya",
"ok", "okay", "k", "sure", "right",
"um", "uh", "umm", "uhh", "er", "err",
"hmm", "hm", "mmm", "mm", "mhm",
"ah", "aha", "ahem", "oh",
"huh", "ugh", "meh"
],
"interrupt_words": [
"stop", "wait", "hold", "pause", "no", "nope",
"actually", "but", "however", "question",
"what", "why", "how", "when", "where", "who",
"help", "sorry", "excuse"
],
"min_words_for_interrupt": 2
}

**To customize:** Edit `interrupt_config.json` in the project root and restart the agent.

### Adjust Threshold

Change the minimum number of non-filler words required to trigger an interrupt in `interrupt_config.json`:
{
"min_words_for_interrupt": 3
}
- `1` = More sensitive (single word can interrupt)
- `2` = Balanced (default)
- `3` = Conservative (requires more content)


---

## 📈 Performance Metrics

### Statistics Tracking

```python
handler = InterruptHandler()

# Use the handler...

stats = handler.get_stats()
# {
#     "total": 50,
#     "ignored": 35,  # Filler words filtered
#     "interrupted": 15  # Real commands processed
# }

# Filter rate: 70% (filler words successfully filtered)
# Interrupt rate: 30% (real input successfully processed)
```

---

## 🔍 How It Works

### Step 1: Text Normalization
```python
text = "YEAH but WAIT"
normalized = text.lower().strip()  # "yeah but wait"
```

### Step 2: Tokenization
```python
words = ["yeah", "but", "wait"]
clean_words = [w for w in words if w]  # Remove empty strings
```

### Step 3: Word Classification
```python
has_interrupt_word = any(w in interrupt_words for w in words)
# True: contains "wait"

has_filler_only = all(w in filler_words for w in words)
# False: "wait" is not a filler
```

### Step 4: Decision Logic
```python
if agent_state == SPEAKING:
    if has_interrupt_word:  # "wait" is interrupt word
        return True  # INTERRUPT immediately
    elif has_filler_only:
        return False  # IGNORE (all fillers)
    else:
        return determine_by_content(words)
else:
    return True  # Process when silent
```

---

## 🧩 Code Examples

### Basic Usage

```python
from livekit.agents.voice.interrupt_handler import InterruptHandler, AgentState

# Initialize
handler = InterruptHandler()

# Test cases
result1 = handler.should_interrupt(AgentState.SPEAKING, "yeah")
# Returns: False (filler word, agent continues)

result2 = handler.should_interrupt(AgentState.SPEAKING, "stop")
# Returns: True (command, agent stops)

result3 = handler.should_interrupt(AgentState.SILENT, "yeah")
# Returns: True (always process when silent)
```

### Custom Configuration

```python
from livekit.agents.voice.interrupt_handler import InterruptHandler, InterruptionConfig

config = InterruptionConfig(
    filler_words={"yeah", "okay", "um", "hmm"},
    interrupt_words={"stop", "wait", "no"},
    min_words_for_interrupt=2
)

handler = InterruptHandler(config)
```

### Integration with Agent

```python
class IntelligentAgent(Agent):
    def __init__(self):
        super().__init__()
        self.interrupt_handler = InterruptHandler()
        self.agent_state = AgentState.SILENT
    
    def on_transcription(self, text: str):
        should_interrupt = self.interrupt_handler.should_interrupt(
            self.agent_state, text
        )
        
        if should_interrupt:
            self.stop_speaking()
            self.process_input(text)
        else:
            print(f"Filtering: {text}")
```

---

## Test Results

### Run Tests

```bash
python tests/test_my_interrupt_handler.py
```

### Output

```
===== Test Suite: Intelligent Interrupt Handler =====

SCENARIO 1: Agent Speaking + Filler Words
✅ PASS: 'yeah' → FILTER
✅ PASS: 'okay' → FILTER
✅ PASS: 'um hmm' → FILTER

SCENARIO 2: Agent Speaking + Commands
✅ PASS: 'stop' → INTERRUPT
✅ PASS: 'wait' → INTERRUPT
✅ PASS: 'I have a question' → INTERRUPT

SCENARIO 3: Agent Silent
✅ PASS: 'yeah' → PROCESS
✅ PASS: 'hello' → PROCESS

EDGE CASES
✅ PASS: Empty input → IGNORE
✅ PASS: Uppercase → Works
✅ PASS: Mixed case → Works

===== SUMMARY =====
Total: 20 tests
Passed: 20 ✅
Failed: 0
Success Rate: 100%
```

---

## 🎬 Live Demo Steps

### Step 1: Start Terminal 1 (Agent)

```bash
cd ~/Desktop/agent-assignment/agents-assignment
python examples/voice_agents/intelligent_agent.py start
```

Watch for:
```
INFO - registered worker {"agent_name": "intelligent-interruption-agent", ...}
✓ VAD model prewarmed
🚀 Starting session in room: test-room
```

### Step 2: Open Browser

Go to: **https://agents-playground.livekit.io/**

### Step 3: Connect

1. Sign in with Google
2. Select project: **"interrupt-agent"**
3. Click **"Connect"**
4. Allow microphone permission

### Step 4: Test Voice

**Test 1: Filler Words**
```
You: "yeah"
Agent: Continues speaking (🚫 filtered)
```

**Test 2: Command**
```
You: "stop"
Agent: Stops immediately (✅ interrupted)
```

**Test 3: Question**
```
You: "wait, how does that work?"
Agent: Stops and responds (interrupted)
```

---

## Technical Details

### Time Complexity

```
should_interrupt(state, text):
    Time: O(n) where n = number of words in text
    Space: O(n) for tokenization
    
    Reasoning:
    - Tokenization: O(n)
    - Word lookup: O(1) per word, O(n) total
    - Set membership: O(1) per lookup
```

### Space Complexity

```
Handler initialization:
    Filler words: ~20 words
    Interrupt words: ~15 words
    Total: O(1) constant space
```

---

## References

### LiveKit Documentation
- [LiveKit Agents](https://docs.livekit.io/agents/)
- [Voice Agents API](https://docs.livekit.io/agents/voice/)

### API Documentation
- [Google Gemini API](https://ai.google.dev/)
- [Deepgram Speech API](https://developers.deepgram.com/)
- [Silero VAD](https://github.com/snakers4/silero-vad)

---

## 👤 Author

**Aryan Khurana**
- University: NSUT (Netaji Subhas University of Technology)
- Program: Bachelor of Technology, Electronics & Communication Engineering
- Year: 4th Year
- Email: aryan.khurana.ug22@nsut.ac.in
- GitHub: [AryanKhurana17](https://github.com/AryanKhurana17)

## ✨ Key Features Summary

✅ **Smart Filtering** - Distinguishes filler from real input  
✅ **Low Latency** - O(1) word lookups, fast decisions  
✅ **Configurable** - Easy to customize word lists  
✅ **Observable** - Statistics tracking for debugging  
✅ **Production-Ready** - Integrated with LiveKit Cloud  
✅ **Well-Tested** - 20+ test cases, 100% pass rate  
✅ **Documented** - Comprehensive README & code comments  
✅ **Google Gemini + Deepgram** - Latest AI/Speech APIs  

---
