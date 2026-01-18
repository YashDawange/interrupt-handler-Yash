# LiveKit Intelligent Interruption Handling Challenge

## What it do

**1. Agent is Talking + You say "yeah/okay/hmm"**
   - Continues speaking

**2. Agent is Quiet + You say "yeah"**
   - Processes it normally

**3. Agent is Talking + You say "stop/wait/no"**
   - Stops immediately

**4. Agent is Talking + You say "yeah but wait"**
   - Stops (because "wait" is in there)

---

## Customizing the Words

just edit these in `.env`:
```bash
# agent ignores while speaking
BACKCHANNEL_WORDS="yeah,ok,hmm,right,uh-huh,cool"

# agent stops immediately
INTERRUPT_WORDS="stop,wait,no,hold,pause"
```

---

### logic:

1. **Disabled auto-interruptions** in LiveKit
   - Default behavior is disabled as we are handling interrupts mannually

2. **Added a smart filter** that checks:
   - Is the agent currently speaking? (yes/no)
   - What type of words did the user say? (backchannel/interrupt/mixed)

3. **Made decisions based on context**:
   if agent_is_speaking and user_said_backchannel_only:
       ignore_it()  # Keep talking
   elif user_said_interrupt_word:
       stop_immediately()  # Stop now

4. **Added categorization logic**:
   - Splits user input into words
   - Checks if ALL words are just "yeah/okay" type stuff
   - Checks if ANY word is a "stop/wait" command
   - Makes smart decision based on that

---

Demonstration Video - https://youtu.be/InPNKF0Hno0?si=JqYlc8edFhFBknKH