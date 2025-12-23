# Voice Agents Examples

This directory contains a collection of voice-based agent examples demonstrating various capabilities and integrations with the LiveKit Agents framework.

## Table of Contents

### Getting Started
- [`basic_agent.py`](./basic_agent.py) — A fundamental voice agent with metrics collection

### Tool Integration & Function Calling
- [`annotated_tool_args.py`](./annotated_tool_args.py) — Using Python type annotations for tool arguments
- [`dynamic_tool_creation.py`](./dynamic_tool_creation.py) — Creating and registering tools dynamically at runtime
- [`raw_function_description.py`](./raw_function_description.py) — Using raw JSON schema definitions for tool descriptions
- [`silent_function_call.py`](./silent_function_call.py) — Executing function calls without verbal responses to the user
- [`long_running_function.py`](./long_running_function.py) — Handling long-running function calls with interruption support

### Real-time Models
- [`weather_agent.py`](./weather_agent.py) — OpenAI Realtime API with function calls for weather information
- [`realtime_video_agent.py`](./realtime_video_agent.py) — Google Gemini with multimodal video and voice capabilities
- [`realtime_joke_teller.py`](./realtime_joke_teller.py) — Amazon Nova Sonic real-time model with function calls
- [`realtime_load_chat_history.py`](./realtime_load_chat_history.py) — Loading previous chat history into real-time models
- [`realtime_turn_detector.py`](./realtime_turn_detector.py) — Using LiveKit's turn detection with real-time models
- [`realtime_with_tts.py`](./realtime_with_tts.py) — Combining external TTS providers with real-time models

### Pipeline Nodes & Hooks
- [`fast-preresponse.py`](./fast-preresponse.py) — Generating quick responses using the `on_user_turn_completed` node
- [`structured_output.py`](./structured_output.py) — Structured data and JSON outputs from agent responses
- [`speedup_output_audio.py`](./speedup_output_audio.py) — Dynamically adjusting agent audio playback speed
- [`timed_agent_transcript.py`](./timed_agent_transcript.py) — Reading timestamped transcripts from `transcription_node`
- [`inactive_user.py`](./inactive_user.py) — Handling inactive users with the `user_state_changed` event hook
- [`resume_interrupted_agent.py`](./resume_interrupted_agent.py) — Resuming agent speech after false interruption detection
- [`toggle_io.py`](./toggle_io.py) — Dynamically toggling audio input/output during conversations

### Multi-agent & AgentTask Use Cases
- [`restaurant_agent.py`](./restaurant_agent.py) — Multi-agent system for restaurant ordering and reservation management
- [`multi_agent.py`](./multi_agent.py) — Collaborative storytelling with multiple specialized agents
- [`email_example.py`](./email_example.py) — Using AgentTask to collect and validate email addresses

### 🔗 MCP & External Integrations
- [`web_search.py`](./web_search.py) — Integrating web search capabilities into voice agents
- [`langgraph_agent.py`](./langgraph_agent.py) — LangGraph integration
- [`mcp/`](./mcp/) — Model Context Protocol (MCP) integration examples
  - [`mcp-agent.py`](./mcp/mcp-agent.py) — MCP agent integration
  - [`server.py`](./mcp/server.py) — MCP server example
- [`zapier_mcp_integration.py`](./zapier_mcp_integration.py) — Automating workflows with Zapier through MCP

### RAG & Knowledge Management
- [`llamaindex-rag/`](./llamaindex-rag/) — Complete RAG implementation with LlamaIndex
- [`chat_engine.py`](./llamaindex-rag/chat_engine.py) — Chat engine integration
- [`query_engine.py`](./llamaindex-rag/query_engine.py) — Query engine used in a function tool
- [`retrieval.py`](./llamaindex-rag/retrieval.py) — Document retrieval

