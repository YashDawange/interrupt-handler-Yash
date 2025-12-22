from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        llm="openai/gpt-4o-mini",
    )

    await session.start(
        agent=Agent(instructions="You are a test agent."),
        room=ctx.room,
    )

if __name__ == "__main__":
    cli.run_app(server)