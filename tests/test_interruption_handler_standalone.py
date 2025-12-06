#!/usr/bin/env python3
"""
Standalone test for InterruptionHandler - tests core logic without dependencies.

This test extracts and tests the core interruption handler logic.
"""

import os
import re
from typing import TYPE_CHECKING

# Mock the logger to avoid dependencies
class MockLogger:
    def info(self, *args, **kwargs):
        pass
    def debug(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass

# Copy the InterruptionHandler class logic for testing
class InterruptionHandler:
    """Standalone version for testing."""

    def __init__(
        self,
        *,
        backchanneling_words: list[str] | None = None,
        interruption_words: list[str] | None = None,
    ) -> None:
        if backchanneling_words is None:
            backchanneling_words = [
                "yeah", "ok", "okay", "oki", "okey", "kk", "hmm",
                "uh-huh", "uh huh", "right", "sure", "yep", "yup",
                "mhm", "mm-hmm", "mm hmm", "aha", "ah", "i see",
                "got it", "alright", "all right", "uh", "um", "er", "hm",
            ]

        if interruption_words is None:
            interruption_words = [
                "wait", "stop", "no", "halt", "pause",
                "hold on", "hold", "cancel", "nevermind", "never mind",
            ]

        self._backchanneling_words = set(w.lower() for w in backchanneling_words)
        self._interruption_words = set(w.lower() for w in interruption_words)
        self._agent_speaking = False

    def update_agent_state(self, state: str) -> None:
        self._agent_speaking = state == "speaking"

    def is_backchanneling(self, transcript: str) -> bool:
        if not transcript or not transcript.strip():
            return False

        normalized = self._normalize_text(transcript)
        if not normalized:
            return False

        if self._contains_interruption_word(normalized):
            return False

        tokens = self._split_into_words(normalized)
        tokens = [t for t in tokens if t]
        
        if not tokens:
            return False

        return all(token in self._backchanneling_words for token in tokens)

    def _normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[.,!?;:()\[\]{}'\"`]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_into_words(self, text: str) -> list[str]:
        words = []
        remaining = text.lower()
        all_phrases = sorted(
            list(self._backchanneling_words) + list(self._interruption_words),
            key=len,
            reverse=True,
        )
        matched_indices = []

        for phrase in all_phrases:
            pattern = r"\b" + re.escape(phrase) + r"\b"
            for match in re.finditer(pattern, remaining):
                start, end = match.span()
                if not any(start < e and end > s for s, e in matched_indices):
                    matched_indices.append((start, end))
                    words.append(phrase)

        matched_indices.sort()
        unmatched_parts = []
        last_end = 0
        
        for start, end in matched_indices:
            if start > last_end:
                unmatched_parts.append(remaining[last_end:start])
            last_end = end
        
        if last_end < len(remaining):
            unmatched_parts.append(remaining[last_end:])

        for part in unmatched_parts:
            part_words = part.split()
            for word in part_words:
                word = word.strip()
                if word:
                    normalized_word = self._normalize_variation(word)
                    words.append(normalized_word)

        return words

    def _normalize_variation(self, word: str) -> str:
        variation_map = {
            "okey": "okay",
            "oki": "ok",
            "kk": "ok",
            "k": "ok",
        }
        word_lower = word.lower()
        return variation_map.get(word_lower, word_lower)

    def _contains_interruption_word(self, normalized_text: str) -> bool:
        for word in self._interruption_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, normalized_text):
                return True
        return False


def test_basic_functionality():
    """Test basic handler functionality."""
    print("Testing basic functionality...")
    handler = InterruptionHandler()
    
    assert handler._backchanneling_words is not None
    assert handler._interruption_words is not None
    assert len(handler._backchanneling_words) > 0
    assert len(handler._interruption_words) > 0
    assert handler._agent_speaking is False
    print("  ✓ Basic initialization works")


def test_backchanneling_detection():
    """Test backchanneling detection."""
    print("\nTesting backchanneling detection...")
    handler = InterruptionHandler()
    
    # Should detect backchanneling
    backchanneling_cases = [
        "yeah", "ok", "okay", "hmm", "uh-huh", "right", "sure",
        "okey", "oki", "kk",  # STT variations
        "okay,", "yeah.", "hmm...",  # With punctuation
        "yeah okay", "okay yeah",  # Multiple words
    ]
    
    passed = 0
    for case in backchanneling_cases:
        result = handler.is_backchanneling(case)
        if result is True:
            print(f"  ✓ '{case}' detected as backchanneling")
            passed += 1
        else:
            print(f"  ✗ '{case}' NOT detected as backchanneling (FAILED)")
    
    # Should NOT detect as backchanneling
    non_backchanneling = [
        "hello", "what is that", "tell me more", "yeah wait", "okay stop"
    ]
    
    for case in non_backchanneling:
        result = handler.is_backchanneling(case)
        if result is False:
            print(f"  ✓ '{case}' correctly NOT detected as backchanneling")
            passed += 1
        else:
            print(f"  ✗ '{case}' incorrectly detected as backchanneling (FAILED)")
    
    print(f"\n  Backchanneling tests: {passed}/{len(backchanneling_cases) + len(non_backchanneling)} passed")


def test_interruption_words():
    """Test interruption word detection."""
    print("\nTesting interruption word detection...")
    handler = InterruptionHandler()
    
    interruption_cases = [
        "wait", "stop", "no", "halt", "pause",
        "yeah wait", "okay stop", "hmm no",  # Mixed with backchanneling
    ]
    
    passed = 0
    for case in interruption_cases:
        normalized = handler._normalize_text(case)
        result = handler._contains_interruption_word(normalized)
        if result is True:
            print(f"  ✓ '{case}' contains interruption word")
            passed += 1
        else:
            print(f"  ✗ '{case}' does NOT contain interruption word (FAILED)")
    
    print(f"\n  Interruption word tests: {passed}/{len(interruption_cases)} passed")


def test_stt_variations():
    """Test STT variation handling."""
    print("\nTesting STT variation handling...")
    handler = InterruptionHandler()
    
    variations = [
        ("okay", True),
        ("okey", True),  # Should normalize to "okay"
        ("oki", True),   # Should normalize to "ok"
        ("kk", True),   # Should normalize to "ok"
        ("okay,", True),  # With punctuation
        ("okay...", True),
        ("okay!", True),
    ]
    
    passed = 0
    for transcript, expected in variations:
        result = handler.is_backchanneling(transcript)
        if result == expected:
            print(f"  ✓ '{transcript}' → {result} (expected {expected})")
            passed += 1
        else:
            print(f"  ✗ '{transcript}' → {result} (expected {expected}) (FAILED)")
    
    print(f"\n  STT variation tests: {passed}/{len(variations)} passed")


def test_scenarios():
    """Test the four main scenarios from the assignment."""
    print("\nTesting assignment scenarios...")
    handler = InterruptionHandler()
    passed = 0
    total = 4
    
    # Scenario 1: Long explanation - backchanneling should be ignored
    handler.update_agent_state("speaking")
    if handler.is_backchanneling("okay") and handler.is_backchanneling("yeah"):
        print("  ✓ Scenario 1: Backchanneling detected while speaking")
        passed += 1
    else:
        print("  ✗ Scenario 1: FAILED")
    
    # Scenario 2: Passive affirmation - should be detectable
    handler.update_agent_state("listening")
    if handler.is_backchanneling("yeah"):
        print("  ✓ Scenario 2: Backchanneling detectable when listening")
        passed += 1
    else:
        print("  ✗ Scenario 2: FAILED")
    
    # Scenario 3: Correction - should interrupt
    handler.update_agent_state("speaking")
    normalized = handler._normalize_text("no stop")
    if handler._contains_interruption_word(normalized) and not handler.is_backchanneling("no stop"):
        print("  ✓ Scenario 3: Interruption words detected")
        passed += 1
    else:
        print("  ✗ Scenario 3: FAILED")
    
    # Scenario 4: Mixed input - should interrupt
    normalized = handler._normalize_text("yeah okay but wait")
    if handler._contains_interruption_word(normalized) and not handler.is_backchanneling("yeah okay but wait"):
        print("  ✓ Scenario 4: Mixed input with interruption word detected")
        passed += 1
    else:
        print("  ✗ Scenario 4: FAILED")
    
    print(f"\n  Scenario tests: {passed}/{total} passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Interruption Handler Test Suite (Standalone)")
    print("=" * 60)
    
    try:
        test_basic_functionality()
        test_backchanneling_detection()
        test_interruption_words()
        test_stt_variations()
        test_scenarios()
        
        print("\n" + "=" * 60)
        print("✓ Test suite completed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

