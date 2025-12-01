# Intelligent Interruption Handling – LiveKit Agents

This project implements a custom interruption handler for a LiveKit real-time voice agent.  
It fixes the issue where the agent stops speaking whenever the user says backchannel words like “yeah”, “ok”, or “hmm”.

## ✔ What This Solves
- Prevents the agent from stopping during long explanations when the user says:
  `["yeah", "ok", "hmm", "right", "yup"]`
- Allows the agent to stop immediately when the user says:
  `["stop", "wait", "hold on", "no"]`
- Responds normally when the agent is silent.
- Supports mixed inputs (e.g., “yeah wait”) → still interrupts.

## ✔ How It Works
- Custom logic added in `_interrupt_by_audio_activity()`
- Soft words ignored only **when the agent is speaking**
- Hard interruption words detected using substring search
- STT transcript fed into `on_transcription()` to ensure decisions use real text
