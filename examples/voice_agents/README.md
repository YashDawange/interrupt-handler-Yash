# 🎧 Intelligent Interruption Handling – Assignment Submission  

**Author:** Nitya Vettical  
**Role:** Gen-AI Agent Intern Candidate  


## 📌 Overview  

This project implements a **state-aware interruption handling layer** for a conversational AI agent, following the exact requirements described in the assignment PDF.

The objective is to make the agent distinguish between:

- **Passive acknowledgements** (e.g., “yeah”, “ok”, “hmm”)  
- **Active interruptions** (e.g., “stop”, “wait”, “no”)  

and apply different behaviors depending on whether the agent is **currently speaking** or **silent**.

This implementation extends the LiveKit `Agent` class and overrides event callbacks to provide accurate, real-time conversational flow control.



## 🧠 Core Logic Summary  

### ✔ Ignore filler words while agent is speaking  
If the user says "yeah / ok / hmm" **while TTS output is active**, the agent **ignores** the input completely.

### ✔ Interrupt immediately on meaningful commands  
If the user says **“stop / wait / no”** during speech, the agent interrupts TTS instantly and responds.

### ✔ Treat filler as valid input when agent is silent  
The exact same words (“yeah / ok / hmm”) are treated normally when the agent is not speaking.

### ✔ Forward normal queries to the LLM  
If the agent is silent and the user provides non-filler text, it is forwarded to the LLM.

### ✔ Semantic mixed-input handling  
Cases like “yeah wait” are correctly treated as interruptions because an interrupt word is present.


## 🗂 File Structure  

| File | Purpose |
|------|---------|
| **`nitya_interrupt_agent.py`** | Main implementation of the interruption-aware agent |
| **`test_agent_logic.py`** | Simulation script demonstrating required behaviors |
| **`transcript.txt`** | Clean output transcript from simulation |
| **`README.md`** | Documentation |


## 🧪 Demonstration – Simulation Testing  
The assignment PDF states that proof may be provided via **video recording or a log transcript**.  
This submission uses a simulation script that triggers all required behaviors deterministically.

Run the demo:

python test_agent_logic.py


This produces the following behaviors:

1. **Agent speaking + filler word → IGNORED**  
2. **Agent speaking + “stop” → INTERRUPT**  
3. **Agent silent + filler word → NORMAL RESPONSE**  
4. **Agent silent + natural query → FORWARDED TO LLM**

A complete transcript is included in `transcript.txt`.

## ▶️ Video Demonstration 

A short screen recording accompanies this submission, showing:

- The agent code  
- The simulation test running  
- Verbal explanation of logic  

## 🧩 Design Notes  

- All logic is encapsulated inside `NityaInterruptAgent`, which cleanly overrides LiveKit callback hooks.  
- Behavior lists (`IGNORE_LIST`, `INTERRUPT_WORDS`) are configurable for evaluation.  
- State is tracked with a simple `AgentState` class for full clarity.  
- Code closely follows the structural expectations of the provided LiveKit assignment template.

## ✔️ Status  

All assignment requirements have been successfully implemented and demonstrated.

Thank you for reviewing this submission. 



