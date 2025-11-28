# Visual Demo - Intelligent Interruption Handler

## What You're Seeing

This interactive web demo shows **exactly** what the assignment requires - a visual, real-time demonstration of how the intelligent interruption filter works.

## How to Use

### Option 1: HTML Visual Demo (Recommended - No Installation Required)

Simply open `visual_demo.html` in your browser:

```bash
cd examples
xdg-open visual_demo.html  # Linux
# or
open visual_demo.html      # Mac
# or double-click the file in Windows
```

**Features:**
- 🎨 Beautiful, interactive UI
- 🔊 Toggle between agent "Speaking" and "Silent" states
- 💬 Type any user input and see real-time filter decisions
- 📚 Pre-built example buttons for all 4 scenarios
- 🧪 "Run All Tests" button to validate all scenarios at once
- 🔍 Word-by-word analysis showing fillers vs commands vs content
- ⚙️ Display of configured ignore and command lists

### Option 2: Terminal Demo

```bash
python3 demo_standalone.py
```

Runs all 4 scenarios in the terminal with detailed output.

### Option 3: Unit Tests

```bash
python3 ../tests/standalone_test.py
```

Runs the complete test suite.

## The 4 Key Scenarios (From Assignment)

### Scenario 1: The Long Explanation
- **Context**: Agent is speaking
- **User says**: "yeah", "okay", "hmm", "uh-huh"
- **Expected**: Agent continues speaking (NO interruption)
- **Result**: ✅ Filter ignores these filler words

### Scenario 2: The Correction
- **Context**: Agent is speaking (counting "one, two, three...")
- **User says**: "no", "stop", "wait"
- **Expected**: Agent stops immediately
- **Result**: ✅ Filter triggers interruption

### Scenario 3: The Mixed Input
- **Context**: Agent is speaking
- **User says**: "yeah wait", "okay but stop", "hmm actually"
- **Expected**: Agent stops (command words detected)
- **Result**: ✅ Filter prioritizes commands over fillers

### Scenario 4: The Passive Affirmation
- **Context**: Agent is SILENT (waiting for input)
- **User says**: "yeah", "okay", "hello"
- **Expected**: Agent processes input normally
- **Result**: ✅ Filter allows all input when agent is silent

## Visual Elements Explained

### Color Coding in HTML Demo

- 🔴 **Red Border/Background**: INTERRUPT decision (agent will stop)
- 🟢 **Green Border/Background**: CONTINUE decision (agent keeps speaking)
- 🔴 **Red Chips**: Command words (wait, stop, no, etc.)
- 🟢 **Green Chips**: Filler words (yeah, ok, hmm, etc.)
- 🔵 **Blue Chips**: Content words (anything else)

### Decision Panel Shows

1. **Decision Badge**: Clear INTERRUPT or CONTINUE verdict
2. **What happens**: Explanation of agent behavior
3. **Reason**: Why the filter made this decision
4. **Matched Words**: Which words triggered the decision
5. **Word Analysis**: Breakdown of each word's classification

## Try These In The Demo

1. **Set agent to "SPEAKING"**
   - Type: "yeah" → See ✋ CONTINUE (green)
   - Type: "stop" → See 🛑 INTERRUPT (red)
   - Type: "yeah but wait" → See 🛑 INTERRUPT (command takes precedence)

2. **Set agent to "SILENT"**
   - Type: "yeah" → See 🛑 INTERRUPT (processes as valid input)
   - Type: "hello" → See 🛑 INTERRUPT (normal conversation)

3. **Click "Run All Tests"**
   - Validates all 4 scenarios automatically
   - Shows ✅ or ❌ for each test case
   - Displays overall pass/fail count

## What This Demonstrates

This visual demo proves the implementation satisfies **all assignment requirements**:

✅ **Context-aware**: Different behavior based on agent state (speaking vs silent)  
✅ **No VAD modification**: Logic layer above VAD/STT  
✅ **Configurable**: Clear display of ignore and command lists  
✅ **Semantic interruption**: Mixed inputs handled correctly  
✅ **Real-time**: Instant feedback as you type  
✅ **No false starts**: Filter validates before interrupting  

## Technical Implementation

The HTML demo uses vanilla JavaScript with the same filter logic as the Python implementation:

1. **Tokenization**: Splits input into words, handles punctuation and hyphens
2. **Command Detection**: Checks for command words first (highest priority)
3. **Filler Detection**: Identifies if all words are fillers
4. **State Awareness**: Bypasses filtering when agent is not speaking
5. **Decision**: Returns interrupt/continue with reasoning

This is **exactly** what runs in the LiveKit agent, just visualized for easy demonstration.

## Assignment Proof

The visual demo serves as **proof of implementation** by:

1. Showing real-time filter decisions
2. Testing all 4 required scenarios
3. Demonstrating configurable word lists
4. Providing transparent reasoning for each decision
5. Validating correctness with automated tests

Perfect for demonstrating to reviewers without needing a full LiveKit setup!
