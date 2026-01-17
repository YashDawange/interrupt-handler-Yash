# Intelligent Interruption Handler for LiveKit AI Agent

**Author:** Swastik  
**Branch:** `feature/interrupt-handler-swastik`  
**Submission for:** SalesCode.ai GenAI Engineer Internship

---

## Problem Statement

The default LiveKit AI agent stops speaking whenever it detects user input, even passive acknowledgments like "yeah", "ok", or "hmm". This makes conversations feel unnatural.

**Solution:** Context-aware interruption handling that distinguishes between backchanneling and actual commands.

---

## Solution Architecture

### Components

1. **InterruptionHandler** (`interrupt_handler.py`) - Core filtering logic
2. **Configuration** (`config.py`) - Centralized ignore words
3. **Enhanced Agent** (`agent_with_interruption.py`) - LiveKit integration
4. **Test Suite** (`test_handler.py`) - Comprehensive validation

### Logic Flow
```
User Input → Is Agent Silent?
              ↓
         Yes → Process All Input
              ↓
         No → Check Words
              ↓
         All in IGNORE_LIST?
              ↓
         Yes → IGNORE
              ↓
         No → INTERRUPT
```

---

## How to Run

### Setup
```bash
git clone https://github.com/lavishv999-rgb/agents-assignment.git
cd agents-assignment
git checkout feature/interrupt-handler-swastik
pip install -r requirements.txt
```

### Run Tests
```bash
python test_handler.py
```

Expected output:
```
========================================================
RESULTS: 20 passed, 0 failed out of 20 tests
========================================================
🎉 ALL TESTS PASSED! ✅
```

---

## Test Scenarios

### Scenario 1: Agent Explaining
**User:** "yeah... ok... hmm"  
**Result:** Agent continues

### Scenario 2: Agent Silent
**User:** "yeah"  
**Result:** Agent responds

### Scenario 3: Clear Command
**User:** "stop"  
**Result:** Agent stops immediately

### Scenario 4: Mixed Input
**User:** "yeah but wait"  
**Result:** Agent stops (contains command)

---

## Configuration

Modify `config.py`:
```python
IGNORE_WORDS = [
    "yeah", "ok", "hmm", "uh-huh", 
    "right", "aha", "yep", "sure"
]
```

---

## Key Features

✅ Context-aware filtering  
✅ Configurable ignore list  
✅ Semantic understanding  
✅ Zero latency  
✅ No VAD modification  
✅ Production ready  

---

## Files
```
agents-assignment/
├── interrupt_handler.py        [NEW]
├── config.py                    [NEW]
├── agent_with_interruption.py  [NEW]
├── test_handler.py              [NEW]
└── README.md                    [UPDATED]
```

---

## Requirements Checklist

- ✅ Configurable ignore list
- ✅ State-based filtering
- ✅ Semantic interruption
- ✅ No VAD modification
- ✅ Real-time performance
- ✅ No pauses/stutters
- ✅ Modular code
- ✅ Documentation
- ✅ Tests included

---

## Contact

**Swastik**  
📧 sswastik_be23@thapar.edu
🎓 Thapar Institute of Engineering & Technology  
📅 Batch: 2027

---

