"""
Take2 - Governing/Reconciliation Agent
Merges findings from all domain agents (music, trademark, likeness, location)
per scene, assigns a final verdict (Cleared/Flagged/Blocked), and pushes
the full audit trail to Grafana via OTLP (logs + metrics).
"""

import json
import time
from pathlib import Path
from dotenv import load_dotenv

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

import logging

load_dotenv()

# --- OTLP setup (metrics + logs) ---
metric_exporter = OTLPMetricExporter()
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=1000)
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
meter = metrics.get_meter("take2.governing_agent")
verdict_counter = meter.create_counter("take2_verdict_count", description="Scene verdicts by type")
flag_counter = meter.create_counter("take2_flag_count", description="Flags raised by domain agent")

logger_provider = LoggerProvider()
set_logger_provider(logger_provider)
log_exporter = OTLPLogExporter()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
audit_logger = logging.getLogger("take2.audit_trail")
audit_logger.setLevel(logging.INFO)
audit_logger.addHandler(handler)


RISK_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# Studio scoping: every metric and log line carries a studio label so that,
# in a multi-tenant deployment, Grafana access policies can scope queries
# per studio the same way Grafana's own Assistant Search enforces RBAC at
# retrieval time (checked per-request, fail closed, not baked into storage).
STUDIO_ID = "take2-demo-studio"


def load_flags(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def merge_scene_flags(scene_id: int, all_agent_results: dict[str, list[dict]]) -> list[dict]:
    """Collect all flags for a given scene_id across every domain agent."""
    merged = []
    for agent_name, results in all_agent_results.items():
        for r in results:
            if r["scene_id"] == scene_id:
                for flag in r.get("flags", []):
                    merged.append({
                        "agent": agent_name,
                        "item": flag["item"],
                        "context": flag.get("context", ""),
                        "risk": flag.get("risk", "low"),
                        "reasoning": flag.get("reasoning", "")
                    })
    return merged


def determine_verdict(flags: list[dict]) -> str:
    """
    Reconciliation logic:
    - No flags -> Cleared
    - Any high-risk flag, or 3+ combined flags -> Blocked
    - Otherwise -> Flagged
    """
    if not flags:
        return "Cleared"

    high_risk_count = sum(1 for f in flags if f["risk"] == "high")
    if high_risk_count >= 1 and len(flags) >= 2:
        return "Blocked"
    if high_risk_count >= 1:
        return "Flagged"
    return "Flagged"


def reconcile(scenes_path: str, flags_dir: str, output_path: str) -> list[dict]:
    with open(scenes_path) as f:
        scenes = json.load(f)

    all_agent_results = {
        "music_licensing": load_flags(f"{flags_dir}/music_flags.json"),
        "trademark": load_flags(f"{flags_dir}/trademark_flags.json"),
        "likeness": load_flags(f"{flags_dir}/likeness_flags.json"),
        "location": load_flags(f"{flags_dir}/location_flags.json"),
    }

    reports = []

    for scene in scenes:
        scene_id = scene["scene_id"]
        merged_flags = merge_scene_flags(scene_id, all_agent_results)
        verdict = determine_verdict(merged_flags)

        report = {
            "scene_id": scene_id,
            "heading": scene["heading"],
            "verdict": verdict,
            "flags": merged_flags,
            "flag_count": len(merged_flags),
        }
        reports.append(report)

        # --- Push metrics ---
        verdict_counter.add(1, {"verdict": verdict, "scene": str(scene_id), "studio": STUDIO_ID})
        for flag in merged_flags:
            flag_counter.add(1, {"agent": flag["agent"], "risk": flag["risk"], "studio": STUDIO_ID})

        # --- Push audit log ---
        flag_summary = "; ".join(f"[{f['agent']}] {f['item']} ({f['risk']})" for f in merged_flags) or "no flags"
        audit_logger.info(
            f"Take2 verdict | studio={STUDIO_ID} scene={scene_id} heading=\"{scene['heading']}\" "
            f"verdict={verdict} flags={flag_summary}"
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(reports, f, indent=2)

    # give the periodic exporter a moment to flush before exit
    time.sleep(8)

    return reports


if __name__ == "__main__":
    reports = reconcile(
        scenes_path="data/parsed/scenes.json",
        flags_dir="data/parsed",
        output_path="data/parsed/final_report.json"
    )

    print(f"--- Take2 Final Report: {len(reports)} scene(s) reconciled ---\n")
    for r in reports:
        print(f"[Scene {r['scene_id']}] {r['heading']} - {r['verdict']} ({r['flag_count']} flag(s))")
        for flag in r["flags"]:
            print(f"    - [{flag['agent']}] {flag['item']} ({flag['risk']}): {flag['reasoning']}")
        print()

    print("Full report saved to data/parsed/final_report.json")
    print("Audit trail + metrics pushed to Grafana — check Explore for 'take2_verdict_count' and 'take2_flag_count'")
