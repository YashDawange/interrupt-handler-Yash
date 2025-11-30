Intelligent interruption handler

Lightweight filter for LiveKit voice agents that treats quick acknowledgements
("yeah", "okay", "mhm") differently from interrupting phrases ("stop", "wait").

This project sits between the speech-to-text output and the agent's input
handler. When the agent is speaking, short backchannels are ignored so the
agent can finish its turn; when the agent is silent, the same phrases are
processed normally.

Demo: https://drive.google.com/file/d/115-X5mTD_7vqRdsv1gzbuwrLmfCEdHvP/view

## What it does
- Tracks whether the agent is currently speaking.
- Runs a fast, three-tier text filter:
  - Exact match against configured lists
  - Simple fuzzy match for short typos
  - Safe fallback (treat unknown short utterances as interrupts)
- Blocks or allows user input based on state and filter result.

## Why use it
- Reduces accidental agent cut-offs when users give passive feedback.
- Small and fast — suitable for realtime pipelines.
- Easy to configure lists of ignored / interrupt words.

## Quick start

Requirements: Python 3.9+ and whatever STT/LLM/TTS plugins your project uses.

1. Copy the example env file and add API keys:

```bash
cp .env.example .env
# edit .env and add keys for your STT/LLM/TTS as needed
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run in development mode:

```bash
python interrupt_handler.py dev
```

Run a console test with:

```bash
python intelligent_agent.py console
```

## Configuration

**Backchannel Words (ignored when agent speaks):**
- Default: yeah, ok, okay, hmm, uh-huh, alright, right, yep, sure, mhm

**Interrupt Words (always stop agent):**
- Default: stop, wait, no, hold on, pause, halt, actually, but, however

**Customize:**
```bash
export IGNORE_WORDS="yeah,ok,yes,sure"
export INTERRUPT_WORDS="stop,wait,pause"
export FUZZY_MATCH_THRESHOLD=0.85
```


## How It Works

**Example: User says "yeah" while agent speaks**

1. STT transcribes → "yeah"
2. Check agent state → Speaking
3. Analyze with filter → Exact match in IGNORE_SET
4. Result → is_backchannel=True
5. Decision → BLOCK
6. Agent → Continues speaking

**3-Tier Analysis:**
- **Tier 1:** Direct lookup in word sets (< 1ms)
- **Tier 2:** Fuzzy matching for "yeahh" → "yeah" (1-3ms)
- **Tier 3:** Unknown words → Safe default (< 1ms)

## Performance
Analysis Speed - < 3ms
Memory - ~5MB 
Tier 1 Hit Rate - 90% 


## Implementation Details

### Word Filtering
```python
IGNORE_SET = {normalize("yeah"), normalize("ok"), ...}
INTERRUPT_SET = {normalize("stop"), normalize("wait"), ...}
```

### State Tracking
```python
@session.on("agent_speech_created")
def on_speaking():
    is_agent_speaking = True

@session.on("agent_speech_committed")
def on_finished():
    is_agent_speaking = False
```

### Analysis
```python
def analyze(text):
    tokens = tokenize(text)
    
    # Tier 1: Exact
    if all(t in IGNORE_SET for t in tokens):
        return BACKCHANNEL
    if any(t in INTERRUPT_SET for t in tokens):
        return INTERRUPT
    
    # Tier 2: Fuzzy
    for token in unknown_tokens:
        similarity = fuzzy_match(token, IGNORE_SET)
        if similarity > 0.80:
            return BACKCHANNEL
    
    # Tier 3: Fallback
    return INTERRUPT  # Safe default
```
