# Intelligent Interruption Handler for LiveKit Agents

This implementation provides intelligent interruption handling for LiveKit voice agents. It distinguishes between passive acknowledgments (like "yeah", "ok", "hmm") and active interruptions (like "wait", "stop", "no") based on whether the agent is currently speaking or silent.

## Core Logic

The system handles the following logic matrix:

| User Input | Agent State | Desired Behavior |
|------------|-------------|------------------|
| "Yeah / Ok / Hmm" | Agent is Speaking | IGNORE: The agent continues speaking without pausing or stopping |
| "Wait / Stop / No" | Agent is Speaking | INTERRUPT: The agent stops immediately and listens to the new command |
| "Yeah / Ok / Hmm" | Agent is Silent | RESPOND: The agent treats this as valid input |
| "Start / Hello" | Agent is Silent | RESPOND: Normal conversational behavior |

## Features

1. *Configurable Ignore List*: Define a list of words that act as "soft" inputs
2. *State-Based Filtering*: The filter only applies when the agent is actively generating or playing audio
3. *Semantic Interruption*: Mixed sentences like "Yeah wait a second" will interrupt because "wait" is in the interrupt list
4. *No VAD Modification*: Implemented as a logic handling layer within the agent's event loop

## Implementation Details

The solution works by:

1. Creating a custom IntelligentAgentActivity that extends the base AgentActivity
2. Overriding the on_end_of_turn method to intercept user input before processing
3. Using an IntelligentInterruptionHandler to determine if input should be ignored based on:
   - Current agent state (speaking or silent)
   - Content of user input (passive acknowledgment vs. active command)
4. Creating a custom IntelligentAgentSession that uses our custom activity

## How to Run

1. Make sure you have the required dependencies installed:
   
   pip install "livekit-agents[openai,silero,deepgram,cartesia]~=1.0"
   

2. Set up your environment variables:
   
   DEEPGRAM_API_KEY=your_deepgram_api_key
   OPENAI_API_KEY=your_openai_api_key
   CARTESIA_API_KEY=your_cartesia_api_key
   

3. Run the agent:
   
   python intelligent_interruption_agent.py dev
   

## Test Cases

The implementation handles these scenarios correctly:

### Scenario 1: The Long Explanation
- *Context*: Agent is reading a long paragraph about history
- *User Action*: User says "Okay... yeah... uh-huh" while Agent is talking
- *Result*: Agent audio does not break. It ignores the user input completely

### Scenario 2: The Passive Affirmation
- *Context*: Agent asks "Are you ready?" and goes silent
- *User Action*: User says "Yeah"
- *Result*: Agent processes "Yeah" as an answer and proceeds

### Scenario 3: The Correction
- *Context*: Agent is counting "One, two, three..."
- *User Action*: User says "No stop"
- *Result*: Agent cuts off immediately

### Scenario 4: The Mixed Input
- *Context*: Agent is speaking
- *User Action*: User says "Yeah okay but wait"
- *Result*: Agent stops (because "but wait" contains a command)

## Configuration

The interruption handler can be easily configured by modifying the word lists in IntelligentInterruptionHandler:

- ignore_list: Words that are treated as passive acknowledgments
- interrupt_list: Words that always trigger interruption regardless of agent state

These lists can be extended or modified based on your specific requirements.