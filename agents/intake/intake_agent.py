"""
Take2 - Intake Agent
Parses a script file (PDF/Markdown/etc.) via Docling, then splits it into
individual scenes based on standard screenplay sluglines (INT./EXT./EST.).
Outputs structured scene data for the domain agents to consume.
"""

import re
import json
from pathlib import Path
from docling.document_converter import DocumentConverter

# Matches standard screenplay scene headings, e.g.:
# "INT. COFFEE SHOP - DAY", "EXT. PARKING LOT - NIGHT"
SCENE_HEADING_PATTERN = re.compile(
    r"^(INT\.|EXT\.|INT/EXT\.|EST\.)\s+.+$",
    re.MULTILINE | re.IGNORECASE
)


def parse_script(file_path: str) -> str:
    """Convert a script file to clean Markdown using Docling."""
    converter = DocumentConverter()
    result = converter.convert(file_path)
    return result.document.export_to_markdown()


def split_into_scenes(markdown_text: str) -> list[dict]:
    """
    Split parsed script text into scenes using screenplay sluglines.
    Returns a list of dicts: {scene_id, heading, content}
    """
    # Strip markdown heading symbols (#) Docling may add before sluglines
    cleaned = re.sub(r"^#+\s*", "", markdown_text, flags=re.MULTILINE)

    matches = list(SCENE_HEADING_PATTERN.finditer(cleaned))

    if not matches:
        # No sluglines found — treat the whole doc as one scene
        return [{
            "scene_id": 1,
            "heading": "UNSTRUCTURED",
            "content": cleaned.strip()
        }]

    scenes = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        block = cleaned[start:end].strip()
        heading_line = block.split("\n", 1)[0].strip()
        body = block[len(heading_line):].strip()

        scenes.append({
            "scene_id": i + 1,
            "heading": heading_line,
            "content": body
        })

    return scenes


def run_intake(file_path: str, output_path: str | None = None) -> list[dict]:
    """Full intake pipeline: parse -> split -> (optionally) save JSON."""
    markdown = parse_script(file_path)
    scenes = split_into_scenes(markdown)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(scenes, f, indent=2)

    return scenes


if __name__ == "__main__":
    import sys

    input_path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_scripts/sample.md"
    output_path = "data/parsed/scenes.json"

    scenes = run_intake(input_path, output_path)

    print(f"--- Parsed {len(scenes)} scene(s) from {input_path} ---\n")
    for scene in scenes:
        print(f"[Scene {scene['scene_id']}] {scene['heading']}")
        print(scene['content'][:200])
        print("---")

    print(f"\nSaved structured output to {output_path}")
