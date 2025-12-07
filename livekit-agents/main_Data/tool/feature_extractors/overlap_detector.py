# overlap_detector.py
"""
Overlap detector uses timestamp info of agent audio playback and user speech events.
It gives a boolean overlap flag and overlap_duration (seconds).

Assumptions:
- agent_playback_intervals: list of (start_ts, end_ts) in seconds (monotonic time)
- user_speech_interval: (start_ts, end_ts)
"""

from typing import List, Tuple

def interval_overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Return overlap duration in seconds."""
    a0, a1 = a
    b0, b1 = b
    start = max(a0, b0)
    end = min(a1, b1)
    return max(0.0, end - start)

def compute_overlap(agent_intervals: List[Tuple[float, float]], user_interval: Tuple[float, float]):
    """
    Return:
      overlap_flag: bool (True if any overlap > 0)
      overlap_total: float (sum of overlapping seconds)
      first_overlap_start: float or None
    """
    total = 0.0
    first_start = None
    for a in agent_intervals:
        ov = interval_overlap(a, user_interval)
        if ov > 0:
            total += ov
            if first_start is None:
                first_start = max(a[0], user_interval[0])
    return (total > 0.0, total, first_start)

# Example usage:
if __name__ == "__main__":
    agent = [(10.0, 18.0), (30.0, 40.0)]   # agent speaking from 10–18s and 30–40s
    user = (15.5, 16.5)                   # user started at 15.5s
    print(compute_overlap(agent, user))   # -> (True, 1.0, 15.5)
