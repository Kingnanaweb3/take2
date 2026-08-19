"""
Take2 - Trademark/Brand Agent
Scans a scene for references to real, named brands, products, or logos
that would need clearance or genericizing before use.
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

INSTRUCTION = """You are a trademark and brand clearance checker for film and TV production. You check ONLY commercial brands, products, logos, and companies.

Given a scene from a script, identify any references to REAL, NAMED commercial brands, products, logos, or companies that appear on-screen or are mentioned, which would need clearance or should be genericized before filming.

Do NOT flag:
- Generic descriptions like "a soda can" or "a phone"
- Fictional brand names
- Songs, music, or artists (a separate music licensing agent handles this)
- Real people, celebrities, or their likeness/image (a separate likeness agent handles this)
- Real locations or landmarks (a separate location agent handles this)

DO flag:
- ONLY real, identifiable commercial brand, product, or company names mentioned or implied to appear on-screen

Respond ONLY in this exact JSON format, no other text:
{
  "flags": [
    {"item": "<brand name>", "context": "<short quote from the scene>", "risk": "high|medium|low", "reasoning": "<one sentence>"}
  ]
}

If nothing is found, respond with: {"flags": []}
"""


async def check_scene(scene: dict) -> dict:
    agent = LlmAgent(
        name="trademark_agent",
        model="gemini-3.5-flash-lite",
        instruction=INSTRUCTION,
    )

    runner = InMemoryRunner(agent=agent, app_name="take2_trademark_check")
    session = await runner.session_service.create_session(
        app_name="take2_trademark_check", user_id="take2_pipeline"
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=f"Scene heading: {scene['heading']}\n\nScene content:\n{scene['content']}")]
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="take2_pipeline", session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {"flags": [], "_parse_error": response_text}

    return {
        "scene_id": scene["scene_id"],
        "heading": scene["heading"],
        "agent": "trademark",
        **result
    }


async def run_trademark_check(scenes_path: str, output_path: str | None = None) -> list[dict]:
    with open(scenes_path) as f:
        scenes = json.load(f)

    results = []
    for scene in scenes:
        result = await check_scene(scene)
        results.append(result)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    import sys

    scenes_path = sys.argv[1] if len(sys.argv) > 1 else "data/parsed/scenes.json"
    output_path = "data/parsed/trademark_flags.json"

    results = asyncio.run(run_trademark_check(scenes_path, output_path))

    print(f"--- Trademark check on {len(results)} scene(s) ---\n")
    for r in results:
        print(f"[Scene {r['scene_id']}] {r['heading']}")
        if r.get("flags"):
            for flag in r["flags"]:
                print(f"  {flag['item']} ({flag['risk']}) - {flag['reasoning']}")
        else:
            print("  No risk: No trademark risks found")
        print("---")

    print(f"\nSaved results to {output_path}")
