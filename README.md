# LiveKit Intelligent Interruption Handling

## Assignment Overview

This project implements an intelligent interruption handling system for LiveKit voice agents that distinguishes between passive acknowledgments (like "yeah", "ok") and active interruptions (like "stop", "wait") based on the agent's speaking state.

### Problem Statement

LiveKit's default Voice Activity Detection (VAD) is too sensitive. When a user says backchanneling words like "yeah" or "ok" while the agent is speaking, the agent incorrectly interprets this as an interruption and stops speaking abruptly. This creates a poor user experience.

### Solution

We implemented a context-aware filtering layer that:
- **Ignores** backchanneling words when the agent is speaking
- **Allows** interruptions for commands like "stop" or "wait"
- **Responds** normally to backchanneling when the agent is silent
- **Handles** mixed inputs intelligently (e.g., "yeah wait" → interrupts on "wait")

---

## How It Works

### Core Concept

The system uses **monkey-patching** to intercept interrupt-related methods in the LiveKit AgentActivity class. When an interruption is triggered, our handler:

1. **Checks the agent's state** - Is it currently speaking?
2. **Analyzes the transcript** - What did the user actually say?
3. **Makes a decision** - Should we allow or prevent the interruption?

### Key Components

#### 1. IntelligentInterruptHandler Class

The main handler class that:
- Maintains lists of ignore words and interrupt commands
- Tracks the agent's speaking state
- Intercepts critical methods to add filtering logic

#### 2. Intercepted Methods

Our implementation intercepts the following methods in `interrupt_handler_agent.py`:
- `_interrupt_by_audio_activity()` - Main interrupt trigger point with explicit command handling
- `on_interim_transcript()` - **Critical**: Filters transcripts before they accumulate
- `on_final_transcript()` - Filters final transcripts and prevents processing fillers
- `on_end_of_turn()` - Prevents turn completion for fillers/interrupt-only commands
- `_user_turn_completed_task()` - Prevents adding interrupt-only commands to chat context

### Decision Logic Flow

```
User speaks → VAD detects audio → Interrupt check triggered
    ↓
Check agent state (speaking or silent?)
    ↓
If speaking:
    ├─ Check transcript
    │   ├─ Empty? → Wait for STT (prevents false interruption)
    │   ├─ Contains interrupt command? → ALLOW interrupt
    │   ├─ Only fillers? → PREVENT interrupt
    │   └─ Has meaningful content? → ALLOW interrupt
    └─ If silent: Always allow (normal conversation)
```

### Implementation Approach

Our implementation (`interrupt_handler_agent.py`) provides:
- Seamless experience with no pauses
- Filters at interim transcript stage (prevents pauses)
- Performance optimizations (caching)
- Explicit interrupt command handling (immediate stop on "stop", "wait", etc.)

---

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- LiveKit account and API keys
- Deepgram API key (for STT)
- Cartesia API key (for TTS)
- Gemini API key (as LLM)

### Installation Steps

1. **Clone the repository:**
```bash
git clone https://github.com/Anuragp22/agents-assignment.git
cd agents-assignment
```

2. **Install dependencies:**
```bash
cd examples/voice_agents
pip install -r requirements.txt
```

3. **Set up environment variables:**
Create a `.env` file in the root directory (or ensure it exists):
```env
LIVEKIT_URL=wss://your-livekit-url.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
DEEPGRAM_API_KEY=your-deepgram-key
CARTESIA_API_KEY=your-cartesia-key
GOOGLE_API_KEY=your-gemini-key
```

4. **Run the agent:**
```bash
cd examples/voice_agents
python interrupt_handler_agent.py console
```

**Note:** Make sure you're in the `examples/voice_agents` directory before running the agent.

---

## Configuration

### Customizing Ignore Words

You can customize which words are ignored when the agent is speaking:

```python
handler = IntelligentInterruptHandler(
    ignore_words=["yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay", "uh", "um", "mm-hmm"],
    interrupt_commands=["stop", "wait", "no", "halt", "pause", "cancel"],
)
```

### Customizing Interrupt Commands

Words that always trigger interruption:

```python
interrupt_commands=["stop", "wait", "no", "halt", "pause", "cancel"]
```

