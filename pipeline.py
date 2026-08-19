"""
Take2 - Full Pipeline Orchestrator
Runs the complete pipeline in one command:
  Intake -> [Music, Trademark, Likeness, Location run in parallel] -> Governing

Usage:
  python3 pipeline.py [path/to/script.md]
"""

import asyncio
import sys
import time

from agents.intake.intake_agent import run_intake
from agents.music_licensing.music_agent import run_music_check
from agents.trademark.trademark_agent import run_trademark_check
from agents.likeness.likeness_agent import run_likeness_check
from agents.location.location_agent import run_location_check
from agents.governing.governing_agent import reconcile

SCENES_PATH = "data/parsed/scenes.json"
FLAGS_DIR = "data/parsed"
FINAL_REPORT_PATH = "data/parsed/final_report.json"


async def run_domain_agents_parallel():
    """Dispatch all four domain agents concurrently against the same scenes file."""
    print("Dispatching domain agents in parallel: music, trademark, likeness, location...\n")

    results = await asyncio.gather(
        run_music_check(SCENES_PATH, f"{FLAGS_DIR}/music_flags.json"),
        run_trademark_check(SCENES_PATH, f"{FLAGS_DIR}/trademark_flags.json"),
        run_likeness_check(SCENES_PATH, f"{FLAGS_DIR}/likeness_flags.json"),
        run_location_check(SCENES_PATH, f"{FLAGS_DIR}/location_flags.json"),
    )

    return {
        "music_licensing": results[0],
        "trademark": results[1],
        "likeness": results[2],
        "location": results[3],
    }


def main():
    script_path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_scripts/sample.md"

    t0 = time.time()

    # --- Step 1: Intake ---
    print(f"Step 1: Parsing script via Docling ({script_path})...")
    scenes = run_intake(script_path, SCENES_PATH)
    print(f"  -> {len(scenes)} scene(s) extracted\n")

    # --- Step 2: Domain agents in parallel ---
    t1 = time.time()
    asyncio.run(run_domain_agents_parallel())
    t2 = time.time()
    print(f"\nDomain agents completed in {t2 - t1:.1f}s\n")

    # --- Step 3: Governing/Reconciliation ---
    print("Step 3: Reconciling flags and writing audit trail...\n")
    reports = reconcile(SCENES_PATH, FLAGS_DIR, FINAL_REPORT_PATH)

    total_time = time.time() - t0

    # --- Summary ---
    print("--- Take2 Final Report ---\n")
    for r in reports:
        print(f"[Scene {r['scene_id']}] {r['heading']} - {r['verdict']} ({r['flag_count']} flag(s))")
        for flag in r["flags"]:
            print(f"    - [{flag['agent']}] {flag['item']} ({flag['risk']}): {flag['reasoning']}")
        print()

    print(f"Full report saved to {FINAL_REPORT_PATH}")
    print("Audit trail + metrics pushed to Grafana")
    print(f"\nTotal pipeline time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
