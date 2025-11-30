# Smart Interruption Agent

A context-aware LiveKit Voice Agent that intelligently handles interruptions. It distinguishes between passive backchanneling (e.g., "yeah", "uh-huh") and active commands (e.g., "stop", "wait"), ensuring a natural conversational flow.

## Features

-   **Context-Aware**: Behaves differently when speaking vs. listening.
-   **Smart Interruption**: Ignores filler words ("yeah", "ok") while speaking, but stops for commands ("stop") or questions.
-   **No Stuttering**: Uses a logic-layer approach to prevent the agent from cutting off audio on false positives.
-   **Configurable**: Customize backchannel words, command words, and timing parameters via environment variables.

## Setup

1.  **Environment Variables**:
    Create a `.env` file with your keys:
    ```env
    LIVEKIT_URL=...
    LIVEKIT_API_KEY=...
    LIVEKIT_API_SECRET=...
    DEEPGRAM_API_KEY=...
    GOOGLE_API_KEY=...
    CARTESIA_API_KEY=...
    
    # Optional Configuration
    COOLDOWN_MS=300
    BUFFER_CAP=20
    DUP_WINDOW_S=0.75
    ```

2.  **Run the Agent**:
    ```bash
    python main.py start
    ```

## Logic Overview

The agent uses a `TurnManager` to decide the strategy based on:
1.  **User Intent**: Classified as `BACKCHANNEL`, `COMMAND`, or `QUERY`.
2.  **Agent State**: `SPEAKING` or `LISTENING`.

| User Input | Agent State | Strategy | Result |
| :--- | :--- | :--- | :--- |
| "Yeah" | Speaking | **IGNORE** | Agent continues speaking seamlessly. |
| "Stop" | Speaking | **INTERRUPT** | Agent stops immediately. |
| "Yeah" | Listening | **RESPOND** | Agent acknowledges (e.g., "Yes?"). |
| "Hello" | Listening | **RESPOND** | Normal conversation. |

## Architecture

-   `main.py`: Entry point and event loop. Handles the `allow_interruptions=False` logic to prevent VAD cutoffs.
-   `dialogue.py`: Contains `SpeechIntentClassifier` and `TurnManager` for core logic.
-   `config.py`: Configuration management.
-   `utils.py`: Logging and transcript deduplication.
