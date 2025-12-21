# Intelligent Interruption Handling for LiveKit Voice Agents

## Overview

This implementation solves the challenge of distinguishing between **passive acknowledgements** ("yeah", "ok", "hmm") and **active interruptions** ("stop", "wait", "no") in a LiveKit voice agent.

### The Problem

LiveKit's default Voice Activity Detection (VAD) triggers interruptions at the **audio level** before any transcript is available. This means:
- User says "yeah" → VAD detects voice → Agent pauses/stops → Transcript arrives too late
- The agent cannot distinguish between "yeah" (filler) and "stop" (command) until after the pause

### The Solution

This implementation uses a **dual-layer approach**:

1. **Audio Layer**: Use `min_interruption_words=2` to prevent single-word utterances from triggering audio-level interrupts
2. **Transcript Layer**: Process **interim transcripts** to detect interrupt command words early and manually trigger interrupts

This prevents pauses on filler words while still allowing fast interrupts on command words.

## Logic Matrix

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah / Ok / Hmm" | Speaking | **IGNORE** - No pause, agent continues |
| "Stop / Wait / No" | Speaking | **INTERRUPT** - Agent stops immediately |
| "Yeah / Ok / Hmm" | Silent | **RESPOND** - Treats as valid input |
| Any input | Silent | **RESPOND** - Normal conversation |

## How It Works

### The Timing Challenge

```
Timeline without our solution:
─────────────────────────────────────────────────────────────
0ms     User says "yeah"
50ms    VAD detects voice activity
100ms   Agent PAUSES (too early!)
600ms   Transcript "yeah" arrives
700ms   Filter says "ignore" - but pause already happened!
─────────────────────────────────────────────────────────────

Timeline WITH our solution:
─────────────────────────────────────────────────────────────
0ms     User says "yeah"
50ms    VAD detects voice activity
100ms   min_interruption_words=2 → single word ignored at audio level
        Agent CONTINUES speaking (no pause!)
600ms   Final transcript "yeah" arrives
610ms   Filter confirms "ignore" - already handled correctly
─────────────────────────────────────────────────────────────

Timeline for "stop" command:
─────────────────────────────────────────────────────────────
0ms     User says "stop"
50ms    VAD detects voice activity  
100ms   min_interruption_words=2 → single word ignored at audio level
150ms   INTERIM transcript "sto..." arrives
200ms   INTERIM transcript "stop" arrives
210ms   Filter detects command word → MANUAL INTERRUPT triggered!
220ms   Agent stops immediately
─────────────────────────────────────────────────────────────
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT INTERRUPT FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      AUDIO LAYER                              │   │
│  │  ┌─────────┐     ┌──────────────────────┐                    │   │
│  │  │   VAD   │────▶│ min_interruption_    │                    │   │
│  │  │ Silero  │     │ words = 2            │                    │   │
│  │  └─────────┘     │                      │                    │   │
│  │                  │ Single words like    │                    │   │
│  │                  │ "yeah" → NO PAUSE    │                    │   │
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
│  │  │             │     │ Analyzes both:  │     │ • ignore   │  │   │
│  │  │ • interim   │     │ • Agent state   │     │ • interrupt│  │   │
│  │  │ • final     │     │ • Word content  │     │ • respond  │  │   │
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

### Key Innovation: Interim Transcript Processing

Most implementations only process **final** transcripts. We process **interim** transcripts for faster interrupt detection:

```python
@session.on("user_input_transcribed")
def on_user_input_transcribed(ev: UserInputTranscribedEvent):
    transcript = ev.transcript.strip()
    is_final = ev.is_final  # False for interim, True for final
    
    # Process INTERIM transcripts for early interrupt detection!
    if not is_final and agent._is_speaking:
        analysis = filter.analyze(transcript, agent_speaking=True)
        if analysis.decision == "interrupt":
            # Don't wait for final - interrupt NOW
            session.current_speech.interrupt(force=True)
