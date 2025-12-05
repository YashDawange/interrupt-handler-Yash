# LiveKit Intelligent Interruption Handling — Assignment

## 📂 Repository to Use
Fork and work on this repository:  
https://github.com/Dark-Sys-Jenkins/agents-assignment  

**DO NOT RAISE PR IN ORIGINAL LIVEKIT REPO**

---

## 📝 Overview
This challenge tests your ability to refine the conversational flow of a real-time AI agent.

### The Problem
LiveKit’s default Voice Activity Detection (VAD) is overly sensitive to user backchanneling.  
When a user says filler words such as “yeah”, “ok”, “hmm”, “aha”, the agent **incorrectly treats them as interruptions**, stopping speech prematurely.

### The Goal
Implement **context-aware logic** so the agent differentiates between:

- **Passive Acknowledgements** → Should NOT interrupt if agent is speaking  
- **Active Interruptions** → Must immediately interrupt agent speech

### Strict Requirement
If the agent is speaking and the user says a filler word, **the agent must continue speaking without stopping, stuttering, or pausing**.

---

## 🎯 Core Logic & Objectives

| User Input           | Agent State      | Desired Behavior |
|----------------------|------------------|------------------|
| “Yeah / Ok / Hmm”    | Speaking         | **IGNORE**: Agent continues speaking |
| “Wait / Stop / No”   | Speaking         | **INTERRUPT**: Agent stops immediately |
| “Yeah / Ok / Hmm”    | Silent           | **RESPOND** normally |
| “Start / Hello”      | Silent           | **RESPOND** normally |

### Key Features to Implement

1. **Configurable Ignore List**  
   Example: `['yeah', 'ok', 'hmm', 'right', 'uh-huh']`

2. **State-Based Filtering**  
   Filtering applies **only** when agent is currently generating or playing audio.

3. **Semantic Interruption Detection**  
   “Yeah wait a second” → Contains interrupt word (“wait”) → **Must interrupt**

4. **No VAD Modifications**  
   Implement logic **above** VAD—do not rewrite VAD internals.

---

## ⚙️ Technical Expectations

### ✔ Integration
Work within the existing **LiveKit Agent framework** in the provided repository.

### ✔ Transcription Logic
- VAD triggers faster than STT.
- Implement a mechanism to prevent false interruptions.
- The agent must verify STT text before deciding whether to stop speech.

### ✔ Real-Time Performance
Any added logic must introduce **imperceptible latency**.

---

## 🧪 Test Scenarios

### **Scenario 1: Long Explanation**
**Agent:** reading a long paragraph  
**User:** “okay… yeah… uh-huh”  
**Expected:** Agent **ignores** all filler words and continues speaking.

---

### **Scenario 2: Passive Affirmation**
**Agent:** asks “Are you ready?” → becomes silent  
**User:** “Yeah.”  
**Expected:** Agent treats it as a valid answer:  
→ “Great, let's continue.”

---

### **Scenario 3: Correction**
**Agent:** “One, two, three…”  
**User:** “No stop.”  
**Expected:** Agent **immediately interrupts** speech.

---

### **Scenario 4: Mixed Input**
**Agent:** speaking  
**User:** “Yeah okay but wait.”  
**Expected:** Agent **interrupts**, because “wait” is not an ignore-word.

---

## ⚖️ Evaluation Criteria

### **1. Strict Functionality — 70%**
- Must continue speaking when hearing filler words.
- **Automatic rejection** if agent:
  - stops  
  - pauses  
  - hiccups  
  on passive acknowledgements.

### **2. State Awareness — 10%**
Correct handling of “yeah” **only when silent**, not when speaking.

### **3. Code Quality — 10%**
- Modular structure  
- Easy-config ignore list (env/config)

### **4. Documentation — 10%**
Clear `README.md` with:
- How to run  
- How the logic layer works  

---

## 🚀 Submission Instructions

1. **Branch Name:**  
   `feature/interrupt-handler-<yourname>`  

2. **Commit Code:**  
   Update `requirements.txt` if you add new libraries.

3. **Proof Required:**  
   Include a short video or log showing:
   - Agent ignores “yeah” while speaking  
   - Agent responds to “yeah” when silent  
   - Agent stops properly on “stop”  

4. **Submit PR:**  
   PR link → https://github.com/Dark-Sys-Jenkins/agents-assignment  
   **Do NOT raise a PR in the main LiveKit repo.**

---

## ⚠️ Important Note
Partial implementations will not be accepted.  
The core challenge is distinguishing the **same word** (“yeah”) differently depending on **agent state** (speaking vs silent).
