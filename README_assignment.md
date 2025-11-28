<!--BEGIN_BANNER_IMAGE-->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="/.github/banner_dark.png">
  <source media="(prefers-color-scheme: light)" srcset="/.github/banner_light.png">
  <img style="width:100%;" alt="GenAI Voice Agent banner showing audio waves and AI dialogue" src="https://raw.githubusercontent.com/Sripaadpatel/agents-assignment/main/.github/banner_light.png">
</picture>

<!--END_BANNER_IMAGE-->
<br />

![Python](https://img.shields.io/badge/Python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Completed-success)
[![GitHub Repo](https://img.shields.io/badge/GitHub-Sripaadpatel-lightgrey?logo=github)](https://github.com/Sripaadpatel/agents-assignment)

<br />

# GenAI Voice Agent – Intelligent Interruption Filter

## What is this project?

The **Intelligent Interruption Filter** is a key component of a conversational **Voice Agent** that can detect **when to interrupt, when to continue speaking, and when to respond**.

The system ensures that the agent doesn't stop speaking unnecessarily when users say fillers like “yeah” or “okay,” but **immediately pauses when users clearly say “stop,” “wait,” or “hold on.”**

This project was built as part of the **GenAI Engineer Campus Assignment** and integrates directly with the LiveKit voice framework.

---

## Features

- **Intelligent Speech Classification**  
  Differentiates between filler speech, real interruptions, and meaningful queries.

- **Real-time Filtering Logic**  
  Detects user intent dynamically during voice interaction.

- **Lightweight Integration**  
  Easy to plug into existing LiveKit Agents voice pipelines.

- **Supports Real Audio Input**  
  Works with both speech-to-text (STT) and pre-recorded `.wav` files.

- **Simple, Extendable Design**  
  Rule-based logic that can later evolve into an NLP intent classifier.

---

## Core Logic — The Interrupt Filter

### Objective

When humans converse, they often use short acknowledgments ("yeah", "ok", "hmm") that do not mean interruption.  
However, explicit commands like “stop” or “wait” should immediately interrupt the agent.

The **Interrupt Filter** is a lightweight classifier that decides how the agent should respond to each user utterance.

### Classification Categories

| Type | Behavior | Examples |
|------|-----------|-----------|
| **ignore** | Backchannels or filler words; agent continues speaking | "yeah", "ok", "hmm", "right" |
| **interrupt** | Explicit user interruption; agent stops | "stop", "wait", "hold on", "pause" |
| **neutral** | Actual input or question; handle normally | "what’s the weather", "tell me a joke" |

### Implementation Overview

1. **Input Cleaning**  
   Converts user text to lowercase, trims spaces, and removes noise.

2. **Keyword Matching**  
   Compares input against predefined sets of words:
   ```python
   IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "mmhmm", "right"}
   INTERRUPT_WORDS = {"stop", "wait", "hold on", "pause"}
3. Classification Decision
   
   ```python
   if word in INTERRUPT_WORDS:
    return "interrupt"
    elif word in IGNORE_WORDS:
    return "ignore"
    else:
    return "neutral"

  This modular approach ensures that the agent reacts appropriately without breaking conversation flow.
Tests and Simulation
**1. Basic Classification Test**

Validate the filter logic directly.

    python tests/test_interrupt_filter.py


Output:

    InterruptFilter quick test
    ----------------------------------------
    'yeah' -> ignore    (expect: ignore)
    'stop' -> interrupt (expect: interrupt)
    'what’s the weather' -> neutral (expect: neutral)

**2. Conversation Flow Simulation**

Simulates how the agent behaves in different states (speaking vs idle):

    python tests/simulate_agent_flow.py


Example:

    [agent_state=speaking] user said: 'yeah' -> ignore
    [agent_state=speaking] user said: 'stop' -> interrupt

**3. Real Audio Verification**

You can also test using your own recorded voice clips (no API keys required).

  1.Record .wav files such as:

    backchannel_yes.wav → “yeah okay”

    interrupt_stop.wav → “wait stop right there”

    neutral_question.wav → “what’s the weather today”

Place them in /tests/ and run:

    python tests/audio_file_interrupt_test.py


Example Output:

    === Testing file: interrupt_stop.wav ===
    Recognized text: 'stop right there'
    InterruptFilter result: interrupt

**Installation**

To set up the environment and dependencies:

    pip install -e livekit-agents
    pip install SpeechRecognition


Optional (for microphone testing on Windows):

    pip install pyaudio

File Structure
    
    agents-assignment-main/
    │
    ├── livekit-agents/
    │   └── livekit/
    │       └── agents/
    │           └── voice/
    │               └── interrupt_filter.py
    │
    ├── tests/
    │   ├── test_interrupt_filter.py
    │   ├── simulate_agent_flow.py
    │   ├── audio_file_interrupt_test.py
    │
    ├── examples/
    │   └── voice_agents/
    │       └── basic_agent.py
    │
    └── README.md

**Evaluation Summary**
| Criteria                   | Demonstrated In                | Result |
| -------------------------- | ------------------------------ | ------ |
| Ignore filler speech       | `test_interrupt_filter.py`     | ✅      |
| Detect explicit interrupts | `simulate_agent_flow.py`       | ✅      |
| Handle neutral phrases     | `simulate_agent_flow.py`       | ✅      |
| Real speech integration    | `audio_file_interrupt_test.py` | ✅      |
| Documentation & clarity    | `README.md`                    | ✅      |





Author

Name: Patel Sripaad
Institute: National Institute of Technology, Warangal
GitHub: github.com/Sripaadpatel
LinkedIn: linkedin.com/in/sripaad-patel-945870280

<!--BEGIN_REPO_NAV-->

<br/><table>

<thead>
  <tr>
    <th colspan="2">Project Navigation</th>
  </tr>
</thead> 
<tbody> 
  <tr>
    <td>Core Logic</td>
    <td>
      <a href="livekit-agents/livekit/agents/voice/interrupt_filter.py">Interrupt Filter
      </a>
    </td>
  </tr>
  <tr>
    <td>Text Simulation</td>
    <td>
      <a href="tests/simulate_agent_flow.py">Simulate Agent Flow</a>
    </td>
  </tr> 
  <tr>
    <td>Real Audio Demo</td>
    <td>
      <a href="tests/audio_file_interrupt_test.py">Audio File Test</a>
    </td>
  </tr>  
</tbody> 
</table> 
<!--END_REPO_NAV--> 
## Execution Logs

All test outputs are logged under `/logs/`:
- `simulate_agent_flow.log`
- `audio_file_interrupt_test.log`

