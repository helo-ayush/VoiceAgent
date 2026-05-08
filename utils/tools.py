import asyncio
import logging
from livekit.agents import llm

class AssistantTools:
    """
    This class holds all the tools (functions) the AI agent can use.
    Methods decorated with @llm.function_tool become accessible to the LLM.
    """
    def __init__(self):
        # We store the session so we can inject messages later for slow tasks
        self.session = None

    @llm.function_tool(description="Run a complex background task to analyze a dataset")
    async def analyze_dataset(self, dataset_name: str):
        """
        SLOW TOOL PATTERN (Decoupled Background Task)
        Use this pattern when a task takes more than ~3 seconds.
        Instead of making the AI wait in silence, we push the work to the background
        and instantly return so the AI can keep chatting with the user.
        """
        # Fire and forget the background task
        asyncio.create_task(self._background_analysis(dataset_name))
        
        # Instantly return so the agent isn't blocked
        return f"Task started for {dataset_name}. Tell the user you will let them know when it's done."

    async def _background_analysis(self, dataset_name: str):
        """The actual background worker for analyze_dataset."""
        # Simulate a real database query that takes 10 seconds
        await asyncio.sleep(10)
        logging.info(f"Background task for {dataset_name} finished. Injecting reply...")
        
        # When done, inject the result into the chat as if the "user" provided it.
        # This prompts the agent to speak immediately.
        if self.session:
            message = llm.ChatMessage(
                role="user",
                # Wrap in a list as required by LiveKit 1.5.6+
                content=[f"[SYSTEM NOTIFICATION]: The background task for '{dataset_name}' has finished. The result is 20% improvement! Please inform me of this result."]
            )
            try:
                self.session.generate_reply(user_input=message)
                logging.info("generate_reply triggered successfully.")
            except Exception as e:
                logging.error(f"Error triggering generate_reply: {e}")
        else:
            logging.error("self.session is None! Cannot inject reply.")

    @llm.function_tool(description="Check the weather for a given city/location")
    async def get_weather(self, location: str):
        """
        FAST TOOL PATTERN
        Use this pattern for quick API calls. The AI will pause for a second,
        grab the result, and continue speaking.
        """
        await asyncio.sleep(1)
        return f"The weather in {location} is 25 degrees."
