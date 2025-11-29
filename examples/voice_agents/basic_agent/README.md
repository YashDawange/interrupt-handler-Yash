# **Intelligent Interruption Handling – Assignment Implementation**

## **Overview**

This project implements a **context-aware interruption system** for a LiveKit voice agent.
The goal is to differentiate between:

* **Passive acknowledgements** such as *“yeah”, “okay”, “hmm”*
* **Active interruptions** such as *“stop”, “wait”, “no”, “cancel”*

The logic ensures:

1. If the **agent is speaking**, filler words must be **ignored**.
2. If the **agent is speaking** and the user says a real command like *“stop”*, the agent must **interrupt instantly**.
3. If the **agent is silent**, the same filler words must be treated as **normal input**.

No modifications were made to the VAD engine — the logic is added as a **custom layer** inside the agent’s event loop.

---

## **Features Implemented**

### ✔ **Custom interrupt/backchannel classifier**

A complete logic layer that classifies user speech into:

* `"ignore"`
* `"interrupt"`
* `"respond"`

### ✔ **State-aware behavior**

The agent tracks:

* Whether it is currently **speaking**
* Whether user input is **final**
* Whether the input contains command tokens or filler tokens

### ✔ **True interruption**

When a command is detected:

* The agent stops speaking **immediately**
* The user turn is cleared so “stop” is never treated as a query

### ✔ **Configurable tokens**

Token lists are fully configurable through environment variables:

```
INTERRUPT_IGNORE_WORDS
INTERRUPT_COMMAND_WORDS
```

Defaults include:

**Ignore (soft fillers):**
yeah, ok, okay, hmm, right, uh-huh, mm-hmm, sure, continue, fine, yup, gotcha...

**Interrupt (commands):**
stop, wait, no, cancel, enough, hold on, pause, sorry, interrupt...

---

## **Folder Structure**

```
basic_agent/
├── basic_agent.py
├── README.md
└── proof.mp4/logs
```

---

## **How to Run the Agent**

### **1. Install dependencies**

Inside your virtual environment:

```bash
pip install -r requirements.txt
```

### **2. Start the agent**

Run:

```bash
python examples/voice_agents/basic_agent/basic_agent.py start
```

Make sure your environment has:

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
```

---

## **How to Test the Logic**

### ✔ **Test 1 — Soft words while agent is speaking (should IGNORE)**

**Agent speaking → you say:**

* yeah
* okay
* hmm
* right

**Expected:**
Agent **continues speaking** without stopping, pausing, or stuttering.

---

### ✔ **Test 2 — Soft words when agent is NOT speaking (should RESPOND)**

Agent finishes talking.

**You say:** “yeah.”

**Expected:**
Agent treats it as normal input and responds.

---

### ✔ **Test 3 — Command words while agent is speaking (should INTERRUPT)**

While agent is mid-sentence:

**You say:**

* stop
* wait
* no
* cancel

**Expected:**
Agent **cuts off immediately**.

---

## **Proof (Video)**

### **Video Demo**


```
proof.mp4
```

<!-- OR
Paste a Google Drive link.

### **Log Transcript Example**

(Replace with your actual logs)

```
Transcript: 'yeah' → ignore (speaking=True)
Ignoring backchannel while speaking (final).

Transcript: 'yeah' → respond (speaking=False)
Agent silent or normal input → letting transcript flow normally.

Transcript: 'stop' → interrupt (speaking=True)
Interrupting agent due to command word.
``` -->

---

## **Branch Used**

```
feature/interrupt-handler-ravik
```

---

## **Notes**

* No modifications were made to VAD kernels.
* All interruption logic is implemented in pure Python event hooking.
* Behavior matches the strict requirements of the challenge.
