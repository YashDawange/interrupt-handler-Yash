# Backchannel Detection: Technical Deep Dive

## Table of Contents

1. [Introduction](#introduction)
2. [The Problem in Detail](#the-problem-in-detail)
3. [Architecture Overview](#architecture-overview)
4. [Component Deep Dive](#component-deep-dive)
5. [Event Flow Analysis](#event-flow-analysis)
6. [Decision Logic](#decision-logic)
7. [STT Transcript Handling](#stt-transcript-handling)
8. [Trade-offs and Design Decisions](#trade-offs-and-design-decisions)
9. [Bug Fixes and Improvements](#bug-fixes-and-improvements)
10. [Performance Considerations](#performance-considerations)
11. [Testing and Debugging](#testing-and-debugging)
12. [Future Improvements](#future-improvements)

---

## Demo Video Link
[Backchannel Detection Demo](https://drive.google.com/file/d/1lq80zSB6DH-Sr2a97F_3Mk3ztCtmINBF/view?usp=sharing)

## Introduction

### What are Backchannels?

In linguistics, **backchannels** are verbal and non-verbal cues that listeners provide during conversation to indicate attention, understanding, or agreement without taking the conversational floor. Examples include:

- **Verbal**: "yeah", "uh-huh", "mm-hmm", "okay", "right", "I see"
- **Non-verbal**: nodding, eye contact (not applicable in voice-only)

### Why Do They Matter for Voice AI?

Voice AI agents use Voice Activity Detection (VAD) and Speech-to-Text (STT) to detect when users speak. The problem: VAD cannot distinguish between:

1. **Intentional interruptions**: "Wait, I have a question"
2. **Backchannel signals**: "Yeah" (while still listening)

Without backchannel handling, every sound the user makes interrupts the agent, creating a frustrating experience.

---

## The Problem in Detail

### The Interrupt Pipeline (Before Implementation)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ORIGINAL INTERRUPT FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

User makes sound
      │
      ▼
┌─────────────────┐
│ Microphone      │ → Raw audio frames
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ VAD (Silero)    │ → Detects: "Speech started"
└─────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ on_vad_inference_done()                                 │
│                                                         │
│ if speech_duration >= min_interruption_duration (0.5s): │
│     → INTERRUPT IMMEDIATELY                             │
└─────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────┐
│ Agent stops     │ ← Problem: User just said "yeah"!
└─────────────────┘
```

### The Problem Scenario

```
Timeline:
─────────────────────────────────────────────────────────────────────────────►

Agent: "The weather today will be sunny with a high of 75 degrees..."
                    │
User: "yeah"        │  ← User acknowledges, wants agent to continue
                    │
Agent: [STOPS]      │  ← VAD detected speech, interrupted agent
                    │
User: 😤            │  ← Frustrated - didn't want to interrupt!
```

### Why VAD Alone Can't Solve This

| Signal | VAD Detection | User Intent |
|--------|---------------|-------------|
| "yeah" | Speech detected (500ms) | Continue listening |
| "wait" | Speech detected (500ms) | Stop and listen to me |
| "uh-huh" | Speech detected (400ms) | I'm following along |
| "stop" | Speech detected (500ms) | Stop immediately |

VAD only knows: **"Is there speech?"** not **"What does the speech mean?"**

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKCHANNEL-AWARE ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────────┐
                              │   AgentSession      │
                              │                     │
                              │ • options           │
                              │ • interrupt_handler │◄─── InterruptHandler
                              │ • agent_state       │     (backchannel detection)
                              └──────────┬──────────┘
                                         │
                                         │ owns
                                         ▼
┌─────────────┐              ┌─────────────────────┐              ┌─────────────┐
│  AudioInput │─────────────►│   AgentActivity     │─────────────►│ AudioOutput │
│  (Mic/RTC)  │   frames     │                     │   TTS audio  │ (Speaker)   │
└─────────────┘              │ • _audio_recognition│              └─────────────┘
                             │ • _current_speech   │
                             │ • on_vad_*()        │
                             │ • on_*_transcript() │
                             └──────────┬──────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
            │     VAD     │     │     STT     │     │     LLM     │
            │   (Silero)  │     │  (Deepgram) │     │  (OpenAI)   │
            └─────────────┘     └─────────────┘     └─────────────┘
```

### Data Flow with Backchannel Detection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEW INTERRUPT FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

User says "yeah"
      │
      ▼
┌─────────────────┐
│ VAD detects     │ → speech_duration = 450ms
│ speech          │
└─────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ on_vad_inference_done()                                                     │
│                                                                             │
│ if interrupt_handler is not None and stt is not None:                       │
│     # Don't interrupt yet - wait for STT to classify                        │
│     logger.debug("Deferring to STT for backchannel analysis")               │
│     return  ◄─── KEY CHANGE: VAD alone doesn't interrupt                    │
│                                                                             │
│ self._interrupt_by_audio_activity()  # Only if no handler                   │
└─────────────────────────────────────────────────────────────────────────────┘
      │
      │ (Audio continues to STT)
      ▼
┌─────────────────┐
│ STT transcribes │ → "Yeah."
│ (Deepgram)      │
└─────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ on_interim_transcript() or on_final_transcript()                            │
│                                                                             │
│ transcript_text = "Yeah."                                                   │
│ self._interrupt_by_audio_activity(transcript=transcript_text)               │
└─────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ _interrupt_by_audio_activity(transcript="Yeah.")                            │
│                                                                             │
│ analysis = interrupt_handler.analyze(                                       │
│     transcript="Yeah.",                                                     │
│     agent_state="speaking"                                                  │
│ )                                                                           │
│                                                                             │
│ # Result:                                                                   │
│ # - action: IGNORE                                                          │
│ # - is_backchannel_only: True                                               │
│ # - matched_words: ["yeah"]                                                 │
│                                                                             │
│ if analysis.action == InterruptAction.IGNORE:                               │
│     return  ◄─── Don't interrupt, agent continues speaking                  │
└─────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
Agent continues: "...and tomorrow will be partly cloudy..."
```

---

## Component Deep Dive

### 1. InterruptHandler (`interrupt_handler.py`)

#### Purpose
Analyzes transcript text to classify user intent and decide whether to interrupt the agent.

#### Class Structure

```python
class InterruptHandler:
    """
    Attributes:
        min_interrupt_duration: int - Minimum speech duration (ms) to consider
        min_interruption_words: int - Minimum word count
        backchannel_words: set[str] - Words that indicate listening
        command_words: set[str] - Words that indicate interrupt intent
    """
```

#### Word Lists Design Philosophy

**Backchannel Words** - Chosen based on:
1. **Linguistic research** on conversational backchannels
2. **STT transcription variations** (e.g., "yeah" vs "ya" vs "yah")
3. **Cultural variations** (e.g., "alright" common in UK English)

```python
DEFAULT_BACKCHANNEL_WORDS = {
    # Core affirmatives - most common backchannels
    "yeah", "yea", "ya", "yah", "yeh",  # STT variations of "yeah"
    "yes", "yep", "yup",
    "okay", "ok", "kay", "k",           # STT variations of "okay"
    "alright", "all right", "aight",
    
    # Acknowledgment sounds - paralinguistic
    "mm-hmm", "mm hmm", "mmhmm", "mhm",  # Agreement hum
    "uh-huh", "uh huh", "uhuh",          # Agreement sound
    "hmm", "hm", "hmmm",                 # Thinking/processing
    "uh", "uhh", "um", "umm",            # Hesitation markers
    
    # Understanding phrases
    "i see", "got it", "gotcha",
    "right", "sure", "exactly",
    # ... more
}
```

**Command Words** - Chosen based on:
1. **Direct imperative verbs** (stop, wait, pause)
2. **Negation markers** (no, don't, cancel)
3. **Clarification requests** (what, repeat, again)

```python
DEFAULT_COMMAND_WORDS = {
    # Stop commands - immediate halt
    "stop", "wait", "pause", "hold on",
    
    # Negation - user disagrees or wants change
    "no", "nope", "don't", "cancel",
    
    # Clarification - user didn't understand
    "what", "huh", "pardon", "repeat",
    # ... more
}
```

#### The `analyze()` Method - Step by Step

```python
def analyze(self, transcript: str, agent_state: str | None = None, 
            speech_duration: int | None = None) -> InterruptAnalysis:
```

**Step 1: Input Validation**
```python
if not transcript or not transcript.strip():
    return InterruptAnalysis(action=RESPOND, ...)  # Empty = no action
```

**Step 2: Tokenization**
```python
# "Yeah." → ["yeah"]
# "Okay, I see." → ["okay", "i", "see"]
words = [word.lower().strip(".,!?;:\"'") for word in transcript.split()]
words = [w for w in words if w]  # Remove empty strings
```

**Step 3: Word Matching**
```python
# Match individual words
matched_backchannels = [w for w in words if w in self.backchannel_words]
matched_commands = [w for w in words if w in self.command_words]
```

**Step 4: Multi-word Phrase Matching**
```python
# Handle phrases like "hold on", "all right", "uh huh"
transcript_lower = transcript.lower()

for phrase in self.backchannel_words:
    if " " in phrase and phrase in transcript_lower:
        matched_backchannels.append(phrase)

for phrase in self.command_words:
    if " " in phrase and phrase in transcript_lower:
        matched_commands.append(phrase)
```

**Step 5: Full Transcript Matching**
```python
# Handle "Yeah." where period is attached
full_cleaned = transcript_lower.strip().strip(".,!?;:\"'").strip()
if full_cleaned in self.backchannel_words:
    matched_backchannels.append(full_cleaned)
```

**Step 6: Classification**
```python
is_backchannel_only = len(matched_backchannels) > 0 and len(matched_commands) == 0
has_command_words = len(matched_commands) > 0
```

**Step 7: Action Decision**
```python
action = self._decide_action(
    is_backchannel_only=is_backchannel_only,
    has_command_words=has_command_words,
    agent_state=agent_state,
    speech_duration=speech_duration,
    word_count=len(words),
)
```

#### The `_decide_action()` Method - Decision Tree

```python
def _decide_action(self, *, is_backchannel_only, has_command_words, 
                   agent_state, speech_duration, word_count) -> InterruptAction:
```

**Decision Tree Visualization:**

```
                    ┌─────────────────────┐
                    │ Analyze transcript  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ speech_duration <   │
                    │ min_interrupt_dur?  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │ Yes            │                │ No
              ▼                │                ▼
     ┌─────────────┐           │     ┌─────────────────────┐
     │   RESPOND   │           │     │ is_backchannel_only?│
     │ (too short) │           │     └──────────┬──────────┘
     └─────────────┘           │                │
                               │   ┌────────────┼────────────┐
                               │   │ Yes        │            │ No
                               │   ▼            │            ▼
                               │ ┌─────────────────────┐  ┌─────────────────────┐
                               │ │ agent_state ==      │  │ has_command_words?  │
                               │ │ "speaking"?         │  └──────────┬──────────┘
                               │ └──────────┬──────────┘             │
                               │            │              ┌─────────┼─────────┐
                               │   ┌────────┼────────┐     │ Yes     │         │ No
                               │   │ Yes    │        │ No  ▼         │         ▼
                               │   ▼        │        ▼  ┌─────────┐  │  ┌─────────┐
                               │ ┌────────┐ │ ┌────────┐│INTERRUPT│  │  │ RESPOND │
                               │ │ IGNORE │ │ │RESPOND ││(command)│  │  │(default)│
                               │ │(backch)│ │ │(silent)│└─────────┘  │  └─────────┘
                               │ └────────┘ │ └────────┘             │
                               │            │                        │
                               └────────────┴────────────────────────┘
```

**Decision Table:**

| is_backchannel_only | has_command_words | agent_state | Action |
|---------------------|-------------------|-------------|--------|
| True | False | speaking | **IGNORE** |
| True | False | listening | RESPOND |
| True | False | idle | RESPOND |
| False | True | any | **INTERRUPT** |
| False | False | any | RESPOND |
| True | True | any | **INTERRUPT** (commands override) |

### 2. AgentActivity Integration (`agent_activity.py`)

#### Modified Methods

**`on_vad_inference_done()`** - VAD callback

```python
def on_vad_inference_done(self, ev: vad.VADEvent) -> None:
    """Called when VAD completes inference on an audio segment."""
    
    # Skip if manual or realtime LLM turn detection
    if self._turn_detection in ("manual", "realtime_llm"):
        return

    if ev.speech_duration >= self._session.options.min_interruption_duration:
        opt = self._session.options
        
        # KEY LOGIC: If backchannel detection enabled, defer to STT
        if (
            opt.interrupt_handler is not None  # Handler exists
            and self.stt is not None           # STT available
            and self._current_speech is not None  # Agent is speaking
            and self._current_speech.allow_interruptions  # Interruptible
            and not self._current_speech.interrupted  # Not already interrupted
        ):
            # Don't interrupt from VAD alone
            # Wait for STT transcript to analyze
            logger.debug("VAD: deferring to STT for backchannel analysis")
            return
        
        # No backchannel detection - interrupt immediately (original behavior)
        self._interrupt_by_audio_activity()
```

**Why defer to STT?**

VAD fires **before** STT has any transcript. The timeline:

```
0ms      100ms     200ms     300ms     400ms     500ms     600ms
│         │         │         │         │         │         │
▼         ▼         ▼         ▼         ▼         ▼         ▼
┌─────────────────────────────────────────────────┐
│              User speaks "yeah"                 │
└─────────────────────────────────────────────────┘
          │                             │
          ▼                             │
    ┌───────────┐                       │
    │VAD fires  │ ← No transcript yet!  │
    │(speech    │                       │
    │detected)  │                       │
    └───────────┘                       │
                                        ▼
                                  ┌───────────┐
                                  │STT returns│ ← "Yeah."
                                  │transcript │
                                  └───────────┘
```

If VAD interrupted at 200ms, we'd never see "Yeah." to know it's a backchannel.

**`_interrupt_by_audio_activity()`** - Core interrupt logic (RESTRUCTURED)

This method has been restructured to prevent any pausing or interruption until the InterruptHandler analyzes the transcript. The key improvement is that backchannels no longer cause even brief pauses.

```python
def _interrupt_by_audio_activity(self, *, transcript: str | None = None) -> None:
    """
    Handle potential interruption from audio activity.
    
    CRITICAL: When interrupt_handler is enabled, we MUST have a transcript
    before making any pause/interrupt decision. This prevents backchannels
    from causing even brief audio pauses.
    
    This method is called from:
    1. on_vad_inference_done() - when VAD detects speech
    2. on_interim_transcript() - when STT provides interim text
    3. on_final_transcript() - when STT provides final text
    
    Args:
        transcript: Optional transcript text for backchannel analysis.
                   If None, tries to get from audio_recognition.
    """
    opt = self._session.options
    
    # Get transcript for analysis
    text = transcript
    if text is None and self._audio_recognition is not None:
        text = self._audio_recognition.current_transcript
    
    # Check minimum word count
    if (self.stt is not None and opt.min_interruption_words > 0):
        if text and len(split_words(text)) < opt.min_interruption_words:
            return  # Not enough words
    
    # BACKCHANNEL DETECTION - MUST ANALYZE BEFORE ANY PAUSE/INTERRUPT
    interrupt_handler = opt.interrupt_handler
    if interrupt_handler is not None and self._current_speech is not None:
        # KEY FIX #1: No transcript yet? Return early, wait for STT
        if not text:
            return  # ← Don't pause without transcript!
        
        if self._current_speech.interrupted or not self._current_speech.allow_interruptions:
            return
        
        agent_state = self._session.agent_state
        
        # Analyze the transcript
        analysis = interrupt_handler.analyze(
            transcript=text,
            agent_state=agent_state,
        )
        
        # Log and emit event for observability
        logger.debug("backchannel analysis result", extra={...})
        self._session.emit("backchannel_detected", BackchannelDetectedEvent(...))
        
        # KEY FIX #2: Handle each action explicitly
        if analysis.action == InterruptAction.IGNORE:
            # Backchannel detected - clear any paused state, resume audio
            logger.debug("backchannel detected, ignoring interrupt")
            
            # Clear paused state and resume audio if paused
            if self._paused_speech is not None:
                if self._session.output.audio and self._session.output.audio.can_pause:
                    self._session.output.audio.resume()
                    self._session._update_agent_state("speaking")
                self._paused_speech = None
            
            # Cancel false interruption timer
            if self._false_interruption_timer is not None:
                self._false_interruption_timer.cancel()
                self._false_interruption_timer = None
            
            return  # ← Don't interrupt!
        
        elif analysis.action == InterruptAction.RESPOND:
            # Not a backchannel, but agent may be silent - don't interrupt
            return  # ← Don't interrupt!
        
        # If we reach here, action is INTERRUPT - fall through to interrupt logic
    
    # Only reaches here if:
    # 1. No interrupt_handler configured, OR
    # 2. Analysis returned INTERRUPT action
    if self._current_speech is not None and not self._current_speech.interrupted:
        self._paused_speech = self._current_speech
        # ... pause/interrupt logic ...
```

**Key Changes Summary:**

| Issue | Old Behavior | New Behavior |
|-------|-------------|--------------|
| No transcript | Fall through to pause | Return early, wait for STT |
| IGNORE action | Return (but might have paused) | Clear pause state, resume audio, return |
| RESPOND action | Fall through to pause | Return without pausing |
| INTERRUPT action | Pause/interrupt | Pause/interrupt (unchanged) |

**`on_final_transcript()`** - Backchannel-aware transcript handling (UPDATED)

```python
def on_final_transcript(self, ev: stt.SpeechEvent, *, speaking: bool | None = None) -> None:
    # ... emit user input event ...
    
    # KEY FIX #3: Check if this is a backchannel BEFORE processing
    is_backchannel = False
    opt = self._session.options
    if (
        opt.interrupt_handler is not None
        and transcript_text
        and self._current_speech is not None
        and not self._current_speech.interrupted
    ):
        analysis = opt.interrupt_handler.analyze(
            transcript=transcript_text,
            agent_state=self._session.agent_state,
        )
        is_backchannel = analysis.action == InterruptAction.IGNORE
    
    # ... call _interrupt_by_audio_activity() ...
    
    # KEY FIX #3 (continued): Only interrupt paused speech if NOT a backchannel
    # This prevents backchannels from stopping the agent mid-sentence
    if not is_backchannel:
        self._interrupt_paused_speech_task = asyncio.create_task(
            self._interrupt_paused_speech(old_task=self._interrupt_paused_speech_task)
        )
```

**`on_end_of_turn()`** - Prevent new reply generation for backchannels (UPDATED)

```python
def on_end_of_turn(self, info: _EndOfTurnInfo) -> bool:
    # KEY FIX #4: Check for backchannels at start of turn handling
    opt = self._session.options
    if (
        opt.interrupt_handler is not None
        and info.new_transcript
        and self._current_speech is not None
        and not self._current_speech.interrupted
    ):
        analysis = opt.interrupt_handler.analyze(
            transcript=info.new_transcript,
            agent_state=self._session.agent_state,
        )
        if analysis.action == InterruptAction.IGNORE:
            logger.debug(
                "backchannel detected in on_end_of_turn, ignoring turn",
                extra={"transcript": info.new_transcript, ...},
            )
            return False  # ← Don't generate new reply for backchannels!
    
    # ... continue with normal turn handling ...
```

### 3. AgentSession Configuration (`agent_session.py`)

#### New Parameter

```python
class AgentSession:
    def __init__(
        self,
        *,
        # ... existing parameters ...
        interrupt_handler: NotGivenOr[InterruptHandler | None] = NOT_GIVEN,
    ):
```

#### Default Behavior

```python
# In __init__:
self._opts = AgentSessionOptions(
    # ... other options ...
    interrupt_handler=interrupt_handler
        if is_given(interrupt_handler)
        else InterruptHandler(),  # ← Default handler created
)
```

This means:
- **Not specified** (`NOT_GIVEN`): Default `InterruptHandler()` is created
- **`None`**: Backchannel detection disabled
- **Custom handler**: Use the provided handler

### 4. Events (`events.py`)

#### BackchannelDetectedEvent

```python
class BackchannelDetectedEvent(BaseModel):
    """Emitted when the interrupt handler analyzes user speech."""
    
    transcript: str
    """The user's speech text that was analyzed."""
    
    action: str
    """The decided action: 'ignore', 'interrupt', or 'respond'."""
    
    confidence: float
    """Confidence score from 0.0 to 1.0."""
    
    matched_words: list[str]
    """Words from the transcript that matched backchannel or command lists."""
    
    is_backchannel_only: bool
    """True if only backchannel words were detected (no commands)."""
    
    has_command_words: bool
    """True if command words were detected."""
```

#### Event Registration

Added to `EventTypes`:

```python
EventTypes = Literal[
    # ... existing events ...
    "backchannel_detected",
]
```

---

## Event Flow Analysis

### Complete Event Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE EVENT FLOW: User says "yeah"                     │
└─────────────────────────────────────────────────────────────────────────────┘

Timeline (milliseconds):
0       100      200      300      400      500      600      700
│        │        │        │        │        │        │        │
▼        ▼        ▼        ▼        ▼        ▼        ▼        ▼

[Audio Stream]
████████████████████████████████████
       "y   e   a   h"

[VAD Processing]
         ┌───────────────────────┐
         │ Speech detected       │
         │ Duration: 0ms         │
         └───────────────────────┘
                  │
                  ▼
         ┌───────────────────────┐
         │ on_start_of_speech()  │
         │ → user_state=speaking │
         └───────────────────────┘

                           ┌───────────────────────┐
                           │ on_vad_inference_done │
                           │ Duration: 400ms       │
                           │ → Defer to STT        │
                           └───────────────────────┘

[STT Processing]
                                    ┌───────────────────────┐
                                    │ on_interim_transcript │
                                    │ transcript: "Yeah"    │
                                    └───────────────────────┘
                                             │
                                             ▼
                                    ┌───────────────────────┐
                                    │_interrupt_by_audio_   │
                                    │activity(transcript=   │
                                    │"Yeah")                │
                                    └───────────────────────┘
                                             │
                                             ▼
                                    ┌───────────────────────┐
                                    │ InterruptHandler.     │
                                    │ analyze("Yeah",       │
                                    │ "speaking")           │
                                    │                       │
                                    │ Result:               │
                                    │ - action: IGNORE      │
                                    │ - backchannel: True   │
                                    └───────────────────────┘
                                             │
                                             ▼
                                    ┌───────────────────────┐
                                    │ emit("backchannel_    │
                                    │ detected", event)     │
                                    └───────────────────────┘
                                             │
                                             ▼
                                    ┌───────────────────────┐
                                    │ IGNORE action:        │
                                    │ - Clear _paused_speech│
                                    │ - Resume audio output │
                                    │ - Cancel false_int_   │
                                    │   timer               │
                                    │ - Return (no pause!)  │
                                    └───────────────────────┘

                                                    ┌───────────────────────┐
                                                    │ on_final_transcript   │
                                                    │ transcript: "Yeah."   │
                                                    │ → Check is_backchannel│
                                                    │ → Skip _interrupt_    │
                                                    │   paused_speech()     │
                                                    └───────────────────────┘

                                                             ┌───────────────────────┐
                                                             │ on_end_of_turn()      │
                                                             │ → Check backchannel   │
                                                             │ → Return False        │
                                                             │ → No new reply        │
                                                             └───────────────────────┘

                                                                      ┌───────────────────────┐
                                                                      │ on_end_of_speech()    │
                                                                      │ → user_state=listening│
                                                                      └───────────────────────┘

[Agent Output]
████████████████████████████████████████████████████████████████████████████████
     "The weather today will be sunny with a high of 75 degrees..."
     (CONTINUES UNINTERRUPTED - NO PAUSE AT ALL)
```

### Detailed Flow: Why Agent No Longer Pauses

The fixes ensure backchannels don't cause ANY pause in agent speech:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│               DETAILED BACKCHANNEL FLOW (After Bug Fixes)                     │
└──────────────────────────────────────────────────────────────────────────────┘

1. VAD detects speech
   └─> on_vad_inference_done()
       └─> interrupt_handler enabled? → Defer to STT (don't call _interrupt_by_audio_activity)

2. STT returns interim "Yeah"
   └─> on_interim_transcript()
       └─> _interrupt_by_audio_activity(transcript="Yeah")
           └─> FIX #1: Have transcript? Yes
           └─> Analyze: action=IGNORE
           └─> FIX #2: Clear paused state, resume audio, return
           └─> ✅ No pause, no interrupt

3. STT returns final "Yeah."
   └─> on_final_transcript()
       └─> FIX #3: Check is_backchannel → True
       └─> _interrupt_by_audio_activity(transcript="Yeah.")
           └─> Same as step 2: action=IGNORE, return
       └─> FIX #3: is_backchannel=True → Skip _interrupt_paused_speech()
       └─> ✅ Agent text not interrupted

4. Turn detection triggers end of turn
   └─> on_end_of_turn()
       └─> FIX #4: Check backchannel → action=IGNORE
       └─> Return False (don't generate new reply)
       └─> ✅ Agent continues current response

5. VAD detects end of speech
   └─> on_end_of_speech()
       └─> Update user_state to "listening"
       └─> ✅ No false interruption timer started (not paused)
```

### Comparison: With vs Without Backchannel Detection

**WITHOUT Backchannel Detection:**

```
0ms                    200ms                   400ms
│                       │                       │
▼                       ▼                       ▼
User: "yeah"────────────►
                        │
                VAD fires│
                        │
                        ▼
              ┌─────────────────┐
              │ INTERRUPT       │
              │ Agent stops     │
              └─────────────────┘
                        │
                        ▼
Agent: "The wea──" [STOPS]

Result: Agent interrupted after 200ms, user frustrated
```

**WITH Backchannel Detection (BEFORE Bug Fixes):**

```
0ms                    200ms                   400ms                   600ms
│                       │                       │                       │
▼                       ▼                       ▼                       ▼
User: "yeah"────────────────────►
                        │               STT returns│
                        │               "Yeah."    │
                        │                       │
                        │                       ▼
                        │             ┌─────────────────┐
                        │             │ Analyze: IGNORE │
                        │             └─────────────────┘
                        │                       │
                        │             But: _interrupt_paused_speech() still called!
                        │                  on_end_of_turn() generates new reply!
                        │                       │
Agent: "The wea──" [PAUSES ~1s] ─── [CONTINUES] "ther today..."

Result: Agent pauses briefly, text may stop mid-sentence in UI
```

**WITH Backchannel Detection (AFTER Bug Fixes):**

```
0ms                    200ms                   400ms                   600ms
│                       │                       │                       │
▼                       ▼                       ▼                       ▼
User: "yeah"────────────────────►
                        │                       │
                VAD fires│                       │
                (defers) │                       │
                        │               STT returns│
                        │               "Yeah."    │
                        │                       │
                        │                       ▼
                        │             ┌─────────────────┐
                        │             │ Analyze: IGNORE │
                        │             │ No pause, no    │
                        │             │ interrupt, no   │
                        │             │ new reply       │
                        │             └─────────────────┘
                        │                       │
Agent: "The weather today will be sunny with a high of 75..."
        ──────────────────────────────────────────────────────►
        (CONTINUES UNINTERRUPTED - ZERO PAUSE)

Result: Agent continues seamlessly, natural conversation flow
```

---

## Decision Logic

### State Machine

```
                          ┌─────────────────────────────────────┐
                          │                                     │
                          │         AGENT SPEAKING              │
                          │                                     │
                          └──────────────────┬──────────────────┘
                                             │
                                             │ User makes sound
                                             ▼
                          ┌─────────────────────────────────────┐
                          │         VAD DETECTS SPEECH          │
                          └──────────────────┬──────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
        ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
        │ No handler        │    │ Handler exists    │    │ No STT            │
        │ (disabled)        │    │ + STT available   │    │ available         │
        └─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘
                  │                        │                        │
                  │                        │                        │
                  ▼                        ▼                        ▼
        ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
        │ INTERRUPT         │    │ DEFER TO STT      │    │ INTERRUPT         │
        │ IMMEDIATELY       │    │ (wait for text)   │    │ IMMEDIATELY       │
        └───────────────────┘    └─────────┬─────────┘    └───────────────────┘
                                           │
                                           │ STT returns transcript
                                           ▼
                          ┌─────────────────────────────────────┐
                          │      ANALYZE TRANSCRIPT             │
                          └──────────────────┬──────────────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
    │ BACKCHANNEL     │            │ COMMAND         │            │ OTHER           │
    │ ONLY            │            │ DETECTED        │            │ SPEECH          │
    │                 │            │                 │            │                 │
    │ "yeah", "mm-hmm"│            │ "stop", "wait"  │            │ "I have a       │
    │                 │            │                 │            │  question"      │
    └────────┬────────┘            └────────┬────────┘            └────────┬────────┘
             │                              │                              │
             ▼                              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
    │ ACTION: IGNORE  │            │ ACTION:INTERRUPT│            │ ACTION: RESPOND │
    │                 │            │                 │            │                 │
    │ Agent continues │            │ Agent stops     │            │ Normal flow     │
    │ speaking        │            │ immediately     │            │ (may interrupt) │
    └─────────────────┘            └─────────────────┘            └─────────────────┘
```

### Edge Cases

| Scenario | Transcript | Analysis | Action | Result |
|----------|------------|----------|--------|--------|
| Pure backchannel | "Yeah." | backchannel_only=True | IGNORE | Agent continues |
| Pure command | "Stop." | has_command=True | INTERRUPT | Agent stops |
| Mixed | "Yeah, wait" | both True | INTERRUPT | Agent stops (command wins) |
| Unknown word | "Blarg" | neither True | RESPOND | May interrupt |
| Empty | "" | neither True | RESPOND | No action |
| Multi-word bc | "Uh huh" | backchannel_only=True | IGNORE | Agent continues |
| Agent silent | "Yeah." | backchannel_only=True | RESPOND | Acknowledge |

---

## STT Transcript Handling

### STT Variations Problem

Different STT providers return different transcriptions for the same audio:

| Audio | Deepgram | Whisper | Google | Azure |
|-------|----------|---------|--------|-------|
| "yeah" | "Yeah." | "Yeah" | "yeah" | "Yeah." |
| "okay" | "Okay." | "OK" | "okay" | "Okay." |
| "uh-huh" | "Uh-huh." | "Uh huh" | "uh huh" | "Uh-huh" |
| "mm-hmm" | "Mm-hmm." | "Mm hmm" | "mm-hmm" | "Mm hmm" |

### Solution: Multi-Layer Matching

```python
# Layer 1: Word tokenization with punctuation stripping
words = [word.lower().strip(".,!?;:\"'") for word in transcript.split()]
# "Yeah." → ["yeah"]

# Layer 2: Individual word matching
matched = [w for w in words if w in backchannel_words]

# Layer 3: Multi-word phrase matching
transcript_lower = transcript.lower()
for phrase in backchannel_words:
    if " " in phrase and phrase in transcript_lower:
        matched.append(phrase)

# Layer 4: Full transcript matching (handles "Yeah." → "yeah")
full_cleaned = transcript_lower.strip().strip(".,!?;:\"'").strip()
if full_cleaned in backchannel_words:
    matched.append(full_cleaned)
```

### Comprehensive Word List

To handle STT variations, we include multiple spellings:

```python
DEFAULT_BACKCHANNEL_WORDS = {
    # Yeah variations
    "yeah", "yea", "ya", "yah", "yeh", "yeaah", "yeahh",
    
    # Okay variations
    "okay", "ok", "okey", "kay", "k", "kk",
    
    # Alright variations
    "alright", "all right", "aight",
    
    # Agreement sounds with variations
    "mm-hmm", "mm hmm", "mmhmm", "mhm", "mmm",
    "uh-huh", "uh huh", "uhuh",
    
    # Hesitation markers with variations
    "uh", "uhh", "uhhh",
    "um", "umm", "ummm",
    "hmm", "hm", "hmmm",
}
```

---

## Trade-offs and Design Decisions

### Trade-off 1: Latency vs Accuracy

**Without backchannel detection:**
- ✅ Instant interruption (~200ms from VAD)
- ❌ False positives (backchannels interrupt)

**With backchannel detection:**
- ✅ Accurate classification
- ❌ Added latency (~200-500ms for STT)

**Decision:** Accept latency for accuracy. Users prefer a slightly delayed but correct response over instant but wrong behavior.

### Trade-off 2: Strict vs Permissive Matching

**Strict matching:**
```python
# Only exact matches
if transcript.lower() == "yeah":
    return IGNORE
```
- ❌ Misses "Yeah.", "yeah!", "ya"

**Permissive matching:**
```python
# Multiple layers of matching
if any(word in backchannel_words for word in tokenize(transcript)):
    return IGNORE
```
- ✅ Catches variations
- ❌ Might match unintended phrases

**Decision:** Use permissive matching with comprehensive word lists.

### Trade-off 3: Default On vs Default Off

**Default On:**
```python
interrupt_handler = InterruptHandler() if NOT_GIVEN else handler
```
- ✅ Users get backchannel detection automatically
- ❌ Might surprise users expecting old behavior

**Default Off:**
```python
interrupt_handler = None if NOT_GIVEN else handler
```
- ✅ Backward compatible
- ❌ Users must explicitly enable

**Decision:** Default On - backchannel detection improves UX for most use cases.

### Trade-off 4: VAD Behavior

**Option A: VAD interrupts immediately, STT can resume**
- ✅ Responsive to real interrupts
- ❌ Agent stops briefly even for backchannels

**Option B: VAD defers to STT entirely**
- ✅ No false interruptions
- ❌ Real interrupts delayed by STT latency

**Decision:** Option B - defer to STT. The slight delay on real interrupts is less disruptive than constant false interruptions.

---

## Bug Fixes and Improvements

This section documents the key bug fixes made to ensure backchannels don't cause any agent speech interruption.

### Bug Fix #1: Wait for Transcript Before Deciding

**Problem:** When VAD detected speech and `_interrupt_by_audio_activity()` was called without a transcript, the code would fall through to the pause/interrupt logic.

**File:** `agent_activity.py` - `_interrupt_by_audio_activity()`

**Fix:**
```python
if interrupt_handler is not None and self._current_speech is not None:
    # KEY FIX: No transcript yet? Return early, wait for STT
    if not text:
        return  # Don't make any decision without transcript
```

### Bug Fix #2: Handle All Actions Explicitly

**Problem:** The RESPOND action would fall through to the pause/interrupt code, causing pauses for speech that wasn't a backchannel but also wasn't a command.

**File:** `agent_activity.py` - `_interrupt_by_audio_activity()`

**Fix:**
```python
if analysis.action == InterruptAction.IGNORE:
    # Clear paused state, resume audio
    if self._paused_speech is not None:
        if self._session.output.audio and self._session.output.audio.can_pause:
            self._session.output.audio.resume()
            self._session._update_agent_state("speaking")
        self._paused_speech = None
    if self._false_interruption_timer is not None:
        self._false_interruption_timer.cancel()
        self._false_interruption_timer = None
    return

elif analysis.action == InterruptAction.RESPOND:
    return  # Don't fall through to pause/interrupt

# Only INTERRUPT action falls through to pause/interrupt logic
```

### Bug Fix #3: Prevent `_interrupt_paused_speech()` for Backchannels

**Problem:** `on_final_transcript()` unconditionally called `_interrupt_paused_speech()` which could interrupt the agent's speech even for backchannels.

**File:** `agent_activity.py` - `on_final_transcript()`

**Fix:**
```python
# Check if this is a backchannel BEFORE processing
is_backchannel = False
if opt.interrupt_handler is not None and transcript_text:
    analysis = opt.interrupt_handler.analyze(transcript_text, agent_state)
    is_backchannel = analysis.action == InterruptAction.IGNORE

# ... existing code ...

# Only interrupt paused speech if NOT a backchannel
if not is_backchannel:
    self._interrupt_paused_speech_task = asyncio.create_task(
        self._interrupt_paused_speech(old_task=self._interrupt_paused_speech_task)
    )
```

### Bug Fix #4: Prevent New Reply Generation for Backchannels

**Problem:** `on_end_of_turn()` would trigger new reply generation even for backchannels, causing the agent to stop and respond.

**File:** `agent_activity.py` - `on_end_of_turn()`

**Fix:**
```python
def on_end_of_turn(self, info: _EndOfTurnInfo) -> bool:
    # Check for backchannels at start
    if opt.interrupt_handler is not None and info.new_transcript:
        analysis = opt.interrupt_handler.analyze(info.new_transcript, agent_state)
        if analysis.action == InterruptAction.IGNORE:
            logger.debug("backchannel detected in on_end_of_turn, ignoring turn")
            return False  # Don't generate new reply
    
    # ... continue with normal turn handling ...
```

### Summary of Fixes

| Fix | Location | Issue | Solution |
|-----|----------|-------|----------|
| #1 | `_interrupt_by_audio_activity()` | No transcript → fell through to pause | Return early if no transcript |
| #2 | `_interrupt_by_audio_activity()` | RESPOND/IGNORE → fell through | Handle each action explicitly |
| #3 | `on_final_transcript()` | `_interrupt_paused_speech()` always called | Track `is_backchannel`, skip if true |
| #4 | `on_end_of_turn()` | New reply generated for backchannels | Check backchannel, return False if IGNORE |

### Result

After these fixes, when a user says a backchannel word like "yeah" while the agent is speaking:

1. ✅ Agent audio continues playing without any pause
2. ✅ Agent text continues displaying in UI without stopping
3. ✅ No new reply is generated
4. ✅ User state transitions normally (speaking → listening)
5. ✅ `backchannel_detected` event is emitted for observability

---

## Performance Considerations

### Memory Usage

```python
# Word sets are stored as Python sets (O(1) lookup)
backchannel_words: set[str]  # ~100 words × ~10 bytes = ~1KB
command_words: set[str]      # ~50 words × ~10 bytes = ~500 bytes

# Pre-cached phrase separation (for O(1) single-word lookup)
_backchannel_singles: set[str]  # Single words (no spaces)
_backchannel_phrases: list[str]  # Multi-word phrases
_command_singles: set[str]
_command_phrases: list[str]
```

**Total overhead:** ~3KB per InterruptHandler instance (negligible).

### CPU Usage - Optimized Time Complexity

The `analyze()` method has been optimized for performance:

```python
# analyze() complexity (OPTIMIZED):
# - Tokenization: O(n) where n = transcript length
# - Single-word matching: O(min(w, b)) using set intersection
# - Multi-word phrase matching: O(p) where p = phrase count (typically few)
# - Full transcript check: O(1) set lookup

# OLD (naive):
# - Word matching: O(w × b) for each word in transcript checking all backchannels

# NEW (optimized):
# - Word matching: O(min(w, b)) using set intersection: word_set & self._backchannel_singles
```

**Optimization Details:**

```python
# Pre-cached phrase separation in __init__:
def _rebuild_phrase_cache(self) -> None:
    self._backchannel_singles = {w for w in self.backchannel_words if " " not in w}
    self._backchannel_phrases = [w for w in self.backchannel_words if " " in w]
    self._command_singles = {w for w in self.command_words if " " not in w}
    self._command_phrases = [w for w in self.command_words if " " in w]

# In analyze():
word_set = set(words)  # O(w)
matched_backchannels = list(word_set & self._backchannel_singles)  # O(min(w, b))
matched_commands = list(word_set & self._command_singles)  # O(min(w, c))

# Only iterate over multi-word phrases (typically very few)
for phrase in self._backchannel_phrases:  # O(p) where p << b
    if phrase in transcript_lower:
        matched_backchannels.append(phrase)
```

**Benchmark (typical):**
- Transcript: "Yeah." (1 word)
- analyze() time: ~0.03ms (improved from ~0.05ms)

### Network Impact

The backchannel detection itself adds **no network calls**. The latency comes from waiting for STT, which would happen anyway.

---

## Testing and Debugging

### Debug Logging

Enable debug logging to see backchannel analysis:

```bash
python my_agent.py dev --log-level debug
```

**Log output example:**

```
DEBUG - VAD: deferring to STT for backchannel analysis - speech_duration=0.45
DEBUG - backchannel analysis result - transcript="Yeah." agent_state="speaking" action="ignore" is_backchannel_only=True matched_words=["yeah"]
DEBUG - backchannel detected, ignoring interrupt - transcript="Yeah." matched_words=["yeah"] confidence=1.0
```

### Event Listener Testing

```python
@session.on("backchannel_detected")
def on_backchannel(ev):
    print(f"[BACKCHANNEL] transcript='{ev.transcript}'")
    print(f"             action={ev.action}")
    print(f"             is_backchannel_only={ev.is_backchannel_only}")
    print(f"             matched_words={ev.matched_words}")
```

### Unit Testing

```python
def test_backchannel_detection():
    handler = InterruptHandler()
    
    # Test backchannel detection
    result = handler.analyze("Yeah.", agent_state="speaking")
    assert result.action == InterruptAction.IGNORE
    assert result.is_backchannel_only == True
    assert "yeah" in result.matched_words
    
    # Test command detection
    result = handler.analyze("Stop!", agent_state="speaking")
    assert result.action == InterruptAction.INTERRUPT
    assert result.has_command_words == True
    
    # Test mixed input (command wins)
    result = handler.analyze("Yeah, wait", agent_state="speaking")
    assert result.action == InterruptAction.INTERRUPT
    
    # Test agent not speaking (no ignore)
    result = handler.analyze("Yeah.", agent_state="listening")
    assert result.action == InterruptAction.RESPOND
```

### Troubleshooting Checklist

| Issue | Check | Solution |
|-------|-------|----------|
| Backchannels still interrupt | Check logs for `action` | Add word to backchannel_words |
| Commands don't interrupt | Check if in command_words | Add word to command_words |
| No analysis happening | Check `interrupt_handler` not None | Verify configuration |
| STT variations missed | Check exact transcript | Add variations to word list |
| Agent pauses briefly on backchannels | Check `_paused_speech` state in logs | Ensure fixes #1-#4 are applied |
| Agent text stops mid-sentence | Check `on_final_transcript()` | Ensure `is_backchannel` check exists |
| New reply generated on backchannel | Check `on_end_of_turn()` | Ensure backchannel check returns False |

---

## Future Improvements

### 1. Machine Learning Classification

Replace word lists with ML model:

```python
class MLInterruptHandler(InterruptHandler):
    def __init__(self, model_path: str):
        self.model = load_model(model_path)
    
    def analyze(self, transcript: str, ...) -> InterruptAnalysis:
        # Use ML model for classification
        prediction = self.model.predict(transcript)
        return InterruptAnalysis(
            action=prediction.action,
            confidence=prediction.confidence,
            ...
        )
```

### 2. Acoustic Features

Use audio features, not just text:

```python
def analyze(self, transcript: str, audio_features: AudioFeatures) -> InterruptAnalysis:
    # Consider:
    # - Speech duration
    # - Pitch contour (rising = question?)
    # - Energy level
    # - Speaking rate
```

### 3. Contextual Analysis

Consider conversation context:

```python
def analyze(self, transcript: str, chat_history: ChatContext) -> InterruptAnalysis:
    # Did agent just ask a question? User response might not be backchannel
    # Is this a clarification context? "What?" might be appropriate
```

### 4. User Adaptation

Learn user's backchannel patterns:

```python
class AdaptiveInterruptHandler(InterruptHandler):
    def __init__(self):
        self.user_patterns = {}  # user_id -> word frequencies
    
    def learn(self, user_id: str, transcript: str, was_backchannel: bool):
        # Update user-specific patterns
        pass
    
    def analyze(self, transcript: str, user_id: str, ...) -> InterruptAnalysis:
        # Use user-specific model
        pass
```

### 5. Configurable Sensitivity

Allow tuning via configuration:

```python
handler = InterruptHandler(
    sensitivity="high",  # More permissive backchannel detection
    # or
    sensitivity="low",   # Only obvious backchannels ignored
)
```

---

## Conclusion

The backchannel detection implementation provides intelligent filtering of user interruptions by:

1. **Deferring VAD interrupts** to wait for STT transcription
2. **Analyzing transcripts** using comprehensive word lists
3. **Making context-aware decisions** based on agent state
4. **Providing observability** through events and logging

The trade-off of added latency (~200-500ms) for improved accuracy is appropriate for conversational AI, where natural interaction is more important than raw speed.

The modular design allows:
- Easy customization via word lists
- Complete disabling if needed
- Future extension with ML-based classification

---

## Appendix: Complete Word Lists

### Backchannel Words (Full List)

```python
{
    # Yeah variations
    "yeah", "yea", "ya", "yah", "yeh", "yeaah", "yeahh",
    
    # Yes variations
    "yep", "yup", "yes", "yess",
    
    # Okay variations
    "okay", "ok", "okey", "okk", "kay", "k", "kk", "okaay",
    "alright", "all right", "aight",
    
    # Sure variations
    "sure", "for sure", "sure thing",
    
    # Agreement sounds
    "uh-huh", "uh huh", "uhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm", "mmm",
    "hmm", "hm", "hmmm",
    
    # Hesitation markers
    "uh", "uhh", "uhhh",
    "um", "umm", "ummm",
    "ah", "ahh",
    "oh", "ohh",
    
    # Affirmatives
    "right", "rite",
    
    # Understanding phrases
    "i see", "got it", "gotcha", "i got it",
    "makes sense", "understood",
    "copy that", "all good",
    
    # Positive acknowledgments
    "perfect", "nice", "cool", "great", "awesome",
    "interesting", "no problem",
    
    # Agreement phrases
    "you're right", "that's right", "i agree",
    "totally", "exactly", "absolutely", "definitely",
    "indeed", "quite",
    
    # Continuation signals
    "go ahead", "please continue", "go on", "continue",
}
```

### Command Words (Full List)

```python
{
    # Stop commands
    "wait", "hold on", "stop", "pause",
    "hold it", "hold up",
    
    # Negation
    "no", "nope", "don't", "don't do that",
    "cancel", "never mind", "never",
    "forget it", "ignore that",
    "skip that", "skip it",
    
    # Navigation
    "back up", "rewind",
    "again", "repeat",
    
    # Speed control
    "slower", "faster",
    "louder", "quieter", "quieter please",
    "speak up",
    
    # Clarification
    "what", "huh", "pardon",
    "come again", "say again", "say that again",
    
    # Redo requests
    "redo", "change that", "different",
    "something else", "alternative",
    "try again", "one more time",
    "rephrase", "rephrase that",
    
    # Explanation requests
    "explain", "clarify", "say it differently",
    "summarize",
    
    # Restart
    "start over", "begin again",
    "let's start over", "restart",
}
```

---

## Running the Agent

This section provides step-by-step instructions for setting up and running a voice agent with backchannel detection using LiveKit Cloud.

### Prerequisites

Before running the agent, ensure you have:

1. **Python 3.10+** installed
2. **LiveKit Cloud Account** - Sign up at [cloud.livekit.io](https://cloud.livekit.io)
3. **API Keys** for your chosen providers:
   - LiveKit API Key and Secret (from LiveKit Cloud dashboard)
   - STT provider key (e.g., Deepgram)
   - LLM provider key (e.g., OpenAI)
   - TTS provider key (e.g., OpenAI, ElevenLabs)

### Step 1: Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/Abdiitb/agents-assignment.git
cd agents-assignment

# Install uv (Python package manager) if not already installed
pip install uv

# Sync dependencies using uv (this creates .venv and installs all packages)
uv sync

# Activate the virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On Windows (CMD):
.\.venv\Scripts\activate.bat

# On Linux/macOS:
source .venv/bin/activate
```

### Step 2: Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
# Create the .env file
touch .env  # Linux/macOS
# Or on Windows PowerShell:
New-Item -Path .env -ItemType File
```

Add the following contents to your `.env` file:

```env
# LiveKit Cloud Credentials
# Get these from https://cloud.livekit.io -> Settings -> Keys
LIVEKIT_URL=wss://your-project-name.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxx
LIVEKIT_API_SECRET=your-api-secret-here

# OpenAI API Key (for LLM and TTS)
# Get from https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-openai-key-here

# Deepgram API Key (for STT)
# Get from https://console.deepgram.com/
DEEPGRAM_API_KEY=your-deepgram-key-here

# Optional: ElevenLabs API Key (alternative TTS)
# ELEVENLABS_API_KEY=your-elevenlabs-key-here

# Optional: Anthropic API Key (alternative LLM)
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Step 3: Run the Example Agent

Start the voice agent with backchannel detection:

```bash
# Run the example agent
uv run examples/voice_agents/voice_agent_with_backchannels.py start
```

### Step 4: Connect via LiveKit Playground

1. Open your browser and go to [LiveKit Agents Playground](https://agents-playground.livekit.io/)
2. Click on **"Connect"** in the top right
3. Select your LiveKit Cloud project from the dropdown
4. Click **"Connect"** to join the room
5. Allow microphone access when prompted
6. Start talking to test the agent!

### Step 5: Test Backchannel Detection

While the agent is speaking, try these phrases:

| Say This | Expected Behavior |
|----------|-------------------|
| "yeah" | Agent **continues** speaking |
| "mm-hmm" | Agent **continues** speaking |
| "okay" | Agent **continues** speaking |
| "uh-huh" | Agent **continues** speaking |
| "stop" | Agent **stops** speaking |
| "wait" | Agent **stops** speaking |
| "hold on" | Agent **stops** speaking |

### Troubleshooting

#### Error: "LIVEKIT_URL not set"

Make sure your `.env` file is in the correct directory and contains:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
```

#### Error: "API key not valid"

Check that your API keys are correct:
```bash
# PowerShell - Check if keys are loaded
echo $env:OPENAI_API_KEY
echo $env:DEEPGRAM_API_KEY
```

#### Error: "Rate limit exceeded (429)"

You've hit API rate limits. Wait a few minutes and try again, or check your plan limits.

#### Backchannels Not Working

1. Enable debug logging: `$env:LIVEKIT_LOG_LEVEL = "DEBUG"`
2. Look for logs containing "backchannel analysis result"
3. Check the transcript and matched_words to see what STT returned
4. Add missing word variations to the handler if needed

#### No Audio Input

- Check microphone permissions in your browser
- Ensure the correct microphone is selected
- Try the console mode to test with local audio

### Example: Custom Backchannel Handler

```python
# Create a custom handler with additional words
custom_handler = InterruptHandler(
    min_interrupt_duration=200,  # ms
    min_interruption_words=1,
)

# Add custom backchannel words
custom_handler.add_backchannel_word("roger")
custom_handler.add_backchannel_word("copy")
custom_handler.add_backchannel_word("affirmative")

# Add custom command words
custom_handler.add_command_word("abort")
custom_handler.add_command_word("halt")

# Use in session
session = AgentSession(
    stt=deepgram.STT(),
    llm=openai.LLM(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    interrupt_handler=custom_handler,
)
```

### Example: Disable Backchannel Detection

```python
# Disable backchannel detection entirely
session = AgentSession(
    stt=deepgram.STT(),
    llm=openai.LLM(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    interrupt_handler=None,  # Backchannels will interrupt
)
```

### Verifying Backchannel Detection is Working

Add this event listener to see real-time analysis:

```python
@session.on("backchannel_detected")
def on_backchannel(ev):
    print("=" * 50)
    print(f"Transcript: '{ev.transcript}'")
    print(f"Action: {ev.action}")
    print(f"Is Backchannel Only: {ev.is_backchannel_only}")
    print(f"Has Command Words: {ev.has_command_words}")
    print(f"Matched Words: {ev.matched_words}")
    print(f"Confidence: {ev.confidence:.2f}")
    print("=" * 50)
```

When you say "yeah" while the agent is speaking, you should see:

```
==================================================
Transcript: 'Yeah.'
Action: ignore
Is Backchannel Only: True
Has Command Words: False
Matched Words: ['yeah']
Confidence: 1.00
==================================================
```

And the agent will continue speaking uninterrupted!
