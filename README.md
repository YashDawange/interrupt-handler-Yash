# Intelligent Interruption Handling - Backchannel Filtering

A context-aware filtering system that allows LiveKit voice agents to distinguish between passive acknowledgments ("yeah", "ok", "hmm") and real interruptions ("wait", "stop").

Demonstration link :- https://drive.google.com/file/d/1Joa3KxEHx3ckuo4N_bIpyGynP3ju6_bh/view?usp=drive_link

---

## Problem Solved

When users say backchannel words like "yeah" or "ok" while the AI agent is speaking, LiveKit's default VAD interprets these as interruptions and stops the agent. This creates a poor conversational experience.

**This solution ensures the agent continues speaking seamlessly through backchannel words while still responding to real interruption commands.**

---

## Quick Start

### 1. Set Environment Variables

```powershell
# PowerShell
$env:OPENAI_API_KEY="your-openai-key"
$env:DEEPGRAM_API_KEY="your-deepgram-key"
$env:LIVEKIT_URL="wss://your-project.livekit.cloud"
$env:LIVEKIT_API_KEY="your-livekit-key"
$env:LIVEKIT_API_SECRET="your-livekit-secret"
```

### 2. Run the Agent

```bash
Activate virtual environment in both(.venv\Scripts\activate)

.\run_agent.ps1 

in 2nd terminal

python connect_to_agent.py
```

### 3. Connect & Test

1. Go to [agents-playground.livekit.io](https://agents-playground.livekit.io)
2. Connect to your LiveKit server
3. Test the filtering:
   - Say: *"Tell me a long story about space"*
   - While agent speaks, say: **"yeah"** or **"hmm"** → Agent continues
   - While agent speaks, say: **"stop"** or **"wait"** → Agent stops

---

## How It Works

### Logic Matrix

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah/Ok/Hmm" | Speaking | **IGNORE** - Agent continues |
| "Wait/Stop/No" | Speaking | **INTERRUPT** - Agent stops |
| "Yeah/Ok/Hmm" | Silent | **RESPOND** - Treated as input |
| Any text | Silent | **RESPOND** - Normal conversation |

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   VAD (Silero)  │────▶│  STT (Deepgram)  │────▶│ BackchannelFilter│
│  Detects speech │     │  Transcribes     │     │  Filters input   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                              ┌───────────▼───────────┐
                                              │   Decision Logic      │
                                              │                       │
                                              │  is_backchannel_only? │
                                              │  + agent_is_speaking? │
                                              └───────────┬───────────┘
                                                          │
                                    ┌─────────────────────┼─────────────────────┐
                                    │                     │                     │
                              ┌─────▼─────┐        ┌──────▼──────┐       ┌──────▼──────┐
                              │  IGNORE   │        │  INTERRUPT  │       │   RESPOND   │
                              │ (continue)│        │   (stop)    │       │  (process)  │
                              └───────────┘        └─────────────┘       └─────────────┘
```

### Key Components

1. **BackchannelFilter** (`livekit-agents/livekit/agents/voice/backchannel_filter.py`)
   - Core filtering logic with `should_ignore_input(text, agent_is_speaking)`
   - Configurable word lists
   - State-aware decision making

2. **Agent Activity Integration** (`agent_activity.py`)
   - Hooks into `on_final_transcript` - filters before processing interruptions
   - Hooks into `on_end_of_turn` - prevents new reply generation for backchannel

---

## Configuration

### Backchannel Words (Ignored While Speaking)

```python
backchannel_ignore_words={
    # Affirmations
    'yeah', 'yep', 'yes', 'yup', 'ya', 'aye',
    # Acknowledgments  
    'ok', 'okay', 'k',
    # Filler sounds
    'hmm', 'hm', 'mhmm', 'mm', 'mmm', 'uh-huh', 'uhuh', 'huh',
    # Agreement
    'right', 'alright', 'gotcha',
    # Casual acknowledgments
    'sure', 'cool', 'nice', 'great', 'good', 'fine',
    'true', 'correct', 'exactly', 'absolutely',
    # Filler sounds
    'ah', 'oh', 'uh', 'um', 'er',
    # Reactions
    'wow', 'really', 'seriously', 'interesting',
}
```

### Interrupt Words (Always Stop Agent)

```python
INTERRUPT_WORDS = {
    'wait', 'stop', 'hold', 'pause',
    'no', 'nope', 'nah',
    'excuse me', 'sorry', 'pardon',
}
```

### Adding Custom Words

**Option 1: In AgentSession**
```python
session = AgentSession(
    backchannel_ignore_words={'yeah', 'ok', 'custom_word'},
    ...
)
```

**Option 2: Environment Variable**
```powershell
$env:BACKCHANNEL_IGNORE_WORDS="aha,yay,sweet"
```

---

## Key Files

| File | Purpose |
|------|---------|
| `test_interruption_agent.py` | Main agent with backchannel filtering |
| `livekit-agents/livekit/agents/voice/backchannel_filter.py` | Core filter logic |
| `livekit-agents/livekit/agents/voice/agent_activity.py` | Integration hooks |
| `tests/test_backchannel_filter.py` | Unit tests (20 tests) |

---

## Testing

### Unit Tests
```bash
python -m pytest tests/test_backchannel_filter.py -v
```

### Manual Testing Checklist

- [ ] Say "yeah" while agent speaks → No interruption
- [ ] Say "ok" while agent speaks → No interruption  
- [ ] Say "hmm" while agent speaks → No interruption
- [ ] Say "stop" while agent speaks → Agent stops
- [ ] Say "wait" while agent speaks → Agent stops
- [ ] Say "yeah" when agent is silent → Agent responds

---