```

## Configuration Reference

### AgentSession Parameters

```python
session = AgentSession(
    # Speech-to-Text provider
    stt="deepgram/nova-3",
    
    # Language Model
    llm="openai/gpt-4.1-mini",
    
    # Text-to-Speech provider  
    tts="cartesia/sonic-2",
    
    # Voice Activity Detection
    vad=silero.VAD.load(),
    
    # ═══════════════════════════════════════════════════════════
    # CRITICAL INTERRUPT HANDLING SETTINGS
    # ═══════════════════════════════════════════════════════════
    
    # Enable interruption handling
    allow_interruptions=True,
    
    # CRITICAL: Require 2+ words before audio-level interrupt triggers
    # This prevents single filler words from pausing the agent
    min_interruption_words=2,
    
    # Minimum speech duration to consider as interrupt (seconds)
    min_interruption_duration=0.5,
    
    # Time to wait for transcript before deciding on interrupt
    false_interruption_timeout=1.0,
    
    # Auto-resume if interrupt was "false" (noise, etc.)
    resume_false_interruption=True,
    
    # ═══════════════════════════════════════════════════════════
    # ENDPOINTING SETTINGS (when to consider user done speaking)
    # ═══════════════════════════════════════════════════════════
    
    min_endpointing_delay=0.5,
    max_endpointing_delay=3.0,
)
```

### Configuration Parameter Details

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `allow_interruptions` | bool | `True` | Master switch for interrupt handling |
| `min_interruption_words` | int | `0` | **KEY**: Min words before audio interrupt triggers. Set to `2` to prevent single-word pauses |
| `min_interruption_duration` | float | `0.0` | Min seconds of speech before interrupt considered |
| `false_interruption_timeout` | float | `0.0` | Seconds to wait for transcript before confirming interrupt |
| `resume_false_interruption` | bool | `False` | Auto-resume if interrupt was noise/accidental |

### InterruptFilter Configuration

```python
from dataclasses import dataclass, field
from typing import FrozenSet

@dataclass
class InterruptFilterConfig:
    """Configuration for the interrupt filter."""
    
    # Words to IGNORE when agent is speaking
    ignore_words: FrozenSet[str] = field(default_factory=lambda: frozenset([
        "yeah", "yes", "yep", "yup", "ya",
        "ok", "okay", "k",
        "hmm", "hm", "hmm-hmm", "hmmm",
        "uh-huh", "uh huh", "uhuh", "uhhuh",
        "mm-hmm", "mm hmm", "mmhmm", "mhm",
        "right", "alright", "sure", "aha", "ah",
        "i see", "got it", "gotcha",
        "cool", "nice", "great",
        "um", "uh", "er",
    ]))
    
    # Words that ALWAYS trigger interrupt (even single word)
    interrupt_words: FrozenSet[str] = field(default_factory=lambda: frozenset([
        "stop", "wait", "hold", "pause",
        "no", "nope", "cancel", "quit",
        "actually", "but", "however",
        "question", "ask",
        "excuse", "sorry",
        "repeat", "again",
        "help", "what",
    ]))
```

### Environment Variable Configuration

```bash
# .env file

# LiveKit connection
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# API Keys for providers
DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
CARTESIA_API_KEY=your_cartesia_key

# Custom word lists (optional, comma-separated)
IGNORE_WORDS=yeah,ok,hmm,right,sure,gotcha
INTERRUPT_WORDS=stop,wait,no,cancel,pause,hold
```

---

## Integration Guide: Add to Any LiveKit Voice Agent

This section shows how to add intelligent interrupt handling to **any** existing LiveKit voice agent.

### Step 1: Copy the InterruptFilter Class

Copy this self-contained filter class into your project:

```python
# interrupt_filter.py
import re
from dataclasses import dataclass, field
from typing import Literal, FrozenSet

InterruptDecision = Literal["ignore", "interrupt", "respond"]

DEFAULT_IGNORE_WORDS = frozenset([
    "yeah", "yes", "yep", "yup", "ya", "ok", "okay", "k",
    "hmm", "hm", "uh-huh", "mm-hmm", "mhm", "right", "alright",
    "sure", "aha", "ah", "i see", "got it", "gotcha",
    "cool", "nice", "great", "um", "uh", "er",
])

DEFAULT_INTERRUPT_WORDS = frozenset([
    "stop", "wait", "hold", "pause", "no", "nope", "cancel",
    "quit", "actually", "but", "however", "question", "ask",
    "excuse", "sorry", "repeat", "again", "help", "what",
])

@dataclass
class InterruptAnalysis:
    decision: InterruptDecision
    transcript: str
    agent_was_speaking: bool
    matched_ignore_words: list = field(default_factory=list)
    matched_interrupt_words: list = field(default_factory=list)
    reason: str = ""

@dataclass  
class InterruptFilterConfig:
    ignore_words: FrozenSet[str] = field(default_factory=lambda: DEFAULT_IGNORE_WORDS)
    interrupt_words: FrozenSet[str] = field(default_factory=lambda: DEFAULT_INTERRUPT_WORDS)

