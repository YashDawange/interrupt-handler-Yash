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
LLM_PROVIDER_NAME=os.getenv("LLM_PROVIDER_NAME", "")
LLM_MODEL_NAME=os.getenv("LLM_MODEL_NAME", "")

# Confidence thresholds (used by ML/LLM engines)
INTERRUPT_CONFIDENCE = float(os.getenv("LK_INTERRUPT_CONFIDENCE", "0.7"))
IGNORE_CONFIDENCE = float(os.getenv("LK_IGNORE_CONFIDENCE", "0.7"))

# ---  RAG ENGINE SETTINGS ---
RAG_VECTOR_STORE_PATH = os.getenv("RAG_VECTOR_STORE_PATH", "./rag_data/chroma_db")
RAG_DATA_FILE = os.getenv("RAG_DATA_FILE", "./rag_data/interrupt_dataset_15k.json") # NEW: Path to your structured data
RAG_K_CONTEXT = int(os.getenv("RAG_K_CONTEXT", "3"))
RAG_LLM_PROVIDER_NAME=os.getenv("RAG_LLM_PROVIDER_NAME", "")
RAG_LLM_MODEL_NAME=os.getenv("RAG_LLM_MODEL_NAME", "")