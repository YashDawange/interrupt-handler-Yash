````markdown
# Sales Code Agent – Interruption Handling

This is my solution for the LiveKit sales code agent assignment.

My goals:

- The agent **does not stop, pause, or hiccup** on backchannel words like `yeah / ok / hmm` while it is speaking.
- The agent **does respond** to short answers like `yeah / ok` when it is not speaking.
- The logic is **modular, configurable**, and built **only** on top of the existing LiveKit Agent framework.

---

## Demo video

I recorded a short demo showing all four key behaviors (backchannels while speaking, “yeah” when silent, explicit “stop”, and mixed phrases):

**Demo:** [Demo video](https://drive.google.com/file/d/1mJjEXv5IZPam73bMaZRS1sFk52dMGXDO/view?usp=sharing)


---


## How I run it

### 1. Environment

I use Python 3.11 and conda:

```bash
conda create -n salescode.ai.assignment python=3.11 -y
conda activate salescode.ai.assignment
````

Then I install the LiveKit stack and dotenv:

```bash
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"
pip install livekit-plugins-elevenlabs
pip install python-dotenv
```

### 2. .env

In the project root, I have a `.env` file like this:

```env
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=YOUR_LIVEKIT_API_KEY
LIVEKIT_API_SECRET=YOUR_LIVEKIT_API_SECRET

# configurable word lists used by the interruption handler
BACKCHANNEL_WORDS=yeah,ok,okay,hmm,mm-hmm,uh-huh,yep,yup,right
INTERRUPT_WORDS=stop,wait,hold on,hang on,pause,one second,one sec
```

At the top of `test.py` I call:

```python
from dotenv import load_dotenv
load_dotenv()
```

so the `.env` file is loaded automatically.

### 3. Start the agent (console mode)

From the project root:

```bash
conda activate salescode.ai.assignment
python test.py console
```

This uses the existing LiveKit Agent CLI and runs my agent in console mode.

---

## How my logic works

### Integration with the LiveKit framework

I don’t modify the LiveKit library or VAD.
I use the public APIs only:

* `Agent`, `AgentSession`, `WorkerOptions`, `cli.run_app`
* VAD: `silero.VAD.load()`
* STT / LLM / TTS via the `livekit.plugins` stack (Deepgram, OpenAI, ElevenLabs/Cartesia)

In `entrypoint`, I:

1. Create an `AgentSession` with VAD, STT, LLM, TTS.
2. Attach my interruption logic with a helper like `install_interruption_handler(session)`.
3. Start the session and generate an initial greeting.

### State awareness

I track whether the agent is speaking using the `agent_state_changed` event:

* I keep a small flag, e.g. `state["agent_speaking"]`.
* When `new_state == "speaking"`, I set it to `True`; otherwise `False`.

In the `user_input_transcribed` handler I branch on this:

* **If the agent *is speaking***:

  * I inspect the STT transcript.
  * If it contains any word from `INTERRUPT_WORDS` (e.g. `stop`, `wait`, `hold on`), I call:

    ```python
    session.interrupt()
    ```

    so TTS stops immediately.
  * If it is made only of words from `BACKCHANNEL_WORDS` (e.g. `yeah`, `ok`, `hmm`), I treat it as backchannel:

    ```python
    session.clear_user_turn()
    ```

    and I do **not** interrupt, so the agent keeps speaking smoothly.
  * Longer mid-speech utterances can be treated as real interruptions (I call `session.interrupt()` so the user can change direction).

* **If the agent is *not speaking***:

  * I don’t override anything.
    Short answers like `yeah / ok` go straight into the normal LiveKit+LLM flow and the agent responds.

This gives me the required behavior:

* `yeah / ok / hmm` **while speaking** → ignored as backchannel (no stop, no pause, no hiccup).
* `yeah / ok` **when silent** → treated as valid answers and responded to.

### Using VAD + STT for “false starts”

VAD is faster and just tells me “the user is speaking now”.
I **never** interrupt based only on VAD. I always wait for the STT text:

1. VAD detects speech → STT runs.
2. I get the transcript in `user_input_transcribed`.
3. Only then do I decide:

   * **Interrupt** if it contains an interrupt phrase.
   * **Ignore/clear** if it is pure backchannel while I’m speaking.
   * **Pass through** if I’m not speaking.

This is how I handle the “false start” problem (e.g. VAD fires on “yeah”, but I do not actually cut off the agent).

### Configurability

The logic is modular:

* The interruption behavior lives in a helper like `install_interruption_handler(session)`.
* The word lists are not hardcoded; they come from:

  ```python
  BACKCHANNEL_WORDS = _load_word_set("BACKCHANNEL_WORDS", "<default list>")
  INTERRUPT_WORDS = _load_word_set("INTERRUPT_WORDS", "<default list>")
  ```
* I can change which words are ignored or treated as interrupts by editing `.env` only.

---

## How I manually test it

I use four simple checks:

1. **Backchannel while speaking**
   Let the agent talk; while it speaks, I say `“yeah”` / `“ok”` / `“hmm”`.
   → The agent keeps speaking with **no stop, no pause, no hiccup**.

2. **“Yeah” when silent**
   Wait until the agent finishes and is quiet; I say `“yeah”`.
   → The agent responds (for example: “Great, let’s continue.”).

3. **Explicit interrupt**
   While the agent is mid-sentence, I say `“stop”` or `“wait, that’s enough”`.
   → The current speech cuts off immediately and the agent stops / acknowledges.

4. **Mixed phrase**
   While it is speaking, I say `“yeah okay but wait”`.
   → Because it contains `wait`, the agent stops speaking and is ready for a new instruction.

This matches the assignment’s functionality, state-awareness, code-quality, and documentation expectations.


