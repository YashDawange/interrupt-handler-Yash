import asyncio
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.llm import LLM

class DemoLLM(LLM):
    async def generate(self, *args, **kwargs):
        # simulate long explanation
        text = (
            "I am explaining something important. "
            "This explanation will continue even if you say yeah or okay. "
            "Please listen carefully."
        )
        for word in text.split():
            yield word + " "
            await asyncio.sleep(0.25)

class DemoAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a demo agent explaining something important."
        )

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        llm=DemoLLM(),
    )

    await session.start(
        agent=DemoAgent(),
        room=ctx.room,
    )

if __name__ == "__main__":
    cli.run_app(server)