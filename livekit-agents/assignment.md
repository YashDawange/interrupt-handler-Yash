# 🎙️ LiveKit Intelligent Interruption Handling Challenge
<!-- pip install -e ".[deepgram,elevenlabs,openai]" -->
### **AI Agent Conversational Flow Enhancement**

---

## 📌 **Repository Instructions**

**Fork and work on this repository:**
👉 [https://github.com/Dark-Sys-Jenkins/agents-assignment](https://github.com/Dark-Sys-Jenkins/agents-assignment)

❗ **DO NOT raise a PR in the original LiveKit repo.**
All work must remain inside your fork.

---

## 📝 **Overview**

This challenge tests your ability to refine the conversational flow of a **real-time AI agent**.

### ❗ The Problem

LiveKit’s default Voice Activity Detection (VAD) is **too sensitive**.
When the agent is speaking and the user says short acknowledgements like:

* "yeah"
* "ok"
* "aha"
* "hmm"

… the agent incorrectly interprets them as **interruptions**, causing it to stop mid-sentence.

These words are called **backchanneling**, and they should *not* break the agent’s speech.

---

## 🎯 **Goal**

You must implement a **context-aware logic layer** that distinguishes between:

* **Passive acknowledgements** → should *not* interrupt the agent
* **Active interruptions** → should *instantly* stop the agent
* **Normal responses** → should be processed normally when the agent is silent

---

## 🧠 **Core Logic Matrix**

| User Input Type    | Agent State    | Desired Behavior                                  |
| ------------------ | -------------- | ------------------------------------------------- |
| “Yeah / Ok / Hmm”  | Agent Speaking | **IGNORE** → Agent continues speaking smoothly    |
| “Wait / Stop / No” | Agent Speaking | **INTERRUPT** → Agent stops immediately           |
| “Yeah / Ok / Hmm”  | Agent Silent   | **RESPOND** → Treat as valid conversational input |
| “Start / Hello”    | Agent Silent   | **RESPOND** → Normal conversational reply         |

---

## 🔑 **Key Features to Implement**

### 1️⃣ **Configurable Ignore List**

A list of “soft” acknowledgement words such as:
`['yeah', 'ok', 'hmm', 'right', 'uh-huh']`

These words should be ignored **only when the agent is speaking**.

---

### 2️⃣ **State-Based Filtering**

Your logic must check:

* Is the agent currently **speaking / playing audio**?
  → Ignore filler words.

* Is the agent **silent**?
  → Process them like normal responses.

---

### 3️⃣ **Semantic Interruption Handling**

If the user says a mixed input like:

> “Yeah wait a second.”

This contains an interruption word ("wait"), so the agent must **stop immediately**.

---

### 4️⃣ **No VAD Modification**

⚠️ Do **not** modify the lower-level VAD kernel.

You must implement this logic **within the agent’s event loop**, filtering input intelligently.

---

## ⚙️ **Technical Expectations**

### 🧩 Integration

Work within the existing **LiveKit Agent framework** in the given repo.

### 🗣️ Transcription Logic

You will rely on **Speech-to-Text (STT)**.
Because **VAD triggers earlier than STT**, you must design a strategy to avoid:

* false interruptions
* premature stopping
* audio stutters

Hint:
You may need to **queue interruptions** and validate STT text before finalizing the interruption.

### ⚡ Real-Time Constraint

Your solution must remain **strictly real-time**.
Any delay introduced must be **imperceptible** to the user.

---

## 🧪 **Test Scenarios**

### ✅ **Scenario 1: The Long Explanation**

* Agent: speaking a long paragraph
* User: “Okay… yeah… uh-huh”
* ✔️ Result: Agent continues uninterrupted

---

### ✅ **Scenario 2: Passive Affirmation**

* Agent: “Are you ready?” (silent afterward)
* User: “Yeah.”
* ✔️ Result: Agent processes and continues naturally
  → “Okay, starting now.”

---

### ✅ **Scenario 3: The Correction**

* Agent: “One, two, three…”
* User: “No stop.”
* ✔️ Result: Agent cuts off immediately

---

### ✅ **Scenario 4: Mixed Input**

* Agent: speaking
* User: “Yeah okay but wait.”
* ✔️ Result: Agent stops (because “wait” is an interruption word)

---

## 📂 **Outcome**

By completing this challenge, you will demonstrate your ability to build **robust conversational handling**, making the agent:

* More natural
* Less sensitive to backchanneling
* Fully interruption-aware
* Real-time stable

---
