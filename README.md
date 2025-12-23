# Context-Aware Interrupt Handler for Voice Agents

## 🎯 Project Goal

Eliminate awkward audio pauses and stutters caused by user backchannel words ("yeah", "uh-huh") while maintaining responsiveness to actual commands ("stop", "wait").

## 🏗️ Three-Layer Defense Architecture

This project implements a robust defense strategy against false interruptions:

1.  **Layer 1: VAD Threshold Gate**  
    *   **Mechanism**: Configured `min_interruption_words=2` in `AgentSession`.
    *   **Result**: Single-word bursts like "yeah" are blocked at the signal processing level, preventing any audio hiccup.

2.  **Layer 2: Semantic Filter (`InterruptionController`)**  
    *   **Mechanism**: A custom controller analyzes transcript content and agent state.
    *   **Logic**:
        *   *Agent Speaking* + "Yeah" → **IGNORE** (Backchannel)
        *   *Agent Silent* + "Yeah" → **NO_DECISION** (User agreement)
        *   *Any State* + "Stop" → **INTERRUPT** (Command)

3.  **Layer 3: Action Dispatcher**  
    *   **Mechanism**: Executes the decision from Layer 2.
    *   **Actions**:
        *   **IGNORE**: Calls `session.clear_user_turn()` to effectively "delete" the filler word from the LLM's buffer.
        *   **INTERRUPT**: Calls `session.interrupt()` for immediate control.

---

## ⚡ Production Optimizations

*   **O(1) Constant-Time Lookups**: Uses `Set` for instant word matching.
*   **Groq Llama 3.3 Intelligence**: Powered by `llama-3.3-70b-versatile` for sub-second latency.
*   **Smart Hyphen Normalization**: Handles "uh-huh" vs "uh huh" variations automatically.
*   **State Transition Grace Period**: 500ms safety buffer to handle race conditions when the agent just stops speaking.
*   **Efficient Interim Processing**: Discards interim filler transcripts to save CPU and reduce noise.
*   **Windows Stability**: Version-locked OpenTelemetry (1.35.0) for reliable logging on Windows systems.

---

## 🚀 How to Run

### 1. Prerequisites
Ensure you have the required dependencies:
```bash
pip install -r examples/voice_agents/requirements.txt
pip install "opentelemetry-api==1.35.0" "opentelemetry-sdk==1.35.0" "opentelemetry-exporter-otlp==1.35.0" "opentelemetry-proto==1.35.0"
```

### 2. Configuration
Create a `.env` file (see `env.example` for template) with your API keys for LiveKit, Groq, Deepgram, and Cartesia.

### 3. Execution
Run the agent:
```bash
cd examples/voice_agents
python basic_agent.py dev
```

### 4. Verification
Run the comprehensive test suite:
```bash
python examples/verify_interrupt_handler.py
```

## 🛠️ Project Structure
- `salescode_interrupt_handler/controllers.py`: Core logic for the `InterruptionController`.
- `examples/voice_agents/basic_agent.py`: The production-ready voice agent.
- `examples/verify_interrupt_handler.py`: Automated test suite for all logic layers.
- `instructions.md`: Detailed setup guide for new users.
