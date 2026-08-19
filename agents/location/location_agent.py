"""
Take2 - Location Rights Agent
Scans a scene for references to real, named locations (landmarks, private
businesses, specific addresses) that would need filming/location permits
or property releases.
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

# Domain-shaped verification: a small curated list of unambiguous, famous
# real-world landmarks. This is Location's own domain-specific structure,
# distinct from the other three agents, which rely purely on LLM judgment.
KNOWN_LANDMARKS = {
    "eiffel tower", "times square", "statue of liberty", "golden gate bridge",
    "big ben", "empire state building", "the louvre", "colosseum",
    "sydney opera house", "mount rushmore", "niagara falls", "central park",
    "hollywood sign", "buckingham palace", "brooklyn bridge",
}


def verify_landmark(item_name: str) -> bool:
    """Check a flagged location against the curated known-landmark list."""
    return item_name.strip().lower() in KNOWN_LANDMARKS


INSTRUCTION = """You are a location rights clearance checker for film and TV production. You check ONLY real, named locations.

Given a scene from a script, identify any references to REAL, NAMED locations (famous landmarks, specific real businesses, named real cities/neighborhoods used as a filming location, specific real addresses) that would need filming permits or property releases before the production can shoot there or depict them.

Do NOT flag:
- Generic settings like "a coffee shop" or "a park" with no real name attached
- Fictional place names
- Commercial brands, products, or companies (a separate trademark agent handles this, unless the brand IS the location itself, e.g. a named real store)
- Songs, music, or artists (a separate music agent handles this)
- Real people or their likeness (a separate likeness agent handles this)

DO flag:
- ONLY real, named, identifiable locations that the scene implies will be filmed at or depicted

Respond ONLY in this exact JSON format, no other text:
{
  "flags": [
    {"item": "<location name>", "context": "<short quote from the scene>", "risk": "high|medium|low", "reasoning": "<one sentence>"}
  ]
}

If nothing is found, respond with: {"flags": []}
"""


async def check_scene(scene: dict) -> dict:
    agent = LlmAgent(
        name="location_agent",
        model="gemini-3.5-flash-lite",
        instruction=INSTRUCTION,
    )

    runner = InMemoryRunner(agent=agent, app_name="take2_location_check")
    session = await runner.session_service.create_session(
        app_name="take2_location_check", user_id="take2_pipeline"
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

    # Domain-specific step: cross-check each flag against the known-landmark
    # list and annotate verification status
    if "flags" in result:
        for flag in result["flags"]:
            flag["verified"] = verify_landmark(flag.get("item", ""))

    return {
        "scene_id": scene["scene_id"],
        "heading": scene["heading"],
        "agent": "location",
        **result
    }


async def run_location_check(scenes_path: str, output_path: str | None = None) -> list[dict]:
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
    output_path = "data/parsed/location_flags.json"

    results = asyncio.run(run_location_check(scenes_path, output_path))

    print(f"--- Location check on {len(results)} scene(s) ---\n")
    for r in results:
        print(f"[Scene {r['scene_id']}] {r['heading']}")
        if r.get("flags"):
            for flag in r["flags"]:
                print(f"  {flag['item']} ({flag['risk']}) - {flag['reasoning']}")
        else:
            print("  No risk: No location risks found")
        print("---")

    print(f"\nSaved results to {output_path}")
