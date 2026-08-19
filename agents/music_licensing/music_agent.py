"""
Take2 - Music Licensing Agent
Scans a scene for references to real, named songs or artists that would
require music licensing clearance. Uses Gemini via ADK to reason over
the scene text rather than relying on a static keyword list.
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv()

INSTRUCTION = """You are a music licensing clearance checker for film and TV production. You check ONLY songs, artists, bands, and albums.

Given a scene from a script, identify any references to REAL, NAMED songs, artists, bands, or albums that would require music licensing clearance before the production can use them.

Do NOT flag:
- Generic descriptions like "upbeat music plays" or "a song plays on the radio"
- Fictional song/artist names
- Commercial brands, products, or companies (a separate trademark agent handles this)
- Real people, celebrities, or their likeness/image (a separate likeness agent handles this)
- Real locations or landmarks (a separate location agent handles this)

DO flag:
- ONLY a real song title mentioned by name
- ONLY a real artist/band name mentioned in connection with music playing

Respond ONLY in this exact JSON format, no other text:
{
  "flags": [
    {"item": "<song or artist name>", "context": "<short quote from the scene>", "risk": "high|medium|low", "reasoning": "<one sentence>"}
  ]
}

If nothing is found, respond with: {"flags": []}
"""


async def check_scene(scene: dict) -> dict:
    agent = LlmAgent(
        name="music_licensing_agent",
        model="gemini-3.5-flash-lite",
        instruction=INSTRUCTION,
    )

    runner = InMemoryRunner(agent=agent, app_name="take2_music_check")
    session = await runner.session_service.create_session(
        app_name="take2_music_check", user_id="take2_pipeline"
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

    # Strip markdown code fences if Gemini wraps the JSON in them
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
        "agent": "music_licensing",
        **result
    }


async def run_music_check(scenes_path: str, output_path: str | None = None) -> list[dict]:
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
    output_path = "data/parsed/music_flags.json"

    results = asyncio.run(run_music_check(scenes_path, output_path))

    print(f"--- Music licensing check on {len(results)} scene(s) ---\n")
    for r in results:
        print(f"[Scene {r['scene_id']}] {r['heading']}")
        if r.get("flags"):
            for flag in r["flags"]:
                print(f"  {flag['item']} ({flag['risk']}) - {flag['reasoning']}")
        else:
            print("  No risk: No music licensing risks found")
        print("---")

    print(f"\nSaved results to {output_path}")
