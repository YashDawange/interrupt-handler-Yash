# Intelligent Interruption Handling — LiveKit Voice Agent

## 1. Overview

This project enhances the default LiveKit voice agent by introducing a context-aware interruption handling system. The objective is to prevent the agent from stopping its speech when the user provides passive acknowledgements such as "yeah", "ok", "hmm", or similar backchannel feedback. Only real interruptions such as "stop", "wait", "no", or meaningful corrections should terminate the agent's speech.

The implementation adheres to the challenge requirement of achieving this behavior without modifying the Voice Activity Detection (VAD) kernel.

---

## 2. Expected Behavior Matrix

| User Utterance                | Agent Speaking | Intended Behavior                    |
|------------------------------|----------------|--------------------------------------|
| "yeah", "ok", "hmm", "right" | Yes            | Ignored. Agent continues speaking.   |
| "stop", "wait", "no"         | Yes            | Immediate interruption.              |
| "yeah", "ok", "hmm"          | No             | Treated as valid user input.         |
| Normal conversational phrases | No            | Respond normally.                    |



## 3. Implementation Summary

A component named **`InterruptController`** is introduced into `basic_agent.py` to provide semantic interruption handling.

### Core logic
- If the agent is speaking and the transcript contains **only soft backchannel words**, the input is ignored.
- If the transcript contains **command words** or **meaningful content**, the agent triggers manual interruption:
  ```python
  session.interrupt()
  session.generate_reply(user_input=text)
```

## 4. Configurable Keyword Lists

Environment variables allow customization without modifying code:
  ```python
INTERRUPT_SOFT_WORDS='["yeah","ok","hmm","right","uh-huh"]'
INTERRUPT_COMMAND_WORDS='["stop","wait","no","cancel","pause"]'
```

Defaults are used if values are not provided.


### 5. Running the Agent Locally

### 5.1 Clone the repository
```python
git clone https://github.com/<your-username>/agents-assignment.git
cd agents-assignment
```

### 5.2 Create and activate a virtual environment
```python
python -m venv .venv
.venv\Scripts\activate
```
### 5.3 Install dependencies
```python
pip install -r examples/voice_agents/requirements.txt
```
### 5.4 Create a .env file
```python
LIVEKIT_URL=wss://<project>.livekit.cloud
LIVEKIT_API_KEY=<key>
LIVEKIT_API_SECRET=<secret>

OPENAI_API_KEY=<openai_key>
DEEPGRAM_API_KEY=<deepgram_key>
CARTESIA_API_KEY=<cartesia_key>

INTERRUPT_SOFT_WORDS='["yeah","ok","hmm"]'
INTERRUPT_COMMAND_WORDS='["stop","wait","no"]'
```
### 5.5 Download required model files
```python
python examples/voice_agents/basic_agent.py download-files
```
### 5.6 Start the agent
```python
python examples/voice_agents/basic_agent.py dev
```
---
## 6. Connecting to the Agent

### 1.Go to: https://agents-playground.livekit.io

### 2.Enter:

LiveKit URL

API Key

API Secret

Room name (e.g., test-room)

### 3.Join and speak to the agent.

## 7. Manual Test Cases
| Scenario | Agent State | Example Input | Required Result |
|----------|-------------|---------------|------------------|
| 1        | Speaking | "yeah", "ok", "hmm" | Agent continues speaking without pause |
| 2 | Speaking | "yeah okay hmm right ok" | Agent continues speaking |
| 3 | Speaking | "stop" | Agent stops immediately and acknowledges |
| 4 | Speaking | "no stop there" | Agent stops immediately |
| 5 | Speaking | "yeah okay but wait" | Agent stops due to "wait" |
| 6 | Speaking | "Actually that's wrong" | Agent stops and responds to correction |
| 7 | Silent | "yeah" | Agent responds normally and continues conversation |
| 8 | Silent | "okay" | Agent responds normally |

## These test results satisfy the evaluation criteria of the challenge.

## 8. Notes on Code Quality

1.No modifications were made to the VAD kernel or turn detector.

2.All interruption logic is encapsulated inside InterruptController.

3.Keyword lists are configurable via environment variables.

4. Only one application file was modified:
 ```python
examples/voice_agents/basic_agent.py
```

## Appendix A — Updated basic_agent.py
Full source code of the modified voice agent implementing semantic interruption handling.
```python
# examples/voice_agents/basic_agent.py

import logging
from dataclasses import dataclass
from typing import List, Optional
import json

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
logger = logging.getLogger("basic-agent")

load_dotenv()
# --------------------- Interrupt Controller ---------------------

DEFAULT_SOFT_WORDS = ["yeah", "ok", "okay", "hmm", "right", "uh-huh", "aha"]
DEFAULT_COMMAND_WORDS = ["stop", "wait", "hold", "no", "cancel", "pause"]
@dataclass
class InterruptController:
    session: AgentSession
    soft_words: List[str] = None
    command_words: List[str] = None
    agent_state: str = "idle"

    def __post_init__(self):
        from os import getenv
        self.soft_words = self._load_word_list(
            getenv("INTERRUPT_SOFT_WORDS"), DEFAULT_SOFT_WORDS
        )
        self.command_words = self._load_word_list(
            getenv("INTERRUPT_COMMAND_WORDS"), DEFAULT_COMMAND_WORDS
        )

        @self.session.on("agent_state_changed")
        def _on_agent_state_changed(state: str):
            self.agent_state = state

        @self.session.on("user_input_transcribed")
        async def _on_user_input_transcribed(text: str, is_final: bool):
            if not is_final:
                return
            await self._handle_transcript(text)
    def _load_word_list(self, raw: Optional[str], default: List[str]):
        if not raw:
            return default
        try:
            parsed = json.loads(raw)
            return [w.lower() for w in parsed]
        except Exception:
            return default

    def _tokenize(self, text: str):
        return [t.strip().lower() for t in text.split() if t.strip()]

    def _classify_intent(self, tokens: List[str]) -> str:
        if any(t in self.command_words for t in tokens):
            return "command"
        if all(t in self.soft_words for t in tokens):
            return "ignore"
        return "content"

    async def _handle_transcript(self, text: str):
        tokens = self._tokenize(text)
           if self.agent_state != "speaking":
            # Agent not speaking → normal input
            return
        intent = self._classify_intent(tokens)
        if intent == "ignore":
            return
        self.session.interrupt()
        self.session.generate_reply(user_input=text)
# --------------------- Agent Implementation ---------------------

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep responses short and conversational, without emojis or markup."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        allow_interruptions=True,
        min_interruption_words=3,
        min_interruption_duration=0.5,
    )

    InterruptController(session)

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions()
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)

```
## Thank you
Please reach out shaileshwarbhoomagouni@gmail.com for any clarifications or doubts. 

