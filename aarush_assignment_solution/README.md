📄 README.md
# LiveKit Intelligent Interruption Handling

## 📌 Overview

This project implements **context-aware interruption handling** for a real-time voice agent built using the LiveKit Agents framework.

The goal is to solve a common conversational UX problem in voice agents:  
**preventing false interruptions caused by passive listener acknowledgements** such as “yeah”, “ok”, or “hmm” while still allowing real interruption commands like “stop” or “wait”.

This solution strictly follows the constraints and evaluation criteria defined in the assignment.

---

## 🚨 The Problem

LiveKit’s default Voice Activity Detection (VAD) is intentionally fast but naive.

When the agent is speaking:
- Any detected user speech (even “yeah”) is treated as an interruption
- The agent abruptly stops speaking

This results in **unnatural and broken conversations**.

---

## 🎯 Objective

Design and implement a **logic-level interruption filter** such that:

| User Input | Agent State | Expected Behavior |
|-----------|------------|------------------|
| “yeah”, “ok”, “hmm” | Speaking | **IGNORE** (agent continues seamlessly) |
| “stop”, “wait”, “no” | Speaking | **INTERRUPT immediately** |
| “yeah”, “ok” | Silent | **RESPOND normally** |
| “yeah but wait” | Speaking | **INTERRUPT** |

> ⚠️ Partial solutions (pause → resume, stutter, or hiccup) are **not acceptable**.

---

## 🧠 Core Insight

- **VAD is fast but does not understand intent**
- **STT is slower but semantically meaningful**

Therefore:
- We must **delay committing to an interruption**
- Until **speech-to-text confirms user intent**

---

## 🏗️ Solution Architecture

The system introduces a **deterministic interruption gate** that sits between:



VAD → STT → Interruption Decision


### Key Signals Used

1. **Agent State**
   - Whether the agent is currently speaking or silent

2. **User Speech Detection**
   - VAD event indicates potential interruption attempt

3. **User Intent**
   - Final transcribed text from STT

---

## ⚙️ Interrupt Gate Logic

### Word Categories

#### Passive Acknowledgements (Soft Signals)
Examples:


yeah, ok, okay, hmm, uh-huh, right


#### Active Interruptions (Hard Signals)
Examples:


stop, wait, no, hold on, cancel


---

## 📊 Interrupt Scoring Mechanism

Each recognized word contributes to an **interrupt score**:

| Word Type | Score |
|----------|-------|
| Active interruption | +1.0 |
| Passive acknowledgement | -0.5 |

### Decision Rule



Final score > 0 → Interrupt
Final score ≤ 0 → Ignore


### Why this works

- A single strong command always wins
- Multiple filler words never cause interruption
- Mixed sentences are handled correctly
- Fully deterministic (no ML, no latency risk)

---

## 🧪 Example Evaluations

| Input | Score | Result |
|------|------|-------|
| “yeah” | -0.5 | IGNORE |
| “yeah ok” | -1.0 | IGNORE |
| “stop” | +1.0 | INTERRUPT |
| “yeah wait” | +0.5 | INTERRUPT |
| “ok but stop” | +0.5 | INTERRUPT |

---

## 🚫 Explicit Constraints Followed

✔ No modification to VAD kernel  
✔ No reduction of VAD sensitivity  
✔ No global disabling of interruptions  
✔ No audible pause or resume artifacts  
✔ Real-time safe and deterministic  

All logic is implemented **purely at the agent event-handling layer**.

---

## 🧩 Code Structure



aarush_assignment_solution/
│
├── agent.py # LiveKit agent + event wiring
├── interrupt_gate.py # Core decision logic
├── config.py # Ignore lists & scoring weights
├── .env.example # Environment variable template
└── README.md # This file


---

## 🧠 Why This Solution Is Correct

- **State-aware**: Same word behaves differently based on agent state
- **Race-condition safe**: VAD events are validated by STT
- **No stutter guarantee**: Agent audio is never stopped unless intent is confirmed
- **Production-grade logic**: Mirrors real-world conversational systems

---

## 📹 Proof of Correctness

The submission includes:
- Agent ignoring “yeah / ok” while speaking
- Agent responding to “yeah” when silent
- Agent immediately stopping on “stop”
- Handling of mixed inputs like “yeah wait”

---

## 📌 Conclusion

This project demonstrates a robust, real-time, context-aware interruption handling system that improves conversational quality without compromising responsiveness or violating system constraints.

It addresses the **exact production 