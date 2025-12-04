# test_realtime.py
"""
Automated test runner for intelligent interruption handler.
Runs a sequence of inputs and logs the actions.

Run from repo root:
python3.11 test_realtime.py
"""

import asyncio
import logging
from examples.voice_agents.realtime_with_tts import MockAgent, classify_input  # note: we need MockAgent exposed
# Slight modification: we'll import interrupt_handler functions directly
from examples.voice_agents.interrupt_handler import classify_input as cls_input
from examples.voice_agents.interrupt_handler import should_interrupt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_realtime")

async def run_sequence():
    # create a short-lived mock agent
    agent = MockAgent()

    # helper to mimic on_user_speech behavior from realtime_with_tts
    async def on_user_speech(user_text: str):
        logger.info(f"INPUT: '{user_text}' | agent_speaking={agent.speaking} | class={cls_input(user_text)}")
        if should_interrupt(user_text, agent.speaking):
            if agent.speaking:
                logger.info("EXPECTED ACTION: INTERRUPT (agent should stop).")
                agent.speaking = False
            else:
                logger.info("EXPECTED ACTION: RESPOND (agent was silent).")
            reply = await agent.handle_input(user_text)
            await agent.generate_reply(reply)
        else:
            if agent.speaking:
                logger.info("EXPECTED ACTION: IGNORE (agent continues).")
            else:
                logger.info("EXPECTED ACTION: RESPOND (agent was silent).")
                reply = await agent.handle_input(user_text)
                await agent.generate_reply(reply)

    # Scenario sequences (match assignment scenarios)
    seq = [
        # Scenario 1: long explanation -> simulate agent speaking then user backchannels
        ("SCENARIO 1 START", None),
        ("agent_says_long", "This is a long explanation about history. It will take some time to speak."),
        ("backchannel1", "yeah"),
        ("backchannel2", "ok"),
        ("backchannel3", "hmm"),

        # Scenario 2: agent silent -> user says 'yeah'
        ("SCENARIO 2 START", None),
        ("agent_silent", None),
        ("user_yes", "yeah"),

        # Scenario 3: agent speaking -> user says 'no stop'
        ("SCENARIO 3 START", None),
        ("agent_counting", "One, two, three..."),
        ("user_stop", "no stop"),

        # Scenario 4: mixed input while speaking
        ("SCENARIO 4 START", None),
        ("agent_explains", "Now I'm continuing to explain more details."),
        ("mixed_input", "yeah okay but wait"),
    ]

    for tag, payload in seq:
        if tag.startswith("SCENARIO"):
            logger.info("==== %s ====", tag)
            await asyncio.sleep(0.2)
            continue
        if tag.startswith("agent_") and payload:
            # agent starts speaking the payload
            logger.info("Agent starts speaking (simulated): %s", payload)
            await agent.generate_reply(payload)
            continue
        if payload is None:
            # simulate silent state
            agent.speaking = False
            logger.info("Agent is now silent.")
            await asyncio.sleep(0.2)
            continue
        # handle user input
        await on_user_speech(payload)
        await asyncio.sleep(0.2)

if __name__ == "__main__":
    asyncio.run(run_sequence())
