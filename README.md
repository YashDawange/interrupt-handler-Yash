# Backchanneling Filter – Implementation Summary

This project adds a context-aware backchanneling filter to the LiveKit Agents framework.  
The filter solves a common problem where the agent gets interrupted too easily when the user gives small, natural feedback like “yeah”, “ok”, or “right” while the agent is speaking. Normally, LiveKit’s VAD treats any sound from the user as a full interruption, which makes the agent stop its sentence suddenly. The filter fixes this by distinguishing between *passive acknowledgements* and *real interruptions*.

## Purpose of the Feature

The main idea is that in normal human conversation, people often say small words like “mhm”, “yeah”, or “right” just to show they’re listening. These shouldn’t stop the speaker.  
However, words like “stop”, “wait”, or “no” should interrupt the speaker immediately.  
The filter makes the agent follow this same conversational pattern.

## Where the Implementation Lives

The core of the implementation is contained entirely within the framework layer.  

### 1. `backchanneling_filter.py` (New File)
This is where all the filtering logic lives. Inside this file, the filter:

- Defines a **list of backchanneling words** (like “yeah”, “ok”, “hmm”, “right”, “uh-huh”)
- Defines **interruption words** (like “wait”, “stop”, “no”, “hold on”)
- Splits the transcript into individual words
- Checks whether the words match backchanneling, interruptions, or a mixture
- Supports **semantic interruption**, meaning phrases like “yeah wait” count as a real interruption
- Decides whether to ignore the input or stop the agent

The filter is flexible and configurable. Users can easily add or remove words from either category.

### 2. `agent_activity.py` (Modified File)
This file handles the internal activity state of the agent (like speaking, paused, waiting for input). The backchanneling filter is integrated here so it runs at the right moment in the agent’s event loop. This file:

- Checks whether the agent is currently speaking or generating audio
- Catches VAD-triggered interruptions before they completely stop the speech
- Marks interruptions as **“pending validation”** until STT provides the transcript
- Calls the backchanneling filter to inspect the transcript
- Resumes speech immediately if the detected interruption was only backchanneling
- Keeps the interruption if the transcript contains interruption words
- Makes the entire process seamless from the agent’s perspective

By doing the filtering inside `agent_activity.py`, the VAD system itself does not need to be modified. All filtering happens at a higher logic layer.

## How the Logic Works

### State-Based Filtering
The filter only applies when the agent is actively speaking.  
If the agent is silent, everything the user says is treated as normal input.

- **Agent speaking + backchanneling words** → ignore and continue speaking  
- **Agent speaking + interruption words** → stop immediately  
- **Agent speaking + mixed input** → stop (because an interruption word is present)  
- **Agent silent** → respond normally and do not filter  

### Handling VAD + STT Timing
One of the trickier parts is that VAD fires before STT finishes transcribing speech.  
To handle this, the filter uses a two-step process:

1. **VAD fires** → temporarily pauses the agent and marks the interruption as “pending”.
2. **STT finishes** → transcript is validated against the filter rules.

If it was just “yeah” or “ok”, the agent resumes instantly.  
If it was “wait” or “stop”, the agent stays interrupted.


Video Link - https://drive.google.com/drive/folders/1MwAomQWIRwzQo2RqcklcIeFJzu8JFuSv
