"""
Comprehensive Tests for Advanced Backchannel Detection System

Tests all components:
- Confidence scoring
- Audio feature extraction
- ML classifier
- User profiles
- Context analysis
- Multi-language support
- Metrics collection
"""

import asyncio
import numpy as np
import pytest
from unittest.mock import Mock, patch

# Import components to test
from livekit.agents.voice.backchannel.confidence import (
    BackchannelConfidence,
    ConfidenceScorer,
)
from livekit.agents.voice.backchannel.audio_features import (
    AudioFeatureExtractor,
    AudioFeatures,
)
from livekit.agents.voice.backchannel.classifier import (
    BackchannelClassifier,
    ClassificationResult,
)
from livekit.agents.voice.backchannel.user_profile import (
    UserBackchannelProfile,
    UserProfileManager,
)
from livekit.agents.voice.backchannel.context_analyzer import (
    ContextAnalyzer,
    ContextFeatures,
)
from livekit.agents.voice.backchannel.language_support import (
    Language,
    LanguageProfile,
    MultiLanguageBackchannelDetector,
)
from livekit.agents.metrics.backchannel_metrics import (
    BackchannelMetrics,
    BackchannelStatsCollector,
)


class TestConfidenceScorer:
    """Test confidence scoring system."""
    
    def test_scorer_initialization(self):
        """Test scorer initializes correctly."""
        scorer = ConfidenceScorer(
            backchannel_words=["yeah", "ok", "hmm"],
            threshold=0.5,
        )
        
        assert scorer._threshold == 0.5
        assert len(scorer._backchannel_words) == 3
    
    def test_word_match_score_all_backchannels(self):
        """Test word matching with all backchannel words."""
        scorer = ConfidenceScorer(backchannel_words=["yeah", "ok"])
        
        confidence = scorer.compute_confidence(
            "yeah ok",
            agent_speaking=True,
        )
        
        assert confidence.word_match_score == 1.0
        assert confidence.decision is True  # All words are backchannels
    
    def test_word_match_score_mixed_input(self):
        """Test word matching with mixed input."""
        scorer = ConfidenceScorer(backchannel_words=["yeah", "ok"])
        
        confidence = scorer.compute_confidence(
            "yeah but wait",
            agent_speaking=True,
        )
        
        # Only 1 of 3 words is backchannel
        assert confidence.word_match_score < 0.5
        assert confidence.decision is False  # Has non-backchannel words
    
    def test_confidence_with_prosody(self):
        """Test confidence with prosody features."""
        scorer = ConfidenceScorer(
            backchannel_words=["yeah"],
            enable_prosody=True,
        )
        
        # Backchannel-like prosody (flat tone, short)
        prosody = {
            "pitch_contour": -0.05,  # Flat/falling
            "duration": 0.4,  # Short
            "energy": 0.5,  # Medium
            "tempo": 1.3,  # Quick
        }
        
        confidence = scorer.compute_confidence(
            "yeah",
            prosody_features=prosody,
            agent_speaking=True,
        )
        
        assert confidence.prosody_score is not None
        assert confidence.prosody_score > 0.5  # Should favor backchannel
    
    def test_threshold_update(self):
        """Test dynamic threshold updates."""
        scorer = ConfidenceScorer(threshold=0.5)
        
        scorer.update_threshold(0.7)
        assert scorer._threshold == 0.7
        
        # Test bounds
        scorer.update_threshold(1.5)
        assert scorer._threshold == 1.0
        
        scorer.update_threshold(-0.1)
        assert scorer._threshold == 0.0
    
    def test_statistics_tracking(self):
        """Test statistics are tracked correctly."""
        scorer = ConfidenceScorer(backchannel_words=["yeah", "ok"])
        
        # Generate some classifications
        scorer.compute_confidence("yeah", agent_speaking=True)
        scorer.compute_confidence("stop", agent_speaking=True)
        scorer.compute_confidence("ok", agent_speaking=True)
        
        stats = scorer.get_stats()
        assert stats["total_analyzed"] == 3
        assert stats["backchannels_detected"] >= 2
        assert stats["commands_detected"] >= 1


