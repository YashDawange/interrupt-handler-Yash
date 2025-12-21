# Intelligent Interruption Handling for LiveKit Voice Agents

> **Assignment Solution**: Distinguish between passive acknowledgements ("yeah", "ok", "hmm") and active interruptions ("stop", "wait", "no") in a LiveKit voice agent.

---

## 📋 Table of Contents

1. [How to Run & Test](#how-to-run--test)
2. [Problem Statement](#problem-statement)
3. [Final Solution](#final-solution)
4. [Easy Word List Configuration](#easy-word-list-configuration)
5. [Modularity & Easy Integration](#modularity--easy-integration)
6. [Performance Optimization](#performance-optimization)
7. [Failed Approaches We Tried](#failed-approaches-we-tried)
8. [Complete Code Reference](#complete-code-reference)

---

## How to Run & Test

### Prerequisites

- **Python 3.10 or higher**
- **uv** (Python package manager)

Verify Python installation:

```bash
python --version
```

---

### Step 1: Create Virtual Environment & Install Dependencies

Create a virtual environment:

```bash
uv venv
```

Activate the virtual environment:

**Windows**

```bash
./venv/Scripts/activate
```

**macOS / Linux**

```bash
source venv/bin/activate
```

Install dependencies:

```bash
uv pip install -r requirements.txt
```

---

### Step 2: Set Up Environment Variables

Create a `.env` file inside the `/examples/` directory and add your API keys:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

OPENAI_API_KEY=your_openai_key
```

> ⚠️ Make sure the `.env` file is placed inside the **`examples/` directory**, not the project root.

---

### Step 3: Run the Agent

*(Ensure the virtual environment is activated)*

```bash
cd examples/voice_agents/intelligent_interrupt
python agent.py console
```

---

### Step 4: Run Unit Tests

*(Ensure the virtual environment is activated)*

```bash
cd examples/voice_agents/intelligent_interrupt
python test_interrupt_filter.py
```

**Expected Output:**

```text
Ran 36 tests in 0.008s
OK
```

---

### 📹 Proof Video

**video Link:**
[view](https://drive.google.com/file/d/1sWpD5jmh0bwUhIAElUHD7BNK0rMSnabc/view)

---

## Problem Statement

### The Challenge

When building voice agents with LiveKit, the default behavior triggers an interruption whenever the user speaks while the agent is talking. This creates a poor user experience because:

- **User says "yeah"** → Agent pauses/stops → But "yeah" was just acknowledgement, not a command
- **User says "ok"** → Agent stops → But user was just confirming they're listening
- **User says "hmm"** → Agent interrupts → But user was just thinking along

The assignment requires building an intelligent system that can:

1. **IGNORE** passive acknowledgements ("yeah", "ok", "hmm", "uh-huh") when the agent is speaking
2. **INTERRUPT** immediately when the user gives an active command ("stop", "wait", "no")
3. **RESPOND** normally when the agent is silent

### The Core Difficulty

LiveKit's Voice Activity Detection (VAD) operates at the **audio level**, detecting voice before any transcript is available:

```
Standard LiveKit Timeline (The Problem):
─────────────────────────────────────────────────────────────
0ms     User says "yeah"
50ms    VAD detects voice activity
100ms   Agent PAUSES (too early! transcript not available yet)
600ms   Transcript "yeah" arrives
700ms   We could filter here, but agent already paused!
─────────────────────────────────────────────────────────────
```

By the time we know **what** the user said, the agent has already stopped. This is the fundamental timing problem we needed to solve.

---

## Final Solution

### The Key Insight

We discovered a powerful combination of settings that solves the problem:

```python
session = AgentSession(
    allow_interruptions=True,   # ✅ Keeps STT active during agent speech
    min_interruption_words=999, # ✅ Blocks all automatic audio-level interrupts
)
```

**Why This Works:**
- `allow_interruptions=True` → STT remains active, we receive transcripts during agent speech
- `min_interruption_words=999` → User would need 999 words for auto-interrupt (effectively disabled)
- We manually trigger interrupts based on transcript analysis!

### The Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT INTERRUPT FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      AUDIO LAYER                              │   │
│  │  ┌─────────┐     ┌──────────────────────┐                    │   │
│  │  │   VAD   │────▶│ min_interruption_    │                    │   │
│  │  │ Silero  │     │ words = 999          │                    │   │
│  │  └─────────┘     │                      │                    │   │
│  │                  │ All audio-level      │                    │   │
│  │                  │ interrupts BLOCKED   │                    │   │
│  │                  └──────────────────────┘                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   TRANSCRIPT LAYER                            │   │
│  │                                                               │   │
│  │  ┌─────────────┐     ┌─────────────────┐     ┌────────────┐  │   │
│  │  │   STT       │────▶│ InterruptFilter │────▶│  Decision  │  │   │
│  │  │ (Deepgram)  │     │                 │     │            │  │   │
│  │  │             │     │ O(1) Set-based  │     │ • ignore   │  │   │
│  │  │ • interim   │     │ word matching   │     │ • interrupt│  │   │
│  │  │ • final     │     │                 │     │ • respond  │  │   │
│  │  └─────────────┘     └─────────────────┘     └─────┬──────┘  │   │
│  │                                                     │         │   │
│  │                    ┌────────────────────────────────┘         │   │
│  │                    ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────┐ │   │
│  │  │                    ACTION                                │ │   │
│  │  │                                                          │ │   │
│  │  │  interrupt → session.current_speech.interrupt(force=True)│ │   │
│  │  │  ignore    → do nothing, agent continues                 │ │   │
│  │  │  respond   → let LLM handle normally                     │ │   │
│  │  └─────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Timeline With Our Solution

```
FOR FILLER WORDS ("yeah"):
─────────────────────────────────────────────────────────────
0ms     User says "yeah"
50ms    VAD detects voice
100ms   min_interruption_words=999 → No auto-interrupt
        Agent CONTINUES speaking ✅
600ms   Transcript "yeah" arrives
610ms   InterruptFilter → "ignore" → Agent continues ✅
─────────────────────────────────────────────────────────────

FOR COMMAND WORDS ("stop"):
─────────────────────────────────────────────────────────────
0ms     User says "stop"
50ms    VAD detects voice
100ms   min_interruption_words=999 → No auto-interrupt
200ms   Interim transcript "stop" arrives
210ms   InterruptFilter → "interrupt" → Manual interrupt!
220ms   Agent stops immediately ✅
─────────────────────────────────────────────────────────────
```

### Decision Logic Matrix

| User Says | Agent State | Filter Decision | Agent Action |
|-----------|-------------|-----------------|--------------|
| "yeah" | Speaking | **IGNORE** | Continues speaking |
| "ok" | Speaking | **IGNORE** | Continues speaking |
| "hmm" | Speaking | **IGNORE** | Continues speaking |
| "stop" | Speaking | **INTERRUPT** | Stops immediately |
| "wait" | Speaking | **INTERRUPT** | Stops immediately |
| "no" | Speaking | **INTERRUPT** | Stops immediately |
| "yeah but wait" | Speaking | **INTERRUPT** | Stops (command word detected) |
| "tell me more" | Speaking | **INTERRUPT** | Stops (substantive content) |
| "yeah" | Silent | **RESPOND** | Processes as input |
| Any input | Silent | **RESPOND** | Normal conversation |

---


## Easy Word List Configuration

### 🎯 The Main Advantage: Simple Word List Updates

One of the **key benefits** of our modular design is how easy it is to update word lists. No code changes required!

### Method 1: Edit `wordlists.py` Directly

Open `wordlists.py` and modify the word sets:

```python
# wordlists.py

# Add words to IGNORE (passive acknowledgements)
DEFAULT_IGNORE_WORDS: frozenset[str] = frozenset([
    # Your custom words here
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k",
    "hmm", "hm", "uh-huh", "mm-hmm",
    "right", "alright", "sure",
    "cool", "nice", "great",
    "um", "uh", "er",
    
    # ← ADD NEW IGNORE WORDS HERE
    "gotcha", "totally", "absolutely",
])

# Add words to INTERRUPT (active commands)
DEFAULT_INTERRUPT_WORDS: frozenset[str] = frozenset([
    "stop", "wait", "hold", "pause",
    "no", "nope", "cancel", "quit",
    "actually", "but", "however",
    "question", "help", "what",
    
    # ← ADD NEW INTERRUPT WORDS HERE
    "emergency", "urgent", "critical",
])
```

### Method 2: Environment Variables (No Code Changes!)

Set word lists via environment variables - perfect for deployment:

```bash
# .env file or system environment
IGNORE_WORDS=yeah,ok,hmm,right,sure,gotcha,totally
INTERRUPT_WORDS=stop,wait,no,cancel,emergency,urgent
```

Then load them:

```python
config = InterruptFilterConfig.from_env()
filter = InterruptFilter(config)
```

### Method 3: Runtime Configuration

Pass custom words when creating the filter:

```python
from intelligent_interrupt import InterruptFilter, InterruptFilterConfig

# Create custom configuration
config = InterruptFilterConfig(
    ignore_words=frozenset([
        "yeah", "ok", "hmm", "uh-huh",
        "sounds good", "makes sense",  # Multi-word phrases work too!
    ]),
    interrupt_words=frozenset([
        "stop", "wait", "cancel",
        "hold on", "one second",  # Multi-word phrases work too!
    ]),
)

filter = InterruptFilter(config)
```

### Method 4: Domain-Specific Word Lists

Create specialized word lists for different use cases:

```python
# For a medical agent
config = InterruptFilterConfig.for_domain(
    "medical",
    additional_ignore=frozenset(["uh-huh", "i understand"]),
    additional_interrupt=frozenset(["emergency", "pain", "help me"]),
)

# For a customer service agent
config = InterruptFilterConfig.for_domain(
    "customer_service",
    additional_ignore=frozenset(["thanks", "thank you"]),
    additional_interrupt=frozenset(["manager", "supervisor", "complaint"]),
)
```

### Default Word Lists Reference

#### Ignore Words (Passive Acknowledgements)
```python
"yeah", "yes", "yep", "yup", "ya",      # Affirmative
"ok", "okay", "k",                       # Confirmation
"hmm", "hm", "uh-huh", "mm-hmm", "mhm",  # Thinking sounds
"right", "alright", "sure", "aha", "ah", # Agreement
"i see", "got it", "gotcha",             # Understanding
"cool", "nice", "great",                 # Positive reactions
"um", "uh", "er",                        # Filler sounds
```

#### Interrupt Words (Active Commands)
```python
"stop", "wait", "hold", "pause",         # Stop commands
"no", "nope", "cancel", "quit",          # Negation
"actually", "but", "however",            # Correction
"question", "ask", "excuse", "sorry",    # Attention
"repeat", "again", "help", "what",       # Requests
"hang on", "one second",                 # Pause requests
```

---

## Modularity & Easy Integration

### 🔌 Plug-and-Play Design

Our solution is designed to integrate into **any LiveKit voice agent** with just **2 lines of code**:

```python
from intelligent_interrupt import attach_interrupt_handlers, get_session_options

# Create session with recommended settings
session = AgentSession(
    llm=llm, stt=stt, tts=tts, vad=vad,
    **get_session_options(),  # ← Line 1: Apply settings
)

# One-line integration!
attach_interrupt_handlers(session)  # ← Line 2: Attach handlers
```

**That's it!** Your agent now has intelligent interrupt handling.

### Module Structure

```
intelligent_interrupt/
├── __init__.py              # Public API - clean exports
├── filter.py                # Core logic - InterruptFilter class
├── wordlists.py             # Configuration - editable word lists
├── session_integration.py   # Integration - plug-and-play setup
├── agent.py                 # Example - working demonstration
├── test_interrupt_filter.py # Testing - 36 unit tests
└── README.md                # Documentation
```

### File Responsibilities

| File | Purpose | What You Can Modify |
|------|---------|---------------------|
| `wordlists.py` | Word configuration | **Add/remove words here!** |
| `filter.py` | Core filtering logic | Decision logic if needed |
| `session_integration.py` | LiveKit integration | Session settings |
| `agent.py` | Example agent | Use as template |
| `__init__.py` | Public exports | Add new exports |

### Integration Examples

#### Example 1: Basic Integration
```python
from intelligent_interrupt import attach_interrupt_handlers, get_session_options

session = AgentSession(**get_session_options())
attach_interrupt_handlers(session)
```

#### Example 2: With Custom Filter
```python
from intelligent_interrupt import InterruptFilter, InterruptFilterConfig

config = InterruptFilterConfig(
    ignore_words=frozenset(["yeah", "ok"]),
    interrupt_words=frozenset(["stop", "emergency"]),
)
custom_filter = InterruptFilter(config)
attach_interrupt_handlers(session, interrupt_filter=custom_filter)
```

#### Example 3: With Logging Enabled
```python
attach_interrupt_handlers(session, log_decisions=True)
# Logs: [INTERRUPT] 'stop' - Found interrupt command words: ['stop']
# Logs: [IGNORE] 'yeah' - Only filler words detected: ['yeah']
```

---


## Performance Optimization

### 🚀 O(1) Set-Based Lookup

We optimized the word matching from **O(n × m)** regex to **O(1)** set-based lookup for maximum performance.

### Before: Regex Approach (Slower)

```python
# Original implementation - O(n × m) complexity
self._ignore_pattern = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b',
    re.IGNORECASE
)

def find_matches(self, text):
    # Scans entire text for pattern matches
    return [m.group() for m in self._ignore_pattern.finditer(text)]
```

**Problems with Regex:**
- Scans entire text character by character
- Pattern complexity grows with word list size
- Performance degrades with longer transcripts

### After: Set-Based Lookup (Faster) ✅

```python
# Optimized implementation - O(1) per word
def _build_lookup_sets(self) -> None:
    # Pre-compute lowercase sets for instant lookup
    self._ignore_set = {w.lower() for w in self.config.ignore_words}
    self._interrupt_set = {w.lower() for w in self.config.interrupt_words}

def _find_ignore_words(self, text: str, words: list[str]) -> list[str]:
    matched = []
    for word in words:
        if word in self._ignore_set:  # O(1) hash lookup!
            matched.append(word)
    return matched
```

**Why Sets Are Faster:**
- Hash-based lookup: O(1) average case
- No text scanning required
- Performance independent of word list size

### Performance Comparison

| Method | Complexity | 36 Tests Runtime |
|--------|------------|------------------|
| Regex | O(n × m) | ~0.015s |
| **Set Lookup** | **O(1)** | **0.008s** |

### How It Works Internally

```python
# 1. Build lookup sets once (at initialization)
self._ignore_set = {"yeah", "ok", "hmm", "uh-huh", ...}
self._interrupt_set = {"stop", "wait", "no", "cancel", ...}

# 2. Split transcript into words
words = transcript.lower().split()  # ["yeah", "sounds", "good"]

# 3. O(1) lookup for each word
for word in words:
    if word in self._ignore_set:    # Hash lookup: O(1)
        # Found ignore word
    if word in self._interrupt_set:  # Hash lookup: O(1)
        # Found interrupt word

# 4. Multi-word phrases checked separately (small set)
for phrase in self._ignore_phrases:
    if phrase in text:  # "i see", "got it", etc.
        # Found phrase
```

---

## Failed Approaches We Tried

### ❌ Approach 1: Disabling Interruptions Entirely

**What We Tried:**
```python
session = AgentSession(
    allow_interruptions=False,  # Disable all interrupts
)
```

**Why It Failed:**
- When `allow_interruptions=False`, LiveKit **completely disables STT** during agent speech
- We never receive transcripts while the agent is talking
- Cannot analyze user input = Cannot make intelligent decisions

**Lesson Learned:** We need transcripts to make decisions, so STT must stay active.

---

### ❌ Approach 2: Post-Transcript Filtering Only

**What We Tried:**
```python
@session.on("user_input_transcribed")
def on_transcript(ev):
    if ev.is_final:  # Only process final transcripts
        analysis = filter.analyze(ev.transcript)
        # ... handle result
```

**Why It Failed:**
- Final transcripts arrive 600-800ms after user speaks
- By then, VAD has already triggered the interrupt
- Agent pauses before we can decide to ignore

**Lesson Learned:** We need to process **interim** transcripts for faster detection.

---

### ❌ Approach 3: VAD Sensitivity Adjustment

**What We Tried:**
- Adjusting VAD sensitivity thresholds
- Trying different `min_interruption_duration` values

**Why It Failed:**
- VAD operates on audio amplitude, not content
- Can't distinguish "yeah" from "stop" at audio level
- Reducing sensitivity causes missed legitimate interrupts

**Lesson Learned:** Content analysis requires transcripts, not audio tuning.

---

### ❌ Approach 4: Simple Word Count Filtering

**What We Tried:**
```python
if len(transcript.split()) == 1:
    # Single word = probably filler, ignore
    return "ignore"
```

**Why It Failed:**
- "stop" is one word but should interrupt
- "yeah okay sure" is three words but should be ignored
- Word count doesn't correlate with intent

**Lesson Learned:** We need semantic understanding, not just counting.

---

### ✅ Final Solution: The Winning Approach

After trying and failing with the above approaches, we discovered the winning combination:

```python
session = AgentSession(
    allow_interruptions=True,   # ✅ Keep STT active
    min_interruption_words=999, # ✅ Block audio-level interrupts
)
```

This:
1. Keeps STT running during agent speech (we get transcripts!)
2. Blocks automatic VAD interrupts (agent doesn't pause prematurely)
3. Lets us manually trigger interrupts based on content analysis

---

## Complete Code Reference

### Core Classes

#### InterruptFilter
```python
class InterruptFilter:
    def __init__(self, config: InterruptFilterConfig | None = None):
        self.config = config or InterruptFilterConfig()
        self._build_lookup_sets()  # O(1) optimization
    
    def analyze(self, transcript: str, agent_speaking: bool) -> InterruptAnalysis:
        """Analyze transcript and return decision with reasoning."""
        # Returns: "ignore", "interrupt", or "respond"
    
    def should_interrupt(self, transcript: str, agent_speaking: bool) -> bool:
        """Simple boolean check."""
        return self.analyze(transcript, agent_speaking).should_interrupt
```

#### InterruptAnalysis
```python
@dataclass
class InterruptAnalysis:
    decision: InterruptDecision      # "ignore" | "interrupt" | "respond"
    transcript: str                   # The analyzed text
    agent_was_speaking: bool          # Agent state when analyzed
    matched_ignore_words: list[str]   # Filler words found
    matched_interrupt_words: list[str] # Command words found
    reason: str                       # Human-readable explanation
```

#### InterruptFilterConfig
```python
@dataclass
class InterruptFilterConfig:
    ignore_words: frozenset[str]     # Words to ignore
    interrupt_words: frozenset[str]  # Words that trigger interrupt
    case_sensitive: bool = False
    partial_match: bool = True
```

### Session Integration Functions

```python
def get_session_options() -> dict:
    """Get recommended session settings."""
    return {
        "allow_interruptions": True,
        "min_interruption_words": 999,
    }

def attach_interrupt_handlers(
    session: AgentSession,
    interrupt_filter: InterruptFilter | None = None,
    log_decisions: bool = True,
) -> dict:
    """Attach intelligent interrupt handling to a session."""
    # Attaches event handlers for state tracking and transcript analysis
```

---

## Troubleshooting

### Agent Still Pauses on "yeah"

Check that you're using the correct session options:
```python
session = AgentSession(
    allow_interruptions=True,       # Must be True
    min_interruption_words=999,     # Must be high
)
```

### Transcripts Not Arriving

Ensure STT is configured and `allow_interruptions=True`:
```python
session = AgentSession(
    stt="deepgram/nova-3",
    allow_interruptions=True,  # Required for STT during speech
)
```

### Interrupt Commands Not Working

Verify event handlers are attached:
```python
attach_interrupt_handlers(session, log_decisions=True)
# Check logs for decision output
```

---

## Summary

Our solution solves the LiveKit intelligent interruption challenge through:

1. **Smart Configuration**: `allow_interruptions=True` + `min_interruption_words=999`
2. **Content Analysis**: O(1) set-based word matching
3. **Manual Interrupts**: `session.current_speech.interrupt(force=True)`
4. **Modular Design**: Easy integration and word list configuration

**Result**: Natural conversation flow where filler words are ignored and command words trigger immediate interruption.

---

## License

Part of the LiveKit Agents project. See [LICENSE](../../../LICENSE) for details.
