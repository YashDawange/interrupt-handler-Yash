# Intelligent Interruption Voice Agent

This README describes how to run and understand the intelligent interruption logic implemented in:

The agent is built using the LiveKit Agents framework and focuses on realistic conversational turn-taking, especially around backchannel words (like “yeah”, “ok”, “hmm”) and interrupt commands (like “stop”, “wait”, “hold on”).

---

## 1. High-Level Overview

This agent implements the following behavior:

1. **When the agent is speaking:**
   - Pure backchannel filler such as “yeah”, “ok”, “hmm” is ignored:
     - It does not interrupt text-to-speech (TTS).
     - It does not get sent to the LLM (GPT).
   - Explicit interrupt commands such as “stop”, “wait”, “hold on”, “no” will:
     - Immediately interrupt the agent’s speech.
     - Be treated as a new user input for the LLM.
   - Any other meaningful user speech (not just filler) will:
     - Interrupt the agent.
     - Be sent as a proper user turn to the LLM.

2. **When the agent is silent:**
   - Backchannel words (e.g., “yeah”, “ok”, “hmm”) are treated as valid responses and sent to the LLM.
   - Interrupt commands are also treated as normal text commands and sent to the LLM.
   - Any other text is treated as a normal user input.

3. The sets of:
   - “ignore words” (backchannels), and
   - “interrupt commands”

   can be extended via entries in the `.env` file without changing the Python code.

The central class that implements this logic is `IntelligentInterruptionManager`, which attaches to an `AgentSession` and controls when user input is committed or cleared.

---

## 2. File and Project Structure

The core file for this logic is:

- `examples/voice_agents/interupt_agent.py`

This file:

1. Loads environment variables from `.env` using `python-dotenv`.
2. Defines helper functions to:
   - Parse CSV-style environment values.
   - Normalize text.
   - Detect backchannel-only input.
   - Detect interrupt commands.
3. Implements `IntelligentInterruptionManager`, which:
   - Listens to agent state changes.
   - Listens to transcribed user input.
   - Decides when to commit or clear user turns, and when to interrupt TTS.
4. Defines `IntelligentInterruptAgent`, the LLM-based conversational agent.
5. Defines `entrypoint(ctx: JobContext)`, which:
   - Connects to LiveKit.
   - Creates an `AgentSession` with manual turn detection.
   - Wires in the interruption manager.
   - Starts the agent.

---

## 3. Prerequisites

You should have the following installed and configured:

1. **Python Environment**
   - Python 3.10+ (or the version you used for LiveKit Agents).
   - A virtual environment (recommended).

2. **LiveKit Agents and Plugins**

   Install the main package with commonly used plugins:

   ```bash
   pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
   ```

3. **API Keys**

   You will need:

   - `OPENAI_API_KEY` for OpenAI models.
   - `DEEPGRAM_API_KEY` for Deepgram STT.
   - LiveKit server credentials:
     - `LIVEKIT_URL`
     - `LIVEKIT_API_KEY`
     - `LIVEKIT_API_SECRET`

4. **Repository**

   - The code is assumed to live inside a project such as `agents-assignment` with the standard LiveKit Agents project layout.
   - `interupt_agent.py` is under `examples/voice_agents/`.

---

## 4. Environment Variables (.env) Configuration

A `.env` file should be placed in the project root (for example: `agents-assignment/.env`).

A typical `.env` would look like:

```env
# LiveKit server configuration
LIVEKIT_URL=wss://your-livekit-domain.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# LLM / STT providers
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key

# Optional: extra ignore words for backchannel detection
IGNORE_WORDS=cool, got it, makes sense

# Optional: extra interrupt commands
INTERRUPT_COMMANDS=pause, cancel
```

### 4.1 How the Word Lists Are Built

The code defines default lists in Python:

- Default ignore (backchannel) words:

  - `yeah, ok, okay, k, hmm, mhm, mmm, uh, uh-huh, uh huh, right, yep, yup, sure`

- Default interrupt commands:

  - `stop, wait, hold on, one second, just a second, hang on, please stop, stop talking, no stop`

Then it does:

- Parse defaults into lists.
- Parse any additional values from `.env`.
- Combine them.

**Effective ignore words:**

