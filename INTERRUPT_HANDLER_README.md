# Interrupt Handler Agent

This agent demonstrates how to use the `interruption_speech_filter` option to allow users to provide backchanneling feedback (e.g., "yeah", "ok") without interrupting the agent's speech.

## How it works

The `AgentSession` is configured with an `interruption_speech_filter` list containing words that should be ignored when determining if the agent should be interrupted.

```python
    session = AgentSession(
        # ... other options
        interruption_speech_filter=["yeah", "ok", "hmm", "uh-huh", "right"],
    )
```

When the user speaks while the agent is speaking:
1.  VAD detects speech activity.
2.  Normally, this would trigger an immediate interruption (or pause if `resume_false_interruption` is enabled).
3.  With `interruption_speech_filter` configured:
    *   The agent waits for the STT transcript.
    *   If the transcript consists **only** of words in the filter list (ignoring case and punctuation, but preserving hyphens), the interruption is ignored, and the agent continues speaking seamlessly.
    *   If the transcript contains other words (e.g., "Yeah stop" or "Wait"), the agent is interrupted immediately.

## Running the Agent

1.  Ensure you have the necessary API keys set in your environment (e.g., `.env` file):
    *   `LIVEKIT_URL`
    *   `LIVEKIT_API_KEY`
    *   `LIVEKIT_API_SECRET`
    *   `DEEPGRAM_API_KEY`
    *   `OPENAI_API_KEY`

2.  Run the agent:

```bash
python examples/voice_agents/interrupt_handler_agent.py start
```

## Testing Scenarios

1.  **The Long Explanation**: Ask the agent to explain something long. While it speaks, say "Yeah", "Ok", "Uh-huh". The agent should continue speaking without pausing.
2.  **The Correction**: While the agent speaks, say "No stop". The agent should stop immediately.
3.  **The Mixed Input**: While the agent speaks, say "Yeah wait". The agent should stop.
4.  **The Passive Affirmation**: When the agent is silent, say "Yeah". The agent should respond (e.g., "Is there anything else?").

## Troubleshooting

*   **Interruption happens on "Uh huh"**: If your STT returns "Uh huh" (two words) but you only added "uh-huh" (one word) to the filter, it will interrupt. Add both forms if unsure, or ensure your STT provider uses standardized formatting.
