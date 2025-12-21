"""Quick verification script for the InterruptionController (Production-Ready)."""
import sys
import time
sys.path.insert(0, 'examples/interrupt_handler')

from controller import Decision, InterruptionController, GRACE_PERIOD_SECONDS

def run_tests():
    c = InterruptionController()
    results = []
    
    print("=" * 60)
    print("INTELLIGENT INTERRUPT HANDLER - PRODUCTION TEST RESULTS")
    print("=" * 60)
    
    # ========== Original 5 Tests ==========
    print("\n📋 ORIGINAL ASSIGNMENT TESTS:")
    
    # Test 1: Backchannel while speaking
    c.update_agent_state('speaking')
    result = c.decide('yeah', True)
    passed = result == Decision.IGNORE
    results.append(('T1: yeah while speaking', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} T1: yeah while speaking → {result.name}")
    
    # Test 2: Command while speaking
    result = c.decide('stop', True)
    passed = result == Decision.INTERRUPT
    results.append(('T2: stop while speaking', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} T2: stop while speaking → {result.name}")
    
    # Test 3: Input while silent (wait for grace period)
    c.update_agent_state('listening')
    time.sleep(GRACE_PERIOD_SECONDS + 0.1)
    result = c.decide('yeah', True)
    passed = result == Decision.NO_DECISION
    results.append(('T3: yeah while silent', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} T3: yeah while silent → {result.name}")
    
    # Test 4: Mixed input
    c.update_agent_state('speaking')
    result = c.decide('yeah but wait', True)
    passed = result == Decision.INTERRUPT
    results.append(('T4: yeah but wait', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} T4: yeah but wait → {result.name}")
    
    # Test 5: Empty string
    result = c.decide('', True)
    passed = result == Decision.IGNORE
    results.append(('T5: empty string', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} T5: empty string → {result.name}")
    
    # ========== Production Fix Tests ==========
    print("\n🔧 PRODUCTION FIX TESTS:")
    
    # Fix #1: Hyphen normalization
    c.update_agent_state('speaking')
    result = c.decide('Uh-huh', True)
    passed = result == Decision.IGNORE
    results.append(('Fix #1: Uh-huh (hyphen)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #1: Uh-huh (hyphen) → {result.name}")
    
    result = c.decide('mm-hmm!', True)
    passed = result == Decision.IGNORE
    results.append(('Fix #1: mm-hmm! (hyphen+punct)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #1: mm-hmm! (hyphen+punct) → {result.name}")
    
    # Fix #2: Multi-word phrases
    result = c.decide('I see', True)
    passed = result == Decision.IGNORE
    results.append(('Fix #2: I see (multi-word)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #2: I see (multi-word) → {result.name}")
    
    result = c.decide('Got it', True)
    passed = result == Decision.IGNORE
    results.append(('Fix #2: Got it (multi-word)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #2: Got it (multi-word) → {result.name}")
    
    # Fix #3: Grace period
    c.update_agent_state('speaking')
    c.update_agent_state('listening')  # Just stopped
    result = c.decide('stop', True)  # Within grace period
    passed = result == Decision.INTERRUPT
    results.append(('Fix #3: stop in grace period', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #3: stop in grace period → {result.name}")
    
    # Fix #4: Question words
    c.update_agent_state('speaking')
    result = c.decide('what?', True)
    passed = result == Decision.INTERRUPT
    results.append(('Fix #4: what? (question)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #4: what? (question) → {result.name}")
    
    result = c.decide('huh?', True)
    passed = result == Decision.INTERRUPT
    results.append(('Fix #4: huh? (question)', passed, f'got {result.name}'))
    print(f"  {'✅' if passed else '❌'} Fix #4: huh? (question) → {result.name}")
    
    # ========== Summary ==========
    passed_count = sum(1 for r in results if r[1])
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"RESULT: {passed_count}/{total} tests passed")
    
    if passed_count == total:
        print("🎉 ALL TESTS PASSED - PRODUCTION READY!")
    else:
        print("⚠️  SOME TESTS FAILED - Review needed")
        for name, passed, detail in results:
            if not passed:
                print(f"   FAILED: {name} ({detail})")
    
    print("=" * 60)
    
    return passed_count == total

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
