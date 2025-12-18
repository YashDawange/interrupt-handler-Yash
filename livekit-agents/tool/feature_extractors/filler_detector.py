# filler_detector.py
"""
Filler/backchannel detector.
Strategy:
 - Fast regex-based detection for common fillers/backchannels.
 - Optional small ML fallback if more accuracy required (plug into ML wrapper).
"""

import re
from typing import Tuple

# A conservative, language-specific list of filler/backchannel tokens.
DEFAULT_FILLERS = {
    "yeah", "ok", "okay", "hmm", "uh", "uh-huh", "uhh", "mmhmm", "yep",
    "yup", "got it", "i'm listening", "right", "aha", "mm", "huh", "ohh",
}

# Precompiled regexes (case-insensitive)
_FILLER_RE = re.compile(r"^\s*(?:" + r"|".join(re.escape(x) for x in DEFAULT_FILLERS) + r")(?:[.!?,\s].*)?$", flags=re.I)
_FILLER_CONTAINS_RE = re.compile(r"\b(?:" + r"|".join(re.escape(x) for x in DEFAULT_FILLERS) + r")\b", flags=re.I)

def is_filler_regex(transcript: str) -> Tuple[bool, float]:
    """
    Return (is_filler, confidence_estimate)
    - Exact short-match -> high confidence (0.9)
    - Contains filler tokens -> lower confidence (0.6)
    """
    if not transcript or not transcript.strip():
        return (False, 0.0)
    t = transcript.strip()
    if _FILLER_RE.match(t):
        return True, 0.95
    if _FILLER_CONTAINS_RE.search(t):
        # may be mixed ("yeah wait"), lower confidence
        return True, 0.55
    return False, 0.0

# Optional ML fallback: you can wire this into ML wrapper to improve recall/precision.
# Example usage:
if __name__ == "__main__":
    for s in ["yeah", "yeah go on", "uh huh", "wait please", "hmm", "i'm listening", "stop now"]:
        print(s, is_filler_regex(s))
