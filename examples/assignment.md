# Intelligent Interruption Handling for LiveKit Agent

## Overview
This repository implements a context-aware interruption logic layer for the LiveKit Voice Agent. It solves the common problem where backchanneling (e.g., "Yeah", "Uh-huh") inadvertently interrupts the AI while it is speaking

The solution differentiates between **Passive Acknowledgement** (ignored while speaking) and **Active Interruption** (commands like "Stop" or "Wait")

##  Configuration Note (Testing vs. Production)
* **Submission Intent:** This project is designed to run with **OpenAI GPT-4o-mini** (STT/LLM/TTS) as per the assignment default.
* **Testing Configuration:** To utilize free tiers during local development and avoid complex service account setups, the agent was tested using a **Hybrid Configuration**:
    * **Brain (LLM):** Google Gemini Pro (via `livekit-plugins-google`)
    * **Ears (STT) & Voice (TTS):** Deepgram (via `livekit-plugins-deepgram`)
**Logic Validity:** The core interruption logic (VAD/STT filtering) operates independently of the provider and functions identically on both configurations

## Key Features
* **Context Awareness:** Ignores filler words *only* when the agent is speaking.Responds to them normally when the agent is silent
* [cite_start]**Latency Handling:** Prevents "false start" interruptions where VAD triggers before STT has decoded the filler word
* [cite_start]**Semantic Filtering:** Correctly interprets mixed sentences (e.g., "Yeah, wait") as interruptions
* [cite_start]**Configurable:** The ignore list can be modified via environment variables

## Logic Matrix
The agent adheres to the following behavioral matrix

| User Input | Agent State | Behavior | Logic |
| :--- | :--- | :--- | :--- |
| "Yeah / Ok" | Speaking | **IGNORE** | Agent continues speaking seamlessly. |
| "Stop / No" | Speaking | **INTERRUPT** | Agent stops immediately. |
| "Yeah wait" | Speaking | **INTERRUPT** | Mixed input treated as a command. |
| "Yeah / Ok" | Silent | **RESPOND** | Treated as valid conversation input. |

## Installation & Setup

1.  **Clone and Install Dependencies:**
    ```bash
    git clone <your-repo-url>

    cd agents-assignment
    pip install -r requirements.txt
    ```

2.  **Environment Configuration:**
    Create a `.env` file. For the **Hybrid Testing Setup**, use the following keys:
    
    ```bash
    # LiveKit Local Server
    LIVEKIT_URL=ws://localhost:7880
    LIVEKIT_API_KEY=devkey
    LIVEKIT_API_SECRET=secret
    
    # Hybrid Keys (Free Tier Testing)
    GOOGLE_API_KEY=AIzaSy...         # For LLM (Gemini)
    DEEPGRAM_API_KEY=288b...         # For STT/TTS
    
    # Submission Keys (If reverting to OpenAI)
    OPENAI_API_KEY=sk-...
    
    # Configurable Logic
    INTERRUPTION_IGNORE_WORDS=["yeah", "ok", "got it", "right", "hmm", "uh-huh"]
    ```

3.  **Run the Agent:**
    ```bash
    python intelligent_interruption_agent.py dev
    ```

## Implementation Details

### The Logic Layer
The core logic is implemented by subclassing `AgentActivity` and overriding `_interrupt_by_audio_activity`.

1.  **VAD Trigger:** When the Voice Activity Detector (VAD) detects speech, it pauses the audio stream by default.
2.  **STT Validation:** We intercept this signal and check the `current_transcript` from the STT provider.
3.  **Filtering:**
    * We normalize the text (remove punctuation, lowercase).
    * We compare the tokens against the `IGNORE_WORDS` set.
    * If **all** detected words are in the ignore list, we return early, preventing the `interrupt()` signal from firing.
4.  **Mixed Inputs:** If the transcript contains "Yeah wait", the word "wait" fails the allowlist check, allowing the interruption to proceed.

### Handling VAD/STT Latency
VAD is significantly faster than STT. To prevent the agent from "stuttering" (pausing for VAD, then resuming after realizing it was just "yeah"):
* The logic rejects interruptions if the transcript is empty/null.
* This forces the agent to wait for the first STT token before deciding to stop speaking.