class TestAudioFeatureExtractor:
    """Test audio feature extraction."""
    
    def test_extractor_initialization(self):
        """Test extractor initializes correctly."""
        extractor = AudioFeatureExtractor(sample_rate=16000)
        assert extractor._sample_rate == 16000
    
    def test_simplified_features(self):
        """Test simplified feature extraction."""
        extractor = AudioFeatureExtractor()
        
        features = extractor.extract_features_simple(
            duration=0.5,
            speech_duration=0.4,
        )
        
        assert "duration" in features
        assert "pause_ratio" in features
        assert "is_short" in features
        assert features["is_short"] is True  # 0.5s is short
    
    def test_baseline_updates(self):
        """Test baseline updates."""
        extractor = AudioFeatureExtractor()
        
        extractor.update_baselines(
            pitch=220.0,
            energy=0.15,
            tempo=1.2,
        )
        
        assert extractor._baseline_pitch == 220.0
        assert extractor._baseline_energy == 0.15
        assert extractor._baseline_tempo == 1.2


class TestBackchannelClassifier:
    """Test ML-based classifier."""
    
    def test_classifier_initialization(self):
        """Test classifier initializes."""
        classifier = BackchannelClassifier()
        assert classifier._model_name == "all-MiniLM-L6-v2"
    
    def test_fallback_classification(self):
        """Test fallback rule-based classification."""
        classifier = BackchannelClassifier()
        
        # Even without ML model, fallback should work
        result = classifier.classify("yeah")
        
        assert isinstance(result, ClassificationResult)
        assert result.method == "fallback" or result.method == "ml"
        assert 0 <= result.confidence <= 1
    
    def test_backchannel_patterns(self):
        """Test backchannel pattern recognition."""
        classifier = BackchannelClassifier()
        
        # Test various backchannel words
        for word in ["yeah", "ok", "uh-huh", "mm-hmm"]:
            result = classifier.classify(word)
            assert result.is_backchannel is True
    
    def test_command_patterns(self):
        """Test command pattern recognition."""
        classifier = BackchannelClassifier()
        
        # Test various command words
        for word in ["wait", "stop", "what", "repeat"]:
            result = classifier.classify(word)
            assert result.is_backchannel is False
    
    def test_add_patterns(self):
        """Test adding new patterns."""
        classifier = BackchannelClassifier()
        
        initial_count = len(classifier.BACKCHANNEL_PATTERNS)
        classifier.add_backchannel_pattern("custom-backchannel")
        
        assert len(classifier.BACKCHANNEL_PATTERNS) == initial_count + 1
        assert "custom-backchannel" in classifier.BACKCHANNEL_PATTERNS


class TestUserProfile:
    """Test user profile and learning."""
    
    def test_profile_creation(self):
        """Test profile creation."""
        profile = UserBackchannelProfile(user_id="test_user")
        
        assert profile.user_id == "test_user"
        assert profile.total_interactions == 0
        assert len(profile.backchannel_phrases) == 0
    
    def test_interaction_recording(self):
        """Test recording interactions."""
        profile = UserBackchannelProfile(user_id="test_user")
        
        profile.record_interaction("yeah", is_backchannel=True)
        profile.record_interaction("yeah", is_backchannel=True)
        profile.record_interaction("stop", is_backchannel=False)
        
        assert profile.total_interactions == 3
        assert profile.total_backchannels == 2
        assert profile.total_commands == 1
        assert profile.backchannel_phrases["yeah"] == 2
        assert profile.command_phrases["stop"] == 1
    
    def test_phrase_confidence(self):
        """Test phrase confidence based on history."""
        profile = UserBackchannelProfile(user_id="test_user")
        
        # Record "yeah" 9 times as backchannel, 1 time as command
        for _ in range(9):
            profile.record_interaction("yeah", is_backchannel=True)
        profile.record_interaction("yeah", is_backchannel=False)
        
        confidence = profile.get_phrase_confidence("yeah")
        assert confidence == 0.9  # 9 out of 10
    
    def test_threshold_adaptation(self):
        """Test threshold adaptation."""
        profile = UserBackchannelProfile(user_id="test_user")
        
        # Good accuracy, should keep threshold
        new_threshold = profile.adapt_threshold(0.5, accuracy=0.90)
        assert new_threshold == 0.5
        assert profile.optimal_threshold == 0.5
    
    def test_serialization(self):
        """Test profile serialization."""
        profile = UserBackchannelProfile(user_id="test_user")
        profile.record_interaction("yeah", is_backchannel=True)
        
        # To dict
        data = profile.to_dict()
        assert data["user_id"] == "test_user"
        assert data["total_backchannels"] == 1
        
        # From dict
        restored = UserBackchannelProfile.from_dict(data)
        assert restored.user_id == profile.user_id
        assert restored.total_backchannels == profile.total_backchannels


