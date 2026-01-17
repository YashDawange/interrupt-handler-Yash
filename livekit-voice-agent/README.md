# Context-Aware Intelligent Voice Agent

This repository contains a LiveKit Voice Agent designed with a custom **Context-Aware Logic Layer**. Unlike standard agents that interrupt at the slightest sound, this agent intelligently distinguishes between "passive backchanneling" (e.g., "Yeah", "Uh-huh") and "active interruptions" (e.g., "Stop").

## 🎯 Assignment Features Implemented

### 1. Strict Functionality (No Stuttering)
The agent utilizes a custom `_on_user_speech_committed` handler that intercepts user transcripts before the interruption signal is processed.
* **Context:** Agent is Speaking.
* **Input:** "Yeah", "Ok", "Right".
* **Behavior:** The agent **IGNORES** these words and continues speaking seamlessly. `allow_interruptions=False` is used to prevent the default VAD "hiccup."

### 2. Active Interruption
* **Context:** Agent is Speaking.
* **Input:** "Stop", "Wait", "I have a question."
* **Behavior:** The logic layer detects these are NOT in the ignore list and explicitly calls `session.interrupt()`.

### 3. State Awareness
* **Context:** Agent is Silent.
* **Input:** "Yeah", "Ok."
* **Behavior:** The agent treats these as valid conversational turns and responds naturally (e.g., "Ready to move on?").

### 4. Modularity
The list of ignored words is not hardcoded. It is loaded dynamically from the `IGNORED_WORDS` environment variable, allowing behavior changes without code edits.

---

## 🚀 Setup & Installation

1.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *(Or `uv pip install -r requirements.txt` if using uv)*

2.  **Configure Environment**
    Create a `.env.local` file in the root directory and add your API keys:
    ```env
    # LiveKit Configuration
    LIVEKIT_URL=wss://your-project.livekit.cloud
    LIVEKIT_API_KEY=API...
    LIVEKIT_API_SECRET=...

    # Model Providers (Golden Trio for Speed)
    OPENAI_API_KEY=sk-...
    DEEPGRAM_API_KEY=...

    # Modular Logic Configuration
    IGNORED_WORDS=yeah,ok,okay,hmm,aha,uh-huh,right,yup,yep,sure,correct,gotcha,i see
    ```

3.  **Run the Agent**
    ```bash
    python agent.py dev
    ```

---

## 🧪 Verification Guide (How to Test)

To verify the assignment criteria, follow these steps in the LiveKit Playground:

**Test 1: The "Seamless Flow" (70% Requirement)**
1.  Connect to the agent. It will start a long introduction.
2.  While it is speaking, say **"Right"** or **"Yep"**.
3.  **Result:** The agent should **NOT** pause or stop.
4.  *Check Terminal:* You will see log: `ACTION: IGNORE (No Hiccup)`.

**Test 2: The "Active Stop"**
1.  While the agent is speaking, say **"Stop immediately."**
2.  **Result:** The agent cuts off instantly.
3.  *Check Terminal:* You will see log: `ACTION: INTERRUPT (Active Command)`.

**Test 3: The "Silent Response" (10% Requirement)**
1.  Wait for the agent to finish speaking.
2.  Say **"Ok."**
3.  **Result:** The agent generates a reply (e.g., "Is there anything else?").
4.  *Check Terminal:* You will see log: `ACTION: RESPOND`.

---

## 📂 Project Structure

* `agent.py`: Main entry point containing the `AssignmentAgent` class and the `_on_user_speech_committed` logic layer.
* `.env.local`: Configuration for API keys and modular filler words.
* `requirements.txt`: Python dependencies.