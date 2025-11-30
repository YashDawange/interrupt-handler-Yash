"""
Audio Feature Extraction for Backchannel Detection

Extracts prosodic and acoustic features from audio to help distinguish:
- Backchannels: "yeah" (flat/falling tone, short, medium energy)
- Questions: "yeah?" (rising tone, longer, higher energy)
- Commands: "stop!" (emphasis, high energy, clear articulation)

Features extracted:
- Pitch contour (rising vs falling)
- Energy/loudness
- Duration
- Tempo/speech rate
- Emphasis/stress patterns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from livekit import rtc

logger = logging.getLogger(__name__)


@dataclass
class AudioFeatures:
    """
    Prosodic and acoustic features extracted from audio.
    
    All values normalized to 0-1 range where possible for easier comparison.
    """
    
    # Pitch features
    pitch_mean: float  # Average pitch (normalized 0-1)
    pitch_std: float  # Pitch variation
    pitch_contour: float  # -1 (falling) to +1 (rising)
    pitch_range: float  # Max - min pitch
    
    # Energy features
    energy_mean: float  # Average energy (normalized 0-1)
    energy_std: float  # Energy variation
    energy_peak: float  # Peak energy
    
    # Temporal features
    duration: float  # Duration in seconds
    tempo: float  # Speech rate (relative to baseline)
    pause_ratio: float  # Ratio of silence to speech
    
    # Derived features
    is_rising_tone: bool  # True if pitch rises (question-like)
    is_emphatic: bool  # True if high energy + pitch variation
    is_hesitant: bool  # True if many pauses, low energy
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/analysis."""
        return {
            "pitch_mean": round(self.pitch_mean, 3),
            "pitch_contour": round(self.pitch_contour, 3),
            "energy_mean": round(self.energy_mean, 3),
            "duration": round(self.duration, 3),
            "tempo": round(self.tempo, 3),
            "is_rising_tone": self.is_rising_tone,
            "is_emphatic": self.is_emphatic,
            "is_hesitant": self.is_hesitant,
        }


