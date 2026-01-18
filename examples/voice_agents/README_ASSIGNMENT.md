# LiveKit Intelligent Interruption Handler

This agent implements a custom logic layer to distinguish between **passive backchanneling** (e.g., "Yeah", "Uh-huh") and **active interruptions** (e.g., "Stop", "Wait").

## 🧠 The Logic
The solution decouples the Voice Activity Detection (VAD) from the interruption mechanism to allow for semantic filtering.

1.  **Disable Auto-Interruption:**
    * We initialized `AgentSession` with `allow_interruptions=False`. This prevents the VAD from blindly stopping audio when any sound is detected.

2.  **Semantic Logic Layer (`stt_node`):**
    * We intercepted the Speech-to-Text (STT) stream in the `MyAgent` class.
    * The system evaluates every transcript against a **Logic Matrix**:

    | Agent State | User Says | Classification | Action |
    | :--- | :--- | :--- | :--- |
    | **Speaking** | "Yeah", "Ok", "Hmm" | **Passive** | **Ignore:** The event is swallowed; audio continues. |
    | **Speaking** | "Stop", "Wait", [Other] | **Active** | **Interrupt:** `interrupt(force=True)` is called. |
    | **Silent** | "Yeah", "Ok" | **Valid Turn** | **Respond:** Standard LLM response generation. |

3.  **Configuration:**
    * Ignored words are defined in the `IGNORE_WORDS` set at the top of `basic_agent.py` for easy customization.

## 🚀 How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set Environment Variables:**
    Create a `.env` file with your keys:
    ```env
    LIVEKIT_URL=...
    LIVEKIT_API_KEY=...
    LIVEKIT_API_SECRET=...
    OPENAI_API_KEY=...
    DEEPGRAM_API_KEY=...
    CARTESIA_API_KEY=...
    ```

3.  **Start the Agent:**
    ```bash
    python basic_agent.py dev
    ```

## 🧪 Testing the Logic
* **Scenario 1:** Ask the agent to tell a story. Say "Yeah" while it speaks. -> *Agent continues.*
* **Scenario 2:** Ask the agent to tell a story. Say "Stop" while it speaks. -> *Agent stops.*
* **Scenario 3:** Wait for silence. Say "Yeah". -> *Agent replies "Yes?".*