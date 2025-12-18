# LiveKit Intelligent Interruption Engine (Switchable & Hybrid)

This repository implements a **Strategy-Pattern** based interruption handling system for LiveKit Agents. It allows dynamic switching of interruption logic (Rule-based, ML, LLM, or RAG) without changing application code.

![Project Flowchart](https://github.com/simran1devloper/this_test/blob/main/Screenshot%20From%202025-12-07%2015-11-53.png)

## 🚀 Features

*   **Switchable Engines:** Change logic without changing code via `INTERRUPT_MODE`.
*   **Hybrid Automatic Switching:** Uses fast Rules for simple cases ("yeah", "stop") and escalates to LLM/RAG for complex queries.
*   **LLM Provider Agnostic:** Supports OpenAI, Google Gemini, and Ollama via Factory pattern.
*   **RAG-Enhanced Decisions:** Retrieves context-aware interruption rules from a vector store, perfect for domain-specific agent interactions.
*   **Microservice Ready:** Engines are decoupled and can be moved to external inference services.

## 🛠 Configuration

Configuration is managed via environment variables (see `.env.example` or `config.py`).

| Variable | Options | Description |
| :--- | :--- | :--- |
| `INTERRUPT_MODE` | `RULES`, `ML`, `LLM`, `RAG`, `HYBRID` | Determines the active logic engine. |
| `LLM_PROVIDER` | `gpt`, `gemini`, `ollama` | Provider for LLM/RAG modes. |
| `LLM_MODEL_NAME` | `gpt-4o`, `llama3`, etc. | Model identifier. |
| `LK_IGNORE_WORDS` | List (csv) | Words to ignore in RULES mode (e.g., "yeah,ok"). |
| `RAG_VECTORSTORE_DIR`| Path | Path to ChromaDB/Vector store for RAG mode. |
| `RAG_K_CONTEXT` | Integer | Number of context documents to retrieve. |

## 🏗 Architecture & Engines

The system uses a **Strategy Pattern** to select the best engine at runtime:

1.  **`RulesEngine`**: Ultra-low latency O(1) keyword regex matching. Best for simple command agents.
2.  **`MLEngine`**: Uses lightweight trained models (LSTM/DistilBERT) on acoustic features (overlap, pitch, energy).
3.  **`LLMEngine`**: Uses Large Language Models to detect semantic intent.
4.  **`RAGEngine`**: **(New)** Uses Retrieval-Augmented Generation to look up specific interruption rules or conversation policies from a vector database before making a decision.

### Mode Selector
The `ModeSelector` component dynamically routes requests based on complexity and available compute:
- Simple "stop" command -> **RULES**
- "Can you explain that policy again?" -> **RAG** (if configured)
- Complex ambiguity -> **LLM**

## � Runtime Logic Flow

Every time the user speaks (STT transcript received) or a VAD event occurs, the system executes the following pipeline:

1.  **Input Capture**: The `InterruptionManager` receives the live transcript and audio metadata (VAD status, timestamps).
2.  **Feature Extraction**:
    *   **OverlapDetector**: Did the user speak *while* the agent was speaking?
    *   **FillerDetector**: Is the input just a backchannel like "uh-huh"?
    *   **SemanticIntent**: Does the text contain explicit keywords ("Stop", "Wait")?
3.  **Mode Selection**: The `ModeSelector` evaluates the features and system constraints (latency budget).
    *   *Example*: If overlap is detected and the user said "Stop", it selects **RULES** (fastest).
    *   *Example*: If the user asks a complex question, it selects **RAG** or **LLM**.
4.  **Engine Execution**: The selected engine runs its logic to produce a decision (`INTERRUPT`, `IGNORE`, or `NORMAL`).
5.  **Action**:
    *   **INTERRUPT**: The agent effectively stops speaking immediately.
    *   **IGNORE**: The agent ignores the noise/filler and continues speaking.
    *   **NORMAL**: The input is treated as a standard user turn, usually processed by the main agent loop.



## 📦 Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
# For Rules Engine
pip install nltk
```

### 2. RAG System Setup
To use the RAG-based system (`INTERRUPT_MODE="RAG"`):

1.  **Install Vector Store dependencies**:
    ```bash
    pip install chromadb langchain-community
    ```
2.  **Prepare your Knowledge Base**:
    Create a vector store at the path specified by `RAG_VECTORSTORE_DIR` containing your interruption rules (e.g., "Always stop if user asks for pricing").
3.  **Configure Environment**:
    ```bash
    export INTERRUPT_MODE="RAG"
    export RAG_VECTOR_STORE_PATH="./rag_data/chroma_db"
    export LLM_PROVIDER="ollama" # or gpt/gemini
    ```


