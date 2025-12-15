
## 📝 Overview

Standard Voice Activity Detection (VAD) is binary: if you speak, the agent stops. This feels robotic.
This implementation adds a **Logic Layer** that analyzes *what* was said before deciding to interrupt.

* **Passive Backchanneling:** If the user says "Yeah" while the agent is talking, the agent **ignores it** and keeps talking.
* **Active Interruption:** If the user says "Stop" or a mixed sentence like "Yeah wait", the agent **stops immediately**.

## 🎯 Logic Matrix (The 4 Scenarios)

The system handles these four distinct states as required by the assignment:

| Scenario | Agent State | User Input | Action | Reason |
| :--- | :--- | :--- | :--- | :--- |
| **1. Long Explanation** | 🗣️ Speaking | "Yeah", "Uh-huh" | **IGNORE** | Pure backchanneling. |
| **2. Passive Affirmation** | 🤫 Silent | "Yeah" | **RESPOND** | User is answering a question. |
| **3. The Correction** | 🗣️ Speaking | "No stop" | **INTERRUPT** | Explicit command. |
| **4. Mixed Input** | 🗣️ Speaking | "Yeah wait" | **INTERRUPT** | Contains non-filler words ("wait"). |

## ⚙️ Implementation Details

### The "Doorman" Logic
The core logic resides in `voice/agent_activity.py` inside the `on_final_transcript` event. Before triggering an interruption, the code performs a strict check:

1.  **State Check:** Is the agent currently `speaking`?
2.  **Word Analysis:** The user's input is cleaned and split into words.
3.  **Strict Filtering:**
    * We verify if **every single word** in the user's sentence belongs to the `ignore_words` list.
    * If `all()` words are ignored (e.g., "Yeah okay"), we `return` early, bypassing the interruption code.
    * If even **one** word is valid (e.g., "Yeah **wait**"), the check fails, and the standard interruption proceeds.

### Modified Files
* `voice/agent_activity.py`: Injected logic into `on_final_transcript` to filter events.








## 🧪 How to Test & Generate Proof

Since this assignment requires specific timing (speaking words like "Yeah" *exactly* while the agent is talking), we use an **automated script** to guarantee the test conditions are met.

### Step 1: Start the Agent (Terminal 1)
Run the main agent runner. This script includes a special "Bridge" that accepts text commands and feeds them into the audio processing logic to test the interruption handlers.

```bash
python assignment_main.py dev


### Step 2: Start the Agent (Terminal 2)

Open a second terminal window in the same folder and run the generator script. This script acts as a "Virtual User" that connects to the room, asks for a story, and fires the test cases automatically.



Step 3: Verify the Logs (The Proof)
Look at Terminal 1 (The Agent). As the generator script runs, you will see the following logs appear in real-time. Take a screenshot of these logs for your submission.

Scenario 1 (Passive Ignore):

INFO:voice.agent_activity: ✅ [SCENARIO 1 PASS] Pure backchannel 'yeah' detected while speaking -> IGNORING. (The agent continues to speak uninterrupted)

Scenario 3 (Active Interruption):

INFO:voice.agent_activity: ⚡ [SCENARIO 3 PASS] Direct command 'stop immediately' detected -> INTERRUPTING. (The agent stops speaking immediately)
