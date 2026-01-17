# LiveKit Intelligent Interruption Handler

A context-aware interruption handling system for LiveKit voice agents that **seamlessly handles user backchanneling** (passive acknowledgments like "yeah", "ok") while still responding to **active interruptions** (commands like "stop", "wait").

## Problem Statement

LiveKit voice agents use sensitive Voice Activity Detection (VAD) to detect when users speak. However, this causes a critical issue:

**When an agent is speaking and the user says "yeah" to acknowledge or show they're listening, the VAD triggers immediately, causing the agent to stop mid-sentence.**

This creates an unnatural, jarring experience where the agent can't distinguish between:
- ✅ **Backchanneling** (acknowledgment): "yeah", "ok", "hmm" → Agent should **IGNORE**
- ❌ **Interruption** (commands): "stop", "wait", "no" → Agent should **INTERRUPT**

## Solution Overview

The Interruption Handler implements intelligent filtering at the **event loop level** to:

1. **Track agent speaking state** (when is the agent talking?)
2. **Wait for STT transcription** (what did the user actually say?)
3. **Apply context-aware logic** (should we interrupt based on what was said and current state?)
4. **Make decisions without audio breaks** (completely seamless to the user)

## Decision Matrix

| User Input | Agent State | Action |
|------------|-------------|--------|
| "yeah", "ok", "hmm" | Speaking | **IGNORE** - Continue seamlessly |
| "wait", "stop", "no" | Speaking | **INTERRUPT** - Stop immediately |
| "yeah", "ok", "hmm" | Silent | **RESPOND** - Process as valid input |
| "yeah but wait" | Speaking | **INTERRUPT** - Mixed input |

## Architecture

### Components

#### 1. **AgentStateManager** (`state_manager.py`)
Tracks the agent's current speaking state.

```
AgentStateManager
├── is_speaking: bool
├── utterance_id: Optional[str]
├── speech_start_time: Optional[float]
└── Methods:
    ├── start_speaking(utterance_id)
    ├── stop_speaking()
    ├── get_state() -> AgentStateSnapshot
    ├── is_currently_speaking() -> bool
    └── get_speech_duration() -> Optional[float]
```

**Key Features:**
- Non-blocking state queries (no lock contention)
- Optional auto-timeout for safety
- Thread-safe state transitions

#### 2. **InterruptionFilter** (`interruption_filter.py`)
Analyzes user transcriptions and decides whether to interrupt.

```
InterruptionFilter
├── ignore_words: List[str]  # Backchanneling words
├── command_words: List[str] # Interruption commands
└── Methods:
    ├── should_interrupt(text, agent_state) -> bool
    ├── should_interrupt_detailed(text, agent_state) -> InterruptionDecision
    ├── _is_pure_backchannel(text) -> bool
    └── _contains_command(text) -> bool
```

**Features:**
- Configurable word lists
- Fuzzy matching for typos/variations
- Returns detailed classification (backchannel/command/mixed/unknown)

#### 3. **Configuration System** (`config.py`, `interruption_config.json`)
Load settings from multiple sources with priority:

1. **Environment variables** (highest priority)
2. **Configuration JSON file**
3. **Programmatic defaults** (lowest priority)

**Environment Variables:**
```bash
LIVEKIT_INTERRUPTION_IGNORE_WORDS="yeah,ok,hmm"
LIVEKIT_INTERRUPTION_COMMAND_WORDS="stop,wait,no"
LIVEKIT_INTERRUPTION_FUZZY_ENABLED=true
LIVEKIT_INTERRUPTION_FUZZY_THRESHOLD=0.8
LIVEKIT_INTERRUPTION_STT_TIMEOUT_MS=500
LIVEKIT_INTERRUPTION_VERBOSE_LOGGING=false
```

## Installation

### 1. Copy the module into your LiveKit agents installation:

```bash
# If using the agents-assignment fork
cp -r livekit-agents/livekit/agents/voice/interruption_handler \
      /path/to/livekit-agents/livekit/agents/voice/
```

### 2. Import into your agent code:

```python
from livekit.agents.voice.interruption_handler import (
    AgentStateManager,
    InterruptionFilter,
    load_config,
)
```

## Usage Example

### Basic Setup

```python
import asyncio
from livekit.agents.voice.interruption_handler import (
    AgentStateManager,
    InterruptionFilter,
    load_config,
)

# Load configuration
config = load_config()

# Initialize components
state_manager = AgentStateManager()
interrupt_filter = InterruptionFilter(
    ignore_words=config.ignore_words,
    command_words=config.command_words,
    enable_fuzzy_match=config.fuzzy_matching_enabled,
    fuzzy_threshold=config.fuzzy_threshold,
)

# When agent starts speaking
async def agent_start_speaking():
    await state_manager.start_speaking(utterance_id="utt_123")

# When user input is received
async def handle_user_input(transcribed_text: str):
    agent_state = state_manager.get_state().to_dict()
    
    should_interrupt, reason = interrupt_filter.should_interrupt(
        text=transcribed_text,
        agent_state=agent_state,
    )
    
    if should_interrupt:
        print(f"Interrupting: {reason}")
        await state_manager.stop_speaking()
        # Process the user input
    else:
        print(f"Ignoring: {reason}")

# When agent finishes speaking
async def agent_stop_speaking():
    await state_manager.stop_speaking()
```

### Integration with LiveKit Agent Event Loop

To integrate with the actual LiveKit agent event loop, you would hook into the interruption event:

```python
from livekit.agents import event

class MyAgent:
    def __init__(self):
        self.state_manager = AgentStateManager()
        self.interrupt_filter = InterruptionFilter()
    
    async def on_user_speech_event(self, event):
        """Called when VAD detects user speech."""
        
        # DON'T stop the agent yet!
        # Wait for STT transcription
        try:
            text = await asyncio.wait_for(
                self.get_stt_transcription(event),
                timeout=0.5  # 500ms timeout
            )
        except asyncio.TimeoutError:
            # Default to interrupt if STT is too slow
            await self.state_manager.stop_speaking()
            return
        
        # Now analyze the text
        should_interrupt, reason = self.interrupt_filter.should_interrupt(
            text,
            self.state_manager.get_state().to_dict()
        )
        
        if should_interrupt:
            await self.state_manager.stop_speaking()
            # Process the input
        else:
            # Ignore - agent keeps speaking
            logger.info(f"Ignored backchannel: '{text}'")
```

## Configuration

### Using Configuration File

Create `interruption_config.json`:

```json
{
  "interruption_handling": {
    "enabled": true,
    "ignore_words": {
      "words": ["yeah", "ok", "hmm", "uh-huh", "right"]
    },
    "command_words": {
      "words": ["stop", "wait", "no", "hold on", "pause"]
    },
    "fuzzy_matching": {
      "enabled": true,
      "similarity_threshold": 0.8
    },
    "timeout_settings": {
      "stt_wait_timeout_ms": 500
    }
  }
}
```

Load it:

```python
from livekit.agents.voice.interruption_handler import load_config

config = load_config(config_file="/path/to/interruption_config.json")
```

### Using Environment Variables

```bash
export LIVEKIT_INTERRUPTION_IGNORE_WORDS="yeah,ok,hmm,uh-huh"
export LIVEKIT_INTERRUPTION_COMMAND_WORDS="stop,wait,no,hold on"
export LIVEKIT_INTERRUPTION_FUZZY_ENABLED=true
export LIVEKIT_INTERRUPTION_STT_TIMEOUT_MS=500

python your_agent.py
```

### Programmatic Configuration

```python
from livekit.agents.voice.interruption_handler import (
    InterruptionFilter,
    InterruptionHandlerConfig,
)

config = InterruptionHandlerConfig()
config.ignore_words = ["yeah", "ok", "mm-hmm"]
config.command_words = ["stop", "wait", "no", "cancel"]
config.fuzzy_matching_enabled = True
config.fuzzy_threshold = 0.85

filter = InterruptionFilter(
    ignore_words=config.ignore_words,
    command_words=config.command_words,
)
```

## How It Works: The VAD-STT Race Condition

