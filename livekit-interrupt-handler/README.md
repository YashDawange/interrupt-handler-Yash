# LiveKit Interrupt Handler

## Overview
This project implements an **interrupt handler** for a LiveKit-based agent.  
The handler allows the agent to respond to certain voice commands in real-time while handling speech-to-text input.

---

## Features
- **Ignore filler words** like "yeah" while the agent is speaking.
- **Respond** to "yeah" when the agent is silent.
- **Stop speaking** immediately when "stop" is detected.
- Easy integration with a LiveKit agent project.

---

## File Structure
livekit-interrupt-handler/
│
├── src/
│ ├── agentIntegrationExample.mjs # Example integration with LiveKit agent
│ ├── config.mjs # Configuration settings
│ ├── interruptHandler.mjs # Main interrupt handler logic
│ └── utils.mjs # Helper functions
│
├── tests/
│ └── test_interruptHandler.mjs # Test cases for interrupt handler
│
├── requirements.txt # Python dependencies (if any)
├── package.json # Node.js project file
├── package-lock.json # Node.js lock file
├── .env.sample # Sample environment variables
├── scripts/run.sh # Script to run the example
└── README.md # Project documentation

yaml
Copy code

---

## How to Use
1. Clone the repository:
```bash
git clone <your-forked-repo-url>
cd livekit-interrupt-handler
Install dependencies:

bash
Copy code
npm install
Run the agent example:

bash
Copy code
npm start
Test the interrupt commands:

Say "yeah" while the agent is speaking → agent ignores it.

Say "yeah" while the agent is silent → agent responds.

Say "stop" → agent immediately stops speaking.

Proof
A log transcript demonstrating the behavior is included:

Copy code
livekit_interrupt_demo.txt
It shows:

Agent ignoring "yeah" while speaking

Agent responding to "yeah" when silent

Agent stopping for "stop"

Author
Ravi-hr26
