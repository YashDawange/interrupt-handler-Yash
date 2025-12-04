from interruption_logic import InterruptionHandler

handler = InterruptionHandler()
print("Test 1 (Speaking + 'Yeah'):", handler.should_interrupt("Yeah...", True))
print("Test 2 (Silent + 'Yeah'):", handler.should_interrupt("Yeah", False))
print("Test 3 (Speaking + 'Stop'):", handler.should_interrupt("Stop", True))