- Defaults plus any words listed in `IGNORE_WORDS` in `.env`.

**Effective interrupt commands:**

- Defaults plus any phrases listed in `INTERRUPT_COMMANDS` in `.env`.

This means:

- You do not have to redefine the full list in `.env`.
- You only add new items there; the defaults are always present.

---

## 5. Running the Agent

All commands below assume you are in the project root (for example, `agents-assignment`) and have your virtual environment activated.

### 5.1 Console Mode (Local Microphone and Speaker Testing)

```bash
python examples/voice_agents/interupt_agent.py console
```

This:

- Runs the agent with local audio I/O.
- Does not require any external LiveKit client.
- Is ideal for quickly testing behavior using your own microphone.

### 5.2 Development Mode (LiveKit + Hot Reload)

```bash
python examples/voice_agents/interupt_agent.py dev
```

This:

- Starts a worker process that connects to your LiveKit server.
- Enables file watching and hot-reload behavior.
- Allows you to connect from:
  - LiveKit Agents Playground.
  - Any LiveKit client (web, mobile, etc.) that joins the room.

You may see an occasional `DuplexClosed` error and then a `registered worker` log; this indicates that the watcher restarted the worker. As long as the worker ends up registered and stays running, this is normal.

### 5.3 Production Mode

```bash
python examples/voice_agents/interupt_agent.py start
```

This:

- Runs the agent in production mode.
- Does not include hot reload behavior.
- Is suitable for a more stable deployment.

---

## 6. Detailed Logic and Workflow

The core logic lives inside the class:

`IntelligentInterruptionManager`

This class is instantiated with an `AgentSession` and does the following:

1. Subscribes to:
   - `agent_state_changed` events.
   - `user_input_transcribed` events.
2. Tracks whether the agent is currently “speaking” or not.
3. For every final user transcript:
   - Normalizes the text.
   - Classifies it as:
     - Pure backchannel (only ignore words).
     - Contains an interrupt command.
     - Other text.
4. Decides whether to:
   - `clear_user_turn()` (throw away the input).
   - `commit_user_turn()` (send it to the LLM).
   - `interrupt()` (stop the agent’s TTS).

### 6.1 Text Normalization

The `_normalize(text)` function:

1. Converts text to lowercase.
2. Removes non-alphanumeric characters (except whitespace).
3. Collapses multiple spaces into a single space.
4. Strips leading and trailing whitespace.

This ensures that input like:

- `"  OK!!! "` → `"ok"`
- `"Uh-huh..."` → `"uh huh"`

is consistently handled.

### 6.2 Backchannel Detection

`is_backchannel_only(text)`:

1. Normalizes the text.
2. Splits into words.
3. Returns `True` if every word is in the `IGNORE_WORDS` set.

Examples:

- `"yeah"` → True
- `"yeah ok"` → True
- `"yeah okay hmm"` → True
- `"yeah that is right"` → False (contains non-backchannel content)

This function is the key to detecting “filler” input that should not interrupt the agent when it is speaking.

### 6.3 Interrupt Command Detection

`contains_interrupt_command(text)`:

1. Normalizes the text.
2. Performs a phrase-level match:
   - Checks whether any phrase in `INTERRUPT_COMMANDS_RAW` is a substring of the normalized text.
   - This handles multi-word commands like `"hold on"` or `"one second"`.
3. Performs a token-level match:
   - Splits the normalized text into tokens.
   - Checks whether any token is in the `INTERRUPT_TOKENS` set.
   - This handles single-word commands like `"stop"`, `"wait"`, `"no"`.

If either check passes, the input is treated as an interrupt signal.

---

## 7. Behavioral Rules (Case-by-Case)

Let `speaking` = whether the agent is currently speaking (`agent_is_speaking` property).

For each final transcript:

1. **If the text is backchannel-only (`is_backchannel_only(text) == True`):**

   - If `speaking` is True:
     - Call `clear_user_turn()`.
     - Result: Input is dropped, not sent to the LLM, does not interrupt TTS.
   - If `speaking` is False:
     - Call `commit_user_turn()`.
     - Result: Input is treated as a valid answer (e.g., `"Yeah"` to a yes/no question).