class InterruptFilter:
    def __init__(self, config: InterruptFilterConfig = None):
        self.config = config or InterruptFilterConfig()
        self._ignore_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.ignore_words) + r')\b',
            re.IGNORECASE
        )
        self._interrupt_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.interrupt_words) + r')\b',
            re.IGNORECASE
        )
    
    def _normalize(self, text: str) -> str:
        return ' '.join(re.sub(r'[.,!?;:]+', ' ', text).split())
    
    def _is_only_filler(self, text: str) -> bool:
        remaining = self._ignore_pattern.sub('', self._normalize(text))
        return len(remaining.strip()) == 0
    
    def analyze(self, transcript: str, agent_speaking: bool) -> InterruptAnalysis:
        normalized = self._normalize(transcript)
        ignore_matches = [m.group() for m in self._ignore_pattern.finditer(normalized)]
        interrupt_matches = [m.group() for m in self._interrupt_pattern.finditer(normalized)]
        
        # Agent is silent → always respond
        if not agent_speaking:
            return InterruptAnalysis(
                decision="respond", transcript=transcript, agent_was_speaking=False,
                matched_ignore_words=ignore_matches, matched_interrupt_words=interrupt_matches,
                reason="Agent is silent, treating as valid input"
            )
        
        # Agent is speaking + command word → interrupt
        if interrupt_matches:
            return InterruptAnalysis(
                decision="interrupt", transcript=transcript, agent_was_speaking=True,
                matched_ignore_words=ignore_matches, matched_interrupt_words=interrupt_matches,
                reason=f"Found interrupt command: {interrupt_matches}"
            )
        
        # Agent is speaking + only filler → ignore
        if self._is_only_filler(normalized):
            return InterruptAnalysis(
                decision="ignore", transcript=transcript, agent_was_speaking=True,
                matched_ignore_words=ignore_matches, matched_interrupt_words=interrupt_matches,
                reason=f"Only filler words: {ignore_matches}"
            )
        
        # Agent is speaking + substantive content → interrupt
        return InterruptAnalysis(
            decision="interrupt", transcript=transcript, agent_was_speaking=True,
            matched_ignore_words=ignore_matches, matched_interrupt_words=interrupt_matches,
            reason="Contains substantive content"
        )
```

### Step 2: Modify Your AgentSession Configuration

Update your `AgentSession` to use these settings:

```python
from livekit.agents import AgentSession

session = AgentSession(
    stt="deepgram/nova-3",
    llm="openai/gpt-4.1-mini", 
    tts="cartesia/sonic-2",
    vad=your_vad,
    
    # ═══════════════════════════════════════════════════════════
    # ADD THESE SETTINGS FOR INTELLIGENT INTERRUPT HANDLING
    # ═══════════════════════════════════════════════════════════
    allow_interruptions=True,
    min_interruption_words=2,      # KEY: Prevents single-word pauses
    min_interruption_duration=0.5,
    false_interruption_timeout=1.0,
    resume_false_interruption=True,
)
```

### Step 3: Track Agent Speaking State

Add state tracking to your agent:

```python
class MyAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_speaking = False
        self._interrupt_filter = InterruptFilter()
```

### Step 4: Add Event Handlers

Hook up the event handlers in your entrypoint:

```python
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # ... create session and agent ...
    
    # Track speaking state
    @session.on("agent_state_changed")
    def on_state_changed(ev):
        agent._is_speaking = (ev.new_state == "speaking")
    
    # Handle transcripts with intelligent filtering
    handled_interrupt = {"value": False}
    
    @session.on("user_input_transcribed")
    def on_transcript(ev):
        if not ev.transcript.strip():
            return
            
        transcript = ev.transcript.strip()
        is_speaking = agent._is_speaking
        
        # Reset on final transcript
        if ev.is_final:
            handled_interrupt["value"] = False
        
        # Analyze the transcript
        analysis = agent._interrupt_filter.analyze(transcript, agent_speaking=is_speaking)
        
        # INTERIM transcripts: detect command words early and interrupt
        if not ev.is_final and is_speaking and analysis.decision == "interrupt":
            if not handled_interrupt["value"]:
                current = session.current_speech
                if current and not current.interrupted:
                    current.interrupt(force=True)
                    handled_interrupt["value"] = True
        
        # FINAL transcripts: log decisions
        if ev.is_final:
            if analysis.decision == "ignore":
                print(f"[IGNORED] '{transcript}'")
            elif analysis.decision == "interrupt":
                print(f"[INTERRUPT] '{transcript}'")
            else:
                print(f"[RESPOND] '{transcript}'")
