# noise_classifier.py
"""
Lightweight noise classifier using simple features:
 - If the transcript is empty but VAD fired -> likely noise (non-verbal).
 - Heuristics: if transcript contains words like 'noise', 'traffic', 'breath' -> noise.
 - Optional energy/spectral features if you have raw audio frames.

This is intentionally simple to remain dependency-free and low-latency.
"""

import re

_NOISE_KEYWORDS = re.compile(r"\b(noise|traffic|breath|breathing|laughter|laugh|cough|background)\b", flags=re.I)

def is_noise_by_text(transcript: str) -> Tuple[bool, float]:
    """
    Return (is_noise, confidence)
    - If transcript is empty or short non-alphanumeric tokens -> high chance of noise
    - Keyword-based -> moderate confidence
    """
    if transcript is None:
        return True, 0.6
    t = transcript.strip()
    if t == "":
        return True, 0.9
    # tokens-only like 'mmm', 'hmm', 'ah' -> non-speech/noise-ish
    if re.fullmatch(r"[^\w\s]{0,2}|[hm]{1,4}", t.lower()):
        return True, 0.75
    if _NOISE_KEYWORDS.search(t):
        return True, 0.7
    return False, 0.0

# If you have raw audio, compute RMS energy and compare to a threshold:
def is_noise_by_energy(rms: float, energy_threshold: float = 1e-4) -> Tuple[bool, float]:
    """Simple RMS energy threshold detector."""
    return (rms < energy_threshold, 0.8 if rms < energy_threshold else 0.0)
