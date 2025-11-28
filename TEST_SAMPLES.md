# Test Samples for Intelligent Interruption Filter

## Quick Test Samples

Copy these samples into the visual demo (visual_demo.html) or use them in your tests.

---

## Scenario 1: Filler Words While Agent is Speaking
**Expected:** Should NOT interrupt (ignored)

```
um
uh
hmm
uh-huh
yeah
okay
right
got it
I see
```

**Test in Visual Demo:**
1. Set Agent State to "Speaking"
2. Enter each phrase above
3. Verify: Decision shows "IGNORE (filler word)"

---

## Scenario 2: Commands While Agent is Speaking
**Expected:** Should interrupt immediately

```
stop
wait
hold on
pause
listen
excuse me
interrupt
one moment
```

**Test in Visual Demo:**
1. Set Agent State to "Speaking"
2. Enter each phrase above
3. Verify: Decision shows "INTERRUPT (command)"

---

## Scenario 3: Mixed Input While Agent is Speaking
**Expected:** Should interrupt (contains non-filler content)

```
um stop please
okay but wait
hmm I have a question
yeah I need help
uh can you repeat that
right but what about the price
I see okay thanks
hmm that's interesting
```

**Test in Visual Demo:**
1. Set Agent State to "Speaking"
2. Enter each phrase above
3. Verify: Decision shows "INTERRUPT (substantive content)"

---

## Scenario 4: Any Input While Agent is Silent
**Expected:** Should always interrupt

```
hello
um
what's the weather
okay
I have a question
hmm
stop
yeah
```

**Test in Visual Demo:**
1. Set Agent State to "Silent"
2. Enter each phrase above
3. Verify: Decision shows "INTERRUPT (agent silent)"

---

## Edge Cases

### Punctuation Variations
```
Um...
Uh-huh!
Wait!
STOP
Hold On Please
```

### Case Sensitivity
```
STOP
Stop
stop
HMM
Hmm
hmm
```

### Multiple Fillers
```
um uh yeah okay
hmm right I see
```

### Single Word Commands
```
stop
wait
pause
listen
```

### Partial Matches (Should NOT Match)
```
stopping by the store
waiting room
pauseless playback
listening party
```

### Natural Conversations While Speaking
**Should INTERRUPT:**
```
actually I disagree
what about the cost
I think you're wrong
can you explain that
tell me more about that
I have another question
what do you mean
how does that work
```

**Should IGNORE:**
```
um
uh-huh
yeah
okay
right
hmm
I see
got it
```

### Natural Conversations While Silent
**Should ALWAYS INTERRUPT:**
```
hello there
how are you
what's the weather
I need assistance
um hello
yeah hi
okay so
hmm interesting
```

---

## Realistic Dialog Sequences

### Customer Service Scenario

**Agent Speaking:**
```
User: "um"                          → IGNORE
User: "uh-huh"                      → IGNORE
User: "wait a second"               → INTERRUPT
User: "okay thanks"                 → IGNORE
User: "but what about refunds"      → INTERRUPT
```

**Agent Silent:**
```
User: "hello"                       → INTERRUPT
User: "I need help"                 → INTERRUPT
User: "um"                          → INTERRUPT
User: "okay"                        → INTERRUPT
```

### Meeting Scenario

**Agent Speaking:**
```
User: "hmm"                         → IGNORE
User: "I see"                       → IGNORE
User: "hold on"                     → INTERRUPT
User: "um I disagree"               → INTERRUPT
User: "right"                       → IGNORE
User: "excuse me"                   → INTERRUPT
```

### Tutorial Scenario

**Agent Speaking:**
```
User: "uh-huh"                      → IGNORE
User: "yeah"                        → IGNORE
User: "got it"                      → IGNORE
User: "wait what"                   → INTERRUPT
User: "can you repeat"              → INTERRUPT
User: "okay"                        → IGNORE
```

---

## Automated Test Suite

Run all these in sequence to verify comprehensive coverage:

### Test Set 1: Pure Fillers (Agent Speaking)
```
um          → IGNORE
uh          → IGNORE
hmm         → IGNORE
yeah        → IGNORE
okay        → IGNORE
right       → IGNORE
I see       → IGNORE
got it      → IGNORE
uh-huh      → IGNORE
```

### Test Set 2: Pure Commands (Agent Speaking)
```
stop        → INTERRUPT
wait        → INTERRUPT
hold on     → INTERRUPT
pause       → INTERRUPT
listen      → INTERRUPT
excuse me   → INTERRUPT
interrupt   → INTERRUPT
one moment  → INTERRUPT
```

### Test Set 3: Mixed Content (Agent Speaking)
```
um stop              → INTERRUPT
okay but wait        → INTERRUPT
hmm I have a query   → INTERRUPT
yeah I need help     → INTERRUPT
right but why        → INTERRUPT
```

### Test Set 4: Silent State (All Input)
```
um              → INTERRUPT
hello           → INTERRUPT
stop            → INTERRUPT
what time       → INTERRUPT
I see           → INTERRUPT
```

---

## Performance Test Samples

### Long Sentences
```
um uh yeah I was wondering if you could possibly help me understand the pricing structure
okay so I think what you're saying is that the service includes everything but I'm not entirely sure
hmm that's interesting but I'd like to know more about the technical implementation details
```

### Rapid Fire
```
stop
um
wait
okay
hold on
yeah
pause
right
```

### Complex Mixed Input
```
um okay so like I was thinking uh that maybe we could uh you know try a different approach because um the current one seems uh not quite right you know
yeah but hold on a second I think there might be uh some issues with that plan that we should probably um address before moving forward okay
```

---

## How to Use These Samples

### In Visual Demo (visual_demo.html):
1. Open `examples/visual_demo.html` in browser
2. Select Agent State (Speaking or Silent)
3. Paste sample into input field
4. Click "Check Interruption"
5. Verify decision matches expected result

### In Python Demo (demo_standalone.py):
```bash
cd /home/raj/Desktop/GenAI/agents-assignment
python3 examples/demo_standalone.py
```
Then paste samples when prompted.

### In Automated Tests:
```bash
cd /home/raj/Desktop/GenAI/agents-assignment
python3 tests/standalone_test.py
```

---

## Expected Results Summary

| Agent State | Input Type | Expected Decision |
|------------|------------|-------------------|
| Speaking | Filler words only | IGNORE |
| Speaking | Command words | INTERRUPT |
| Speaking | Mixed (filler + content) | INTERRUPT |
| Speaking | Substantive content | INTERRUPT |
| Silent | Any input | INTERRUPT |

---

## Quick Copy-Paste Tests

**Test 1 - Fillers (Speaking):**
```
um
```

**Test 2 - Command (Speaking):**
```
stop
```

**Test 3 - Mixed (Speaking):**
```
um I have a question
```

**Test 4 - Anything (Silent):**
```
hello
```

All samples provided cover the 4 core scenarios specified in the assignment.
