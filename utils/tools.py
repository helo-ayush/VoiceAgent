"""
Custom LLM Function Calling Tools.

This module houses custom functions (tools) that the AI agent can execute.
Methods decorated with `@llm.function_tool` are automatically parsed by LiveKit,
creating JSON tool schemas which are served to the LLM (GPT-4o).
We showcase two design patterns:
1. **Slow Tool Pattern**: Pushes long-running operations (> 3 seconds) to a non-blocking
   background thread and returns instantly so the agent can keep speaking. Once finished,
   the result is dynamically injected into the live room session.
2. **Fast Tool Pattern**: Ideal for quick synchronous API lookups (< 2 seconds) that can
   block conversational playback momentarily.
"""

import asyncio
import logging
from livekit.agents import llm

logger = logging.getLogger(__name__)


class AssistantTools:
    """
    Container class for AI LLM action tools.
    """
    def __init__(self):
        # We store the active AgentSession reference here.
        # This is crucial for injecting replies asynchronously once slow background tasks finish.
        self.session = None

    # Decorator turns this method into a tool schema visible to the LLM.
    @llm.function_tool(description="Run a complex background task to analyze a dataset")
    async def analyze_dataset(self, dataset_name: str):
        """
        PATTERN 1: DECOUPLED ASYNC BACKGROUND WORKER (For tasks taking > 3 seconds)
        Instead of holding the agent in an awkward silent thinking loop,
        we trigger the heavy database/calculation worker as an independent non-blocking task
        and return a quick status report instantly.
        """
        # Fire and forget: Spawns the background calculations worker
        asyncio.create_task(self._background_analysis(dataset_name))
        
        # Instantly return response to the LLM, prompting the agent to say:
        # "I have started processing this dataset in the background and will let you know when it's done."
        return f"Task started for {dataset_name}. Tell the user you will let them know when it's done."

    async def _background_analysis(self, dataset_name: str):
        """
        Heavy non-blocking background calculations worker.
        Simulates long running database pipelines and then forcefully updates the agent.
        """
        logger.info(f"Starting async background analysis for dataset: {dataset_name}...")
        
        # Simulate a real heavy calculation task (e.g. database query, ML model run) taking 10 seconds.
        await asyncio.sleep(10)
        
        logger.info(f"Background task for {dataset_name} finished. Injecting reply...")
        
        # Ensure the session reference is active
        if self.session:
            # We wrap the results inside a SYSTEM NOTIFICATION role message.
            # LiveKit requires the text to be wrapped inside a list in 1.5.6+.
            message = llm.ChatMessage(
                role="user",
                content=[f"[SYSTEM NOTIFICATION]: The background task for '{dataset_name}' has finished. The result is 20% improvement! Please inform me of this result."]
            )
            try:
                # Forcefully inject this message into the chat session as a user event.
                # This automatically wakes up the LLM, triggering it to immediately interrupt
                # whatever it is doing and announce the completion of the background task out loud.
                self.session.generate_reply(user_input=message)
                logger.info("generate_reply successfully injected into LiveKit room session.")
            except Exception as e:
                logger.error(f"Error triggering session.generate_reply: {e}")
        else:
            logger.error("self.session is not populated! Cannot inject async background task reply.")

    # Decorator registers this fast method with the LLM schema
    @llm.function_tool(description="Check the weather for a given city/location")
    async def get_weather(self, location: str):
        """
        PATTERN 2: FAST SYNCHRONOUS LOOKUP (For tasks taking < 2 seconds)
        Ideal for brief, real-time API integrations. The LLM blocks and waits for a brief moment,
        acquires the result, and immediately incorporates it into its immediate spoken response.
        """
        # Simulate a quick 1-second REST API payload call
        await asyncio.sleep(1)
        
        # Return the literal string results directly back to the active conversation loop
        return f"The weather in {location} is 25 degrees."