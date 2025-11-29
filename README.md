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

> **Note:** For detailed information about intercepted methods, component architecture, and data flows, see the [Architecture](#architecture) section below.

### Decision Logic Flow

When user audio is detected:

1. **Check Agent State**
   - If **silent**: Allow all inputs (normal conversation)
   - If **speaking**: Proceed to transcript analysis

2. **Transcript Analysis** (when agent is speaking)
   - **Empty/No STT**: Wait for transcription (prevents false interruption)
   - **Interrupt command** ("stop", "wait"): Force immediate stop
   - **Only fillers** ("yeah", "ok"): Filter out, continue speaking
   - **Meaningful content**: Allow normal interruption

> **See also:** Detailed data flow diagrams in the [Architecture](#architecture) section.

### Implementation Approach

Our implementation (`interrupt_handler_agent.py`) provides:
- Seamless experience with no pauses
- Filters at interim transcript stage (prevents pauses)
- Performance optimizations (caching)
- Explicit interrupt command handling (immediate stop on "stop", "wait", etc.)

---

## Architecture

### System Overview

The intelligent interruption handling system is built as a **non-invasive middleware layer** that sits between LiveKit's voice activity detection (VAD) and the agent's response generation pipeline. It uses monkey-patching to intercept critical methods without modifying the LiveKit framework.

### Component Architecture

```
                    ┌─────────────────────┐
                    │   User Audio Input   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   VAD (Silero)       │
                    │   Audio Detection    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   STT (Deepgram)     │
                    │   Interim + Final    │
                    └──────────┬───────────┘
                               │
                               ▼
         ┌──────────────────────────────────────┐
         │  IntelligentInterruptHandler          │
         │  • State Tracking                     │
         │  • Transcript Analysis                │
         │  • Decision Logic                     │
         └──────────┬────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                      │
         ▼                      ▼
    [Filtered]            [Allowed]
         │                      │
         │                      ▼
         │            ┌─────────────────────┐
         │            │   LLM (Gemini)      │
         │            │   Response Gen      │
         │            └──────────┬──────────┘
         │                       │
         │                       ▼
         │            ┌─────────────────────┐
         │            │   TTS (Cartesia)    │
         │            │   Audio Output      │
         │            └─────────────────────┘
         │
         └──────→ [Continue Speaking]
```

### Core Components

#### 1. IntelligentInterruptHandler
**Location:** `examples/voice_agents/interrupt_handler_agent.py`

The main handler class that orchestrates the interruption filtering logic:

- **State Management**: Tracks agent state (`speaking`, `listening`, `thinking`, `idle`) via event listeners
- **Word Classification**: Maintains sets of ignore words and interrupt commands
- **Transcript Processing**: Normalizes and processes transcripts for analysis
- **Decision Engine**: Implements the core logic for allowing/preventing interruptions

#### 2. Intercepted Methods (Monkey-Patched)

The handler intercepts five critical methods in `AgentActivity`:

| Method | Purpose | Interception Point |
|--------|---------|-------------------|
| `_interrupt_by_audio_activity()` | Main interrupt trigger | Before interruption logic executes |
| `on_interim_transcript()` | Partial STT results | **Critical**: Filters before accumulation |
| `on_final_transcript()` | Complete STT results | Filters before processing |
| `on_end_of_turn()` | Turn completion | Prevents turn completion for fillers |
| `_user_turn_completed_task()` | Chat context update | Prevents adding interrupt-only commands |

#### 3. State Tracking System

The handler monitors agent state transitions via `agent_state_changed` events:

```
    idle ──→ thinking ──→ speaking ──→ idle
      │         │            │
      └─────────┴────────────┘
                 │
            listening
```

**State Transitions:**
- `idle` → `thinking`: Agent starts processing
- `thinking` → `speaking`: Agent begins response
- `speaking` → `idle`: Agent finishes speaking
- Any state → `listening`: User input detected

### Data Flow

#### Decision Flow

```
User Audio
    │
    ▼
VAD Detection ──→ STT Processing ──→ Transcript Analysis
                                            │
                                            ▼
                                    Agent Speaking?
                                    │              │
                                   YES             NO
                                    │              │
                                    ▼              ▼
                            Check Transcript   Allow (Normal)
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            Empty/No STT    Interrupt Cmd    Only Fillers
                    │               │               │
                    ▼               ▼               ▼
            Wait for STT    Force Stop      Filter & Continue
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                                    ▼
                            Meaningful Content?
                                    │
                                    ▼
                            Allow Interrupt
```

**Key Decision Points:**
1. **Empty Transcript**: Wait for STT completion (prevents false interruptions)
2. **Interrupt Commands** ("stop", "wait"): Immediate force stop
3. **Only Fillers** ("yeah", "ok"): Filter out, continue speaking
4. **Meaningful Content**: Allow normal interruption

### Integration Points

#### 1. LiveKit AgentActivity
- **Access Method**: Monkey-patching after session initialization
- **Key Properties Accessed**:
  - `_current_speech`: Current speech handle for interruption
  - `_audio_recognition`: Audio recognition state for transcript access
  - `_preemptive_generation`: Preemptive response generation

#### 2. AgentSession Events
- **`agent_state_changed`**: Tracks agent state transitions
- **`user_input_transcribed`**: Monitors transcript updates

#### 3. External Services
- **Deepgram STT**: Provides speech-to-text transcription
- **Cartesia TTS**: Generates speech output
- **Google Gemini**: LLM for response generation
- **Silero VAD**: Voice activity detection

### Design Patterns

#### 1. Monkey-Patching Pattern
- **Purpose**: Non-invasive interception without framework modification
- **Implementation**: Store original methods, replace with wrappers
- **Benefits**: Maintainable, flexible, easy to enable/disable

#### 2. Wrapper Pattern
- **Purpose**: Add filtering logic around existing methods
- **Implementation**: Wrapper methods call original methods conditionally
- **Benefits**: Preserves original functionality while adding intelligence

#### 3. State Observer Pattern
- **Purpose**: Track agent state changes reactively
- **Implementation**: Event listeners on session events
- **Benefits**: Real-time state awareness without polling

#### 4. Early Filtering Pattern
- **Purpose**: Prevent race conditions between VAD and STT
- **Implementation**: Filter at interim transcript stage
- **Benefits**: Eliminates pauses, seamless user experience

### Performance Optimizations

1. **Word Caching**: Caches processed word lists to reduce repeated processing
2. **Regex Pre-compilation**: Pre-compiles punctuation regex for faster processing
3. **Early Returns**: Short-circuits decision logic when possible
4. **Set-based Lookups**: Uses sets for O(1) word classification lookups

### Error Handling

- **Graceful Degradation**: If AgentActivity not found, logs error but doesn't crash
- **Timeout Protection**: Waits up to 2 seconds for AgentActivity initialization
- **Null Checks**: Validates all accessed properties before use
- **Fallback Behavior**: Calls original methods if handler fails

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

**For console mode:**
```bash
cd examples/voice_agents
python interrupt_handler_agent.py console
```

**For agent playground:**
```bash
cd examples/voice_agents
python interrupt_handler_agent.py dev
```

**Note:** Make sure you're in the `examples/voice_agents` directory before running the agent.

---

## Configuration

### Customizing Ignore Words

You can customize which words are ignored when the agent is speaking. The default list includes:

```python
default_ignore_words = [
    "yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay", "uh", "um", "mm-hmm", "yes",
    "sure", "alright", "mhm", "yup", "correct", "gotcha", "roger", "indeed", "exactly", "absolutely",
    "understood", "see", "true", "agreed", "fine", "good", "nice", "great", "wow", "oh"
]
```

**Custom example:**
```python
handler = IntelligentInterruptHandler(
    ignore_words=["yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay", "uh", "um", "mm-hmm"],
    interrupt_commands=["stop", "wait", "no", "halt", "pause", "cancel"],
)
```

### Customizing Interrupt Commands

Words that always trigger interruption. Default list:

```python
default_interrupt_commands = ["stop", "wait", "no", "halt", "pause", "cancel"]
```

**Custom example:**
```python
handler = IntelligentInterruptHandler(
    interrupt_commands=["stop", "wait", "no", "halt", "pause", "cancel", "abort"]
)
```

**Note:** All words are case-insensitive and automatically normalized (punctuation removed, lowercased).

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

> **Note:** For information about monkey-patching approach, state management, and design patterns, see the [Architecture](#architecture) section above.

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


## Proof of Functionality

### Video Demonstration

A video recording demonstrating all 4 test scenarios:

- **Video Link:** [Watch Demonstration](https://drive.google.com/file/d/1pIWBnfkIsOOSoi8J12vT-mykFDxo9tw0/view?usp=sharing)

The video demonstrates:
1. Agent ignoring "yeah/ok" while speaking (no pause, no interruption)
2. Agent responding to "yeah" when silent (normal conversation)
3. Agent stopping immediately on "stop" command
4. Agent handling mixed input "yeah wait" (interrupts on "wait")

---

## Submission Information

- Branch: `feature/interrupt-handler-anurag`
- Repository: Fork of `https://github.com/Dark-Sys-Jenkins/agents-assignment`


