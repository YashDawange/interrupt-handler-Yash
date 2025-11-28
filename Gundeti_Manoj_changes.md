# **Intelligent Backchanneling & Interruption Handling for LiveKit Voice Agents**

## **Overview**

This module adds **smart interruption handling** to LiveKit voice agents.
The agent can now distinguish between:

* **Backchanneling** (passive acknowledgements like *“yeah”, “hmm”, “ok”*)
* **Actual interruptions** (e.g., *“stop”, “wait”, “hold on”*)

This results in **much more natural, human-like conversations** where the agent is not interrupted unnecessarily.

---

## **Key Features**

###  **1. Backchanneling Detection**

The agent ignores short acknowledgements while it is speaking:

```
yeah, ok, okay, hmm, uh-huh, right, aha, mhmm, yep, yup, sure, alright
```

These words **do not interrupt** the agent’s speech.

---

###  **2. Context-Aware Interpretation**

The *same word* behaves differently depending on state:

| Situation         | User Says “yeah”    | Behavior            |
| ----------------- | ------------------- | ------------------- |
| Agent is speaking | Ignored             | Agent keeps talking |
| Agent is silent   | Treated as response | Agent processes it  |

This makes interactions feel conversational, not brittle.

---

###  **3. Accurate Interruption Handling**

If the user says anything **beyond backchanneling**, interruption occurs normally.

Examples:

```
"yeah wait"   → interrupt (contains a non-backchannel word)
"stop"        → interrupt
"wait stop"   → interrupt
```

---

###  **4. Fully Customizable**

You can override the default backchannel word list:

```python
session = AgentSession(
    ...,
    backchanneling_words=["yeah", "ok", "sure", "right"],
)
```

---

###  **5. Example Test Agent Included**

`interruption_test_agent.py` demonstrates:

* Ignoring backchanneling during long speech
* Accepting backchanneling as responses when silent
* Real interruptions
* Mixed inputs

This is the quickest way to validate the feature.

---

## **Installation**

### 1. Install core package

```bash
pip install -e livekit-agents
```

### 2. Install required plugins

```bash
pip install livekit-plugins-deepgram
pip install livekit-plugins-openai
pip install livekit-plugins-cartesia
pip install livekit-plugins-silero
pip install livekit-plugins-turn-detector
pip install python-dotenv
```

Or install everything:

```bash
pip install -r requirements.txt
```

---

## **Running the Test Agent**

### Development Mode

```bash
python examples/voice_agents/interruption_test_agent.py dev
```

### Download Required Models

```bash
python examples/voice_agents/interruption_test_agent.py download-files
```

---

## **How It Works (Simplified Logic)**

### 1. Check if user said *only* backchanneling words

If yes → mark as backchanneling.

### 2. Check if agent is speaking

* **Speaking + backchanneling** → ignore
* **Silent + backchanneling** → accept
* **Anything else** → interrupt

### 3. Apply this logic at multiple stages:

* Audio-based interruption
* Interim transcript handling
* Final transcript handling

This ensures stable, consistent behavior.

---

## **Directory Structure**

```
agents-assignment/
├── examples/voice_agents/
│   └── interruption_test_agent.py     # Test agent
├── livekit-agents/livekit/agents/
│   ├── voice/agent_activity.py        # Backchannel logic
│   ├── voice/agent_session.py         # API + config
│   └── version.py
└── requirements.txt
```

---

## **Why This Matters**

This feature significantly improves:

* **Conversation flow**
* **User experience**
* **Long-form speech usability**
* **Accuracy of real interruptions**
* **Human-like interaction quality**

Voice agents can now handle natural spoken cues like humans do.
