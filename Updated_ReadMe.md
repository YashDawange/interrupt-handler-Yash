LiveKit Voice Agent (Kelly)This project implements a real-time voice agent named Kelly using the LiveKit Agents framework. It features intelligent interruption handling, backchanneling (ignoring filler words like "uh-huh"), and integrates with top-tier AI models for transcription, reasoning, and speech synthesis.FeaturesReal-time Communication: Built on LiveKit's WebRTC infrastructure.Intelligent Turn Detection: Uses VAD (Voice Activity Detection) to handle interruptions naturally.Backchanneling Support: Specifically configured to ignore filler words (yeah, ok, hmm) while the agent is speaking, allowing for more natural "listening" behavior without cutting off the agent.Metrics & Telemetry: Built-in usage tracking for session resource consumption.Modular Design: Easy to swap out STT, LLM, and TTS providers.PrerequisitesPython 3.9 or higherA LiveKit Cloud project (or self-hosted instance)API Keys for the services used (Deepgram, OpenAI, ElevenLabs/Cartesia)InstallationClone the repository (or download the files):git clone <your-repo-url>
cd <your-repo-name>
Create a virtual environment (recommended):python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies:pip install -r requirements.txt
ConfigurationCreate a file named .env in the root directory.Add your API keys as shown below.# LiveKit Configuration
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=<your-api-key>
LIVEKIT_API_SECRET=<your-api-secret>

# Model Service Keys
OPENAI_API_KEY=<your-openai-key>
DEEPGRAM_API_KEY=<your-deepgram-key>
ELEVEN_API_KEY=<your-elevenlabs-key>
# CARTESIA_API_KEY=<your-cartesia-key> # Optional: If using Cartesia TTS
Running the AgentStart the agent worker by running:python basic_agent.py start
Once running, the agent will wait for a room connection. You can connect to it using a LiveKit frontend or the LiveKit Agents Playground.CustomizationSwitching TTS ProviderThe provided code might default to Cartesia. To use ElevenLabs (matching your API keys), you need to make a small change in basic_agent.py:Import the plugin:from livekit.plugins import elevenlabs
Update the AgentSession:Change the tts argument in the AgentSession initialization:# Old (Cartesia)
# tts=cartesia.TTS(model="...")

# New (ElevenLabs)
tts=elevenlabs.TTS(),
Adjusting Interruption SensitivityYou can tune how aggressive the agent is about stopping when you speak by modifying these variables in basic_agent.py:min_endpointing_delay: How long to wait after speech stops to reply.ignored_interruption_words: List of words that won't stop the agent.