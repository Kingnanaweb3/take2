"""
Take2 - Clearance Control Room (demo web app)
Serves a branded dashboard that pulls live verdict/flag data from Grafana
Cloud via the datasource proxy, using a read-scoped service-account token.
"""

import os
import asyncio
import tempfile
import json
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

GRAFANA_BASE = "https://valiantbeaver2622.grafana.net"
PROM_UID = "grafanacloud-prom"
SA_TOKEN = os.environ["GRAFANA_SA_TOKEN"]
QUERY_URL = f"{GRAFANA_BASE}/api/datasources/proxy/uid/{PROM_UID}/api/v1/query"

app = FastAPI(title="Take2 Clearance Control Room")
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/templates")


def prom_query(promql: str) -> list[dict]:
    resp = requests.get(
        QUERY_URL,
        params={"query": promql},
        headers={"Authorization": f"Bearer {SA_TOKEN}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("result", [])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/stats")
async def stats():
    """Pull live verdict + flag data from Grafana, normalized for the UI."""
    try:
        # Verdicts — query raw, then normalize casing in Python
        verdict_raw = prom_query('sum by (verdict) (last_over_time(take2_verdict_count_total[7d]))')
        verdicts = {"Cleared": 0, "Flagged": 0, "Blocked": 0}
        for r in verdict_raw:
            v = r["metric"].get("verdict", "")
            v_norm = v.capitalize() if v.lower() == "cleared" else v
            if v_norm in verdicts:
                verdicts[v_norm] += int(float(r["value"][1]))

        # Flags by agent
        flag_raw = prom_query('sum by (agent) (last_over_time(take2_flag_count_total[7d:]))')
        flags = {}
        for r in flag_raw:
            agent = r["metric"].get("agent", "unknown")
            flags[agent] = int(float(r["value"][1]))

        total_scenes = sum(verdicts.values())
        total_flags = sum(flags.values())
        blocked_rate = round(100 * verdicts["Blocked"] / total_scenes) if total_scenes else 0
        avg_flags = round(total_flags / total_scenes, 1) if total_scenes else 0

        return JSONResponse({
            "verdicts": verdicts,
            "flags": flags,
            "total_scenes": total_scenes,
            "total_flags": total_flags,
            "blocked_rate": blocked_rate,
            "avg_flags": avg_flags,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/latest")
async def latest():
    """Return the full detail of the most recent pipeline run."""
    try:
        with open("data/parsed/final_report.json") as f:
            report = json.load(f)
        return JSONResponse({"scenes": report})
    except FileNotFoundError:
        return JSONResponse({"scenes": []})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/analyze")
async def analyze(request: Request):
    """Accept pasted script text, run the full pipeline, return the fresh result."""
    try:
        body = await request.json()
        script_text = body.get("script", "").strip()
        if not script_text:
            return JSONResponse({"error": "No script provided"}, status_code=400)

        # Write the pasted text to a temp .md file for the pipeline
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir="data/sample_scripts") as tf:
            tf.write(script_text)
            temp_path = tf.name

        # Import from the real source modules (pipeline.py imports these too)
        from agents.intake.intake_agent import run_intake
        from agents.governing.governing_agent import reconcile
        from pipeline import run_domain_agents_parallel, SCENES_PATH, FLAGS_DIR, FINAL_REPORT_PATH

        # Intake writes to SCENES_PATH; the parallel agents read that global path
        run_intake(temp_path, SCENES_PATH)
        await run_domain_agents_parallel()
        reports = reconcile(SCENES_PATH, FLAGS_DIR, FINAL_REPORT_PATH)

        return JSONResponse({"scenes": reports})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
