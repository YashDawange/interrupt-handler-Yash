#!/usr/bin/env python3
"""
Four Scenarios Test for Intelligent Interruption Handling

This script tests the four key scenarios to validate that the interruption filter
works correctly in different conversational contexts.
"""

import asyncio
import logging
import sys
import time
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent
from livekit.agents.voice.interruption_filter import InterruptionFilter
from livekit.plugins import openai, deepgram

# Load environment variables
load_dotenv()

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Enable debug logging for voice components
logging.getLogger("livekit.agents.voice.agent_activity").setLevel(logging.INFO)
logging.getLogger("livekit.agents.voice.interruption_filter").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


class ScenarioTester:
    """Helper class to manage test scenarios"""

    def __init__(self):
        self.current_scenario = None
        self.test_results = {}

    def start_scenario(self, scenario_name: str):
        """Start a new test scenario"""
        self.current_scenario = scenario_name
        print(f"\n{'='*60}")
        print(f"🧪 TESTING SCENARIO: {scenario_name}")
        print(f"{'='*60}")

    def log_result(self, expected: str, actual: str):
        """Log test result"""
        success = "✅" if "PASS" in actual else "❌"
        self.test_results[self.current_scenario] = {
            "expected": expected,
            "actual": actual,
            "success": "PASS" in actual,
        }
        print(f"{success} Expected: {expected}")
        print(f"   Actual: {actual}")


# Global scenario tester
tester = ScenarioTester()


