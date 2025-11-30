"""
Backchannel Detection Metrics

Comprehensive metrics for monitoring backchannel detection system:
- Detection accuracy and performance
- User interaction patterns
- System health and diagnostics
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..voice.backchannel.confidence import BackchannelConfidence


class BackchannelMetrics(BaseModel):
    """
    Metrics for a single backchannel detection event.
    
    Collected for analytics, monitoring, and improvement.
    """
    
    timestamp: float = Field(default_factory=time.time)
    
    # Detection details
    transcript: str
    overall_confidence: float
    word_match_score: float
    prosody_score: float | None
    context_score: float
    user_history_score: float | None
    
    # Decision
    decision: bool  # True = backchannel, False = command
    threshold: float
    confidence_level: str  # "very_high", "high", "medium", "low", "very_low"
    
    # Context
    agent_speaking: bool
    word_count: int
    duration_ms: float | None  # Speech duration if available
    
    # Performance
    processing_time_ms: float  # Time to compute confidence
    
    # Features used
    prosody_available: bool
    context_available: bool
    user_profile_available: bool
    
    # Outcome
    interrupted: bool  # Whether agent was actually interrupted
    prevented_interruption: bool  # Whether interruption was prevented
    
    class Config:
        frozen = True


@dataclass
class BackchannelStatsCollector:
    """
    Collects and aggregates backchannel detection statistics.
    
    Tracks:
    - Detection rates (backchannels vs commands)
    - Confidence distributions
    - Performance metrics
    - User patterns
    """
    
    # Counters
    total_detections: int = 0
    backchannels_detected: int = 0
    commands_detected: int = 0
    interruptions_prevented: int = 0
    interruptions_allowed: int = 0
    
    # Confidence distributions
    confidence_scores: list[float] = field(default_factory=list)
    backchannel_confidence_scores: list[float] = field(default_factory=list)
    command_confidence_scores: list[float] = field(default_factory=list)
    
    # Performance
    processing_times_ms: list[float] = field(default_factory=list)
    
    # Feature availability
    prosody_available_count: int = 0
    context_available_count: int = 0
    user_profile_available_count: int = 0
    
    # User patterns
    user_backchannel_phrases: dict[str, int] = field(default_factory=dict)
    user_command_phrases: dict[str, int] = field(default_factory=dict)
    
    # Timestamps
    first_detection_time: float | None = None
    last_detection_time: float | None = None
    
    def record_detection(
        self,
        confidence: BackchannelConfidence,
        *,
        agent_speaking: bool,
        interrupted: bool,
        prevented_interruption: bool,
        processing_time_ms: float,
    ) -> None:
        """Record a backchannel detection event."""
        self.total_detections += 1
        
        # Track timestamps
        now = time.time()
        if self.first_detection_time is None:
            self.first_detection_time = now
        self.last_detection_time = now
        
        # Count decision types
        if confidence.decision:
            self.backchannels_detected += 1
            self.backchannel_confidence_scores.append(confidence.overall_score)
            
            # Track user patterns
            phrase = confidence.transcript.lower().strip()
            self.user_backchannel_phrases[phrase] = (
                self.user_backchannel_phrases.get(phrase, 0) + 1
            )
        else:
            self.commands_detected += 1
            self.command_confidence_scores.append(confidence.overall_score)
            
            # Track user patterns
            phrase = confidence.transcript.lower().strip()
            self.user_command_phrases[phrase] = (
                self.user_command_phrases.get(phrase, 0) + 1
            )
        
        # Track interruptions
        if prevented_interruption:
            self.interruptions_prevented += 1
        if interrupted:
            self.interruptions_allowed += 1
        
        # Track confidence scores
        self.confidence_scores.append(confidence.overall_score)
        
        # Track performance
        self.processing_times_ms.append(processing_time_ms)
        
        # Track feature availability
        if confidence.prosody_score is not None:
            self.prosody_available_count += 1
        if confidence.features.get("context_available"):
            self.context_available_count += 1
        if confidence.user_history_score is not None:
            self.user_profile_available_count += 1
    
    def get_summary(self) -> dict:
        """Get summary statistics."""
        if self.total_detections == 0:
            return {
                "total_detections": 0,
                "message": "No backchannel detections yet",
            }
        
        # Calculate rates
        backchannel_rate = self.backchannels_detected / self.total_detections
        command_rate = self.commands_detected / self.total_detections
        prevention_rate = (
            self.interruptions_prevented / self.total_detections
            if self.total_detections > 0
            else 0.0
        )
        
        # Calculate average confidence scores
        avg_confidence = (
            sum(self.confidence_scores) / len(self.confidence_scores)
            if self.confidence_scores
            else 0.0
        )
        avg_backchannel_confidence = (
            sum(self.backchannel_confidence_scores) / len(self.backchannel_confidence_scores)
            if self.backchannel_confidence_scores
            else 0.0
        )
        avg_command_confidence = (
            sum(self.command_confidence_scores) / len(self.command_confidence_scores)
            if self.command_confidence_scores
            else 0.0
        )
        
        # Calculate average processing time
        avg_processing_time = (
            sum(self.processing_times_ms) / len(self.processing_times_ms)
            if self.processing_times_ms
            else 0.0
        )
        
        # Calculate feature availability rates
        prosody_rate = self.prosody_available_count / self.total_detections
        context_rate = self.context_available_count / self.total_detections
        user_profile_rate = self.user_profile_available_count / self.total_detections
        
        # Get top user phrases
        top_backchannels = sorted(
            self.user_backchannel_phrases.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        top_commands = sorted(
            self.user_command_phrases.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        
        # Calculate session duration
        session_duration = (
            self.last_detection_time - self.first_detection_time
            if self.first_detection_time and self.last_detection_time
            else 0.0
        )
        
        return {
            # Overall stats
            "total_detections": self.total_detections,
            "backchannels_detected": self.backchannels_detected,
            "commands_detected": self.commands_detected,
            "interruptions_prevented": self.interruptions_prevented,
            "interruptions_allowed": self.interruptions_allowed,
            
            # Rates
            "backchannel_rate": round(backchannel_rate, 3),
            "command_rate": round(command_rate, 3),
            "prevention_rate": round(prevention_rate, 3),
            
            # Confidence
            "avg_confidence": round(avg_confidence, 3),
            "avg_backchannel_confidence": round(avg_backchannel_confidence, 3),
            "avg_command_confidence": round(avg_command_confidence, 3),
            "confidence_separation": round(
                abs(avg_backchannel_confidence - avg_command_confidence), 3
            ),
            
            # Performance
            "avg_processing_time_ms": round(avg_processing_time, 2),
            "max_processing_time_ms": round(max(self.processing_times_ms), 2) if self.processing_times_ms else 0.0,
            
            # Feature availability
            "prosody_availability": round(prosody_rate, 3),
            "context_availability": round(context_rate, 3),
            "user_profile_availability": round(user_profile_rate, 3),
            
            # User patterns
            "top_backchannel_phrases": dict(top_backchannels),
            "top_command_phrases": dict(top_commands),
            "unique_backchannel_phrases": len(self.user_backchannel_phrases),
            "unique_command_phrases": len(self.user_command_phrases),
            
            # Session info
            "session_duration_seconds": round(session_duration, 1),
            "detections_per_minute": round(
                (self.total_detections / session_duration * 60)
                if session_duration > 0
                else 0.0,
                2
            ),
        }
    
    def get_health_status(self) -> dict:
        """
        Get health status of backchannel detection system.
        
        Returns status indicators and warnings if any issues detected.
        """
        issues = []
        warnings = []
        
        if self.total_detections == 0:
            return {
                "status": "inactive",
                "message": "No detections yet",
                "issues": [],
                "warnings": [],
            }
        
        # Check confidence separation (should be good separation)
        if self.backchannel_confidence_scores and self.command_confidence_scores:
            avg_bc = sum(self.backchannel_confidence_scores) / len(self.backchannel_confidence_scores)
            avg_cmd = sum(self.command_confidence_scores) / len(self.command_confidence_scores)
            separation = abs(avg_bc - avg_cmd)
            
            if separation < 0.2:
                warnings.append(
                    f"Low confidence separation ({separation:.2f}). "
                    "Model may have difficulty distinguishing backchannels from commands."
                )
        
        # Check processing time
        if self.processing_times_ms:
            avg_time = sum(self.processing_times_ms) / len(self.processing_times_ms)
            max_time = max(self.processing_times_ms)
            
            if avg_time > 5.0:
                warnings.append(
                    f"High average processing time ({avg_time:.1f}ms). "
                    "May impact real-time performance."
                )
            if max_time > 20.0:
                issues.append(
                    f"Very high max processing time ({max_time:.1f}ms). "
                    "Check for performance bottlenecks."
                )
        
        # Check feature availability
        if self.total_detections > 10:
            prosody_rate = self.prosody_available_count / self.total_detections
            if prosody_rate < 0.5:
                warnings.append(
                    f"Low prosody availability ({prosody_rate:.1%}). "
                    "Consider enabling audio feature extraction."
                )
        
        # Determine overall status
        if issues:
            status = "issues"
        elif warnings:
            status = "warnings"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_detections": self.total_detections,
            "issues": issues,
            "warnings": warnings,
            "metrics": self.get_summary(),
        }
    
    def reset(self) -> None:
        """Reset all statistics."""
        self.__init__()
