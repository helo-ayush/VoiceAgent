# LiveKit Voice Agent: Tool Calling Guide

This guide explains how we have implemented Agentic Tool Calling (Function Calling) for the voice agent, and how you can add new tools in the future.

## 🌟 What We Have Implemented So Far

1. **Integrated OpenAI GPT-4o**: We swapped the LLM to GPT-4o through the LiveKit AI Proxy. This prevents the model from hallucinating during complex tool calls and handles Hinglish naturally.
2. **Generalized Filler Words**: The `SYSTEM_PROMPT` automatically instructs the agent to use natural filler phrases (*"Ek second dena, main check karta hoon..."*) right before it triggers **any** tool. You do not need to write custom filler lines for new tools.
3. **Decoupled Background Tasks**: We implemented a multi-tasking architecture that allows the agent to run long tasks (like 10-20 seconds) in the background without muting or pausing the agent. You can continue talking to the agent while it works!

---

## 🛠️ How to Add New Tools

When adding a new tool to `agent.py` inside the `AssistantTools` class, you must decide if the tool is **Fast** or **Slow**.

### Option 1: Fast Tools (1 to 3 seconds)
Use this for simple API calls like checking the weather, looking up a stock price, or reading a small file.

**How it works:** 
The agent will say a filler word, pause for 1 second while your code runs, and then instantly read the result back to the user.

**Example Code:**
```python
@llm.function_tool(description="Check the weather for a given city/location")
async def get_weather(self, location: str):
    # This represents a fast API call
    await asyncio.sleep(1) 
    
    # Return the string directly to the LLM
    return f"The weather in {location} is 25 degrees."
```

---

### Option 2: Slow Tools (10+ seconds)
Use this for heavy database queries, deep data analysis, or web scraping. If you use Option 1 for a slow tool, the agent will sit in awkward silence for 10 seconds and ignore the user. 

To keep the agent alive and chatty, we use the **Decoupled Background Task** pattern.

**How it works:**
1. The tool fires off a background task and returns **instantly**.
2. The agent tells the user *"I've started working on that."*
3. The user and agent can continue having a normal conversation.
4. When the background task finally finishes, it acts like a webhook—injecting a secret `user` message into the agent's brain to force it to announce the result!

**Example Code:**
```python
@llm.function_tool(description="Run a complex background task to analyze a dataset")
async def analyze_dataset(self, dataset_name: str):
    # 1. Fire and forget the background task so the agent can keep talking
    asyncio.create_task(self._background_analysis(dataset_name))
    
    # 2. Return instantly so the agent isn't blocked
    return f"Task started for {dataset_name}. Tell the user you will let them know when it's done."

async def _background_analysis(self, dataset_name: str):
    # 3. Do the heavy lifting here (e.g., 10+ seconds)
    await asyncio.sleep(10)
    
    # 4. When done, inject the result using self.session to force the agent to speak
    if self.session:
        message = llm.ChatMessage(
            role="user",
            content=[f"[SYSTEM NOTIFICATION]: The background task for '{dataset_name}' has finished. The result is 20% improvement! Please inform me of this result."]
        )
        self.session.generate_reply(user_input=message)
```

## 🚨 Important Notes on the Decoupled Pattern
* **`self.session.generate_reply()`**: This is the magic command that forces the agent to wake up and speak the background task result.
* **`role="user"`**: Always inject the background notification as a `"user"` message. If you inject it as a `"system"` message at the end of a conversation, LLMs (especially Llama 3 / Groq) get confused and start hallucinating random data.
* **`content=[...]`**: LiveKit 1.5.6 requires message content to be wrapped in a python `list[]` (to support multimodal images/text). Never pass a raw string directly to `content=`.