2. **Else, if the text contains an interrupt command (`contains_interrupt_command(text) == True`):**

   - If `speaking` is True:
     - Call `interrupt()` to stop TTS.
     - Then call `commit_user_turn()` to send this input to the LLM.
     - Result: Hard interruption.
   - If `speaking` is False:
     - Call `commit_user_turn()`.
     - Result: The command is handled as a normal text input by the LLM.

3. **Else, if the text is “other” content (not pure backchannel, no interrupt command):**

   - If `speaking` is True:
     - Treat this as a polite interruption with actual content:
       - Call `interrupt()`.
       - Then `commit_user_turn()`.
   - If `speaking` is False:
     - Just call `commit_user_turn()`.

---

## 8. Flowchart of the Workflow

The following flowchart shows the high-level decision flow for each final user transcript:

```text
+------------------------------------------------------+
|  User speaks -> STT produces a final transcript      |
+-----------------------------+------------------------+
                              |
                              v
                  +------------------------+
                  |  _handle_transcript()  |
                  +------------------------+
                              |
              Is ev.is_final? |   (partial or final STT)
                 /                    /              No ----/        \----> Yes
        (ignore)               |
                               v
                  +-----------------------------+
                  | Normalize and get transcript|
                  +-----------------------------+
                               |
                      Is text empty?
                       /                             /                      Yes ----/           \----> No
    clear_user_turn()                 |
                                      v
                       +-----------------------------+
                       | is_backchannel_only(text)? |
                       +-----------------------------+
                               /                                      /                                Yes ---/            \--- No
                         |                     |
                         v                     v
             +--------------------+   +------------------------------+
             | agent_is_speaking? |   | contains_interrupt_command? |
             +--------------------+   +------------------------------+
                     /   \                    /                                 /     \                  /                        True -----/       \---- False    Yes               No
          |                     |         |                 |
          v                     v         v                 v

(Backchannel + speaking)   (Backchannel + silent)   +---------------------+
clear_user_turn()          commit_user_turn()       | agent_is_speaking? |
(ignore filler while       (treat as valid answer)  +---------------------+
agent is talking)                                   /                                                             /                                                     True ----/               \---- False
                                         |                           |
                                         v                           v
                   +-----------------------------------+   commit_user_turn()
                   | interrupt() + commit_user_turn()  |   (normal response)
                   | (hard interrupt or user talking   |
                   |  over TTS with real content)      |
                   +-----------------------------------+
```

Interpretation:

- Backchannel-only + speaking → clear (ignore).
- Backchannel-only + silent → commit.
- Interrupt command + speaking → interrupt and commit.
- Interrupt command + silent → commit.
- Other text + speaking → interrupt and commit.
- Other text + silent → commit.

---

## 9. Agent Personality and First Turn

The agent class `IntelligentInterruptAgent` defines:

- The instruction that explains:
  - The agent is friendly and talkative.
  - Backchannel words during agent speech should not interrupt.
  - Interrupt words should stop the agent.

On `on_enter`, it:

- Generates an initial reply that:
  - Greets the user.
  - Explains that they can say “stop” or “wait” to interrupt.
  - Begins a short explanation, giving you something to talk over for testing.

This ensures that as soon as you connect, the agent is speaking and you can immediately verify the interruption behavior.

---

## 10. Testing Checklist

Once you have:

- Created the `.env` file,
- Installed dependencies,
- Activated your virtual environment,

you can run:

```bash
python examples/voice_agents/interupt_agent.py console
```

Then test the following cases:

1. **Agent is speaking; you say only “Yeah” or “Ok”:**
   - Output: Agent continues speaking.
   - No new reply should be triggered by that “Yeah” or “Ok”.
   - Internally, that segment is cleared and not sent to the LLM.

2. **Agent is speaking; you say “Stop”, “Wait”, or “Hold on”:**
   - Agent should stop speaking immediately.
   - Agent should respond to your interruption.

3. **Agent is silent; you say only “Yeah”:**
   - Agent should interpret this as a valid response and say something appropriate.

4. **Agent is silent; you ask a full question:**
   - Agent should respond normally.

These tests confirm that the interruption logic works as intended and that the ignore and interrupt word sets are correctly integrated with your `.env` configuration.