class TestProfileManager:
    """Test user profile manager."""
    
    def test_manager_initialization(self):
        """Test manager initializes."""
        manager = UserProfileManager(profiles_dir=".test_profiles")
        assert manager._profiles_dir.name == ".test_profiles"
    
    def test_get_or_create_profile(self):
        """Test getting or creating profiles."""
        manager = UserProfileManager(profiles_dir=".test_profiles")
        
        # Get new profile
        profile = manager.get_profile("user1")
        assert profile.user_id == "user1"
        assert profile.total_interactions == 0
        
        # Get same profile again
        profile2 = manager.get_profile("user1")
        assert profile2 is profile  # Same object
    
    def test_record_interaction(self):
        """Test recording through manager."""
        manager = UserProfileManager(
            profiles_dir=".test_profiles",
            auto_save=False,  # Disable for testing
        )
        
        manager.record_interaction("user1", "yeah", is_backchannel=True)
        
        profile = manager.get_profile("user1")
        assert profile.total_interactions == 1


class TestContextAnalyzer:
    """Test context analysis."""
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes."""
        analyzer = ContextAnalyzer()
        assert analyzer._enable_llm is False
    
    def test_negation_detection(self):
        """Test negation pattern detection."""
        analyzer = ContextAnalyzer()
        
        assert analyzer._has_negation("don't stop") is True
        assert analyzer._has_negation("do not interrupt") is True
        assert analyzer._has_negation("yeah ok") is False
    
    def test_question_detection(self):
        """Test question detection."""
        analyzer = ContextAnalyzer()
        
        assert analyzer._is_question("what do you mean?") is True
        assert analyzer._is_question("why is that?") is True
        assert analyzer._is_question("yeah ok") is False
    
    def test_feature_extraction(self):
        """Test context feature extraction."""
        analyzer = ContextAnalyzer()
        
        features = analyzer.extract_features(
            "yeah",
            agent_speaking=True,
            agent_utterance="Let me explain how this works...",
        )
        
        assert isinstance(features, ContextFeatures)
        assert features.agent_asked_question is False
        assert features.has_negation is False
    
    def test_context_score(self):
        """Test context score computation."""
        analyzer = ContextAnalyzer()
        
        features = ContextFeatures(
            agent_utterance_duration=8.0,  # Long utterance
            agent_asked_question=False,
            agent_utterance_length=50,
            has_negation=False,
            is_mid_sentence=False,
            after_silence=False,
            turns_since_user_spoke=2,
            conversation_topic=None,
            time_since_agent_started_speaking=8.0,
            time_since_user_last_spoke=None,
        )
        
        score = analyzer.compute_context_score("yeah", features, agent_speaking=True)
        
        # Long utterance should favor backchannel
        assert score > 0.5
    
    def test_state_updates(self):
        """Test conversation state tracking."""
        analyzer = ContextAnalyzer()
        
        analyzer.update_state(agent_started_speaking=True)
        assert analyzer._agent_speaking_start_time is not None
        
        analyzer.update_state(user_spoke=True)
        assert analyzer._user_last_spoke_time is not None
        
        analyzer.reset()
        assert analyzer._agent_speaking_start_time is None


class TestMultiLanguageSupport:
    """Test multi-language support."""
    
    def test_language_profiles_exist(self):
        """Test all language profiles are defined."""
        from livekit.agents.voice.backchannel.language_support import LANGUAGE_PROFILES
        
        assert len(LANGUAGE_PROFILES) >= 12
        assert Language.ENGLISH in LANGUAGE_PROFILES
        assert Language.SPANISH in LANGUAGE_PROFILES
        assert Language.MANDARIN in LANGUAGE_PROFILES
    
    def test_language_profile_structure(self):
        """Test language profile has required fields."""
        from livekit.agents.voice.backchannel.language_support import LANGUAGE_PROFILES
        
        profile = LANGUAGE_PROFILES[Language.ENGLISH]
        
        assert isinstance(profile, LanguageProfile)
        assert len(profile.backchannel_words) > 0
        assert len(profile.command_words) > 0
    
    def test_multilanguage_detector(self):
        """Test multi-language detector."""
        detector = MultiLanguageBackchannelDetector()
        
        words = detector.get_backchannel_words()
        assert len(words) > 0
    
    def test_language_detection(self):
        """Test language detection."""
        detector = MultiLanguageBackchannelDetector(auto_detect=True)
        
        # Should detect or default to English
        words = detector.get_backchannel_words(text="yeah ok")
        assert "yeah" in words or len(words) > 0
    
    def test_get_all_words(self):
        """Test getting words for multiple languages."""
        detector = MultiLanguageBackchannelDetector()
        
        backchannels, commands = detector.get_all_words()
        
        assert len(backchannels) > 50  # Should have many words
        assert len(commands) > 30
        assert "yeah" in backchannels
        assert "wait" in commands


class TestBackchannelMetrics:
    """Test metrics collection."""
    
    def test_stats_collector_initialization(self):
        """Test stats collector initializes."""
        collector = BackchannelStatsCollector()
        
        assert collector.total_detections == 0
        assert collector.backchannels_detected == 0
    
    def test_record_detection(self):
        """Test recording detections."""
        collector = BackchannelStatsCollector()
        
        # Create mock confidence
        confidence = BackchannelConfidence(
            overall_score=0.8,
            word_match_score=1.0,
            prosody_score=0.7,
            context_score=0.6,
            user_history_score=0.9,
            decision=True,
            threshold=0.5,
            transcript="yeah",
        )
        
        collector.record_detection(
            confidence,
            agent_speaking=True,
            interrupted=False,
            prevented_interruption=True,
            processing_time_ms=2.5,
        )
        
        assert collector.total_detections == 1
        assert collector.backchannels_detected == 1
        assert collector.interruptions_prevented == 1
    
    def test_summary_generation(self):
        """Test summary statistics."""
        collector = BackchannelStatsCollector()
        
        # Record multiple detections
        for i in range(10):
            confidence = BackchannelConfidence(
                overall_score=0.8,
                word_match_score=1.0,
                prosody_score=None,
                context_score=0.5,
                user_history_score=None,
                decision=i < 7,  # 7 backchannels, 3 commands
                threshold=0.5,
                transcript="test",
            )
            
            collector.record_detection(
                confidence,
                agent_speaking=True,
                interrupted=False,
                prevented_interruption=i < 7,
                processing_time_ms=2.0,
            )
        
        summary = collector.get_summary()
        
        assert summary["total_detections"] == 10
        assert summary["backchannels_detected"] == 7
        assert summary["commands_detected"] == 3
        assert summary["backchannel_rate"] == 0.7
    
    def test_health_status(self):
        """Test health status monitoring."""
        collector = BackchannelStatsCollector()
        
        health = collector.get_health_status()
        assert health["status"] == "inactive"  # No detections yet
        
        # Add some detections
        confidence = BackchannelConfidence(
            overall_score=0.9,
            word_match_score=1.0,
            prosody_score=0.8,
            context_score=0.7,
            user_history_score=0.9,
            decision=True,
            threshold=0.5,
            transcript="yeah",
        )
        
        for _ in range(20):
            collector.record_detection(
                confidence,
                agent_speaking=True,
                interrupted=False,
                prevented_interruption=True,
                processing_time_ms=2.0,
            )
        
        health = collector.get_health_status()
        assert health["status"] in ["healthy", "warnings"]


class TestIntegration:
    """Integration tests for the complete system."""
    
    def test_end_to_end_backchannel(self):
        """Test complete backchannel detection flow."""
        # Setup
        scorer = ConfidenceScorer(
            backchannel_words=["yeah", "ok", "hmm"],
            threshold=0.5,
        )
        
        classifier = BackchannelClassifier()
        profile = UserBackchannelProfile(user_id="test")
        collector = BackchannelStatsCollector()
        
        # Test backchannel input
        transcript = "yeah"
        
        # Classify
        ml_result = classifier.classify(transcript)
        
        # Compute confidence
        confidence = scorer.compute_confidence(
            transcript,
            agent_speaking=True,
        )
        
        # Record in profile
        profile.record_interaction(transcript, confidence.decision, confidence)
        
        # Record metrics
        collector.record_detection(
            confidence,
            agent_speaking=True,
            interrupted=False,
            prevented_interruption=confidence.decision,
            processing_time_ms=5.0,
        )
        
        # Verify
        assert confidence.decision is True  # Should be backchannel
        assert profile.total_backchannels == 1
        assert collector.interruptions_prevented == 1
    
    def test_end_to_end_command(self):
        """Test complete command detection flow."""
        scorer = ConfidenceScorer(
            backchannel_words=["yeah", "ok"],
            threshold=0.5,
        )
        
        # Test command input
        transcript = "wait stop"
        
        confidence = scorer.compute_confidence(
            transcript,
            agent_speaking=True,
        )
        
        # Should NOT be backchannel
        assert confidence.decision is False
        assert confidence.word_match_score < 0.5


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

