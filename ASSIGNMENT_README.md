# Smart Interruption System for LiveKit Agents

## Overview

This project implements a context-aware interruption filtering system for LiveKit voice agents. The agent distinguishes between passive backchannel feedback (e.g., "yeah", "okay", "hmm") and active interruption commands (e.g., "stop", "wait", "no") based on whether the agent is currently speaking or silent.

## How Our Logic Works

### The Core Logic

Our system uses two word lists to classify user speech:

**Ignore List** (backchannels): yeah, yup, yes, ok, okay, hmm, mm, mmm, mm-hmm, uh-huh, mhmm, hm, ah, ohh, right, aha, ya, yep

**Interrupt List** (commands): stop, wait, no, hold, pause, but

### Decision Algorithm

**Step 1: Check for Interrupt Words**
- If transcript contains ANY word from interrupt list -> Allow interruption
- Example: "stop" or "yeah but wait" -> Agent stops

**Step 2: Check for Pure Backchannel**
- If transcript has 3 or fewer words AND all words in ignore list -> Block interruption
- Example: "yeah", "okay yeah" -> Agent continues

**Step 3: Everything Else**
- Longer utterances or words not in ignore list -> Allow interruption
- Example: "yeah that makes sense now" (6 words) -> Agent stops

### Context-Awareness

**When Agent is Speaking:**
- Apply filtering logic above
- Backchannels are ignored, interrupts are allowed

**When Agent is Silent:**
- No filtering applied
- All input processed normally (allows "yeah" as valid response)

### Examples

**Example 1: Backchannel Ignored**
- Agent: "One, two, three, four..."
- User: "yeah" (while counting)
- Result: Agent continues "five, six, seven..."

**Example 2: Explicit Interrupt**
- Agent: "One, two, three, four..."
- User: "stop"
- Result: Agent stops immediately

**Example 3: Mixed Input**
- Agent: "History is the study of..."
- User: "yeah but wait"
- Result: Agent stops (contains "but")

**Example 4: Silent Agent**
- Agent: "Are you ready?" (then silent)
- User: "yeah"
- Result: Agent processes "yeah" as affirmative response

### State-Based Behavior

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "yeah", "ok", "hmm" | Speaking | Agent continues seamlessly |
| "stop", "wait", "no" | Speaking | Agent stops immediately |
| "yeah but wait" | Speaking | Agent stops (contains interrupt word) |
| "yeah", "ok" | Silent | Agent processes as normal input |
| Normal speech | Any state | Agent processes normally |

## Configuration

The word lists can be easily customized:

```python
from livekit.agents.voice.smart_interruption import SmartInterruptionFilter

# Custom word lists
custom_ignore = {"yeah", "ok", "sure", "gotcha"}
custom_interrupt = {"stop", "wait", "hold"}

filter = SmartInterruptionFilter(
    ignore_list=custom_ignore,
    interrupt_list=custom_interrupt,
    max_words=3  # Maximum words for backchannel classification
)
```

**Default word lists:**
- Ignore List: yeah, yup, yes, ok, okay, hmm, mm, mmm, mm-hmm, uh-huh, mhmm, hm, ah, ohh, right, aha, ya, yep
- Interrupt List: stop, wait, no, hold, pause, but
- Max Words: 3

## Installation & Setup

### Prerequisites

- Python 3.13
- LiveKit account and API credentials
- Google API key (for LLM)
- Deepgram API key (for STT/TTS)

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/AAK121/agents-assignment.git
cd agents-assignment
```

2. Configure environment variables:
Create a `.env` file in the root directory:
```
LIVEKIT_URL=wss://your-instance.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
GOOGLE_API_KEY=your-google-api-key
DEEPGRAM_API_KEY=your-deepgram-api-key
```

## Running the Agent

Run the agent in development mode:

```bash
python examples\voice_agents\smart_interruption_simple.py dev
```

The agent will start and you have to open LiveKit Playground (https://agents-playground.livekit.io/) in your browser where you can connect and test.

## Testing Scenarios

### Test Case 1: Long Explanation with Backchannels
1. Say: "Tell me a long story about history"
2. While agent is speaking, say: "okay... yeah... uh-huh"
3. Expected: Agent continues without interruption

### Test Case 2: Passive Affirmation When Silent
1. Say: "Are you ready?"
2. Wait for agent to finish speaking
3. Say: "Yeah"
4. Expected: Agent processes "Yeah" as valid input and responds

### Test Case 3: Explicit Interruption
1. Say: "Count from one to thirty"
2. While agent is counting, say: "Stop"
3. Expected: Agent stops immediately

### Test Case 4: Mixed Input
1. Say: "Tell me about machine learning"
2. While agent is speaking, say: "Yeah okay but wait"
3. Expected: Agent stops (contains "wait" which is in interrupt list)

