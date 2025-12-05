#!/usr/bin/env python3
"""
Quick Test Script for Backchanneling Filter

This script runs a simple test to verify the backchanneling filter
is working correctly with your LiveKit configuration.

Usage:
    python test_with_env.py
"""

import os

# Optional dependency: python-dotenv. If unavailable, use a minimal fallback loader.
try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    def load_dotenv(dotenv_path: str = ".env") -> None:
        """Minimal .env loader: key=value per line, ignores comments/blank lines."""
        if not os.path.exists(dotenv_path):
            return
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

# Load environment variables from .env
load_dotenv()

# Import the backchanneling filter without pulling full dependency tree
# (avoids optional heavy deps like numpy when not installed)
import importlib.util
from pathlib import Path

BACKCHANNEL_PATH = Path(__file__).parent / "livekit-agents" / "livekit" / "agents" / "voice" / "backchanneling_filter.py"

spec = importlib.util.spec_from_file_location("backchanneling_filter", BACKCHANNEL_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load BackchannelingFilter module at {BACKCHANNEL_PATH}")
backchanneling_filter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backchanneling_filter)
BackchannelingFilter = backchanneling_filter.BackchannelingFilter


def test_backchanneling_filter():
    """Test the backchanneling filter with various inputs."""
    
    # Get custom words from environment if set
    ignore_words_env = os.getenv("IGNORE_WORDS", "")
    interrupt_words_env = os.getenv("INTERRUPT_WORDS", "")
    
    # Create filter with custom words if provided
    if ignore_words_env and interrupt_words_env:
        ignore_words = set(ignore_words_env.split(","))
        interrupt_words = set(interrupt_words_env.split(","))
        filter = BackchannelingFilter(
            ignore_words=ignore_words,
            command_keywords=interrupt_words
        )
        print(f"✅ Using custom configuration from .env:")
        print(f"   Ignore words: {ignore_words}")
        print(f"   Interrupt words: {interrupt_words}")
    else:
        filter = BackchannelingFilter()
        print("✅ Using default configuration")
    
    print("\n" + "="*80)
    print("BACKCHANNELING FILTER TEST SUITE")
    print("="*80)
    
    # Test scenarios
    test_cases = [
        # (text, agent_speaking, expected_interrupt, description)
        ("yeah", True, False, "Agent speaking, user says 'yeah'"),
        ("ok", True, False, "Agent speaking, user says 'ok'"),
        ("hmm", True, False, "Agent speaking, user says 'hmm'"),
        ("uh-huh", True, False, "Agent speaking, user says 'uh-huh'"),
        ("right", True, False, "Agent speaking, user says 'right'"),
        ("sure", True, False, "Agent speaking, user says 'sure'"),
        
        ("yeah", False, True, "Agent silent, user says 'yeah'"),
        ("ok", False, True, "Agent silent, user says 'ok'"),
        
        ("stop", True, True, "Agent speaking, user says 'stop'"),
        ("wait", True, True, "Agent speaking, user says 'wait'"),
        ("no", True, True, "Agent speaking, user says 'no'"),
        ("hold on", True, True, "Agent speaking, user says 'hold on'"),
        ("pause", True, True, "Agent speaking, user says 'pause'"),
        
        ("yeah but wait", True, True, "Agent speaking, user says 'yeah but wait'"),
        ("ok hold on", True, True, "Agent speaking, user says 'ok hold on'"),
        ("hmm actually stop", True, True, "Agent speaking, user says 'hmm actually stop'"),
        
        # Multi-word pure backchanneling using the configured ignore list
        ("yeah uh-huh right", True, False, "Agent speaking, multiple backchanneling"),
    ]
    
    passed = 0
    failed = 0
    
    print(f"\nRunning {len(test_cases)} test cases...\n")
    
    for text, agent_speaking, expected_interrupt, description in test_cases:
        result = filter.should_interrupt_agent(text, agent_speaking)
        status = "✅ PASS" if result == expected_interrupt else "❌ FAIL"
        
        if result == expected_interrupt:
            passed += 1
        else:
            failed += 1
        
        state = "speaking" if agent_speaking else "silent"
        action = "INTERRUPT" if result else "IGNORE"
        expected_action = "INTERRUPT" if expected_interrupt else "IGNORE"
        
        print(f"{status} | {description}")
        print(f"      Text: '{text}' | Agent: {state} | Action: {action} | Expected: {expected_action}")
        print()
    
    print("="*80)
    print(f"RESULTS: {passed}/{len(test_cases)} tests passed")
    if failed > 0:
        print(f"❌ {failed} test(s) failed")
    else:
        print("✅ All tests passed!")
    print("="*80)
    
    return failed == 0


def test_environment_config():
    """Test that environment variables are loaded correctly."""
    print("\n" + "="*80)
    print("ENVIRONMENT CONFIGURATION TEST")
    print("="*80 + "\n")
    
    required_vars = {
        "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
        "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
        "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
    }
    
    optional_vars = {
        "IGNORE_WORDS": os.getenv("IGNORE_WORDS"),
        "INTERRUPT_WORDS": os.getenv("INTERRUPT_WORDS"),
        "STT_CONFIDENCE_THRESHOLD": os.getenv("STT_CONFIDENCE_THRESHOLD"),
        "TRANSCRIPTION_BUFFER_MS": os.getenv("TRANSCRIPTION_BUFFER_MS"),
    }
    
    all_ok = True
    
    print("Required Variables:")
    for var, value in required_vars.items():
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var:
                display_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_ok = False
    
    print("\nOptional Variables:")
    for var, value in optional_vars.items():
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚪ {var}: Not set (using defaults)")
    
    print("\n" + "="*80)
    if all_ok:
        print("✅ All required environment variables are set!")
    else:
        print("❌ Some required environment variables are missing!")
    print("="*80 + "\n")
    
    return all_ok


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("LIVEKIT BACKCHANNELING FILTER - CONFIGURATION TEST")
    print("="*80)
    
    # Test environment configuration
    env_ok = test_environment_config()
    
    if not env_ok:
        print("\n⚠️  Warning: Some environment variables are missing.")
        print("   The backchanneling filter will still work, but you won't be able")
        print("   to run the full voice agent demo.\n")
    
    # Test backchanneling filter logic
    tests_ok = test_backchanneling_filter()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Environment Config: {'✅ PASS' if env_ok else '⚠️  PARTIAL'}")
    print(f"Filter Logic Tests: {'✅ PASS' if tests_ok else '❌ FAIL'}")
    print("="*80)
    
    if env_ok and tests_ok:
        print("\n🎉 Everything is working perfectly!")
        print("\nYou can now run the voice agent:")
        print("  python examples/voice_agent_with_backchanneling.py")
    elif tests_ok:
        print("\n✅ Backchanneling filter is working correctly!")
        print("⚠️  Set missing environment variables to run the full demo.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
    
    print()


if __name__ == "__main__":
    main()
