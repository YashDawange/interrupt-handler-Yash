# Multi-Agent Voice Storyteller — Example

This repository contains an example multi-agent voice application using LiveKit agents. The main example is `examples/voice_agents/multi_agent.py`. The example demonstrates how to build a voice-driven interactive storyteller that uses VAD, STT, TTS, and an LLM.

## Features
- Intro agent that gathers user name and location.
- Story agent that generates an interactive, personalized story.
- Interrupt / pause / resume handling during TTS playback.
- Usage metrics collection and logging.
- VAD prewarm for lower latency on session start.

## Prerequisites
- Python 3.9+
- Network access to LiveKit and any provider APIs used (LLM, STT/TTS)
- Provider credentials (see Environment variables)
- Recommended: virtual environment

## Environment variables
Create a `.env` file in the project root (or set env vars in your environment). Required/used variables include:
- LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET
- DEEPGRAM_API_KEY (used for STT/TTS in the example)
- GOOGLE_APPLICATION_CREDENTIALS (or other Google auth config required by the google plugin)

Example `.env` contents:
```
LIVEKIT_URL=https://your-livekit.example
LIVEKIT_API_KEY=ak_...
LIVEKIT_API_SECRET=sk_...
DEEPGRAM_API_KEY=dg_...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-sa.json
```

## Install dependencies
1. Create and activate a virtual environment:
   - Unix/macOS:
     - python -m venv .venv
     - source .venv/bin/activate
   - Windows:
     - python -m venv .venv
     - .\.venv\Scripts\activate
2. Install requirements (project-specific file or editable install):
   - pip install -r requirements.txt
   - or pip install -e ".[all]" if the repo exposes extras

Ensure packages for LiveKit agents and the plugins (deepgram, google, silero) are installed.

## Run the example
From the examples/voice_agents folder or repository root, run the example module. Example invocations:
- Local console test mode:
  - python examples/voice_agents/multi_agent.py console
- Alternate runner (if present in the repository):
  - uv run examples/voice_agents/multi_agent.py console

Modes commonly supported by the example CLI:
- console — local interactive audio I/O for manual testing
- dev — hot-reload development mode
- start — production mode (no auto-reload)

## How it works (high level)
- Session prewarms Silero VAD to reduce first-response latency.
- IntroAgent prompts for name and location and calls a function tool to hand off to StoryAgent.
- StoryAgent runs on an LLM + TTS, keeps the conversation interactive, and handles interruptions.
- Metrics are collected and logged; the example attempts to delete the LiveKit room when finished.

## Configuration & customization
- Change LLM model or provider instances in the code:
  - Replace google.LLM(...) with another provider or model name.
- Swap STT/TTS plugins by editing session creation arguments.
- Adjust interruption sensitivity by modifying `min_interruption_words`.
- Disable VAD prewarm by removing the `prewarm` server setup function.

## Troubleshooting
- Authentication errors: verify env vars and provider credentials.
- VAD model load errors: verify the silero package and required model files are installed.
- LLM/STT/TTS failures: check network access, quota, and model compatibility.
- Check logs (example uses DEBUG level) for detailed error messages.

## Cleanup
- The example attempts to delete the LiveKit room at the end of a session. If rooms persist, remove them from the LiveKit dashboard or via API.

## Security & cost
- Do not commit `.env` or credential files to version control.
- Monitor LLM/STT/TTS usage; these calls may incur costs.

## Files of interest
- examples/voice_agents/multi_agent.py — main example implementation
- .env (create for credentials)
- any repository-level README or requirements files for project-specific instructions

If needed, additional artifacts can be provided:
- a `.env.example` file
- a minimal requirements.txt derived from the example imports
- a short PowerShell launch script (if desired)
```// filepath: c:\Users\lenovo\OneDrive\Desktop\new2\upstream-repo\README.md

# Multi-Agent Voice Storyteller — Example

This repository contains an example multi-agent voice application using LiveKit agents. The main example is `examples/voice_agents/multi_agent.py`. The example demonstrates how to build a voice-driven interactive storyteller that uses VAD, STT, TTS, and an LLM.

## Features
- Intro agent that gathers user name and location.
- Story agent that generates an interactive, personalized story.
- Interrupt / pause / resume handling during TTS playback.
- Usage metrics collection and logging.
- VAD prewarm for lower latency on session start.

## Prerequisites
- Python 3.9+
- Network access to LiveKit and any provider APIs used (LLM, STT/TTS)
- Provider credentials (see Environment variables)
- Recommended: virtual environment

## Environment variables
Create a `.env` file in the project root (or set env vars in your environment). Required/used variables include:
- LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET
- DEEPGRAM_API_KEY (used for STT/TTS in the example)
- GOOGLE_APPLICATION_CREDENTIALS (or other Google auth config required by the google plugin)

Example `.env` contents:
```
LIVEKIT_URL=https://your-livekit.example
LIVEKIT_API_KEY=ak_...
LIVEKIT_API_SECRET=sk_...
DEEPGRAM_API_KEY=dg_...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-sa.json
```

## Install dependencies
1. Create and activate a virtual environment:
   - Unix/macOS:
     - python -m venv .venv
     - source .venv/bin/activate
   - Windows:
     - python -m venv .venv
     - .\.venv\Scripts\activate
2. Install requirements (project-specific file or editable install):
   - pip install -r requirements.txt
   - or pip install -e ".[all]" if the repo exposes extras

Ensure packages for LiveKit agents and the plugins (deepgram, google, silero) are installed.

## Run the example
From the examples/voice_agents folder or repository root, run the example module. Example invocations:
- Local console test mode:
  - python examples/voice_agents/multi_agent.py console
- Alternate runner (if present in the repository):
  - uv run examples/voice_agents/multi_agent.py console

Modes commonly supported by the example CLI:
- console — local interactive audio I/O for manual testing
- dev — hot-reload development mode
- start — production mode (no auto-reload)

## How it works (high level)
- Session prewarms Silero VAD to reduce first-response latency.
- IntroAgent prompts for name and location and calls a function tool to hand off to StoryAgent.
- StoryAgent runs on an LLM + TTS, keeps the conversation interactive, and handles interruptions.
- Metrics are collected and logged; the example attempts to delete the LiveKit room when finished.

## Configuration & customization
- Change LLM model or provider instances in the code:
  - Replace google.LLM(...) with another provider or model name.
- Swap STT/TTS plugins by editing session creation arguments.
- Adjust interruption sensitivity by modifying `min_interruption_words`.
- Disable VAD prewarm by removing the `prewarm` server setup function.

## Troubleshooting
- Authentication errors: verify env vars and provider credentials.
- VAD model load errors: verify the silero package and required model files are installed.
- LLM/STT/TTS failures: check network access, quota, and model compatibility.
- Check logs (example uses DEBUG level) for detailed error messages.

## Cleanup
- The example attempts to delete the LiveKit room at the end of a session. If rooms persist, remove them from the LiveKit dashboard or via API.

## Security & cost
- Do not commit `.env` or credential files to version control.
- Monitor LLM/STT/TTS usage; these calls may incur costs.

## Files of interest
- examples/voice_agents/multi_agent.py — main example implementation
- .env (create for credentials)
- any repository-level README or requirements files for project-specific instructions

If needed, additional artifacts can be provided:
- a `.env.example` file
- a minimal requirements.txt derived from the example imports
- a short PowerShell launch script (if desired)