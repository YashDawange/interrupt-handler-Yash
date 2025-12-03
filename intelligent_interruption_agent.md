# Intelligent Interruption Agent

### Summary
- This agent prevents short backchannel words (e.g. "yeah", "ok") from interrupting the agent's spoken output.
- It buffers a short VAD window, runs a fast STT validation, and only forwards audio to the normal interruption pipeline when the utterance is not an ignore word. Backchannels are suppressed and the agent resumes speaking seamlessly.

### Files
- livekit-agents/livekit/agents/voice/intelligent_interruption_agent.py

### Requirements
- Install required packages:
  - `pip install livekit-agents livekit python-dotenv`
  - `pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"`
  - If using local plugins: ensure `livekit.plugins.silero` and `livekit.plugins.openai` are available.
- Set environment variables (OpenAI is used for STT/LLM):
  - OPENAI_API_KEY

### Run the agent in terminal
1. From the folder livekit-agents/livekit/agents/voice run:
    `python intelligent_interruption_agent.py console`
2. Monitor logs in the terminal. INFO / DEBUG messages show detection, suppression and forwarding.

### How the logic works
1. VAD wraps the underlying VAD implementation and buffers a small initial window (configurable, default ~100–150 ms).
2. When speech is detected:
   - The wrapper buffers a short window of frames and assembles the raw audio bytes.
   - A quick STT recognition is executed on that small buffer.
   - If the transcription is an "ignore/backchannel" (matches the IGNORE_WORDS set), the wrapper suppresses forwarding those frames and the agent continues speaking without interruption.
   - If the transcription is not a backchannel, the wrapper forwards the buffered frames to the normal stream and STT + interrupt handling proceed as usual.
3. Additionally a STT wrapper delegates capabilities and events, returning None for backchannel results when necessary so the LiveKit interruption logic does not treat them as valid user turns.

### Configuration
- **IGNORE_WORDS** set in the file are the words considered backchannels.
- **initial_buffer_ms** (VAD wrapper) — shorter buffer → less delay but lower detection; longer buffer → more accurate but more latency (recommended 120–180 ms).
- Logging level — set logger to DEBUG to trace buffer / STT validation / suppression decisions.

### Why this avoids breaking the agent response
- The agent prevents the framework from triggering full interruption immediately on the first VAD spike by validating the short buffered audio first. If the buffered audio is only a backchannel, it is dropped and not forwarded to STT/interrupt path so that TTS is not stopped. If it is real speech, frames are forwarded and the normal interrupt flow occurs.