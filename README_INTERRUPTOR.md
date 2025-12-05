# LiveKit Intelligent Interruption Handling

This repository contains the solution for the **LiveKit Intelligent Interruption Handling Challenge** [cite: 1].  
It implements a context-aware Voice Agent that solves the "barge-in" problem by distinguishing between passive backchanneling (e.g., "Yeah", "Uh-huh") and active interruptions (e.g., "Stop") [cite: 7-11].

---

## Example

**You:** 
Tell me a really big story.

**Agent:**  
Absolutely! Here’s a long story for you:

---

**The Chronicles of Eldoria**

In a time long forgotten, when magic and mystery wove through the lands like threads of silver light, there lay the vast kingdom of Eldoria. It was a realm of towering mountains, endless forests, and deep, shimmering lakes. Eldoria was ruled by a wise and benevolent queen named Elara, who was beloved by all her subjects

---

**You:**  
Oh,

**Agent:**  
Would you like me to continue

---

**You:**  
Stop.

**Agent:**  
Got it! If you want to hear another story or talk about something else, just let me know!

---

**You:**  
Tell me another very big story.

**Agent:**  
Certainly! Here’s another expansive story for you:

---

**The Voyage of the Starbound**

Long ago, in an age when the stars were still young and the universe a vast, uncharted ocean, there existed

---

**You:**  
Stop.

**Agent:**  
Understood! If you want me to continue or switch topics, just say the word!

---

**You:**  
Continue.

**Agent:**  
Of course! I’ll pick up where I left off:

---

Long ago, in an age when the stars were still young and the universe a vast, uncharted ocean, there was a

---

**You:**  
Wait.

**Agent:**  
No problem! Take your time—just let me know when you’re ready to continue.

---

**You:**  
Humbert.  
Hello?

**Agent:**  
Hello!

---

**You:**  
Hi. How are

**Agent:**  
Hello! I’m doing great, thanks for asking. How about you? How can I assist

---

**You:**  
Bye bye.

**Agent:**  
Goodbye! Feel free to come back anytime. Have a great day!



## Core Logic & Architecture

The solution is implemented in `examples/voice_agents/intelligent_agent.py` as a modular logic layer [cite: 77].  
It subclasses the standard `VoicePipelineAgent` to intercept STT (Speech-to-Text) events before they reach the LLM.

---

### 1. State-Based Filtering [cite: 38]

The agent tracks an internal `_is_speaking` flag to determine how to handle user input:

- **Agent Speaking + "Yeah" (Ignore Word):**  
  Dropped silently. Audio continues without pausing [cite: 32, 54].

- **Agent Speaking + "Stop" (Command):**  
  Triggers an active interruption. Audio stops immediately [cite: 33, 63].

- **Agent Silent + "Yeah":**  
  Treated as a valid conversational turn and forwarded to the LLM [cite: 34, 59].

---

### 2. Latency Synchronization ("Buffer Fix")

To satisfy the requirement that the agent **must NOT stop** on partial inputs [cite: 13], a buffering strategy is added:

- **Problem:**  
  TTS finishes generating audio faster than the user hears it.  
  If `_is_speaking` switches to `False` too early, a late "Yeah" during playback incorrectly triggers interruption.

- **Solution:**  
  The custom `tts_node` adds a **1.5-second delay** in its `finally` block, keeping the agent in a "Logically Speaking" state until audio fully drains from client buffers.

---

### 3. Configurable Ignore List [cite: 37, 78]

A configurable O(1) lookup set for backchannel words:

```python
IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha", "mhm"}
```

## Installation & Setup

### Prerequisites
- Python 3.10+
- LiveKit Cloud project (URL, API Key, Secret)

---

### 1. Install Dependencies

Navigate to the agent folder and install the requirements:

```bash
cd examples/voice_agents
pip install -r requirements.txt
```

(Uses specific protobuf and onnxruntime versions for macOS/Apple Silicon compatibility.)

## 2. Environment Variables

Create a `.env` file inside `examples/voice_agents`:

```
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-secret>
```

---

## 3. macOS Fix (M1/M2/M3)

```bash
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
```

## How to Run

Start the agent in development mode:

```bash
cd examples/voice_agents
python3 basic_agent.py dev
```

## Mock Harness Mode

Because paid API keys (OpenAI / Deepgram) were not available:

- **MockTTS** simulates speech by generating silent audio frames.
- **Verification Loop** injects simulated user events (“Yeah”, “Stop”) into the pipeline to validate interruption logic without a microphone or STT provider.

---

## Logic Matrix Verification

| User Input      | Agent State | Action     | Result                                           |
|-----------------|-------------|------------|--------------------------------------------------|
| "Yeah / Ok"     | Speaking    | IGNORE     | Agent continues; audio does not break            |
| "Stop / Wait"   | Speaking    | INTERRUPT  | Agent stops immediately                          |
| "Yeah wait"     | Speaking    | INTERRUPT  | Contains "wait", so treated as a command         |
| "Yeah / Ok"     | Silent      | RESPOND    | Agent processes the input and replies            |

## File Structure

```
examples/voice_agents/intelligent_agent.py   # New: core interruption filtering + TTS sync logic
examples/voice_agents/basic_agent.py         # Modified: runs Intelligent Agent + Mock Harness
examples/voice_agents/requirements.txt   
```