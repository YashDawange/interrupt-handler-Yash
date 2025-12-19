# Smart Interruption Filter for Voice Agents

A sophisticated speech processing solution that intelligently distinguishes between passive user acknowledgments (backchanneling) and active commands, enabling natural conversational flow in voice-based AI agents.

## 📋 Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Architecture](#architecture)
- [Key Components](#key-components)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
- [Testing](#testing)
- [Customization](#customization)
- [Technical Details](#technical-details)
- [Future Improvements](#future-improvements)

---

## Problem Statement

### The Challenge

In traditional voice agents, **any user speech triggers an interruption**, causing the agent to stop speaking. This creates a poor user experience because:

1. **Backchanneling is misinterpreted**: Natural acknowledgments like "yeah," "uh-huh," or "okay" cause unnecessary interruptions
2. **UI flickering**: Start-of-speech events trigger visual indicators even for brief utterances
3. **Conversation feels unnatural**: Users can't provide feedback without disrupting the agent

### Real-World Scenario

```
Agent: "First, you'll need to gather your documents, then..."
User:  "Uh-huh"  ← Should be IGNORED (backchanneling)
Agent: [STOPS SPEAKING] ← ❌ Bad experience

Agent: "First, you'll need to gather your documents, then..."
User:  "Wait, I have a question"  ← Should INTERRUPT
Agent: [STOPS SPEAKING] ← ✅ Good experience
```

---

## Solution Overview

We implemented a **Smart Interruption Filter** that:

✅ **Ignores passive backchanneling** ("yeah," "okay," "uh-huh") while the agent speaks  
✅ **Immediately reacts to commands** ("stop," "wait," "actually")  
✅ **Suppresses UI flickering** from start-of-speech events during agent speech  
✅ **Uses dual-path processing** for both speed and accuracy  

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUDIO PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   User Audio → VAD → STT → [SMART FILTER] → LLM → TTS → Agent Speech    │
│                             ↑                                            │
│                             │                                            │
│                    ┌────────┴────────┐                                   │
│                    │  stt_node()     │                                   │
│                    │  Override       │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│              ┌──────────────┼──────────────┐                             │
│              ↓              ↓              ↓                             │
│         INTERIM       FINAL          START_OF_SPEECH                     │
│         (Fast Path)   (Accurate)     (Suppressed)                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Dual-Path Processing

| Path | Event Type | Purpose | Latency |
|------|------------|---------|---------|
| **Fast Path** | `INTERIM_TRANSCRIPT` | React to commands instantly | ~100ms |
| **Accurate Path** | `FINAL_TRANSCRIPT` | Make informed decisions | ~500ms |

---

## Key Components

### 1. `interruption_filter.py`

The core filtering logic module containing:

| Function | Purpose |
|----------|---------|
| `should_interrupt_optimistic(text)` | Fast check for interim results - detects commands early |
| `should_interrupt_agent(text, is_speaking)` | Robust check for final transcripts |
| `clean_text(text)` | Normalizes text for matching |

### 2. `basic_agent.py` 

The main agent with custom `stt_node()` override:

- Intercepts all speech events before they reach the LLM
- Applies intelligent filtering based on agent state
- Controls what the LLM "hears" and what gets ignored

---

## How It Works

### Speech Event Processing Flow

```python
async def stt_node(self, audio, model_settings):
    async for event in Agent.default.stt_node(self, audio, model_settings):
        is_speaking = self.session.agent_state == "speaking"

        if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
            # FAST PATH: React to commands immediately
            if is_speaking and should_interrupt_optimistic(partial_text):
                self.session.interrupt()
            yield event

        elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
            # ACCURATE PATH: Make informed decision
            if should_interrupt_agent(text, is_speaking):
                if is_speaking:
                    self.session.interrupt()
                yield event  # LLM sees this
            else:
                continue  # SWALLOW - LLM never sees this

        elif event.type == SpeechEventType.START_OF_SPEECH:
            if is_speaking:
                continue  # SUPPRESS UI flickering
            yield event
```

### Decision Matrix

| User Says | Agent Speaking? | Contains Command? | Action |
|-----------|-----------------|-------------------|--------|
| "Yeah" | ✅ Yes | ❌ No | **IGNORE** (backchannel) |
| "Yeah" | ❌ No | ❌ No | **PROCESS** (it's a reply) |
| "Stop" | ✅ Yes | ✅ Yes | **INTERRUPT** immediately |
| "Yeah but wait" | ✅ Yes | ✅ Yes | **INTERRUPT** (command wins) |
| "Tell me more" | ✅ Yes | ❌ No | **INTERRUPT** (real question) |

---

## Configuration

### Word Categories

Edit `interruption_filter.py` to customize:

#### Passive Words (Ignored while agent speaks)

```python
PASSIVE_WORDS = {
    "yeah", "yep", "yes", "yup", "ok", "okay", "alright", "right",
    "uh-huh", "uh huh", "hmm", "mhm", "aha", "sure", "got it", "i see",
    "understood", "cool", "great", "nice", "really", "absolutely",
    "exactly", "go on", "makes sense", "mhmm", "mm-hmm", "mmhmm",
    "oh", "mm", "mmm", "wow"
}
```

#### Active Words (Always trigger interruption)

```python
ACTIVE_WORDS = {
    "stop", "wait", "hold", "pause", "no", "nope", "cancel",
    "listen", "hang on", "excuse me", "actually", "wrong",
    "quiet", "shut up", "enough", "never mind", "nevermind"
}
```

### Agent Session Settings

```python
session = AgentSession(
    # Core interruption settings
    allow_interruptions=True,           # Enable interruption handling
    resume_false_interruption=True,     # Resume after false positives
    false_interruption_timeout=1.5,     # Seconds before resuming
    min_interruption_words=2,           # Minimum words to trigger
    
    # Other settings...
)
```

---

## Installation & Setup

### Prerequisites

- Python 3.9+
- LiveKit Agents SDK
- Required API keys (Deepgram, OpenAI, Cartesia)

### Environment Variables

Create `.env` in the `voice_agents` directory:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
CARTESIA_API_KEY=your_cartesia_key
```

### Run the Agent

```bash
cd examples/voice_agents
python basic_agent.py dev
```

---

## Usage

### Basic Usage

The smart interruption filter is automatically active. Simply run the agent and:

1. Connect to the LiveKit room
2. Start speaking with the agent
3. Try backchanneling ("yeah", "okay") while the agent talks → Agent continues
4. Try commanding ("wait", "stop") while the agent talks → Agent stops

### Observing Logs

Watch the terminal for filter decisions:

```
⚡ FAST INTERRUPT: Heard partial 'sto...'     → Command detected early
🛑 FINAL INTERRUPT: Heard 'wait a moment'    → Command confirmed
🔇 IGNORING BACKCHANNEL: 'yeah'              → Passive word ignored
```

---

## Testing

### Manual Testing Scenarios

| Test | User Says | Expected Log | Expected Behavior |
|------|-----------|--------------|-------------------|
| 1 | "Uh-huh" (while agent speaks) | `🔇 IGNORING BACKCHANNEL` | Agent continues |
| 2 | "Stop" (while agent speaks) | `⚡ FAST INTERRUPT` | Agent stops immediately |
| 3 | "Actually, I have a question" | `🛑 FINAL INTERRUPT` | Agent stops, processes |
| 4 | "Yeah okay cool" | `🔇 IGNORING BACKCHANNEL` | Agent continues |
| 5 | "Yeah but wait" | `🛑 FINAL INTERRUPT` | Agent stops (command wins) |

### Edge Cases

- **Mixed input**: "Yeah, but actually..." → INTERRUPT (contains "actually")
- **Long passive**: "Oh yeah okay sure" → IGNORE (all passive words)
- **Unknown phrase**: "My cat is orange" → INTERRUPT (unknown = real speech)

---

## Customization

### Adding New Passive Words

```python
# In interruption_filter.py
PASSIVE_WORDS.add("fine")
PASSIVE_WORDS.add("totally")
```

### Adding New Command Words

```python
# In interruption_filter.py
ACTIVE_WORDS.add("help")
ACTIVE_WORDS.add("question")
```

### Language Support

The current implementation is English-focused. For other languages:

1. Create language-specific word sets
2. Consider using an LLM for intent classification (slower but more accurate)

### Advanced: LLM-Based Classification

For more sophisticated classification, you could enhance `should_interrupt_agent()`:

```python
async def should_interrupt_agent_llm(text: str, context: str) -> bool:
    """Use an LLM to classify user intent (slower but smarter)."""
    prompt = f"""
    Context: Agent is explaining: "{context}"
    User said: "{text}"
    
    Is this: (A) Backchanneling/acknowledgment or (B) A real question/command?
    Reply with just A or B.
    """
    response = await llm.complete(prompt)
    return response.strip() == "B"
```

---

## Technical Details

### Why Override `stt_node()`?

The `stt_node()` method is the **Speech-to-Text processing node** in the agent pipeline. By overriding it:

- We intercept speech events **before** they reach the LLM
- We can **filter, modify, or suppress** events
- The LLM only "hears" what we want it to hear

### Event Types

| Event | Description | Our Handling |
|-------|-------------|--------------|
| `START_OF_SPEECH` | User started speaking | Suppress while agent speaks |
| `INTERIM_TRANSCRIPT` | Partial transcription | Fast command detection |
| `FINAL_TRANSCRIPT` | Complete transcription | Full classification logic |
| `END_OF_SPEECH` | User stopped speaking | Pass through unchanged |

### Performance Considerations

- **Fast Path Latency**: ~100ms (interim results)
- **Accurate Path Latency**: ~500ms (final transcript)
- **Memory**: Minimal (just word set lookups)
- **CPU**: Negligible (string operations only)

---

## Future Improvements

### Planned Enhancements

- [ ] **Context-aware filtering**: Consider what the agent just said
- [ ] **Sentiment analysis**: Detect frustration even without command words
- [ ] **Multi-language support**: Dynamic language detection
- [ ] **Learning system**: Adapt to individual user patterns
- [ ] **Confidence scoring**: Return probability instead of boolean

### Known Limitations

1. **English-only**: Word sets are currently English
2. **No context**: Doesn't consider agent's current topic
3. **Binary decision**: No uncertainty handling

---

## File Structure

```
examples/voice_agents/
├── basic_agent.py                    # Main agent with stt_node() override
├── interruption_filter.py            # Smart filtering logic
├── .env                              # API keys (not committed)
├── README.md                         # General examples documentation
└── SMART_INTERRUPTION_FILTER.md      # This documentation
```

---

## References

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [Speech-to-Text Models](https://docs.livekit.io/agents/models/stt/)
- [Turn Detection Guide](https://docs.livekit.io/agents/build/turns)
- [Audio Processing](https://docs.livekit.io/agents/build/audio/)

---

## License

This implementation is part of the LiveKit Agents examples and follows the same license terms.

---

## Contributing

Feel free to extend the word sets or improve the classification logic. PRs welcome!
