# Context-Aware Interruption Handler for LiveKit Agents
This repository implements a Context-Aware Interruption Handling mechanism for LiveKit Voice Agents. It addresses the challenge of "backchanneling", where agents mistake passive listening cues (e.g., "Yeah", "Uh-huh") for active interruptions, ensuring a seamless conversational flow without stuttering.

# Problem
Standard LiveKit agents rely heavily on Voice Activity Detection (VAD) to handle interruptions. While fast, VAD is semantically blind; it detects sound, not intent. This creates a race condition between the VAD and the Speech-to-Text (STT) modules:
- <u>False Positives:</u> If a user provides passive feedback (e.g., "Mhmm"), the VAD triggers an immediate interruption, pausing the agent.
- <u>The "Stutter":</u> By the time the STT transcribes the word as a backchannel, the agent has already paused. Resuming speech results in a jarring stutter.
- <u>Misinterpret Context:</u> Standard agents do not differentiate between ignoring a word while speaking and acknowledging a word while listening.

# Solution
This solution implements a **Hook-Based Architecture** that effectively "removes" the VAD's ability to trigger interruptions directly. Instead, interruption logic is deferred to the STT layer, allowing the agent to verify the semantic content of the audio before stopping playback
## Features
1. **Zero-Stutter Guarantee:** The VAD trigger is disabled for interruptions. The agent never pauses for a backchannel word because it waits for the transcript to validate the intent.
2. **State-Aware Filtering:**
	- *While Speaking:* Backchannel words are ignored; the agent continues speaking seamlessly.
	- *While Silent:* Backchannel words are treated as valid input; the agent responds (e.g., User: "Yeah" -> Agent: "Go on").
3. **Clean UI Transcription:** Backchannel words detected during agent speech are filtered out of the chat history to keep the conversation log clean.
4. **Configurable Ignore List:** Users can define custom backchannel words via the `AgentSession` options.

# Implementation Details

## 1. The Interruption Policy (`interruption_policy.py`)
A modular policy layer responsible for text classification.

Functions performed by the layer:
- Normalization:- Converts different types of input to handle punctuation and variations (e.g., "Uh-huh" -> "uh huh").
- Partial Matching: Analyzes interim transcripts to detect potential backchannels early (e.g., preventing interruption on "Ye..." before "Yeah" is fully transcribed).

## 2. Event Loop Modifications (`agent_activity.py`)
The core event loop was modified to shift control from VAD to STT.
### Suppressed VAD Interruption
The `on_vad_inference_done` hook was modified to ignore `START_OF_SPEECH` events. This prevents the immediate "blind" pause.

### STT-Driven Interruptions
Logic was added to `on_interim_transcript` and `on_final_transcript`. The agent now manually triggers an interruption **only** if the transcript is _not_ a backchannel word.
### State-Aware Commit
The `on_end_of_turn` hook was updated to check `self._session.agent_state`. It discards backchannel transcripts if the agent is actively speaking, preventing the LLM from processing them.
## 3. Session Configuration (`agent_session.py`)
The `AgentSession` class was updated to accept a `backchannel_words` list, allowing for easy configuration of ignored words at instantiation.

# Installation & Usage
To run this modified agent, you must install the library in editable mode so the local changes to `livekit-agents` are active.

Prerequisites
- Python 3.10+
- A LiveKit Cloud project (or local instance)
- API Keys from the [LiveKit Playground](https://agents-playground.livekit.io/)

### Setup Steps
1. Clone the Repository
```bash
git clone -b feature/interrupt-handler-devesh https://github.com/devesh0099/agents-assignment.git
cd agents-assessment
```

2. Set up Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate # On Windows: .venv\Scripts\activate
```

3. Configure Environment Variables Create a `.env` file in `examples/voice_agents/` and add your keys:

4. Install the example requirements:
```bash
pip install -r  examples/voice_agents/requirements.txt
```

5. Install the local `livekit-agents` package in editable mode to apply the logic changes: (Crucial)
```bash
pip install -e livekit-agents
```

6. Run the Agent and connect from [Livekit Playground](https://agents-playground.livekit.io/) 
```bash
python examples/voice_agents/basic_agent.py download-files 
python examples/voice_agents/basic_agent.py dev
```

# Design Trade-offs
### Latency vs. Reliability
- **Trade-off:** By decoupling interruptions from VAD, we introduce a slight dependency on STT latency (approximately 300-500ms depending on the provider).
- **Justification:** VAD lacks the semantic context required to distinguish "Stop" from "Yeah". Relying on VAD results in unavoidable stuttering. The slight increase in interruption latency is a necessary cost to achieve the Strict Functionality requirement of seamless speech over backchannels.