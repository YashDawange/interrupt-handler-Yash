# LiveKit Voice Agent - Smart Interrupt Handler

A sophisticated voice agent implementation that intelligently handles user interruptions using state-aware filtering and semantic analysis.

## 🎯 Overview

This agent solves a critical UX problem in voice conversations: distinguishing between **passive backchanneling** ("yeah", "ok", "hmm") and **intentional interruptions** ("stop", "wait"). The solution provides a natural conversation flow where users can acknowledge the agent without disrupting its speech, while still allowing immediate interruption when needed.

## ✨ Key Features

### 1. **Configurable Word Lists**

* **Soft Words** (backchannels): "yeah", "ok", "hmm", "uh-huh", "right" - ignored during agent speech
* **Hard Words** (commands): "stop", "wait", "no", "cancel", "pause" - force immediate interruption
* Easily customizable via `interrupt_config.py`

### 2. **State-Aware Filtering**

The agent behavior adapts based on its current state:

| Agent State        | User Input               | Behavior                             |
| ------------------ | ------------------------ | ------------------------------------ |
| **Speaking** | Soft words only ("yeah") | Ignored completely - no interruption |
| **Speaking** | Hard words ("stop")      | Force interrupt immediately          |
| **Speaking** | Mixed/other content      | Treat as real interruption           |
| **Idle**     | Soft words ("yeah")      | Process as normal user input         |
| **Idle**     | Hard words ("stop")      | Process as normal user input         |
| **Idle**     | Any other input          | Process as normal user input         |

### 3. **Semantic Interruption Detection**

The system tokenizes and analyzes entire utterances:

* "Yeah okay hmm" → Pure soft, ignored while speaking
* "Yeah wait a second" → Contains "wait" (hard word), triggers interrupt
* "Okay but actually..." → Contains non-soft words, triggers interrupt

### 4. **Zero VAD Modification**

* Works entirely at the application logic layer
* No low-level audio processing changes
* Leverages existing LiveKit framework events

## 🏗️ Architecture

### Core Components

```
interrupt_config.py          # Word list configuration
    ├── SOFT_WORDS (set)     # Backchannel words
    └── HARD_WORDS (set)     # Interrupt commands

interrupt-handler-harshmehta1618.py  # Main agent logic
    ├── MyAgent              # Agent class with instructions
    ├── _tokens()            # Text tokenization
    ├── _is_soft()           # Soft word detection
    ├── _has_hard()          # Hard word detection
    └── _on_user_input_transcribed()  # Core interrupt logic
```

### Critical Configuration

```python
session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-nano",
    tts="inworld/inworld-tts-1",
  
    # 🔒 KEY: Disable automatic interruptions
    allow_interruptions=False,
  
    # 🔑 KEY: Keep STT running even when uninterruptible
    discard_audio_if_uninterruptible=False,
  
    # Still handle false interruptions gracefully
    resume_false_interruption=True,
    false_interruption_timeout=1.0,
)
```

## 🧠 How It Works

### Decision Flow

```
User speaks → STT finalizes → Check agent_state
                                      ↓
                        Is agent speaking?
                        ↓              ↓
                      YES             NO
                       ↓               ↓
            Contains hard word?    Process normally
            ↓              ↓       (LLM handles it)
          YES            NO
           ↓              ↓
    Force interrupt   Only soft words?
                      ↓           ↓
                    YES          NO
                     ↓            ↓
               IGNORE       Force interrupt
            (no hiccup)    (real content)
```

### Example Execution Traces

**Scenario 1: Soft backchannel while speaking**

```
[STT] FINAL text='yeah' | agent_state=speaking
[LOGIC] words=['yeah'] | is_soft=True | has_hard=False
[LOGIC] SOFT backchannel while speaking -> IGNORE COMPLETELY
```

**Scenario 2: Hard interrupt while speaking**

```
[STT] FINAL text='stop' | agent_state=speaking
[LOGIC] words=['stop'] | is_soft=False | has_hard=True
[LOGIC] HARD interrupt while speaking -> calling session.interrupt(force=True)
```

**Scenario 3: Soft word while idle**

```
[STT] FINAL text='yeah' | agent_state=listening
[LOGIC] words=['yeah'] | is_soft=True | has_hard=False
[LOGIC] SOFT input while agent NOT speaking -> normal user turn
```

**Scenario 4: Mixed input**

