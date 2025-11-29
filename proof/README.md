# 🎙️ Intelligent Interrupt Handling Agent

### Real-time Speech Interrupt & Backchannel Detection Demo

This project implements an **interrupt-aware conversational agent** designed for real-time speech systems.
The agent decides whether to **respond**, **continue speaking**, **ignore**, or **stop immediately** based on live user input.

This repository includes:

* The **interrupt handler logic**
* The **agent speaking/silent state logic**
* A **terminal demo UI** that shows agent state in real-time
* A **clean interface** between UI → decision engine → agent behavior
* Unit test support (optional)

---

## 📌 1. Project Overview

Many voice assistants can talk, but they fail at natural **turn-taking**:

* They don’t know when a user is giving a small backchannel (“yeah”, “ok, hmm”)
* They don’t know when a user wants to **stop** the agent
* They don’t know when a user is trying to **start the conversation**
* They don’t smoothly resume speaking after small confirmations

This project solves this by implementing a **rule-based interrupt model** that closely mirrors human conversation patterns.

---

## 📌 2. Core Behavior Logic

The agent has **two states**:

```
SPEAKING
SILENT
```

It also tracks whether it has been **recently speaking** (last few seconds).

All decisions are made by:

```
livekit.agents.voice.interrupt_handler.decide_action()
```

which returns a structured result:

```json
{
  "decision": "RESPOND" | "IGNORE" | "INTERRUPT",
  "mode": "once" | "continue" | null,
  "reason": "<explanation>",
  "transcript": "<normalized_user_text>"
}
```

---

## 📌 3. Decision Rules

The interrupt logic implements **four conversational rules**:

---

### **1️⃣ Agent is SPEAKING**

**User says interrupt words** (`stop`, `wait`, `no`, `pause`)
→ **INTERRUPT** — Agent stops immediately.

**User says ignore/backchannel** (`yeah`, `ok`, `hmm`, `right`)
→ **IGNORE** — Agent continues speaking.

**Anything else**
→ **IGNORE** — (Humans often talk over small filler words.)

---

### **2️⃣ Agent is SILENT (and recently spoke)**

**User says backchannel words**
→ **RESPOND & CONTINUE SPEAKING** — Agent interprets it as: “Yes, go on.”

**User says anything else**
→ **RESPOND ONCE** — Agent replies once and stays silent.

---

### **3️⃣ Agent is SILENT (and has NOT spoken recently)**

**User says start/hello/hi**
→ **RESPOND ONCE** — Agent starts the conversation.

**User says anything else**
→ **RESPOND ONCE** — Agent answers normally.

---

### **4️⃣ Timeout / STT error handling**

* Silent → respond once
* Speaking → ignore

This ensures smooth, predictable behavior.

---

## 📌 4. How the Agent Works Internally

### ✔️ `interrupt_handler.py`

This file contains **all decision-making logic**.
It normalizes text, detects keywords, checks agent state, and returns the appropriate action.

### ✔️ `interactive_console.py`

This is only **a UI layer**:

* Displays the agent status (`SILENT` / `SPEAKING`)
* Shows user input
* Calls `interrupt_handler.decide_action()`
* Updates the state accordingly
* Never contains logic of its own

### ✔️ Agent State Tracking

The UI tracks:

```python
agent_speaking: bool
last_speech_end: timestamp
```

This allows deciding whether the agent:

* “Recently spoke”
* Should continue talking
* Should stop immediately

---

## 📌 5. How to Install & Run the Agent

### Step 1 — Create virtual environment

```bash
python -m venv .venv
```

### Step 2 — Activate virtualenv

**macOS/Linux:**

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```bash
.venv\Scripts\Activate.ps1
```

---

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

If no requirements file exists, install manually:

```bash
pip install colorama pytest pytest-asyncio
```

---

### Step 4 — Run the console demo

```bash
python demos/interactive_console.py
```

---

## 📌 6. How the Demo Works

When you start the demo, the terminal shows:

```
Agent Status: SILENT
You>
```

The status line **always stays at the top**.
User input appears under it.

Examples:

**Say:** `hello`
Agent responds once.

**Say while agent is speaking:** `yeah`
Agent ignores and continues.

**Say while agent is speaking:** `stop`
Agent stops immediately.

**Say after agent finished speaking:** `ok`
Agent responds and starts speaking again.

All transitions update the top status line **in place**.

---