class AudioFeatureExtractor:
    """
    Extracts audio features for backchannel detection.
    
    Uses lightweight signal processing (no heavy ML models) for real-time performance.
    """
    
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
    ):
        """
        Initialize feature extractor.
        
        Args:
            sample_rate: Audio sample rate in Hz
            frame_duration_ms: Frame duration in milliseconds
        """
        self._sample_rate = sample_rate
        self._frame_duration_ms = frame_duration_ms
        self._frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Baseline values for normalization (learned from typical speech)
        self._baseline_pitch = 200.0  # Hz
        self._baseline_energy = 0.1
        self._baseline_tempo = 1.0
        
        logger.info(
            f"AudioFeatureExtractor initialized: "
            f"sample_rate={sample_rate}, frame_duration={frame_duration_ms}ms"
        )
    
    def extract_features(
        self,
        audio_frames: list[rtc.AudioFrame],
    ) -> AudioFeatures | None:
        """
        Extract audio features from a sequence of audio frames.
        
        Args:
            audio_frames: List of audio frames from user speech
            
        Returns:
            AudioFeatures object or None if extraction fails
        """
        try:
            # Convert frames to numpy array
            audio_data = self._frames_to_numpy(audio_frames)
            
            if audio_data is None or len(audio_data) == 0:
                return None
            
            # Extract individual features
            pitch_features = self._extract_pitch_features(audio_data)
            energy_features = self._extract_energy_features(audio_data)
            temporal_features = self._extract_temporal_features(audio_data)
            
            # Derive high-level features
            is_rising_tone = pitch_features["contour"] > 0.1
            is_emphatic = (
                energy_features["peak"] > 0.7
                and pitch_features["std"] > 0.3
            )
            is_hesitant = (
                temporal_features["pause_ratio"] > 0.3
                and energy_features["mean"] < 0.4
            )
            
            return AudioFeatures(
                pitch_mean=pitch_features["mean"],
                pitch_std=pitch_features["std"],
                pitch_contour=pitch_features["contour"],
                pitch_range=pitch_features["range"],
                energy_mean=energy_features["mean"],
                energy_std=energy_features["std"],
                energy_peak=energy_features["peak"],
                duration=temporal_features["duration"],
                tempo=temporal_features["tempo"],
                pause_ratio=temporal_features["pause_ratio"],
                is_rising_tone=is_rising_tone,
                is_emphatic=is_emphatic,
                is_hesitant=is_hesitant,
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract audio features: {e}")
            return None
    
    def extract_features_simple(
        self,
        duration: float,
        speech_duration: float,
    ) -> dict[str, float]:
        """
        Extract simplified features when full audio isn't available.
        
        Uses only timing information (duration and pauses).
        
        Args:
            duration: Total duration including pauses
            speech_duration: Actual speech duration (no pauses)
            
        Returns:
            Dictionary of simplified features
        """
        pause_ratio = (
            (duration - speech_duration) / duration
            if duration > 0
            else 0.0
        )
        
        # Short utterances are typically backchannels
        is_short = duration < 0.5
        
        # High pause ratio suggests hesitation
        is_hesitant = pause_ratio > 0.3
        
        return {
            "duration": duration,
            "speech_duration": speech_duration,
            "pause_ratio": pause_ratio,
            "is_short": is_short,
            "is_hesitant": is_hesitant,
            "tempo": 1.0,  # Unknown, use baseline
        }
    
    def _frames_to_numpy(
        self,
        frames: list[rtc.AudioFrame],
    ) -> np.ndarray | None:
        """Convert audio frames to numpy array."""
        if not frames:
            return None
        
        try:
            # Concatenate all frame data
            audio_data = np.concatenate([
                np.frombuffer(frame.data.tobytes(), dtype=np.int16)
                for frame in frames
            ])
            
            # Convert to float and normalize to [-1, 1]
            audio_data = audio_data.astype(np.float32) / 32768.0
            
            return audio_data
            
        except Exception as e:
            logger.warning(f"Failed to convert frames to numpy: {e}")
            return None
    
    def _extract_pitch_features(self, audio_data: np.ndarray) -> dict:
        """
        Extract pitch-related features.
        
        Uses autocorrelation for pitch estimation (lightweight, no ML).
        """
        try:
            # Simple pitch estimation using autocorrelation
            pitches = []
            
            # Process in overlapping windows
            window_size = int(self._sample_rate * 0.03)  # 30ms windows
            hop_size = window_size // 2
            
            for i in range(0, len(audio_data) - window_size, hop_size):
                window = audio_data[i:i + window_size]
                
                # Apply window function
                window = window * np.hanning(len(window))
                
                # Autocorrelation
                autocorr = np.correlate(window, window, mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                
                # Find first peak after initial peak
                # (corresponds to fundamental frequency)
                min_period = int(self._sample_rate / 500)  # Max 500 Hz
                max_period = int(self._sample_rate / 50)   # Min 50 Hz
                
                if len(autocorr) > max_period:
                    autocorr_segment = autocorr[min_period:max_period]
                    if len(autocorr_segment) > 0:
                        peak_idx = np.argmax(autocorr_segment) + min_period
                        pitch_hz = self._sample_rate / peak_idx
                        pitches.append(pitch_hz)
            
            if not pitches:
                # Return neutral values if no pitch detected
                return {
                    "mean": 0.5,
                    "std": 0.0,
                    "contour": 0.0,
                    "range": 0.0,
                }
            
            pitches = np.array(pitches)
            
            # Normalize pitch to 0-1 range (relative to baseline)
            pitch_normalized = pitches / (self._baseline_pitch * 2)
            pitch_normalized = np.clip(pitch_normalized, 0, 1)
            
            # Calculate pitch contour (rising vs falling)
            if len(pitches) > 1:
                # Linear regression slope
                x = np.arange(len(pitches))
                slope = np.polyfit(x, pitches, 1)[0]
                # Normalize slope to [-1, 1]
                contour = np.clip(slope / 50, -1, 1)  # 50 Hz per frame = strong rise/fall
            else:
                contour = 0.0
            
            return {
                "mean": float(np.mean(pitch_normalized)),
                "std": float(np.std(pitch_normalized)),
                "contour": float(contour),
                "range": float(np.max(pitch_normalized) - np.min(pitch_normalized)),
            }
            
        except Exception as e:
            logger.warning(f"Pitch extraction failed: {e}")
            return {
                "mean": 0.5,
                "std": 0.0,
                "contour": 0.0,
                "range": 0.0,
            }
    
    def _extract_energy_features(self, audio_data: np.ndarray) -> dict:
        """Extract energy/loudness features."""
        try:
            # RMS energy
            energy = np.sqrt(np.mean(audio_data ** 2))
            
            # Peak energy
            peak_energy = np.max(np.abs(audio_data))
            
            # Energy variation (std of frame energies)
            window_size = int(self._sample_rate * 0.02)  # 20ms windows
            frame_energies = []
            
            for i in range(0, len(audio_data) - window_size, window_size):
                frame = audio_data[i:i + window_size]
                frame_energy = np.sqrt(np.mean(frame ** 2))
                frame_energies.append(frame_energy)
            
            energy_std = np.std(frame_energies) if frame_energies else 0.0
            
            # Normalize to 0-1 range
            energy_normalized = min(1.0, energy / self._baseline_energy)
            peak_normalized = min(1.0, peak_energy)
            energy_std_normalized = min(1.0, energy_std / self._baseline_energy)
            
            return {
                "mean": float(energy_normalized),
                "std": float(energy_std_normalized),
                "peak": float(peak_normalized),
            }
            
        except Exception as e:
            logger.warning(f"Energy extraction failed: {e}")
            return {
                "mean": 0.5,
                "std": 0.0,
                "peak": 0.5,
            }
    
    def _extract_temporal_features(self, audio_data: np.ndarray) -> dict:
        """Extract temporal/timing features."""
        try:
            # Total duration
            duration = len(audio_data) / self._sample_rate
            
            # Detect speech vs silence using simple energy threshold
            window_size = int(self._sample_rate * 0.02)  # 20ms windows
            threshold = 0.01  # Energy threshold for speech detection
            
            speech_frames = 0
            total_frames = 0
            
            for i in range(0, len(audio_data) - window_size, window_size):
                frame = audio_data[i:i + window_size]
                energy = np.sqrt(np.mean(frame ** 2))
                total_frames += 1
                if energy > threshold:
                    speech_frames += 1
            
            # Speech ratio (inverse of pause ratio)
            speech_ratio = speech_frames / total_frames if total_frames > 0 else 0
            pause_ratio = 1.0 - speech_ratio
            
            # Estimate tempo (speech rate)
            # More frames of speech in less time = faster tempo
            speech_duration = speech_frames * window_size / self._sample_rate
            tempo = (speech_duration / duration) if duration > 0 else 1.0
            
            return {
                "duration": float(duration),
                "tempo": float(tempo / self._baseline_tempo),
                "pause_ratio": float(pause_ratio),
            }
            
        except Exception as e:
            logger.warning(f"Temporal extraction failed: {e}")
            return {
                "duration": 0.0,
                "tempo": 1.0,
                "pause_ratio": 0.0,
            }
    
    def update_baselines(
        self,
        *,
        pitch: float | None = None,
        energy: float | None = None,
        tempo: float | None = None,
    ) -> None:
        """
        Update baseline values for normalization.
        
        Can be called to adapt to user's voice characteristics.
        """
        if pitch is not None:
            self._baseline_pitch = pitch
        if energy is not None:
            self._baseline_energy = energy
        if tempo is not None:
            self._baseline_tempo = tempo
        
        logger.info(
            f"Updated audio baselines: pitch={self._baseline_pitch:.1f}Hz, "
            f"energy={self._baseline_energy:.3f}, tempo={self._baseline_tempo:.2f}"
        )

