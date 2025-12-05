 How to Test the Interruption Logic

Using **LiveKit Playground** is the simplest way to test the agent because Windows terminals often have trouble rendering emoji correctly.

## Quick Start Guide

### 1. Launch the Agent

```bash
cd agents-assignment/examples/voice_agents
../../venv/Scripts/python.exe intelligent_interruption_agent.py dev
```

When the agent starts, it will display messages confirming successful registration with LiveKit.

**Note:** All logs are automatically written to `LOGS_SUBMISSION.log` in the root folder.

---

### 2. Connect via LiveKit Playground

Visit this link in your browser:

https://agents-playground.livekit.io/

Select your agent from the available list and connect.

---

## 3. Testing Scenarios

Use the scenarios below to check that the interruption mechanism behaves correctly.

---

### **Test 1: Filler Words Should NOT Interrupt**

- Ask: **"Explain quantum computing."**
- While the agent is talking, say: **"uh-huh"**, **"right"**, or **"hmm okay"**
- **Expected Outcome:**  
  The agent **continues speaking** without stopping.

---

### **Test 2: Filler Words Should Trigger Response When Agent Is Silent**

- Allow the agent to finish speaking.
- Then say: **"okay"** or **"hmm"**
- **Expected Outcome:**  
  The agent treats it as valid input and **replies normally**.

---

### **Test 3: Real Interruptions Should Immediately Stop the Agent**

- Say: **"Read the numbers from 1 to 30."**
- While it is counting, interrupt with:  
  **"stop here"**, **"hold on"**, or **"wait"**
- **Expected Outcome:**  
  The agent **stops at once** and acknowledges the interruption.

---

### **Test 4: Hybrid Phrases (Contain Both Filler & Interrupt Words)**

- Ask a question that leads to a long response.
- While the agent talks, say: **"yeah actually pause"** or **"okay but listen"**
- **Expected Outcome:**  
  Because these phrases contain strong interruption cues, the agent should **stop immediately**.

---

## 4. Checking the Logs

Open the terminal or inspect `LOGS_SUBMISSION.log`.

You will find entries such as:

- `🔇 Filler detected — ignoring`
- `🛑 Interruption detected — stopping`
- Agent state transitions
- Transcripts with timestamps

Example:

```
📝 User said: 'Right.' (agent_is_speaking: True)
🔍 Checking: agent_is_speaking=True, content='Right.'
➡️ Agent currently talking → analyzing content
🔇 Detected filler word → NOT interrupting
🔎 Continuing agent response
```

---

## Alternative Testing Methods

If connecting through LiveKit Playground is not an option, you may:

### 1. **Do a Code Walkthrough**
Record a video explaining the decision logic in the interruption handler.

### 2. **Simulate Expected Logs**
Manually show what the logs would look like for each scenario.

### 3. **Perform Code Review**
Explain the reasoning behind the algorithm step-by-step.

Live testing is still the most accurate and preferred method.

---

## Troubleshooting

### **Agent not connecting?**
- Verify that `.env` contains valid API keys.
- Confirm that the LiveKit URL and credentials are correct.

### **Emojis appear as question marks in Windows console?**
- This is a known encoding limitation.
- Use **dev mode**, not standard console mode.
- View logs through `LOGS_SUBMISSION.log` for proper emoji display.

### **Agent not ignoring filler words?**
- Ensure the filler phrase is spoken **while** the agent is actively talking.
- Check logs to see if `agent_is_speaking` was `True`.
- Timing is important—filler spoken after a response is treated as normal input.

---
