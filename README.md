
# Intelligent Interruption Handling Agent Feature

This project implements a context-aware voice agent using LiveKit, Deepgram, and Silero VAD. The core feature is a custom Logic Layer that distinguishes between "passive backchanneling" (listener feedback) and "active interruption" (commands) based on the agent's current speaking state.

## Project Goal
To solve the problem of over-sensitive VAD where agents stop speaking when a user says "Yeah" or "Uh-huh". This agent implements a strict logic matrix to ensure seamless conversation flow.

## Setup & Installation

### 1. Prerequisites
* Python 3.9+
* A Deepgram API Key (for STT/TTS)
* A LiveKit Cloud Project 

### 2. Install Dependencies
```bash
pip install -r requirements.txt
````

(Ensure `livekit-agents`, `livekit-plugins-deepgram`, `livekit-plugins-silero`, and `python-dotenv` are installed)

### 3\. Environment Configuration

Create a `.env` file in the root directory:

```ini
LIVEKIT_URL="wss://<your-project>.livekit.cloud"
LIVEKIT_API_KEY="<your-api-key>"
LIVEKIT_API_SECRET="<your-api-secret>"
DEEPGRAM_API_KEY="<your-deepgram-key>"
```

## How to Run

1.  Start the agent in development mode:
    ```bash
    python agent.py dev
    ```
2.  Connect to the agent using the LiveKit Agents Playground.
3.  Wait for the audio prompt: "System Ready. Say Start."

## Logic Implementation

The interruption logic is implemented within the agent's event loop, intercepting transcriptions before they trigger a state change.

### The Logic Matrix

The system filters user input based on two factors: Input Content vs. Agent State.

| User Says | Agent State | System Action | Logic Rule |
| :--- | :--- | :--- | :--- |
| "Yeah" / "Okay" | Speaking | IGNORE | Backchannel detected. Agent continues speaking seamlessly. |
| "Stop" / "Wait" | Speaking | INTERRUPT | Command detected. Agent stops immediately. |
| "Start" / "Okay" | Silent | RESPOND | Valid trigger. Agent resumes the monologue. |
| "Mixed Input" | Speaking | INTERRUPT | E.g., "Yeah wait". Since "wait" is not ignored, the whole phrase interrupts. |

### Code Structure

  * **IGNORE\_WORDS**: A configurable set of words (e.g., "yeah", "uh-huh") treated as noise during speech.
  * **START\_WORDS**: A set of words (e.g., "start", "continue") that trigger the agent to speak when silent.
  * **State Management**: A global `state["is_speaking"]` flag tracks whether the TTS is currently active.
  * **Audio Engine**: A chunked playback system (`play_audio`) allows for granular interruption checks between sentences, ensuring low-latency stopping.

## Testing Methodology

To ensure deterministic verification of the interruption logic, this agent utilizes a fixed audio stream (Deepgram TTS reading a standardized monologue about LiveKit) rather than a generative LLM.

This approach was chosen to:

1.  **Isolate Logic:** Eliminate variable LLM latency ("thinking time") to prove that the interruption handling is instantaneous.
2.  **Reproducibility:** Provide a consistent audio stream to verify that "Yeah" is ignored exactly the same way every time.

**Verified Scenarios:**

  * **Ignore Test:** User says "Yeah" while agent speaks -\> Audio continues.
  * **Interrupt Test:** User says "Stop" -\> Audio cuts off immediately.
  * **Resume Test:** User says "Start" -\> Audio resumes from the correct paragraph.

<!-- end list -->

```
```