# LiveKit Intelligent Interruption Handling

A context-aware interruption handler for LiveKit voice agents that distinguishes between passive acknowledgements (backchanneling) and active interruptions.

## Problem Statement

LiveKit's default Voice Activity Detection (VAD) is too sensitive to user feedback. When users say filler words like "yeah," "ok," or "hmm" to indicate they're listening, the agent incorrectly interprets these as interruptions and stops speaking.

## Solution

This implementation adds a logic layer that filters user input based on the agent's current state:

| User Input | Agent State | Behavior |
|------------|-------------|----------|
| "Yeah / Ok / Hmm" | Speaking | **IGNORE** - Agent continues without pause |
| "Wait / Stop / No" | Speaking | **INTERRUPT** - Agent stops immediately |
| "Yeah / Ok / Hmm" | Silent | **RESPOND** - Treated as valid input |
| Any input | Silent | **RESPOND** - Normal conversation |

## How It Works

The `interruption_handler.py` module installs event listeners on the agent session:

1. **State Tracking**: Monitors `agent_state_changed` events to know when the agent is speaking
2. **Input Filtering**: On `user_input_transcribed` events, applies the following priority logic:
   - **Priority 1**: Explicit interrupt phrases (stop, wait, hold on) → Always interrupt
   - **Priority 2**: Pure backchannel words (yeah, ok, hmm) → Ignore and clear user turn
   - **Priority 3**: Multi-word utterances → Treat as real interruption
   - **Priority 4**: Single unknown words → Ignore (safer default)

3. **Mixed Input Handling**: Sentences like "Yeah okay but wait" trigger an interrupt because they contain interrupt phrases

## Project Structure

```
├── agent.py                 # Main agent configuration and LiveKit session
├── interruption_handler.py  # Core interruption logic module
├── requirements.txt        # Python dependencies
└── mathew_readme.md              # This file
```

## Prerequisites

- Python 3.9+
- LiveKit Cloud account or self-hosted LiveKit server
- API keys for:
  - LiveKit
  - Deepgram (STT)
  - OpenAI (LLM)
  - Cartesia (TTS)

## Installation

1. **Clone and enter the repository**
   ```bash
   git clone https://github.com/Dark-Sys-Jenkins/agents-assignment.git
   cd agents-assignment
   git checkout -b feature/interrupt-handler-mathew
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env.local` file with your credentials:
   ```env
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   
   DEEPGRAM_API_KEY=your_deepgram_key
   OPENAI_API_KEY=your_openai_key
   CARTESIA_API_KEY=your_cartesia_key
   ```

## Running the Agent

1. **Download required model files** (first time only):
   ```bash
   python3 agent.py download-files
   ```

2. **Start the agent in console mode**:
   ```bash
   python3 agent.py console
   ```

The agent will connect to your LiveKit room and begin handling voice sessions.

## Configuration

### Customizing Backchannel Words

Set the `BACKCHANNEL_WORDS` environment variable to customize which words are ignored:

```env
BACKCHANNEL_WORDS=yeah,ok,okay,aha,hmm,mhm,uh-huh,yup,right,mmm,etc..
```

### Customizing Interrupt Phrases

Set the `INTERRUPT_WORDS` environment variable to customize which phrases trigger interruptions:

```env
INTERRUPT_WORDS=stop,wait,hold on,hang on,pause,no,one sec,sorry,excuse me,but,actually,etc...
```

## Testing

### Test Scenario 1: Long Explanation
- Have the agent explain something lengthy
- Say "okay," "yeah," "uh-huh" while it speaks
- **Expected**: Agent continues without breaking

### Test Scenario 2: Passive Affirmation
- Wait for the agent to ask a question and go silent
- Say "Yeah"
- **Expected**: Agent processes it as a valid response

### Test Scenario 3: Active Interruption
- While the agent is speaking
- Say "No stop" or "Wait"
- **Expected**: Agent stops immediately

### Test Scenario 4: Mixed Input
- While the agent is speaking
- Say "Yeah okay but wait"
- **Expected**: Agent stops (detects "wait" as interrupt phrase)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LiveKit Session                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌───────────────────────────────┐  │
│  │  VAD/STT     │───▶│   interruption_handler.py     │  │
│  │  (Deepgram)  │    │                               │  │
│  └──────────────┘    │  • Tracks agent speaking state│  │
│                      │  • Filters backchannel words  │  │
│  ┌──────────────┐    │  • Detects interrupt phrases  │  │
│  │  Agent State │───▶│  • Passes through valid input │  │
│  │  Events      │    │                               │  │
│  └──────────────┘    └───────────────────────────────┘  │
│                                  │                       │
│                                  ▼                       │
│                      ┌───────────────────────────────┐  │
│                      │      session.interrupt()      │  │
│                      │   or session.clear_user_turn()│  │
│                      └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Key Implementation Details

- **No VAD Modification**: The solution works as a logic layer above VAD, not by modifying low-level detection
- **Real-time Performance**: Filtering adds negligible latency since it only processes finalized transcripts
- **Seamless Continuation**: Uses `session.clear_user_turn()` to prevent backchannels from queuing responses
- **Modular Design**: The handler is a separate module that can be installed on any `AgentSession`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent still stops on "yeah" | Check that `install_interruption_handler(session)` is called before `session.start()` |
| Agent ignores all input | Verify the state tracking is working by checking console logs |
| High latency | Ensure you're only processing `is_final` transcripts |


## Demo Video

A video demonstration showing the interruption handling in action:

**[Watch Demo on Google Drive](https://drive.google.com/file/d/1qSwtBRipG37Ae6txSoUGauQvr6tDrpsq/view?usp=drive_link)**

The demo covers:
- Agent ignoring "yeah"( and other backchannel words ) while speaking
- Agent responding to "yeah"/"Hello" when silent ,so the agent starts to interact with the user
- Agent stopping immediately for "stop" (and other stop phrases)
- Agent deals with mixed phrases (ex. "yeah but wait" (here gives importance to stop words)) 