### Specialized Use Cases
- [`background_audio.py`](./background_audio.py) — Playing background audio or ambient sounds during conversations
- [`push_to_talk.py`](./push_to_talk.py) — Push-to-talk interaction
- [`tts_text_pacing.py`](./tts_text_pacing.py) — Pacing control for TTS requests
- [`speaker_id_multi_speaker.py`](./speaker_id_multi_speaker.py) — Multi-speaker identification

### Tracing & Error Handling
- [`langfuse_trace.py`](./langfuse_trace.py) — LangFuse integration for conversation tracing
- [`error_callback.py`](./error_callback.py) — Error handling callback
- [`session_close_callback.py`](./session_close_callback.py) — Session lifecycle management

---

## Voice Agent: Smart Interruption Handling (English + Hinglish)

This example extends the standard voice agent by adding **real-time interruption awareness**.  
It listens to **transcription events** and applies a lightweight semantic filter to:

- **Ignore backchannel / filler** while the agent is speaking (e.g., “yeah”, “haan”, “hmm”)
- **Interrupt immediately** on explicit commands (e.g., “wait”, “stop”, “hold on”)
- **Interrupt on mixed intent** (e.g., “yeah wait a second”) to satisfy “semantic interruption”

> Note: This does **not** modify LiveKit VAD or turn detection. The logic runs at the event layer.

### What changed
- [`basic_agent_interruption.py`](./basic_agent_interruption.py) — Runs the agent and hooks interruption logic into the session.
- [`basic_agent_interruption_handler.py`](./basic_agent_interruption_handler.py) — Classifies ASR text as filler, interrupt, or normal speech.

### Behavior Summary

| User says (while agent is speaking) | Result |
|---|---|
| `yeah`, `okay`, `right`, `uh`, `um`, `hmm`, `haan` | Ignored — agent continues speaking |
| `wait` / `stop` / `hold on` | Immediate interruption |
| `umm okay stop` | Immediate interruption |
| `yeah wait a second` | Interruption (semantic / mixed intent) |
| filler when agent is silent | Treated as normal user input |

### Known Issues / Edge Cases

| Case | Description | Mitigation |
|---|---|---|
| Heavy background noise | Can produce higher-confidence tokens that look like speech | Increase `FILLER_LOW_CONF_THRESHOLD` |
| Very fast interruption phrases | Interruption spoken very quickly after filler | Tune thresholds + add common interrupt phrases |
| Different language filler sets | Defaults support English + Hinglish | Extend lists via `.env` |

### Steps to Test
1. Start the agent in console mode:
   ```bash
   cd agents/examples/voice_agents
   python basic_agent_interruption.py console
  ```
2. Ensure the agent begins speaking (e.g., greeting).

3. While the agent is speaking:
  - Say: "umm hmm haan" - Agent should continue speaking.
  - Say: "wait" or "stop" - Agent should stop immediately.

4. When the agent is silent:
  - Say: "umm" - Agent should treat it as input and respond normally.

#### Configuration 

##### 1. (`.env`)
```env
OPENAI_API_KEY=
ASSEMBLYAI_API_KEY=
CARTESIA_API_KEY=

LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

IGNORED_WORDS=yeah,okay,right,uh,uh-huh,umm,um,hmm,er,ah,uhh,mm,mhm,mmm,haan,haina,achha,acha,arey
HARD_INTERRUPTS=wait,stop,no,hold on,one second,pause,listen,excuse me

FILLER_LOW_CONF_THRESHOLD=0.35
FALSE_INTERRUPT_TIMEOUT=1.0

STT_MODEL=assemblyai/universal-streaming:en
LLM_MODEL=openai/gpt-4.1-mini
TTS_MODEL=cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc

```
##### 2. `requirements.txt`
```bash
pip install -r examples/voice_agents/requirements.txt
```
## 📖 Additional Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [Agents Starter Example](https://github.com/livekit-examples/agent-starter-python)
- [More Agents Examples](https://github.com/livekit-examples/python-agents-examples)