---

## Test Scenarios

### Scenario 1: Long Explanation (Backchanneling Ignored)

**Setup:** Agent is explaining a long topic about history.

**User Action:** User says "Okay... yeah... uh-huh" while agent is talking.

**Expected Result:** Agent continues speaking without any pause or interruption.

**Test Command:**
```bash
# Start agent, ask a long question, then say "yeah" while it's responding
```

### Scenario 2: Passive Affirmation (Normal Response)

**Setup:** Agent asks "Are you ready?" and goes silent.

**User Action:** User says "Yeah."

**Expected Result:** Agent processes "Yeah" as a valid answer and responds appropriately.

**Test Command:**
```bash
# Wait for agent to finish speaking, then say "yeah"
```

### Scenario 3: Correction (Immediate Interrupt)

**Setup:** Agent is counting "One, two, three..."

**User Action:** User says "No stop."

**Expected Result:** Agent stops immediately.

**Test Command:**
```bash
# While agent is speaking, say "stop" or "wait"
```

### Scenario 4: Mixed Input (Semantic Interruption)

**Setup:** Agent is speaking.

**User Action:** User says "Yeah okay but wait."

**Expected Result:** Agent stops because "wait" is an interrupt command.

**Test Command:**
```bash
# While agent is speaking, say "yeah wait" - should interrupt on "wait"
```

---

## Technical Implementation Details

### Monkey Patching Approach

We use monkey-patching to intercept methods without modifying the LiveKit framework:

```python
# Store original method
self._original_interrupt = self._activity._interrupt_by_audio_activity

# Replace with our wrapper
self._activity._interrupt_by_audio_activity = self._interrupt_wrapper
```

**Why this approach?**
- Non-invasive: Doesn't require modifying framework code
- Maintainable: Easy to update if framework changes
- Flexible: Can be enabled/disabled easily

### VAD/STT Timing Issue

**The Challenge:**
- VAD detects audio activity in ~10-50ms
- STT needs ~100-500ms to generate transcript
- This creates a race condition where VAD triggers before STT completes

**Our Solution:**

- Intercepts interim transcripts (partial results from STT)
- Filters fillers immediately as they arrive
- When VAD triggers, transcript is already filtered → no pause
- This prevents the race condition by filtering before interruption logic triggers

### State Management

The handler tracks agent state through event listeners:

```python
session.on("agent_state_changed", lambda ev: setattr(self, '_agent_state', ev.new_state))
```

This ensures we always know if the agent is:
- `"speaking"` - Currently generating/playing audio
- `"listening"` - Waiting for user input
- `"thinking"` - Processing response
- `"idle"` - Not active

### Interrupt Command Handling

When an interrupt command (like "stop" or "wait") is detected, the handler explicitly:

```python
if is_interrupt_command:
    # Force immediate stop
    activity._current_speech.interrupt(force=True)
    # Cancel preemptive generation
    activity._preemptive_generation.speech_handle._cancel()
    # Clear user turn to prevent response
    self._session.clear_user_turn()
    # Clear audio recognition state
    audio_recognition._audio_transcript = ""
    audio_recognition._audio_interim_transcript = ""
```

This ensures immediate stopping without waiting for normal interrupt flow.

### Word Processing

Words are normalized and processed for comparison:

```python
def _process_words(self, text: str) -> List[str]:
    # Remove punctuation, lowercase, split into words
    text = _PUNCTUATION_REGEX.sub(' ', text.lower().strip())
    return [w[0].lower().strip() for w in split_words(text, split_character=True) if w[0].strip()]
```

This handles:
- Case insensitivity ("Yeah" = "yeah")
- Punctuation ("yeah." = "yeah")
- Multiple words ("yeah ok" = ["yeah", "ok"])

---

## Code Structure

```
examples/voice_agents/
└── interrupt_handler_agent.py    # Our implementation

Key Files:
├── README.md                      # This documentation
└── requirements.txt               # Python dependencies
```

---


## Submission Information

- Branch: `feature/interrupt-handler-anurag`
- Repository: Fork of `https://github.com/Dark-Sys-Jenkins/agents-assignment`