```
[STT] FINAL text='yeah wait a second' | agent_state=speaking
[LOGIC] words=['yeah', 'wait', 'a', 'second'] | is_soft=False | has_hard=True
[LOGIC] HARD interrupt while speaking -> calling session.interrupt(force=True)
```

## 🚀 Setup & Installation

### Prerequisites

* Python 3.9+
* LiveKit server (local or cloud)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>

# Install dependencies once inside voice_agents
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys:
# LIVEKIT_URL=<your-livekit-url>
# LIVEKIT_API_KEY=<your-api-key>
# LIVEKIT_API_SECRET=<your-api-secret>
```

### Running the Agent

```bash
# Start the agent
python interrupt-handler-harshmehta1618.py console
```

## 🧪 Test Scenarios

### Scenario 1: The Long Explanation ✅

* **Context** : Agent reading a long paragraph
* **User** : "Okay... yeah... uh-huh" (while agent talks)
* **Result** : Agent continues uninterrupted

### Scenario 2: The Passive Affirmation ✅

* **Context** : Agent asks "Are you ready?" and goes silent
* **User** : "Yeah"
* **Result** : Agent processes "Yeah" as answer and proceeds

### Scenario 3: The Correction ✅

* **Context** : Agent counting "One, two, three..."
* **User** : "No stop"
* **Result** : Agent cuts off immediately

### Scenario 4: The Mixed Input ✅

* **Context** : Agent speaking
* **User** : "Yeah okay but wait"
* **Result** : Agent stops (contains "wait", not pure soft)

## 📊 Proof Artifacts

Located in the `proof/` directory:

### 1. `log-transcript-harshmehta1618.txt`

Complete console logs showing:

* "Yeah" while agent is speaking → **ignored** (no interruption)
* "Yeah" while agent is idle → **processed** as normal turn
* "Stop" and "wait" while agent is speaking → **hard interrupt** via `session.interrupt(force=True)`
* State transitions and decision logic for each utterance

### 2. `video-demo-harshmehta1618.mp4`

Short recording demonstrating:

* Natural backchanneling without disruption
* Immediate response to hard interrupts
* Smooth conversation flow

## ⚙️ Customization

### Adding New Words

Edit `interrupt_config.py`:

```python
SOFT_WORDS: set[str] = {
    # Add your backchannel words
    "yeah", "ok", "hmm",
    "sure",      # ← Add new soft words
    "gotcha",    # ← Add new soft words
}

HARD_WORDS: set[str] = {
    # Add your interrupt commands
    "stop", "wait", "no",
    "hold on",   # ← Add new hard words
    "interrupt", # ← Add new hard words
}
```

### Adjusting Agent Behavior

Modify `MyAgent` instructions in `interrupt-handler-harshmehta1618.py`:

```python
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. "
                "Keep responses concise. "
                # ← Customize personality and behavior
            ),
        )
```

## 🔧 Technical Details

### Latency Optimization

* **Final transcripts only** : Ignores noisy partial transcripts
* **Pre-compiled sets** : O(1) word lookup with Python sets
* **Minimal processing** : Simple tokenization with regex
* **No blocking calls** : All logic runs in async event handlers

### False Interruption Handling

The system handles "false starts" gracefully:

1. VAD detects speech (faster than STT)
2. Agent may start to interrupt
3. STT finalizes → reveals soft word
4. `resume_false_interruption=True` allows agent to continue

### Error Handling

```python
try:
    session.interrupt(force=True)
except Exception:
    logger.exception("[ERROR] interrupt failed")
    # Agent continues gracefully
```

## 📝 Code Structure

### Token Analysis

```python
def _tokens(text: str) -> list[str]:
    # "Yeah, okay?" → ["yeah", "okay"]
    return [w for w in re.split(r"[^a-z]+", text.lower()) if w]

def _is_soft(words: list[str]) -> bool:
    # All words must be in SOFT_WORDS
    return bool(words) and all(w in SOFT_WORDS for w in words)

def _has_hard(words: list[str]) -> bool:
    # Any word in HARD_WORDS
    return any(w in HARD_WORDS for w in words)
```

### State-Based Logic

```python
if agent_state == "speaking":
    if has_hard:
        session.interrupt(force=True)  # Hard interrupt
    elif is_soft:
        return  # Ignore completely
    else:
        session.interrupt(force=True)  # Real content
else:
    # Agent not speaking: process all input normally
    return
```

## 👤 Author

**Harsh Mehta** (harshmehta1618)