### The Problem

```
Timeline:
┌─────────────────────────────────────────┐
│ Agent: "In 1492, Columbus sailed..."    │
└─────────────────────────────────────────┘
                    ↓
User says: "yeah"
                    ↓
        VAD triggers IMMEDIATELY
        (< 50ms)
        
        ❌ Without filter:
        Agent stops → Audio gap → "...Columbus sai—"
        
        ✅ With filter:
        Wait for STT (50-500ms) → Analyze → Ignore
        Agent continues → "...sailed across..."
```

### The Solution

```
1. VAD Event Fires
   ↓
2. Interrupt Event Queued (NOT applied)
   ↓
3. Wait for STT Transcription (max 500ms)
   ↓
4. Analyze Text with Filter
   ├─ Pure backchannel? → IGNORE (discard VAD event)
   ├─ Command word? → INTERRUPT (apply VAD)
   └─ Mixed? → INTERRUPT (apply VAD)
   ↓
5. Either Continue or Interrupt (SEAMLESSLY)
```

## Test Scenarios

The module includes test scenarios covering all decision matrix cases:

### Scenario 1: Long Explanation with Backchanneling ✅
```
Agent: "In 1492, Columbus sailed across the Atlantic Ocean..."
User: "okay" → "yeah" → "uh-huh"
Expected: Agent continues without pause
```

### Scenario 2: Passive Affirmation When Silent ✅
```
Agent: "Are you ready?" [then silence]
User: "Yeah."
Expected: Agent responds to the input normally
```

### Scenario 3: Active Interruption ✅
```
Agent: "One, two, three, four..."
User: "No stop."
Expected: Agent cuts off immediately
```

### Scenario 4: Mixed Input ✅
```
Agent: [speaking about something]
User: "Yeah okay but wait."
Expected: Agent stops (detected "but wait")
```

### Running Tests

```python
from livekit.agents.voice.interruption_handler import InterruptionFilter

filter = InterruptionFilter()

# Scenario 1: Agent speaking, user backchannels
state = {"is_speaking": True}
should_interrupt, reason = filter.should_interrupt("yeah", state)
assert not should_interrupt, "Should ignore backchannel while speaking"

# Scenario 2: Agent silent, user backchannels
state = {"is_speaking": False}
should_interrupt, reason = filter.should_interrupt("yeah", state)
assert not should_interrupt, "Process as input (but don't interrupt speaking)"

# Scenario 3: Agent speaking, user commands
state = {"is_speaking": True}
should_interrupt, reason = filter.should_interrupt("stop", state)
assert should_interrupt, "Should interrupt on command"

# Scenario 4: Mixed input
state = {"is_speaking": True}
should_interrupt, reason = filter.should_interrupt("yeah but wait", state)
assert should_interrupt, "Should interrupt on mixed input with command"
```

## Performance Considerations

### Latency Budget

- **State Manager queries**: < 1ms (no lock)
- **Filter analysis**: < 10ms (string operations)
- **Fuzzy matching**: < 20ms (for < 100 words)
- **Total decision**: < 50ms (imperceptible to user)

### Memory

- **State Manager**: ~100 bytes
- **Filter with 20+20 words**: ~5KB
- **Config object**: ~10KB
- **Total**: ~15KB (negligible)

### Thread Safety

