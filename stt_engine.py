import os
import asyncio

OPENAI_AVAILABLE = False
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

class SimulatedSTT:
    """Simulates STT by returning canned transcripts after a short delay."""
    async def transcribe_stream(self, audio_stream):
        # audio_stream is ignored in simulation
        await asyncio.sleep(0.05)
        # yield a sequence of sample texts to simulate user speaking
        for text in ["yeah", "stop", "yeah"]:
            yield text
            await asyncio.sleep(0.1)

class OpenAIWhisperSTT:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured for STT")
        openai.api_key = self.api_key

    async def transcribe_stream(self, audio_stream):
        # Placeholder: in a real system you'd stream chunks to the OpenAI speech endpoint.
        # Here we just raise NotImplementedError to indicate where to integrate.
        raise NotImplementedError("Streaming OpenAI STT integration goes here")

def get_stt(allow_sim=True):
    if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIWhisperSTT()
        except Exception:
            pass
    if allow_sim:
        return SimulatedSTT()
    raise RuntimeError("No STT backend available")
