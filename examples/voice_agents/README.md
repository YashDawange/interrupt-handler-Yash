---

## 🚀 ASSIGNMENT IMPLEMENTATION: Intelligent Interruption Handler

This section documents the implementation of the context-aware interruption handling logic, addressing the **Core Logic & Objectives** and **Strict Requirements** of the assignment.

### 1. Code Architecture and State Awareness

The intelligent handling logic is implemented in `examples/voice_agents/basic_agent.py` by:

* **Creating a new class:** `IntelligentInterruptionHandler` encapsulates the core filtering logic, ensuring **Code Quality** and modularity.
* **State Management:** The custom `IntelligentAgent` tracks its speaking status (`is_agent_speaking`) by overriding `on_agent_speech_start` and `on_agent_speech_end` hooks, meeting the **State Awareness** criterion.

### 2. Context-Aware Filtering Logic

The core logic is executed inside the `on_user_turn_completed` method, which correctly intercepts the final user transcript (extracted from `kwargs['new_message'].text`) before it is processed by the LLM.

#### Logic Matrix and Behavior: 
| User Input Content | Agent State | Desired Behavior | Assignment Criterion |
| :--- | :--- | :--- | :--- |
| **Filler Word Only** (e.g., "yeah," "uh-huh") | **SPEAKING** | **IGNORE**: Agent continues speaking seamlessly. | Strict Functionality (70%) |
| **Active Command** (e.g., "Stop," "Wait") | **SPEAKING** | **INTERRUPT**: Agent cuts off and processes command. | Semantic Interruption |
| **Any Input** (e.g., "Yeah," "Hello") | **SILENT** | **RESPOND**: Processes as a normal conversational turn. | State Awareness (10%) |

#### Key Implementations:

* **Strict Functionality:** To achieve seamless continuation when ignoring input, the method simply returns if the input is only filler, preventing the LLM from starting a new turn. This relies on the AgentSession's `resume_false_interruption=True` setting to recover the VAD-triggered pause.
* **Semantic Interruption:** The code uses regular expressions and set checks to verify if the transcription contains **only** words from the configurable `IGNORED_WORDS` set. Any non-filler word forces an INTERRUPT.
* **Configurable Ignore List:** The `IGNORED_WORDS` set within the handler class allows for easy modification of filler words (Code Quality).

---

### 3. Proof of Functionality

**[ACTION REQUIRED: Paste the final URL to your video recording or the transcribed console log here.]**

This proof demonstrates the required scenarios:
* The agent ignoring "yeah" while talking.
* The agent responding to "yeah" when silent.
* The agent stopping for "stop".

# Voice Agents Examples

This directory contains a comprehensive collection of voice-based agent examples demonstrating various capabilities and integrations with the LiveKit Agents framework.

## 📋 Table of Contents

### 🚀 Getting Started

- [`basic_agent.py`](./basic_agent.py) - A fundamental voice agent with metrics collection

### 🛠️ Tool Integration & Function Calling

- [`annotated_tool_args.py`](./annotated_tool_args.py) - Using Python type annotations for tool arguments
- [`dynamic_tool_creation.py`](./dynamic_tool_creation.py) - Creating and registering tools dynamically at runtime
- [`raw_function_description.py`](./raw_function_description.py) - Using raw JSON schema definitions for tool descriptions
- [`silent_function_call.py`](./silent_function_call.py) - Executing function calls without verbal responses to user
- [`long_running_function.py`](./long_running_function.py) - Handling long running function calls with interruption support

### ⚡ Real-time Models

- [`weather_agent.py`](./weather_agent.py) - OpenAI Realtime API with function calls for weather information
- [`realtime_video_agent.py`](./realtime_video_agent.py) - Google Gemini with multimodal video and voice capabilities
- [`realtime_joke_teller.py`](./realtime_joke_teller.py) - Amazon Nova Sonic real-time model with function calls
- [`realtime_load_chat_history.py`](./realtime_load_chat_history.py) - Loading previous chat history into real-time models
- [`realtime_turn_detector.py`](./realtime_turn_detector.py) - Using LiveKit's turn detection with real-time models
- [`realtime_with_tts.py`](./realtime_with_tts.py) - Combining external TTS providers with real-time models

### 🎯 Pipeline Nodes & Hooks

- [`fast-preresponse.py`](./fast-preresponse.py) - Generating quick responses using the `on_user_turn_completed` node
- [`flush_llm_node.py`](./flush_llm_node.py) - Flushing partial LLM output to TTS in `llm_node`
- [`structured_output.py`](./structured_output.py) - Structured data and JSON outputs from agent responses
- [`speedup_output_audio.py`](./speedup_output_audio.py) - Dynamically adjusting agent audio playback speed
- [`timed_agent_transcript.py`](./timed_agent_transcript.py) - Reading timestamped transcripts from `transcription_node`
- [`inactive_user.py`](./inactive_user.py) - Handling inactive users with the `user_state_changed` event hook
- [`resume_interrupted_agent.py`](./resume_interrupted_agent.py) - Resuming agent speech after false interruption detection
- [`toggle_io.py`](./toggle_io.py) - Dynamically toggling audio input/output during conversations

### 🤖 Multi-agent & AgentTask Use Cases

- [`restaurant_agent.py`](./restaurant_agent.py) - Multi-agent system for restaurant ordering and reservation management
- [`multi_agent.py`](./multi_agent.py) - Collaborative storytelling with multiple specialized agents
- [`email_example.py`](./email_example.py) - Using AgentTask to collect and validate email addresses

### 🔗 MCP & External Integrations

- [`web_search.py`](./web_search.py) - Integrating web search capabilities into voice agents
- [`langgraph_agent.py`](./langgraph_agent.py) - LangGraph integration
- [`mcp/`](./mcp/) - Model Context Protocol (MCP) integration examples
  - [`mcp-agent.py`](./mcp/mcp-agent.py) - MCP agent integration
  - [`server.py`](./mcp/server.py) - MCP server example
- [`zapier_mcp_integration.py`](./zapier_mcp_integration.py) - Automating workflows with Zapier through MCP

### 💾 RAG & Knowledge Management

- [`llamaindex-rag/`](./llamaindex-rag/) - Complete RAG implementation with LlamaIndex
  - [`chat_engine.py`](./llamaindex-rag/chat_engine.py) - Chat engine integration
  - [`query_engine.py`](./llamaindex-rag/query_engine.py) - Query engine used in a function tool
  - [`retrieval.py`](./llamaindex-rag/retrieval.py) - Document retrieval

### 🎵 Specialized Use Cases

- [`background_audio.py`](./background_audio.py) - Playing background audio or ambient sounds during conversations
- [`push_to_talk.py`](./push_to_talk.py) - Push-to-talk interaction
- [`tts_text_pacing.py`](./tts_text_pacing.py) - Pacing control for TTS requests
- [`speaker_id_multi_speaker.py`](./speaker_id_multi_speaker.py) - Multi-speaker identification

### 📊 Tracing & Error Handling

- [`langfuse_trace.py`](./langfuse_trace.py) - LangFuse integration for conversation tracing
- [`error_callback.py`](./error_callback.py) - Error handling callback
- [`session_close_callback.py`](./session_close_callback.py) - Session lifecycle management

## 📖 Additional Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [Agents Starter Example](https://github.com/livekit-examples/agent-starter-python)
- [More Agents Examples](https://github.com/livekit-examples/python-agents-examples)
