Semantic Interruption Voice Agent
This project implements a LiveKit Voice Agent capable of Semantic Backchannel Filtering.

Unlike standard agents that use acoustic Voice Activity Detection (VAD) to stop speaking immediately upon hearing sound, this agent analyzes the content of the speech. It ignores passive acknowledgments (backchannels) like "yeah", "ok", or "uh-huh" without pausing, but interrupts immediately for substantive requests.

Evaluation Criteria Compliance
1. Strict Functionality (Zero Latency)
Behavior: The agent uses allow_interruptions=False as the default state.

Result: When the user says "Yeah" or "Ok", the agent does not stop, pause, or hiccup. The audio stream remains completely uninterrupted because the VAD signal is effectively ignored by the player.

Interruption: The agent only stops if the real-time transcript contains words not found in the allowed backchannel list.

2. State Awareness
Logic: The filtering logic includes a check for session.agent_state == "speaking".

Result:

While Agent Speaks: "Yeah" is treated as a backchannel (ignored).

While Agent listens (Silent): "Yeah" is treated as a valid user reply (processed normally). The agent will respond to "Yeah" if it was waiting for an answer.

3. Code Quality & Modularity
Configuration: The list of ignored words is decoupled from the logic logic, stored in a BACKCHANNEL_WORDS set.

Extensibility: This list can be easily modified in the code or extended to load from an environment variable/JSON file without touching the core interruption logic.

How It Works: The "Unlock & Kill" Pattern
Standard VAD is "Acoustic" (Sound = Stop). We implemented Semantic Interruption:

The Child Lock (allow_interruptions=False): We initialize the session with interruptions disabled. This ensures that VAD triggers generate events and transcripts, but never stop the audio playback automatically.

The Gatekeeper: We listen to the user_input_transcribed event. As the user speaks, we sanitize the text and check it against our BACKCHANNEL_WORDS whitelist.

The Decision Matrix:

All words are backchannels (e.g., "Yeah, uh-huh"):

Action: Do Nothing.

Result: Agent continues speaking with 0ms latency.

Contains real words (e.g., "Wait, stop"):

Action: Interrupt.

Mechanism: We manually unlock the speech handle (allow_interruptions = True) and immediately call .interrupt().

Configuration
Modifying Ignored Words
To change which words are ignored during speech, modify the BACKCHANNEL_WORDS set at the top of the on_transcription function (or move it to a global constant):

Python

BACKCHANNEL_WORDS = {
    "yeah", "ok", "okay", "hmm", "mhm", 
    "sure", "right", "uh-huh", "yep", "wait" # Add/Remove words here
}
