import asyncio
from nitya_interrupt_agent import NityaInterruptAgent, AgentState


class FakeSession:
    """
    A fake session object to simulate LiveKit AgentSession for testing logic.
    Only implements methods that our agent logic calls.
    """
    async def interrupt_tts(self):
        print("👉 [SESSION] interrupt_tts() CALLED")

    async def send_message(self, msg: str):
        print(f"🗣️ [AGENT] {msg}")

    async def provide_input(self, text: str):
        print(f"🧠 [LLM] Received user query → '{text}'")


async def simulate_event(agent: NityaInterruptAgent, session: FakeSession, text: str, agent_speaking: bool):
    print("\n======================================")
    print(f"User says: '{text}'")
    print(f"Agent speaking? {agent_speaking}")
    print("======================================")

    # adjust agent speaking state
    agent.state.is_speaking = agent_speaking

    # simulate STT transcript event
    await agent.on_transcription(text, session)


async def main():
    print("\n BEGINNING LOGIC TESTING…\n")

    agent = NityaInterruptAgent(instructions="You are a helpful assistant.")

    session = FakeSession()

    # TEST CASE 1 — agent is speaking, user says "yeah"
    await simulate_event(agent, session, "yeah", agent_speaking=True)

    # TEST CASE 2 — agent is speaking, user says "okay"
    await simulate_event(agent, session, "okay", agent_speaking=True)

    # TEST CASE 3 — agent is speaking, user says "stop"
    await simulate_event(agent, session, "stop", agent_speaking=True)

    # TEST CASE 4 — agent is silent, user says "yeah"
    await simulate_event(agent, session, "yeah", agent_speaking=False)

    # TEST CASE 5 — agent is silent, user asks a real question
    await simulate_event(agent, session, "what time is it?", agent_speaking=False)

    print("\n TEST COMPLETE.\n")


if __name__ == "__main__":
    asyncio.run(main())
