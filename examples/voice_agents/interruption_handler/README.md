# Intelligent Interruption Handler

A voice agent that handles interruptions naturally by understanding what the user wants and responding appropriately.

## What It Does

When someone interrupts the agent while it's talking, the system figures out why they interrupted and responds in the right way. It's like having a conversation with someone who actually listens and adapts.

The agent can tell if you're just saying "interesting!" because you want to hear more, or if you're saying "wait, stop!" because you need it to be quiet. Then it acts accordingly - either keeping the conversation going or changing direction based on what you need.

## How It Works

The interruption agent watches for interruptions in real-time using LiveKit's event system. When the user starts speaking while the agent is talking, it catches that immediately - within about 500 milliseconds.

Once an interruption is detected, the interruption agent hands off the analysis work to the context analyzer. This is a separate component that exists specifically to understand what just happened. The context analyzer takes the user's words, looks at what the agent was saying, and examines the recent conversation history. Then it uses an LLM to figure out what type of interruption this is and what the user actually wants.

The context analyzer can identify 8 different interruption types - things like urgent questions, corrections, clarification requests, topic changes, or just simple agreement. It classifies the interruption with a confidence score and recommends one of 6 response strategies. For instance, if you say "That's cool!" while it's explaining AI, the context analyzer recognizes this as an agreement interruption and recommends the "acknowledge and continue" strategy. But if you say "Hold on", it sees this as a stop request and recommends stopping immediately.

Once the context analyzer finishes its work and sends back its recommendation, the interruption agent takes over again. It uses the recommended strategy to craft an appropriate response. If the strategy is "acknowledge and continue", the agent briefly acknowledges your interest and then provides more detailed information on the same topic. If it's "answer and resume", the agent answers your question quickly and then returns to what it was originally explaining.

The whole process happens fast enough to feel natural in conversation - usually under 3 seconds from interruption to response.

## Files

- `interruption_agent.py` - Main agent with event handlers and response strategies
- `context_analyzer.py` - LLM-powered interruption classification
- `test_phase3.py` - Unit tests
- `requirements.txt` - Python dependencies

## Example

Here's what a typical interaction looks like:

```
You: "What is artificial intelligence?"
Agent: "Artificial intelligence refers to..."

You: "That's interesting!"
[Agent detects interruption, analyzes it as AGREEMENT, continues with detail]

Agent: "Exactly! So to dive deeper into AI, there are several key aspects..."
```

The agent understood you wanted more information rather than wanting to stop or change topics.

## Testing

Run the unit tests:
```powershell
pytest test_phase3.py -v
```

## Why We Built It This Way

Most voice agents either ignore interruptions or handle them clumsily. We wanted something that feels natural, like talking to a real person who can read the room.

We separated the context analyzer into its own component because interruption analysis is genuinely hard. It's not enough to just detect that someone spoke - you need to understand why they spoke and what they want. A simple keyword matcher wouldn't cut it because the same words can mean different things depending on context. "That's interesting" could mean "tell me more" or "let's talk about that instead" depending on what's happening in the conversation.

By giving the context analyzer access to the full conversation history and both sides of the interaction, it can make smarter decisions. The LLM inside the context analyzer understands nuance and can pick up on subtle cues that rule-based systems would miss.

The interruption agent keeps conversation memory so it can resume topics intelligently. If someone asks a quick question mid-explanation, the agent remembers what it was explaining and picks up where it left off. This separation of concerns makes the whole system cleaner - the interruption agent handles the conversation flow and delegates the "what does this mean?" question to the context analyzer.

## Technical Notes

The system uses Deepgram for speech-to-text, OpenAI's GPT-4o-mini for the LLM (both for conversation and interruption analysis), and Cartesia for text-to-speech. We found we needed to wait about 2.5 seconds after detecting an interruption to get the full, accurate transcript from the STT service.

Testing showed about 90% accuracy on classifying interruption types correctly. The total response time from interruption to agent reply is usually under 3 seconds, which feels natural in conversation.

---

