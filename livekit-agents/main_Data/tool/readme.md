# LiveKit Intelligent Interruption Engine (Switchable & Hybrid)

This repository implements a **Strategy-Pattern** based interruption handling system for LiveKit Agents. It supports multiple modes of operation including Rule-based, ML-based, and LLM-based classification.

## 🚀 Features

* **Switchable Engines:** Change logic without changing code via `INTERRUPT_MODE`.
* **Hybrid Automatic Switching:** Uses fast Rules for simple cases ("yeah", "stop") and escalates to LLM for complex sentences ("Yeah, wait a second, I think...").
* **LLM Provider Agnostic:** Supports OpenAI, Google Gemini, and Ollama via Factory pattern.
* **Microservice Ready:** Engines are decoupled and can be moved to external inference services.

## 🛠 Configuration (`config.py` & Env Vars)

| Variable | Options | Description |
| :--- | :--- | :--- |
| `INTERRUPT_MODE` | `RULES`, `ML`, `LLM`, `HYBRID` | Determines the logic engine. |
| `LLM_PROVIDER` | `gpt`, `gemini`, `ollama` | Which LLM to use (if mode is LLM/HYBRID). |
| `LLM_MODEL_NAME` | `gpt-4o`, `llama3`, etc. | Model identifier. |
| `LK_IGNORE_WORDS` | List (csv) | Words to ignore in RULES mode. |

## 🏗 Architecture

The system uses a **Strategy Pattern**:

1.  **`BaseEngine`**: Interface defining `classify(transcript, state)`.
2.  **`RulesEngine`**: Regex/Keyword matching (O(1) latency).
3.  **`MLEngine`**: Placeholder for GAP/PodcastFillers trained models.
4.  **`LLMEngine`**: LangChain wrapper for semantic intent detection.

## 🤖 ML/DL Model Notes

For the `ML` mode, we recommend training a classification model on the **GAP Derived Interruption Dataset** or **PodcastFillers**.

* **Input Features:** Text embeddings + Audio Energy + Overlap Duration.
* **Model Architecture:** A lightweight LSTM or DistilBERT for latency <100ms.
* **Output:** Softmax over `[INTERRUPT, IGNORE, NORMAL]`.

## 📦 Setup

1.  Install dependencies:
    ```bash
    pip install langchain langchain-openai langchain-ollama
    ```
2.  Set Environment:
    ```bash
    export INTERRUPT_MODE="HYBRID"
    export LLM_PROVIDER="ollama"
    export OPENAI_API_KEY="sk-..." # if using GPT
    ```
3.  Run Agent.