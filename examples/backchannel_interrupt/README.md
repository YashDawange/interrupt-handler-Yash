# Backchannel Interrupt Handler Example

This example demonstrates how to implement a "backchannel-aware" interrupt handler for a LiveKit Voice Assistant.
It allows the agent to ignore soft backchannel words (like "yeah", "ok", "hmm") while speaking, but still interrupt on hard keywords (like "stop", "wait") or legitimate interruptions.

## How it works

The logic is implemented in `BackchannelAwareAgent` (subclass of `Agent`) by overriding the `stt_node`.
It filters the STT stream before it reaches the agent's interruption logic.

- **Soft Backchannels**: Words like "yeah", "ok" are ignored if the agent is currently speaking.
- **Hard Interruptions**: Words like "stop", "wait" cause an immediate interruption.
- **Generic Input**: Any other input causes an interruption as usual.
- **Silence**: If the agent is not speaking, all input (including "yeah") is treated as a user turn.

## Configuration

You can configure the behavior using environment variables:

- `BACKCHANNEL_IGNORE`: Comma-separated list of words to ignore (default: "yeah, ok, hmm, ...")
- `BACKCHANNEL_INTERRUPT`: Comma-separated list of words to force interrupt (default: "stop, wait, ...")
- `BACKCHANNEL_INTERRUPT_PHRASES`: Comma-separated list of phrases to force interrupt (default: "wait a second, ...")

## Prerequisites

- LiveKit Server running
- `DEEPGRAM_API_KEY` (for STT)
- `ELEVENLABS_API_KEY` (for TTS)
- `OPENAI_API_KEY` (for LLM)
- `LIVEKIT_URL` and `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`

## Running

1. Install dependencies:
   ```bash
   pip install -e .[examples]
   pip install livekit-plugins-deepgram livekit-plugins-elevenlabs livekit-plugins-openai livekit-plugins-silero
   ```

2. Run the agent:
   ```bash
   python examples/backchannel_interrupt/main.py dev
   ```

3. Connect to the room using a LiveKit client (e.g., https://agents-playground.livekit.io/).

## Testing Scenarios

1. **Ignore Backchannel**: While agent is speaking, say "yeah", "uh-huh". Agent should continue speaking.
2. **Hard Interrupt**: While agent is speaking, say "stop" or "wait". Agent should stop immediately.
3. **Normal Response**: While agent is silent, say "yeah". Agent should respond (e.g., "Great, let's continue").
4. **Mixed**: While agent is speaking, say "yeah but wait". Agent should stop (because of "wait").