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
        *   **IGNORE**: Calls `session.clear_user_turn()` to effectively "delete" the filler word from the LLM's buffer (zero token waste).
        *   **INTERRUPT**: Calls `session.interrupt()` for immediate control.

---

## ⚡ Production Optimizations

This implementation includes several critical optimizations to ensure production-grade reliability and speed:

*   **O(1) Constant-Time Lookups**  
    Switched from `List` to `Set` data structures for all word matching. This ensures that checking against 100+ filler words takes the same negligible time as checking 1, preventing latency spikes as the vocabulary grows.

*   **Groq Llama 3.3 Intelligence**  
    Replaced the default LLM with Groq's LPUs running `llama-3.3-70b-versatile`. This reduces inference latency to sub-second levels, essential for a snappy, conversational voice interface.

*   **Smart Hyphen Normalization**  
    Custom regex logic converts variations like "uh-huh" → "uh huh" *before* matching. This solves the critical issue where STT variations of hyphenated fillers were previously bypassing the filter.

*   **State Transition Grace Period**  
    Implemented a **500ms safety buffer** after the agent stops speaking. This robustly handles the race condition where a user's command (e.g., "Stop") arrives milliseconds after the agent mentally enters the `listening` state, ensuring it is still correctly treated as a valid interruption.

*   **Efficient Interim Processing**  
    The system now intelligently pre-filters interim results. If an interim transcript contains only potential fillers, it is discarded immediately. This significantly reduces CPU load and prevents unnecessary decision cycles before the final transcript arrives.

---

## 📹 Demo & Logs

*   **[Link to Demo Video]**: (https://drive.google.com/file/d/1r4hr7tlUqShhmjk0KRuvILAzvJL3bqAn/view?usp=sharing) - Demonstrates the agent ignoring "yeah" while speaking, yet stopping immediately for "stop".
*   **Log Transcript**: Please refer to `logs_of_context_aware_filter.md` in the `agents-assignment` folder. It contains the detailed logs showing `🔇 CLEARED` and `🛑 INTERRUPTED` events.

---

## 🚀 How to Run

### 1. Prerequisites
Ensure you have the required dependencies (version-locked for stability):
```bash
pip install -r examples/voice_agents/requirements.txt
```

### 2. Configuration
Create a `.env` file in `examples/voice_agents/` with your keys:
```env
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
GROQ_API_KEY=...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
```

### 3. Execution
Run the agent in development mode:
```bash
cd examples/voice_agents
python basic_agent.py dev
```

### 4. Verification
Run the comprehensive test suite to verify all logic:
```bash
python verify_interrupt_handler.py
```

---

## 🛠️ Customization

The logic is modular and located in `examples/interrupt_handler/controller.py`. You can easily modify the word lists:

```python
# controller.py
IGNORE_WORDS = {"yeah", "ok", "custom_word"}
INTERRUPT_WORDS = {"stop", "halt"}
```
