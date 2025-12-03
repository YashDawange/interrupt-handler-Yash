README — LiveKit Intelligent Interruption Handler

Overview

This project implements a context-aware interruption handler for a LiveKit voice agent.
It prevents the agent from being accidentally cut off by soft backchannels like “yeah”, “ok”, “hmm” while the agent is speaking, but still allows true interruptions like “stop”, “wait”, “no” (including mixed phrases such as “yeah wait”). The solution sits above the VAD: it uses STT transcripts and the agent’s speaking state to decide whether to ignore, interrupt, or respond.

⸻

Quick features
	•	Configurable ignore list (soft backchannels)
	•	Configurable interrupt list (hard commands)
	•	State-aware: different behavior when agent is speaking vs silent
	•	VAD false-start protection: VAD events are validated by STT before causing interruption
	•	Two run modes:
	•	SIMULATION mode (default) — no LiveKit required, deterministic STT samples
	•	LIVE mode — connect to a LiveKit server and work with real audio (placeholder live code included; integration guidance given)

⸻

Files included
	•	main_agent.py — entry point. Chooses simulation or live mode and wires components.
	•	livekit_agent.py — agent class: state tracking, transcript handling, simulation runner, placeholder for live integration.
	•	interrupt_filter.py — core logic: classifies transcripts into ignore/interrupt/respond.
	•	stt_engine.py — pluggable STT: simulated STT (and a placeholder OpenAI Whisper wrapper).
	•	tts_engine.py — simple TTS wrapper (uses pyttsx3 if available, otherwise prints).
	•	.env.template — environment variables template.
	•	requirements.txt — dependencies list.
	•	run.sh — helper to run (creates venv, installs deps, runs agent).
	•	proof_log.txt — file you can create by redirecting stdout to capture proof logs for submission.