# 🎤 Intelligent Interrupt Handler — LiveKit Voice Agent

## 📌 Overview

This project implements a custom **InterruptHandler** for the LiveKit voice agent that intelligently decides when a user's speech should **interrupt** the agent and when it should be **ignored** (backchannel speech).

### Key Features
- **Backchannel Recognition**: Acknowledging phrases like *"yeah"*, *"ok"*, *"hmm"* don't interrupt the agent
- **Command Detection**: Critical words like *"stop"*, *"wait"*, *"no"* immediately interrupt
- **Natural Conversation Flow**: Reduces accidental interruptions while staying responsive
- **Automated Testing**: Comprehensive test suite validates all interrupt logic

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager
- LiveKit API credentials (optional for console mode)

### 1️⃣ Create & Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2️⃣ Install Required Dependencies

```bash
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
pip install python-dotenv
```

### 3️⃣ Set Up Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
DEEPGRAM_API_KEY=your_deepgram_key_here  # Optional
CARTESIA_API_KEY=your_cartesia_key_here  # Optional
LIVEKIT_URL=your_livekit_url             # Optional
LIVEKIT_API_KEY=your_livekit_api_key     # Optional
LIVEKIT_API_SECRET=your_livekit_secret   # Optional
```

### 4️⃣ Run Agent in Console Mode (No Audio Required)

```bash
python3 -m examples.voice_agents.basic_agent console --text
```

The agent will now process text input with your custom interrupt logic applied.

---

## 🧪 Running Tests

Verify that all interrupt logic works correctly:

```bash
python3 test.py
```

**Expected Output:**
```
test_ignore_backchannel_words ✓ PASS
test_interrupt_command_words ✓ PASS
test_normal_speech_interrupts ✓ PASS
test_ignore_multiple_backchannels ✓ PASS
test_mixed_content_handling ✓ PASS

All tests PASSED ✓
```

---

## 🧠 Interrupt Logic Reference

### Decision Table

| Speech Type | Category | Agent Speaking? | Result |
|------------|----------|-----------------|--------|
| *"yeah"*, *"ok"*, *"hmm"* | Backchannel | ✅ Yes | ❌ **Ignore** |
| *"stop"*, *"wait"*, *"no"* | Interrupt Command | ✅ Yes | ⛔ **Interrupt** |
| Regular sentence | Normal Speech | ✅ Yes | ⛔ **Interrupt** |
| Any speech | General | ❌ No | ✔️ **Accept** |

### Word Categories

Configured in `interrupt_handler.py`:

**Backchannel Words (Ignored):**
```python
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh",
    "mhm", "huh", "yep", "sure", "alright"
}
```

**Interrupt Commands (Always interrupt):**
```python
INTERRUPT_WORDS = {
    "stop", "wait", "no", "hold on",
    "pause", "cancel", "abort", "quit"
}
```

### Logic Flow

```
User speaks while agent is responding
    ↓
Extract transcript
    ↓
Contains INTERRUPT_WORDS? → ⛔ INTERRUPT (highest priority)
    ↓
Contains ONLY IGNORE_WORDS? → ❌ IGNORE (backchannel)
    ↓
Contains other words? → ⛔ INTERRUPT (user has something to say)
    ↓
Agent accepts or rejects interrupt
```

---

## 📂 Project Structure

```
agents-assignment/
│
├── examples/
│   └── voice_agents/
│       ├── basic_agent.py              # Main agent with interrupt handler registration
│       ├── interrupt_handler.py        # Custom interrupt logic implementation
│       └── __init__.py
│
├── test.py                             # Automated test suite
├── .env                                # Environment variables (create this)
├── .gitignore                          # Git ignore patterns
├── requirements.txt                    # Python dependencies
└── README.md                           # Documentation (you are here)
```

---

## 💻 Core Implementation

### interrupt_handler.py

The `InterruptHandler` class handles interrupt decisions:

```python
class InterruptHandler(UserMessageHandler):
    IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh", ...}
    INTERRUPT_WORDS = {"stop", "wait", "no", "hold on", ...}
    
    def on_message(self, message: UserMessage) -> None:
        """Decide whether to interrupt or ignore user speech"""
        
    def _should_interrupt(self, text: str) -> bool:
        """Intelligent interrupt decision logic"""
        
    def _normalize_text(self, text: str) -> str:
        """Normalize and clean transcript"""
```

### basic_agent.py

Registers and uses the custom interrupt handler:

```python
def create_agent():
    agent = VoiceAssistantOptions(
        model=openai.LLM.with_ai_functions(...),
        interrupt_handler=InterruptHandler(),  # Custom handler
        ...
    )
    return agent
```

---

## 🔧 Configuration

### Customizing Word Lists

Edit `interrupt_handler.py` to add or remove words:

```python
# Add backchannel words
IGNORE_WORDS = {"yeah", "ok", "mmm", "right", "sure"}

# Add interrupt commands
INTERRUPT_WORDS = {"stop", "wait", "help", "emergency"}
```

### Adjusting Sensitivity

For more aggressive interruption, add words to `INTERRUPT_WORDS`:

```python
INTERRUPT_WORDS.add("um")  # Interrupt on hesitation filler
```

For more lenient behavior, expand `IGNORE_WORDS`:

```python
IGNORE_WORDS.add("exactly")  # Treat as backchannel
```

---
