# livekit-agents/livekit/interrupt_config.py
import os
import json

DEFAULT_IGNORE = ["yeah", "ok", "okay", "hmm", "right", "uh-huh", "uh huh", "mm-hmm"]
DEFAULT_INTERRUPT = ["stop", "wait", "no", "hold on", "wait a second", "hold up", "stop it"]

def load_lists(config_path=None):
    ignore = list(DEFAULT_IGNORE)
    interrupt = list(DEFAULT_INTERRUPT)

    env_ignore = os.getenv("INTERRUPT_IGNORE_WORDS")
    env_interrupt = os.getenv("INTERRUPT_INTERRUPT_WORDS")
    if env_ignore:
        ignore = [w.strip().lower() for w in env_ignore.split(",") if w.strip()]
    if env_interrupt:
        interrupt = [w.strip().lower() for w in env_interrupt.split(",") if w.strip()]

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "ignore_words" in cfg:
                ignore = [w.lower() for w in cfg["ignore_words"]]
            if "interrupt_words" in cfg:
                interrupt = [w.lower() for w in cfg["interrupt_words"]]
        except Exception:
            pass

    return ignore, interrupt