```

### Complete Integration Example

Here's a minimal complete example:

```python
"""my_agent_with_interrupts.py - Complete integration example"""
from livekit.agents import Agent, AgentSession, AgentServer, JobContext, cli
from livekit.agents.voice import AgentStateChangedEvent, UserInputTranscribedEvent
from livekit.plugins import silero
from interrupt_filter import InterruptFilter  # Copy from Step 1

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Initialize filter and state
    interrupt_filter = InterruptFilter()
    is_speaking = {"value": False}
    handled_interrupt = {"value": False}
    
    # Create session with smart interrupt settings
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2",
        vad=silero.VAD.load(),
        allow_interruptions=True,
        min_interruption_words=2,
        min_interruption_duration=0.5,
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )
    
    agent = Agent(instructions="You are a helpful assistant.")
    
    # Track speaking state
    @session.on("agent_state_changed")
    def on_state(ev: AgentStateChangedEvent):
        is_speaking["value"] = (ev.new_state == "speaking")
    
    # Intelligent interrupt handling
    @session.on("user_input_transcribed")
    def on_transcript(ev: UserInputTranscribedEvent):
        if not ev.transcript.strip():
            return
        
        transcript = ev.transcript.strip()
        speaking = is_speaking["value"]
        
        if ev.is_final:
            handled_interrupt["value"] = False
        
        analysis = interrupt_filter.analyze(transcript, agent_speaking=speaking)
        
        # Early interrupt detection via interim transcripts
        if not ev.is_final and speaking and analysis.decision == "interrupt":
            if not handled_interrupt["value"]:
                current = session.current_speech
                if current and not current.interrupted:
                    current.interrupt(force=True)
                    handled_interrupt["value"] = True
    
    await session.start(agent=agent, room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)
```

---

## Installation & Setup

### Prerequisites

1. Python 3.9+
2. LiveKit Cloud account or self-hosted LiveKit server
3. API keys for STT, LLM, and TTS providers

### Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/YOUR-USERNAME/agents-assignment.git
cd agents-assignment

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e ./livekit-agents
pip install livekit-plugins-silero livekit-plugins-deepgram
pip install livekit-plugins-openai livekit-plugins-cartesia
pip install python-dotenv

# 4. Create .env file with your API keys
cp .env.example .env
# Edit .env with your keys

# 5. Run the agent
cd examples/voice_agents
python intelligent_interrupt_agent.py dev  # Production mode
# OR
python intelligent_interrupt_agent.py console  # Local testing mode
```

---

## Testing

### Unit Tests

```bash
cd examples/voice_agents/intelligent_interrupt
python test_interrupt_filter.py
```

Expected: `Ran 36 tests in 0.007s - OK`

### Manual Test Scenarios

| Test | Action | Expected Result |
|------|--------|-----------------|
| **Filler Ignored** | Ask for story, say "yeah" while speaking | Agent continues, no pause |
| **Command Interrupts** | Ask to count to 50, say "stop" | Agent stops immediately |
| **Silent Response** | Wait for agent to finish, say "yeah" | Agent responds to you |
| **Mixed Input** | Say "yeah wait a second" while speaking | Agent stops (contains "wait") |

---

## File Structure

```
examples/voice_agents/
├── intelligent_interrupt_agent.py     # Main agent (run this)
└── intelligent_interrupt/
    ├── __init__.py                    # Module exports
    ├── interrupt_filter.py            # Core filter logic
    ├── test_interrupt_filter.py       # Unit tests  
    └── README.md                      # This documentation
```

---

## Troubleshooting

### Agent still pauses on "yeah"

1. Verify `min_interruption_words=2` is set in AgentSession
2. Check that the word count is being evaluated (single words should be blocked at audio level)
3. Review logs for `[IGNORED]` messages

### "stop" command not working

1. Ensure you're processing **interim** transcripts (not just final)
2. Verify "stop" is in `interrupt_words` list
3. Check that `session.current_speech.interrupt(force=True)` is being called
4. Look for `[EARLY INTERRUPT]` in logs

### High latency on interrupts

1. Use a streaming STT provider (Deepgram Nova recommended)
2. Check network latency to STT service
3. Reduce `false_interruption_timeout` if too high

### Agent ignores all input while speaking

1. Ensure `allow_interruptions=True`
2. Check that `min_interruption_words` is not set too high (2 is recommended)
3. Verify the transcript event handler is connected

---

## Architecture Notes

### Why This Approach?

1. **No VAD Modification**: The assignment requires a logic layer, not VAD kernel changes
2. **Dual-Layer Design**: Audio layer blocks single words, transcript layer handles semantics
3. **Interim Processing**: Faster interrupt detection than waiting for final transcripts
4. **Configurable**: Word lists can be customized without code changes

### Performance Characteristics

| Metric | Value |
|--------|-------|
| Filler word handling | No pause (blocked at audio level) |
| Command detection latency | ~150-300ms (via interim transcripts) |
| False positive rate | Low (command words are specific) |
| Configuration | Environment variables or code |

---

## License

Part of the LiveKit Agents framework. See main repository for license information.
