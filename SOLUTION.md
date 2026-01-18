## Solution Logic

The mentioned issue is that **Voice Activity Detection (VAD)** reacts faster than **Speech-to-Text (STT)**, which can cause false interruption triggers.

Because VAD fires almost instantly, a raw VAD signal can prematurely cut off the agent’s audio before the system understands *what* the user actually said. To prevent this, the interruption is **buffered** in a `_pending_vad_event` instead of being acted upon immediately.

This buffering allows the system to wait for **interim STT results**, which provide enough semantic context to determine whether the detected sound was:

- A filler or backchannel (e.g., “yeah”, “ok”, “mhm”), or
- A real command that should interrupt the agent

Only after this semantic check does the system decide whether to stop the agent’s speech.

---

## Why We Use Interim Transcripts

Waiting for the **final** transcript to decide whether to interrupt would introduce noticeable latency, making the agent feel unresponsive. Instead, the system relies on **interim transcripts**:

- **Interim Results**  
  Provide sufficient semantic signal to quickly distinguish a command (e.g., “stop”) from a filler (e.g., “yeah”).

- **Early Return**  
  By returning `False` from `on_interim_transcript`, interruptions are blocked immediately when a filler is detected, ensuring the agent’s audio playback is never disturbed.

---

## Intent Resolution Logic

When a transcript becomes available, the **IntentScorer** performs a dual check to resolve the *“Stay vs. Stop”* decision:

1. **Agent State Check**  
   Determines whether the agent is currently speaking or silent.

2. **Semantic Intent Check**  
   Determines whether the user input is a passive backchannel (e.g., “yeah”, “ok”, “mhm”) or a meaningful directive.

If a passive backchannel is detected while the agent is speaking, the system performs a **deep ignore** by short-circuiting the entire pipeline.

---

## Deep Ignore Behavior

When a filler is ignored, the system ensures:

- **UI Suppression**  
  No transcript bubbles are added to the user interface, keeping the visual feed clean.

- **Context Preservation**  
  The filler is never written to the chat history, keeping the LLM context focused on relevant input.

- **Zero LLM Overhead**  
  No LLM call is triggered, minimizing latency and token usage.

By returning `False` from the transcription hooks for fillers, the agent maintains seamless audio playback without the stutters or pauses commonly caused by naive VAD-based interruption logic.

---

## Working

By returning `False` from both the `on_interim_transcript` and `on_final_transcript` hooks, the entire pipeline is **short-circuited** for filler words. This prevents them from:

- **Interrupting Audio**  
  The agent never pauses or stutters because interruption logic is bypassed.

- **Polluting History**  
  Filler words like _“uh-huh”_ never enter the `ChatContext`, saving tokens and keeping the LLM focused on meaningful input.

- **Triggering Responses**  
  Since no transcription event is finalized for fillers, the agent does not accidentally respond to a simple _“Okay.”_

---

## State-Aware Behavior

This state-aware logic ensures that the **same word** (e.g., _“Yeah”_) is:

- **Ignored** while the agent is actively speaking
- **Accepted as valid input** when the agent is silent and waiting for a response