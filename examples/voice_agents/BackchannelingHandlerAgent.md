# Contextual Interruption Handler for Voice Agents

This project provides a context-aware speech manager for voice agents, enabling more natural, human-like conversations. It solves the common problem where a voice agent abruptly stops speaking when it detects simple listening cues from the user, such as "yeah," "okay," or "uh-huh."

This handler acts as a gatekeeper for the agent's interruption system. It analyzes user input in real-time, considering both the agent's state (speaking or silent) and the content of the user's speech to decide whether to interrupt.

## Key Features

*   **Context-Aware Logic:** The handler behaves differently depending on the situation. It intelligently ignores affirmations while the agent is speaking but correctly interprets them as valid input when the agent is silent and waiting for a response.

*   **Robustness in Mixed Scenarios:** The system is designed to handle complex cases gracefully. For instance, in an input like "Yeah, wait a second," it prioritizes the "wait" command over the "Yeah" affirmation, ensuring the agent stops immediately as a user would expect.

*   **Clean, Decoupled Design:** All filtering logic is encapsulated within a standalone `AgentSpeechManager` class. This keeps the main agent code clean and makes the handler easy to maintain and integrate into other projects.

*   **Simple Configuration:** The words that trigger interruptions or are ignored can be easily customized through a `.env` file, without needing to modify the source code.

## A Note on Implementation

This solution works by attaching to non-public, internal methods of the `AgentSession`. This approach is powerful but inherently fragile and may be affected by future updates to the `livekit-agents` library. A more robust, long-term solution would involve public APIs for custom interruption handling.

## How It Works

The system's behavior can be summarized by the following logic:

| User Input           | Agent State   | Behavior  | Result                                        |
| -------------------- | ------------- | --------- | --------------------------------------------- |
| "Yeah", "Ok", "Hmm"  | Speaking      | **Ignore**    | The agent continues speaking without a pause. |
| "Wait", "Stop", "No" | Speaking      | **Interrupt** | The agent stops speaking immediately.         |
| "Yeah", "Ok", "Hmm"  | Silent        | **Respond**   | The agent treats the input as a valid turn.   |
| "Start", "Hello"     | Silent        | **Respond**   | The agent engages in normal conversation.     |

## Setup and Usage

Follow these steps to run the agent.

#### Prerequisites

*   Python 3.9+
*   LiveKit, Deepgram, and OpenAI API keys

#### Installation

1.  Clone the repository.
2.  Install the required dependencies:
    ```bash
    pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
    ```

#### Configuration

1.  Create a `.env` file in the root directory.
2.  Add your API keys and define the words for the interruption handler. The ignore words are treated as case-insensitive regular expressions for flexible matching.

    ```
    # LIVEKIT KEYS
    LIVEKIT_API_KEY=...
    LIVEKIT_API_SECRET=...
    LIVEKIT_URL=...

    # SERVICE KEYS
    DEEPGRAM_API_KEY=...
    OPENAI_API_KEY=...

    # Defines words to ignore (as regex) while the agent is speaking
    LIVEKIT_IGNORE_WORDS="yeah?,ok(ay)?,h+m+,right,uh-?huh,aha,yep,uh+,um+,mm-?hmm+,yes,sure,got it,alright,mhm+,yup,correct,gotcha,roger,indeed,exactly,absolutely,understood,see,true,agreed,fine,good,nice,great,wow,oh"

    # Defines words that will always interrupt the agent
    LIVEKIT_INTERRUPT_WORDS="stop,wait,hold,cancel,no,pause"
    ```

## Running your agent

### Testing in terminal

```shell
python3 examples/voice_agents/user_backchanneling_handler_agent.py console
```

Runs your agent in terminal mode, enabling local audio input and output for testing.
This mode doesn't require external servers or dependencies and is useful for quickly validating behavior.

### Developing with LiveKit clients

```shell
python3 examples/voice_agents/user_backchanneling_handler_agent.py dev
```

Starts the agent server and enables hot reloading when files change. This mode allows each process to host multiple concurrent agents efficiently.

The agent connects to LiveKit Cloud or your self-hosted server. Set the following environment variables:
- LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET

You can connect using any LiveKit client SDK or telephony integration.
To get started quickly, try the [Agents Playground](https://agents-playground.livekit.io/).

### Running for production

```shell
python3 examples/voice_agents/user_backchanneling_handler_agent.py start
```

Runs the agent with production-ready optimizations.