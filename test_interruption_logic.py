#!/usr/bin/env python3
"""
Test script to validate intelligent interruption handling

This script demonstrates the different scenarios handled by the
intelligent interruption logic.
"""

from livekit.agents.voice.agent import PASSIVE_BACKCHANNEL_WORDS, ACTIVE_INTERRUPT_WORDS

def simulate_interruption_check(user_input: str, is_agent_speaking: bool) -> str:
    """
    Simulates the interruption logic to show what action would be taken
    
    Args:
        user_input: What the user said
        is_agent_speaking: Whether the agent is currently speaking
    
    Returns:
        str: The action that would be taken (IGNORE, INTERRUPT, or RESPOND)
    """
    # Clean and split
    cleaned_text = user_input.lower().strip()
    words = cleaned_text.split()
    
    if not words:
        return "NO_ACTION (empty input)"
    
    # Check word categories
    has_active_interrupt = any(w in ACTIVE_INTERRUPT_WORDS for w in words)
    all_passive = all(w in PASSIVE_BACKCHANNEL_WORDS for w in words)
    
    # Apply logic matrix
    if is_agent_speaking:
        if all_passive and not has_active_interrupt:
            return f"✓ IGNORE - Agent continues speaking (pure backchannel)"
        elif has_active_interrupt:
            return f"⚠ INTERRUPT - Agent stops immediately (active interrupt detected)"
        else:
            return f"⚠ INTERRUPT - Agent stops (new conversation input)"
    else:
        return f"💬 RESPOND - Agent treats as valid input (agent was silent)"


def main():
    print("=" * 80)
    print("INTELLIGENT INTERRUPTION HANDLING - TEST SCENARIOS")
    print("=" * 80)
    print()
    
    print(f"📚 Passive Backchannel Words: {', '.join(PASSIVE_BACKCHANNEL_WORDS[:8])}...")
    print(f"🛑 Active Interrupt Words: {', '.join(ACTIVE_INTERRUPT_WORDS[:8])}...")
    print()
    
    # Test scenarios
    scenarios = [
        # (user_input, is_agent_speaking, scenario_name)
        ("yeah", True, "Scenario 1: Pure passive backchannel (agent speaking)"),
        ("ok", True, "Scenario 1b: Another passive word (agent speaking)"),
        ("hmm mhmm", True, "Scenario 1c: Multiple passive words (agent speaking)"),
        
        ("stop", True, "Scenario 2: Active interrupt word (agent speaking)"),
        ("wait", True, "Scenario 2b: Another active interrupt (agent speaking)"),
        ("hold on", True, "Scenario 2c: Multi-word interrupt (agent speaking)"),
        
        ("yeah wait", True, "Scenario 3: Mixed sentence - passive + active (agent speaking)"),
        ("ok stop", True, "Scenario 3b: Mixed sentence (agent speaking)"),
        ("hmm hold on a second", True, "Scenario 3c: Mixed with extra words (agent speaking)"),
        
        ("yeah", False, "Scenario 4: Passive word (agent silent)"),
        ("stop", False, "Scenario 4b: Active word (agent silent)"),
        ("hello there", False, "Scenario 4c: New conversation (agent silent)"),
        
        ("tell me more", True, "Scenario 5: Regular conversation (agent speaking)"),
        ("what about the weather", True, "Scenario 5b: Question (agent speaking)"),
        
        ("thanks", True, "Scenario 6: Polite acknowledgment (agent speaking)"),
    ]
    
    print("-" * 80)
    print("TEST RESULTS")
    print("-" * 80)
    print()
    
    for user_input, is_agent_speaking, scenario_name in scenarios:
        agent_state = "🗣️ Speaking" if is_agent_speaking else "🤫 Silent"
        result = simulate_interruption_check(user_input, is_agent_speaking)
        
        print(f"{scenario_name}")
        print(f"  User says: \"{user_input}\"")
        print(f"  Agent state: {agent_state}")
        print(f"  Result: {result}")
        print()
    
    print("=" * 80)
    print("LEGEND:")
    print("  ✓ IGNORE     - Agent continues speaking seamlessly (no pause/stutter)")
    print("  ⚠ INTERRUPT  - Agent stops immediately and listens")
    print("  💬 RESPOND    - Agent treats input as normal conversation")
    print("=" * 80)


if __name__ == "__main__":
    main()
