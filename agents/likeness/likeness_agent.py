"""
Take2 - Real-Person Likeness Agent
Scans a scene for references to real, named public figures (living or
recently deceased) that could pose right-of-publicity or defamation risk.
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

INSTRUCTION = """You are a real-person likeness clearance checker for film and TV production. You check ONLY references to real, named public figures.

Given a scene from a script, identify any references to REAL, NAMED public figures (celebrities, politicians, athletes, etc. - living or recently deceased) whose name, image, or likeness is mentioned or implied to appear on-screen (e.g. a poster, photo, or direct reference).

Do NOT flag:
- Fictional character names
- Generic descriptions of people
- Commercial brands, products, or companies (a separate trademark agent handles this)
- Songs, music, artists, or bands mentioned in a musical/dialogue sense - e.g. "play me some Fleetwood Mac" or "he loves Fleetwood Mac" (a separate music agent handles this entirely; do not flag band or artist names unless their actual VISUAL image, photo, or poster is explicitly described as appearing on-screen)
- Real locations or landmarks (a separate location agent handles this)

DO flag:
- ONLY real, named public figures whose likeness (image, poster, photo, direct portrayal) is referenced

Respond ONLY in this exact JSON format, no other text:
{
  "flags": [
    {"item": "<person's name>", "context": "<short quote from the scene>", "risk": "high|medium|low", "reasoning": "<one sentence>"}
  ]
}

If nothing is found, respond with: {"flags": []}
"""


async def check_scene(scene: dict) -> dict:
    agent = LlmAgent(
        name="likeness_agent",
        model="gemini-3.5-flash-lite",
        instruction=INSTRUCTION,
    )

    runner = InMemoryRunner(agent=agent, app_name="take2_likeness_check")
    session = await runner.session_service.create_session(
        app_name="take2_likeness_check", user_id="take2_pipeline"
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
        "agent": "likeness",
        **result
    }


async def run_likeness_check(scenes_path: str, output_path: str | None = None) -> list[dict]:
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
    output_path = "data/parsed/likeness_flags.json"

    results = asyncio.run(run_likeness_check(scenes_path, output_path))

    print(f"--- Likeness check on {len(results)} scene(s) ---\n")
    for r in results:
        print(f"[Scene {r['scene_id']}] {r['heading']}")
        if r.get("flags"):
            for flag in r["flags"]:
                print(f"  {flag['item']} ({flag['risk']}) - {flag['reasoning']}")
        else:
            print("  No risk: No likeness risks found")
        print("---")

    print(f"\nSaved results to {output_path}")
