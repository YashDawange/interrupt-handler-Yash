# config.py
import os
from dotenv import load_dotenv
load_dotenv()

# Modes: RULES, ML, LLM, RAG
INTERRUPT_MODE = os.getenv("INTERRUPT_MODE", "RULES").upper()


# Comma separated lists allowed via env for easy configuration
IGNORE_WORDS = os.getenv(
"LK_IGNORE_WORDS",
"yeah,ok,okay,hmm,uh-huh,right,mmhmm"
).split(",")
INTERRUPT_WORDS = os.getenv(
"LK_INTERRUPT_WORDS",
"stop,wait,no,hold,hold on,please stop,pause"
).split(",")


# Timing (in seconds) to wait for STT to confirm before honoring VAD stop
STT_CONFIRM_DELAY = float(os.getenv("LK_STT_CONFIRM_DELAY", "0.12"))
STT_MAX_WAIT = float(os.getenv("LK_STT_MAX_WAIT", "0.5"))


# ML/LLM specific settings
ML_MODEL_PATH = os.getenv("LK_ML_MODEL_PATH", "")
LLM_PROVIDER = os.getenv("LK_LLM_PROVIDER", "ollama") # gpt, gemini, ollama, etc.
RAG_VECTORSTORE_DIR = os.getenv("LK_RAG_VECTORSTORE_DIR", "/var/lib/lk_rag_vectors")
LLM_PROVIDER_NAME=os.getenv("Ollama", "")
LLM_MODEL_NAME=os.getenv("lamma3", "")

# Confidence thresholds (used by ML/LLM engines)
INTERRUPT_CONFIDENCE = float(os.getenv("LK_INTERRUPT_CONFIDENCE", "0.7"))
IGNORE_CONFIDENCE = float(os.getenv("LK_IGNORE_CONFIDENCE", "0.7"))

# ---  RAG ENGINE SETTINGS ---
RAG_VECTOR_STORE_PATH = os.getenv("RAG_VECTOR_STORE_PATH", "./rag_data/chroma_db")
RAG_DATA_FILE = os.getenv("RAG_DATA_FILE", "./rag_data/interrupt_dataset_15k.json") # NEW: Path to your structured data
RAG_K_CONTEXT = int(os.getenv("RAG_K_CONTEXT", "3"))
RAG_LLM_PROVIDER_NAME=os.getenv("Ollama", "")
RAG_LLM_MODEL_NAME=os.getenv("lamma3", "")


## ⚙️ Connection Settings ##
# Since these are typically loaded from the environment, but the prompt
# provides them as explicit values, we'll map them to variables.
# In a real setup with load_dotenv, the environment variables would be set first.

RULES_CONNECTION = os.getenv("RULES_CONNECTION", "offline")
ML_CONNECTION = os.getenv("ML_CONNECTION", "offline")
LLM_CONNECTION = os.getenv("LLM_CONNECTION", "offline")
RAG_CONNECTION = os.getenv("RAG_CONNECTION", "offline")

# Base Endpoints
GATEWAY_ENDPOINT = os.getenv("GATEWAY_ENDPOINT", "http://172.22.124.89:8888/")
RULES_ENDPOINT = os.getenv("RULES_ENDPOINT", "http://172.22.124.89:8888/")
ML_ENDPOINT = os.getenv("ML_ENDPOINT", "http://172.22.124.89:8888/")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://172.22.124.89:8888/")
RAG_ENDPOINT = os.getenv("RAG_ENDPOINT", "http://172.22.124.89:8888/")


#system/env constraints
LATENCY_BUDGET = os.getenv("LATENCY_BUDGET", "LOW")
COMPUTE_POWER = os.getenv("COMPUTE_POWER", "LOW")