async def entrypoint(ctx: agents.JobContext):
    """Test agent with the four key interruption scenarios."""

    logger.info("🧪 Starting Four Scenarios Interruption Test...")

    await ctx.connect()

    # Create interruption filter with comprehensive word sets
    interruption_filter = InterruptionFilter(
        backchannel_words={
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "mm-hmm",
            "right",
            "yes",
            "yep",
            "sure",
            "aha",
            "ah",
            "mhm",
            "mm",
            "uh",
            "um",
            "got it",
            "alright",
            "gotcha",
            "understood",
            "i see",
            "absolutely",
            "definitely",
            "roger that",
            "make sense",
        },
        interruption_words={
            "wait",
            "stop",
            "hold on",
            "pause",
            "no",
            "actually",
            "but",
            "however",
            "excuse me",
            "sorry",
            "let me",
            "can i",
            "what about",
        },
    )

    logger.info(
        f"✅ Filter configured with {len(interruption_filter.backchannel_words)} backchannel words"
    )
    logger.info(
        f"✅ Filter configured with {len(interruption_filter.interruption_words)} interruption words"
    )

    # Create agent session with traditional pipeline
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            language="en",
            smart_format=True,
            interim_results=True,
        ),
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.3,  # Lower temperature for more consistent responses
        ),
        tts=openai.TTS(
            voice="nova",
            speed=0.9,  # Slightly slower for easier interruption testing
        ),
        interruption_filter=interruption_filter,
        resume_false_interruption=False,
        min_interruption_duration=0.2,
        min_interruption_words=1,
    )

    # Define test agent with specific scenario behaviors
    agent_instructions = """
    You are a test assistant for validating interruption handling. Follow these instructions exactly:

    When user says:
    
    1. "start scenario 1" or "test long explanation":
       - Say: "Let me explain how artificial intelligence works in detail."
       - Then speak continuously for 45+ seconds about AI, machine learning, neural networks, etc.
       - Speak at a moderate pace with natural pauses.
       - If interrupted with backchannel words like "okay", "yeah", "uh-huh", continue speaking.
       - Only stop if you hear clear interruption words like "stop", "wait", etc.

    2. "start scenario 2" or "test passive affirmation":
       - Ask: "Are you ready to begin the demonstration?"
       - Wait for user response.
       - When they respond with "yeah" or similar, say: "Okay, starting now. Here we go!"

    3. "start scenario 3" or "test correction":
       - Say: "I'll count slowly from one to twenty."
       - Count: "One... two... three... four..." with 2-second pauses between numbers.
       - Continue until interrupted or you reach twenty.
       - If interrupted, acknowledge immediately: "Okay, I'll stop counting."

    4. "start scenario 4" or "test mixed input":
       - Say: "Let me describe the weather forecast for this week in great detail."
       - Speak continuously about weather for 30+ seconds.
       - Be ready to stop immediately if you detect interruption words mixed with backchannel.

    5. "show results":
       - Summarize how the testing went based on what happened.

    Always acknowledge interruptions politely and ask what they need.
    """

    await session.start(room=ctx.room, agent=Agent(instructions=agent_instructions))

    # Initial greeting with test instructions
    await session.generate_reply(
        instructions="""
        Welcome the user and say:
        
        "Hello! I'm ready to test intelligent interruption handling with four key scenarios:

        🧪 Scenario 1: Say 'start scenario 1' - I'll give a long explanation. Try saying 'okay', 'yeah', 'uh-huh' while I speak. I should continue talking.

        🧪 Scenario 2: Say 'start scenario 2' - I'll ask if you're ready. When you say 'yeah', I should process it normally.

        🧪 Scenario 3: Say 'start scenario 3' - I'll count slowly. Try saying 'no stop' to interrupt me immediately.

        🧪 Scenario 4: Say 'start scenario 4' - I'll describe weather. Try saying 'yeah okay but wait' - I should stop at 'wait'.

        Which scenario would you like to test first?"
        """
    )

    logger.info("✅ Four Scenarios Test Agent ready!")

    # Print test instructions in console
    print("\n" + "=" * 80)
    print("🧪 FOUR SCENARIOS INTERRUPTION TEST")
    print("=" * 80)
    print()
    print("📝 Test Instructions:")
    print()
    print("✅ SCENARIO 1: The Long Explanation")
    print("   1. Say: 'start scenario 1'")
    print("   2. Agent will give long AI explanation")
    print("   3. While speaking, say: 'Okay… yeah… uh-huh'")
    print("   4. Expected: Agent continues uninterrupted")
    print()
    print("✅ SCENARIO 2: Passive Affirmation")
    print("   1. Say: 'start scenario 2'")
    print("   2. Agent asks: 'Are you ready?'")
    print("   3. Say: 'Yeah.'")
    print("   4. Expected: Agent processes normally → 'Okay, starting now.'")
    print()
    print("✅ SCENARIO 3: The Correction")
    print("   1. Say: 'start scenario 3'")
    print("   2. Agent counts: 'One, two, three…'")
    print("   3. Say: 'No stop.'")
    print("   4. Expected: Agent cuts off immediately")
    print()
    print("✅ SCENARIO 4: Mixed Input")
    print("   1. Say: 'start scenario 4'")
    print("   2. Agent describes weather")
    print("   3. Say: 'Yeah okay but wait.'")
    print("   4. Expected: Agent stops (because 'wait' is interruption word)")
    print()
    print("💡 Say 'show results' at the end to see a summary!")
    print("=" * 80)


async def monitor_interruptions():
    """Background task to monitor and log interruption events"""
    # This would be enhanced to capture real-time interruption decisions
    # For now, we rely on the logging from the agent activity
    pass


if __name__ == "__main__":
    print(
        """
🧪 FOUR SCENARIOS INTERRUPTION TEST
===================================

This test validates that your intelligent interruption filter correctly handles:

✅ Scenario 1: Backchannel during long speech (should NOT interrupt)
✅ Scenario 2: Backchannel when agent silent (should process normally)  
✅ Scenario 3: Clear interruption words (should interrupt immediately)
✅ Scenario 4: Mixed backchannel + interruption (should interrupt)

Starting the test agent...
    """
    )

    # Configure worker options
    worker_options = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
    )

    # Start the agent
    logger.info("🚀 Starting Four Scenarios Test Agent...")
    agents.cli.run_app(worker_options)
