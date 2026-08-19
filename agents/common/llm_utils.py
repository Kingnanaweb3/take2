"""
Take2 - Shared LLM call utilities
Provides a rate-limited, auto-retrying wrapper around ADK/Gemini calls
so multiple domain agents running in parallel don't blow the free-tier
quota (5 requests/minute on gemini-3.5-flash-lite).
"""

import asyncio
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.genai.errors import ClientError

# Free tier allows 5 req/min - cap concurrent in-flight calls well under that
_SEMAPHORE = asyncio.Semaphore(2)

MAX_RETRIES = 4
BASE_DELAY = 15  # seconds, generous since free tier resets per minute


async def call_agent(agent_name: str, instruction: str, model: str, prompt: str, app_name: str) -> str:
    """
    Runs a single-turn ADK/Gemini call with concurrency limiting and
    automatic retry on 429 RESOURCE_EXHAUSTED.
    """
    async with _SEMAPHORE:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                agent = LlmAgent(name=agent_name, model=model, instruction=instruction)
                runner = InMemoryRunner(agent=agent, app_name=app_name)
                session = await runner.session_service.create_session(
                    app_name=app_name, user_id="take2_pipeline"
                )
                message = types.Content(role="user", parts=[types.Part(text=prompt)])

                response_text = ""
                async for event in runner.run_async(
                    user_id="take2_pipeline", session_id=session.id, new_message=message
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text

                return response_text

            except ClientError as e:
                if "RESOURCE_EXHAUSTED" in str(e) and attempt < MAX_RETRIES:
                    wait = BASE_DELAY * attempt
                    print(f"  [{agent_name}] Rate limited, retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})...")
                    await asyncio.sleep(wait)
                    continue
                raise

        raise RuntimeError(f"{agent_name} failed after {MAX_RETRIES} retries")
