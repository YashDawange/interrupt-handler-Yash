# overlap_detector.py
"""
Overlap detector uses timestamp info of agent audio playback and user speech events.
It gives a boolean overlap flag and overlap_duration (seconds).

Assumptions:
- agent_playback_intervals: list of (start_ts, end_ts) in seconds (monotonic time)
- user_speech_interval: (start_ts, end_ts)
"""

from typing import List, Tuple, Optional

class OverlapDetector:
    """
    Detects and computes the overlap between a list of agent audio intervals
    and a single user speech interval.
    """

    @staticmethod
    def interval_overlap(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """
        Calculates the overlap duration in seconds between two intervals a and b.
        
        Args:
            a: The first interval (start_ts, end_ts).
            b: The second interval (start_ts, end_ts).
            
        Returns:
            The overlap duration in seconds (>= 0.0).
        """
        a0, a1 = a
        b0, b1 = b
        
        # The start of the overlap is the maximum of the two start times.
        start = max(a0, b0)
        # The end of the overlap is the minimum of the two end times.
        end = min(a1, b1)
        
        # If start >= end, there is no overlap (or overlap is zero duration).
        return max(0.0, end - start)

    @staticmethod
    def compute_overlap(agent_intervals: List[Tuple[float, float]], 
                        user_interval: Tuple[float, float]) -> Tuple[bool, float, Optional[float]]:
        """
        Computes total overlap, overlap flag, and the start time of the first overlap.

        Args:
            agent_intervals: List of (start_ts, end_ts) for agent audio.
            user_interval: The single (start_ts, end_ts) for user speech.

        Returns:
            Tuple: (
              overlap_flag: bool (True if any overlap > 0),
              overlap_total: float (sum of overlapping seconds),
              first_overlap_start: float or None (start time of the first detected overlap)
            )
        """
        total = 0.0
        first_start: Optional[float] = None
        
        for a in agent_intervals:
            ov = OverlapDetector.interval_overlap(a, user_interval)
            
            if ov > 0:
                total += ov
                
                # Check if this is the first time we've encountered an overlap
                if first_start is None:
                    # The start of the first overlap is the maximum of the two intervals' start times
                    first_start = max(a[0], user_interval[0])
                    
        return (total > 0.0, total, first_start)

# Example usage:
if __name__ == "__main__":
    # Agent speaking from 10–18s and 30–40s
    agent_intervals = [(10.0, 18.0), (30.0, 40.0)]
    
    # User speech interval
    user_interval1 = (15.5, 16.5)                   # Overlaps agent interval (10.0, 18.0)
    print(f"User 1: {user_interval1}")
    print(f"Result 1: {OverlapDetector.compute_overlap(agent_intervals, user_interval1)}")
    # Expected output: (True, 1.0, 15.5)
    
    # User speech outside agent speech
    user_interval2 = (20.0, 25.0)                   
    print(f"\nUser 2: {user_interval2}")
    print(f"Result 2: {OverlapDetector.compute_overlap(agent_intervals, user_interval2)}")
    # Expected output: (False, 0.0, None)
    
    # User speech overlapping multiple agent intervals (or one that contains two)
    # The current agent_intervals are not conducive to a single user interval overlapping two non-contiguous agent intervals.
    # Let's test an overlap that spans two agent intervals but has a gap:
    user_interval3 = (17.0, 31.0) # Overlaps (10, 18) by 1.0s and (30, 40) by 1.0s
    print(f"\nUser 3: {user_interval3}")
    print(f"Result 3: {OverlapDetector.compute_overlap(agent_intervals, user_interval3)}")
    # Expected output: (True, 2.0, 17.0) (1.0s from [17, 18] and 1.0s from [30, 31])