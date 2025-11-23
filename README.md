# Seamless Interruption for LiveKit Agents 🎙️

Welcome! This project demonstrates a smarter, more natural way for Voice Agents to handle interruptions.

## 🤔 The Problem
Standard voice agents are often too sensitive. If you just say *"Yeah"* or *"Uh-huh"* to show you're listening, they abruptly stop speaking. This breaks the flow of conversation and feels robotic.

## 💡 The Solution
We built a **"Seamless Interruption"** logic layer. Now, the agent understands context:
1.  **It Ignores Filler Words**: If you say *"Yeah"*, *"Okay"*, or *"Right"* while it's talking, it keeps going. No awkward pauses.
2.  **It Obeys Commands**: If you say *"Stop"*, *"Wait"*, or *"No"*, it stops immediately.
3.  **It's Context-Aware**: If the agent is silent and you say *"Yeah?"*, it responds to you instead of ignoring it.

---

## 🎮 Try It Live (Playground)

You don't need to build a custom frontend to test this. You can use the **LiveKit Agents Playground**.

1.  **Run the Agent**:
    ```bash
    python examples/voice_agents/basic_agent.py dev
    ```
2.  **Open the Playground**:
    Go to [https://agents-playground.livekit.io/](https://agents-playground.livekit.io/)
3.  **Connect**:
    The playground will automatically detect your local agent running on `localhost`. Click **Connect**.

### 🧪 Things to Test
Once you're talking to the agent, try these experiments:

*   **The "Listener" Test**: Ask it to tell a story. While it speaks, throw in a few *"Yeah"*s or *"Uh-huh"*s. Watch how it ignores them and keeps the story moving.
*   **The "Command" Test**: Interrupt it mid-sentence with *"Stop!"* or *"Wait!"*. It should cut off immediately.
*   **The "Mixed" Test**: Try saying *"Yeah, wait a second."* The agent is smart enough to hear the "wait" and stop.

---

## ⚙️ How It Works (Under the Hood)

We didn't rewrite the core Voice Activity Detection (VAD). Instead, we added a smart logic layer in `agent_activity.py`:

*   **VAD Bypass**: We disabled the "interrupt on any sound" feature.
*   **Smart Filtering**: When you speak, we check the text. If it's just a filler word (and the agent is speaking), we discard it.
*   **Priority Override**: If the text contains a command like "stop", we force an interruption immediately.

### 📝 A Note on the LLM
You'll notice we are using a **`MockLLM`** instead of OpenAI.
*   **Why?** We wanted to make this project accessible without requiring an OpenAI API Key.
*   **How it helps:** The `MockLLM` is programmed to be a reliable storyteller. This gives us a consistent stream of speech, which is perfect for testing interruption logic without wasting tokens or money.

---

## 🚀 Installation & Setup

Follow these steps to get the agent running on your machine.

### 1. Create a Virtual Environment
It's best to run this in a clean environment.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
Install the required packages:
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a file named `.env` in the root directory. You will need your LiveKit project keys and API keys for the voice models.

Add the following lines to your `.env` file:

```env
# LiveKit Project Keys (from cloud.livekit.io)
LIVEKIT_URL=wss://your-project-url.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Model API Keys
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
```

*(Note: No OpenAI API Key is required for this project).*

---

*Enjoy building smoother voice interactions!*
