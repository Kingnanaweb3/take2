import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

async def main():
    agent = LlmAgent(
        name="smoke_test_agent",
        model="gemini-3.6-flash",
        instruction="You are a smoke test. Reply with exactly: ADK connection OK.",
    )

    runner = InMemoryRunner(agent=agent, app_name="take2_smoke_test")
    session = await runner.session_service.create_session(
        app_name="take2_smoke_test", user_id="smoke_test_user"
    )

    message = types.Content(role="user", parts=[types.Part(text="ping")])

    async for event in runner.run_async(
        user_id="smoke_test_user", session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print("Agent response:", part.text)

if __name__ == "__main__":
    asyncio.run(main())