# Backchannel Filter

## How to Run

1. Install dependencies:
   ```bash
   uv sync --all-extras --dev
   ```
   Or with pip:
   ```bash
   pip install livekit-agents[openai,deepgram,cartesia,silero]
   ```

2. Create a `.env` file in the `examples` directory with your API keys:
   ```
   OPENAI_API_KEY=your-key-here
   DEEPGRAM_API_KEY=your-key-here
   CARTESIA_API_KEY=your-key-here
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your-key-here
   LIVEKIT_API_SECRET=your-secret-here
   ```

3. Run the example:
   ```bash
   uv run examples/voice_agents/backchannel_filter_example.py dev
   ```

4. Connect using the LiveKit Playground at https://agents-playground.livekit.io or use console mode:
   ```bash
   uv run examples/voice_agents/backchannel_filter_example.py console
   ```

## How It Works

When the agent is speaking and VAD (Voice Activity Detection) detects that the user started talking, the system gets a transcript from STT (Speech-to-Text). The backchannel filter then looks at this transcript to decide what to do.

If the transcript only has backchannel words like "yeah", "ok", "hmm", or "uh-huh", the filter tells the system to ignore the interruption. The agent keeps talking like nothing happened.

If the transcript has real commands like "stop", "wait", or "no", the agent interrupts immediately. Same thing happens if there are any other words that aren't backchannels - the filter assumes the user actually wants to say something.

When the agent isn't speaking, the filter doesn't do anything. All user input gets treated as normal conversation, even if it's just "yeah" or "ok".

## What Changed

### New Files

- `livekit-agents/livekit/agents/voice/backchannel_filter.py` - The main filter code that checks if something is a backchannel or not
- `examples/voice_agents/backchannel_filter_example.py` - Example showing how to use it

### Modified Files

- `livekit-agents/livekit/agents/voice/agent_session.py` - Added options to turn the filter on/off and customize the backchannel word list
- `livekit-agents/livekit/agents/voice/agent_activity.py` - Added the filter check before interrupting the agent

## Configuration

The filter is on by default. You can customize it when creating an AgentSession:

```python
session = AgentSession(
    vad=silero.VAD.load(),
    llm=openai.LLM(model="gpt-4o-mini"),
    stt=deepgram.STT(),
    tts=cartesia.TTS(),
    enable_backchannel_filter=True,  # Turn it on or off
    backchannel_words=["yeah", "ok", "hmm"],  # Custom list (optional)
)
```

If you don't provide `backchannel_words`, it uses a default list that includes common acknowledgments like "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "right", "sure", "got it", "i see", and more.

## Testing It Out

Once the agent is running, try these scenarios:

**Should be ignored (agent keeps talking):**
- Say "yeah" while agent is speaking
- Say "ok" while agent is speaking
- Say "hmm" while agent is speaking

**Should interrupt (agent stops immediately):**
- Say "stop" while agent is speaking
- Say "wait" while agent is speaking
- Say "yeah but wait" while agent is speaking (has "wait" in it)

**Normal conversation (when agent is silent):**
- Say "yeah" - agent responds normally
- Say "ok" - agent responds normally

## How the Code Works

The filter runs in two places:

1. In `_interrupt_by_audio_activity()` - This gets called when VAD or STT detects user speech. Before interrupting, it checks the transcript with the filter.

2. In `on_end_of_turn()` - This gets called when a user turn is complete. It also checks the transcript to make sure we're not ignoring something important.

The filter itself is pretty simple. It normalizes the text (removes punctuation, lowercases everything), then checks if all the words are in the backchannel list. If they are, it returns true to ignore the interruption. If there's any word that's not a backchannel, or if there's an interruption command, it returns false to let the interruption happen.

## Notes

- The filter only works when the agent is currently speaking
- It doesn't change how VAD or STT work - it just looks at the transcript they produce
- The filter is fast because it uses simple word lookups, no AI models or API calls
- You can turn it off by setting `enable_backchannel_filter=False` if you don't want it
