import os, asyncio
from interrupt_filter import InterruptionFilter

USE_SIM = os.getenv("USE_SIMULATION", "true").lower() in ("1","true","yes")

class LiveKitAgent:
    def __init__(self, stt, tts, room_name="voice-room"):
        self.stt = stt
        self.tts = tts
        self.room_name = room_name
        self.filter = InterruptionFilter()
        self.agent_state = "silent"
        self.pending_vad = False

    async def on_agent_start_speaking(self):
        self.agent_state = "speaking"
       
        print("[Agent] START speaking (state -> speaking)")
        self.tts.speak("I will now give a long explanation. Listen carefully.")

    async def on_agent_stop_speaking(self):
        self.agent_state = "silent"
        print("[Agent] STOP speaking (state -> silent)")

    async def handle_transcripts(self, transcript_generator):
        async for text in transcript_generator:
            print(f"[STT] Transcript arrived: '{text}'")
            action = self.filter.process_transcript(text, self.agent_state)
            if action == "ignore":
                print(f"[FILTER] Ignored while speaking: '{text}'")
                self.pending_vad = False
                continue
            if action == "interrupt":
                print(f"[FILTER] INTERRUPT triggered by: '{text}'")
                
                if self.agent_state == "speaking":
                    await self.on_agent_stop_speaking()
                
                self.tts.speak(f"Heard interrupt: {text}")
                continue
            if action == "respond":
                print(f"[FILTER] Responding to: '{text}'")
                self.tts.speak(f"Response to: {text}")
                continue

    async def run_simulation(self):

        await self.on_agent_start_speaking()
       
        gen = self.stt.transcribe_stream(None)
        consumer = asyncio.create_task(self.handle_transcripts(gen))
       
        await asyncio.sleep(1.5)
        await self.on_agent_stop_speaking()
        await consumer
        print("Simulation finished.")

    async def run_live(self):
      
        raise NotImplementedError("The LiveKit live mode must be implemented for your environment.")
