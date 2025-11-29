"""Unit tests for semantic interruption handling."""

import pytest

from livekit.agents.voice.interruption import (
    InterruptionClassifier,
    InterruptionConfig,
    UtteranceType,
)


class TestInterruptionClassifier:
    """Test the InterruptionClassifier logic."""

    def test_pure_backchannel(self):
        """Pure backchannel words should be classified as BACKCHANNEL."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("yeah") == UtteranceType.BACKCHANNEL
        assert classifier.classify("ok") == UtteranceType.BACKCHANNEL
        assert classifier.classify("hmm") == UtteranceType.BACKCHANNEL
        assert classifier.classify("yeah ok") == UtteranceType.BACKCHANNEL
        assert classifier.classify("ok hmm right") == UtteranceType.BACKCHANNEL
        assert classifier.classify("yeah, ok, right") == UtteranceType.BACKCHANNEL

    def test_pure_command(self):
        """Pure command words should be classified as COMMAND."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("stop") == UtteranceType.COMMAND
        assert classifier.classify("wait") == UtteranceType.COMMAND
        assert classifier.classify("no") == UtteranceType.COMMAND
        assert classifier.classify("pause") == UtteranceType.COMMAND

    def test_command_phrases(self):
        """Command phrases should be classified as COMMAND."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("wait a second") == UtteranceType.COMMAND
        assert classifier.classify("hold on") == UtteranceType.COMMAND
        assert classifier.classify("hang on") == UtteranceType.COMMAND
        assert classifier.classify("wait a minute") == UtteranceType.COMMAND

    def test_mixed_backchannel_and_command(self):
        """Mixed backchannel + command should be classified as COMMAND."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        # Command word overrides backchannel
        assert classifier.classify("yeah wait") == UtteranceType.COMMAND
        assert classifier.classify("ok but stop") == UtteranceType.COMMAND
        assert classifier.classify("yeah okay but wait a second") == UtteranceType.COMMAND

    def test_normal_content(self):
        """Normal content should be classified as NORMAL."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("Can you repeat that?") == UtteranceType.NORMAL
        assert classifier.classify("What time is it?") == UtteranceType.NORMAL
        assert classifier.classify("Tell me more") == UtteranceType.NORMAL
        assert classifier.classify("I disagree with that") == UtteranceType.NORMAL

    def test_empty_and_noise(self):
        """Empty text and noise should be classified as BACKCHANNEL."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("") == UtteranceType.BACKCHANNEL
        assert classifier.classify("   ") == UtteranceType.BACKCHANNEL
        assert classifier.classify("...") == UtteranceType.BACKCHANNEL

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        config = InterruptionConfig()
        classifier = InterruptionClassifier(config)

        assert classifier.classify("YEAH") == UtteranceType.BACKCHANNEL
        assert classifier.classify("Yeah") == UtteranceType.BACKCHANNEL
        assert classifier.classify("STOP") == UtteranceType.COMMAND
        assert classifier.classify("Stop") == UtteranceType.COMMAND
        assert classifier.classify("WAIT A SECOND") == UtteranceType.COMMAND

    def test_custom_config(self):
        """Custom configuration should work correctly."""
        config = InterruptionConfig(
            ignore_words={"yep", "nope"},
            command_words={"halt", "freeze"},
            command_phrases={"give me a sec"},
        )
        classifier = InterruptionClassifier(config)

        assert classifier.classify("yep") == UtteranceType.BACKCHANNEL
        assert classifier.classify("nope") == UtteranceType.BACKCHANNEL
        assert classifier.classify("halt") == UtteranceType.COMMAND
        assert classifier.classify("freeze") == UtteranceType.COMMAND
        assert classifier.classify("give me a sec") == UtteranceType.COMMAND

        # Default words should not work with custom config
        assert classifier.classify("yeah") == UtteranceType.NORMAL
        assert classifier.classify("stop") == UtteranceType.NORMAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
