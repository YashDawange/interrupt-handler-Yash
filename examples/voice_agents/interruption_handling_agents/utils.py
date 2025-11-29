from __future__ import annotations
import os


def require_env(*keys: str) -> None:
    """Ensure required environment variables are set, otherwise raise an error."""
    missing = []
    for k in keys:
        v = os.getenv(k, "").strip()
        if not v:
            missing.append(k)
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def extract_user_utterance(event) -> str:
    """Extract the user's spoken text from various possible event fields."""
    for attr in ("user_transcript", "transcript", "text"):
        v = getattr(event, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()

    alts = getattr(event, "alternatives", None)
    if isinstance(alts, list) and alts:
        text = getattr(alts[0], "text", "")
        if isinstance(text, str) and text.strip():
            return text.strip()

    return ""