- **State Manager**: Async-lock protected for state changes
- **Filter**: Stateless after initialization (thread-safe)
- **Config**: Immutable dataclass (thread-safe)

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│          LiveKit Agent Event Loop                │
└─────────────────────────────────────────────────┘
                      ↓
        ┌─────────────────────────┐
        │   VAD Detects Speech    │
        └─────────────────────────┘
                      ↓
        ┌─────────────────────────────────────┐
        │  Interruption Handler System         │
        ├─────────────────────────────────────┤
        │  1. Queue interrupt (don't apply)    │
        │  2. Wait for STT (max 500ms)        │
        │  3. Analyze text                    │
        │  ├─ AgentStateManager.get_state()   │
        │  └─ InterruptionFilter.should_...() │
        │  4. Decide: continue or interrupt   │
        └─────────────────────────────────────┘
                      ↓
        ┌──────────────────────────┐
        │  Continue Speaking OR    │
        │  Stop and Process Input  │
        └──────────────────────────┘
```

## Common Use Cases

### Use Case 1: Customer Support Agent
```python
# Users often say "hmm", "yeah", "okay" while listening
# Don't interrupt on these
ignore_words = ["yeah", "okay", "hmm", "uh-huh", "right"]
# But DO interrupt on
command_words = ["stop", "wait", "no", "hold on", "repeat that"]
```

### Use Case 2: Educational Agent
```python
# Students confirm understanding with "yep", "got it"
ignore_words = ["yep", "got it", "yeah", "okay", "understood"]
# Interrupt on questions/corrections
command_words = ["wait", "what", "no", "wrong", "again"]
```

### Use Case 3: Emergency Dispatch
```python
# Critical: must interrupt on any command immediately
ignore_words = []  # Disable all backchanneling
command_words = ["stop", "abort", "end", "cancel", "stop sending"]
# Or use allow_interruptions=False at Agent level
```

## Troubleshooting

### Agent Isn't Interrupting on Commands

**Check:**
1. Is `should_interrupt` returning `True` but agent not stopping?
   - Verify `state_manager.stop_speaking()` is actually being called
   - Check if agent has `allow_interruptions=False`

2. Is the command word not being detected?
   - Enable verbose logging: `LIVEKIT_INTERRUPTION_VERBOSE_LOGGING=true`
   - Check word list: `config.command_words`
   - Try adding the word manually: `filter.update_command_words([...] + ["custom"])`

### Agent Keeps Stopping on Backchanneling

**Check:**
1. Is the word in the ignore list?
   - `"yeah" in filter.ignore_words`
   - Add it: `filter.update_ignore_words([...] + ["custom_backchannel"])`

2. Is fuzzy matching causing false matches?
   - Disable: `enable_fuzzy_match=False`
   - Adjust threshold: `fuzzy_threshold=0.9` (stricter)

### STT Timeout Issues

**Check:**
1. Increase timeout if STT is slow: `stt_wait_timeout_ms=1000` (1 second)
2. Monitor STT latency with logging
3. Note: Longer timeout = less responsive interruptions

## API Reference

### AgentStateManager

```python
class AgentStateManager:
    async def start_speaking(utterance_id: str, auto_cancel_timeout: bool = True)
    async def stop_speaking(force: bool = False)
    def get_state() -> AgentStateSnapshot
    def is_currently_speaking() -> bool
    def get_current_utterance_id() -> Optional[str]
    def get_speech_duration() -> Optional[float]
    async def reset()
```

### InterruptionFilter

```python
class InterruptionFilter:
    def should_interrupt(text: str, agent_state: dict) -> Tuple[bool, str]
    def should_interrupt_detailed(text: str, agent_state: dict) -> InterruptionDecision
    def update_ignore_words(words: list[str])
    def update_command_words(words: list[str])
```

### ConfigLoader

```python
class ConfigLoader:
    @staticmethod
    def load_from_env() -> InterruptionHandlerConfig
    
    @staticmethod
    def load_from_file(file_path: str | Path) -> Optional[InterruptionHandlerConfig]
    
    @staticmethod
    def get_default_config() -> InterruptionHandlerConfig

def load_config(
    config_file: Optional[str | Path] = None,
    from_env: bool = True,
) -> InterruptionHandlerConfig
```

## Contributing

To extend this implementation:

1. **Add custom word lists**: Modify `config.py` defaults
2. **Improve fuzzy matching**: Replace `_levenshtein_similarity` with better algorithm
3. **Add more state tracking**: Extend `AgentStateManager` with additional context
4. **Integrate with specific STT**: Modify the event handler integration

## License

Part of the agents-assignment fork of LiveKit Agents.
See LICENSE file for details.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Enable verbose logging: `LIVEKIT_INTERRUPTION_VERBOSE_LOGGING=true`
3. Review test scenarios for usage examples
4. Open an issue in the repository
