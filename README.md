
# 🎙️ Intelligent Interruption Handling

## 🧩 Problem

When users say **“yeah,” “ok,” or “hmm”** while the agent is talking, the default LiveKit VAD treats these as interruptions — causing the agent to stop speaking even though the user is just listening.

---

## 💡 Solution

Added a context-aware interruption handler that distinguishes between:

* **Soft interruptions** (e.g., *yeah, ok, hmm*) → ignored while the agent is speaking
* **Hard interruptions** (e.g., *stop, wait, no*) → immediately stop the agent
* **Mixed inputs** (e.g., *yeah but wait*) → treated as valid interruptions

---

## ⚙️ Implementation


### `interruption.py`

* Defines a configurable ignore/interrupt word filter
* Uses the agent’s current speaking state to decide whether to ignore or stop
* Cleans and tokenizes transcripts for comparison
* Easily customizable through environment variables

### `agent_test.py`

* Sets up the LiveKit agent session with VAD, STT, TTS, and LLM
* Attaches the custom `attach_interruption_filter()`
* Demonstrates correct handling of interruptions in real time

---

## 🧠 How It Works

```
User speaks → STT transcribes → Check if agent is speaking
                                ↓
              YES → Soft word? Ignore.  Hard word? Interrupt.
              NO  → Process normally.
```

---

## 🚀 Setup & Run

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Dark-Sys-Jenkins/agents-assignment.git
cd agents-assignment
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
```

### 3️⃣ Add Environment Variables

Create a `.env` file in the project root:

```bash
LIVEKIT_URL=wss://your-livekit-server
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

### 4️⃣ Run the Agent

```bash
python -m dotenv run -- python agent_test.py console
```

---

## 🧪 Test Scenarios

| Scenario         | Input                 | Expected Behavior        |
| ---------------- | --------------------- | ------------------------ |
| Long Explanation | “yeah ok hmm”         | Agent continues speaking |
| Affirmation      | “yeah” (agent silent) | Agent responds normally  |
| Real Command     | “stop”                | Agent stops immediately  |
| Mixed Input      | “okay but wait”       | Agent stops              |

---

## 🎥 Demo Video

A short demo video namded **demo.mp4** showing all test cases has been uploaded along with this submission to demonstrate:

1. The agent ignoring filler words while speaking
2. Responding correctly when silent
3. Stopping instantly on “stop”

---
## 👩‍💻 Author

**Name:** Maria Helana Manickam
**GitHub Repo:** [https://github.com/helenavrm/agents-assignment](https://github.com/helenavrm/agents-assignment)

---

