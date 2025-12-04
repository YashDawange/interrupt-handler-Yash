import sys
from interruption_logic import InterruptionHandler

log_file = open("proof_final.log", "w")

def log(message):
    print(message)
    log_file.write(message + "\n")

def run_test():
    handler = InterruptionHandler()

    log("      LIVEKIT LOGIC COMPLIANCE VERIFICATION       ")

    log("--- Scenario 1: The Long Explanation ---")
    log("Context: Agent is SPEAKING")
    input_text = "Okay... yeah... uh-huh"
    decision = handler.should_interrupt(input_text, is_agent_speaking=True)
    
    if decision == "IGNORE":
        log(f"[PASS] Input='{input_text}' -> Result=IGNORE (Correct)")
    else:
        log(f"[FAIL] Input='{input_text}' -> Result={decision} (Expected IGNORE)")
    log("")

    log("--- Scenario 2: The Passive Affirmation ---")
    log("Context: Agent is SILENT")
    input_text = "Yeah"
    decision = handler.should_interrupt(input_text, is_agent_speaking=False)
    
    if decision == "RESPOND":
        log(f"[PASS] Input='{input_text}' -> Result=RESPOND (Correct)")
    else:
        log(f"[FAIL] Input='{input_text}' -> Result={decision} (Expected RESPOND)")
    log("")

    log("--- Scenario 3: The Correction ---")
    log("Context: Agent is SPEAKING")
    input_text = "No stop"
    decision = handler.should_interrupt(input_text, is_agent_speaking=True)
    
    if decision == "INTERRUPT":
        log(f"[PASS] Input='{input_text}' -> Result=INTERRUPT (Correct)")
    else:
        log(f"[FAIL] Input='{input_text}' -> Result={decision} (Expected INTERRUPT)")
    log("")

    log("--- Scenario 4: The Mixed Input ---")
    log("Context: Agent is SPEAKING")
    input_text = "Yeah okay but wait"
    decision = handler.should_interrupt(input_text, is_agent_speaking=True)
    
    if decision == "INTERRUPT":
        log(f"[PASS] Input='{input_text}' -> Result=INTERRUPT (Correct)")
    else:
        log(f"[FAIL] Input='{input_text}' -> Result={decision} (Expected INTERRUPT)")
    log("VERIFICATION COMPLETE")
    log_file.close()

if __name__ == "__main__":
    run_test()