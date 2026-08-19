# Take2 — Clearance Control Room

**A multi-agent rights & clearance orchestrator for film and TV production.**

Take2 gives a script a second pass before it's locked. It scans each scene in parallel for legal clearance risks — real songs, real brands, real people's likenesses, and real locations — then a governing agent reconciles every finding into a single verdict per scene: **Cleared**, **Flagged**, or **Blocked**. Every decision is logged to Grafana, so the whole process is auditable, not a black box.

Built for the **Agentic Cinema: The Blockbuster Hackathon** (Google Cloud) — Grafana partner track.

---

## What it does

Rights clearance is a real, expensive bottleneck in production. A missed song, brand, or landmark can mean reshoots, legal disputes, or blocked distribution. Take2 automates the first-pass review:

1. **Intake Agent** — parses an uploaded script (via Docling) and splits it into scenes.
2. **Four domain agents run in parallel**, each scoped to one risk type:
   - **Music Licensing** — real songs, artists, bands
   - **Trademark & Brands** — real commercial brands and products
   - **Likeness & People** — real public figures whose image appears on-screen
   - **Location Clearance** — real named landmarks and locations needing permits
3. **Governing / Reconciliation Agent** — merges all findings per scene, assigns a verdict (Cleared / Flagged / Blocked), and pushes a full audit trail to Grafana.

Each flag carries the agent that raised it, a risk level, and plain-language reasoning (e.g. *"Blinding Lights by The Weeknd requires synchronization and master use licensing"*).

---

## Architecture Script → Intake Agent (Docling)
→ [ Music | Trademark | Likeness | Location ] (parallel, via asyncio.gather)
→ Governing Agent → verdict + audit trail
→ Grafana (OTLP: metrics + logs)
Take2 mirrors the same architectural pattern Grafana uses internally for its own AI Assistant: specialized agents per domain, reconciled by a governing layer, with full observability into every decision. The Location agent is deliberately domain-shaped — it cross-checks flagged landmarks against a curated reference list rather than relying on the model alone. Every metric and log carries a `studio` label, providing a real basis for multi-tenant access scoping via Grafana access policies (checked at retrieval, fail-closed) as the system scales to multiple studios.

---

## Tech stack

- **Google Cloud / Gemini** via the Agent Development Kit (ADK) — the reasoning engine for all agents
- **Docling** — open-source document parsing for scripts
- **Grafana Cloud** — observability layer (Prometheus metrics + Loki logs via OpenTelemetry/OTLP), plus a live "Clearance Control Room" dashboard
- **FastAPI** — the web app: serves the branded dashboard, queries Grafana live, and runs the pipeline on demand

---

## Running it locally

1. Clone the repo and create a virtual environment:
```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and fill in your Google and Grafana credentials.
3. Run the pipeline from the command line:
```bash
   python3 pipeline.py data/sample_scripts/sample.md
```
4. Or launch the web app:
```bash
   uvicorn webapp.main:app --port 8080
```
   Then open http://localhost:8080 to paste a script and analyze it live.

---

## License

MIT — see [LICENSE](LICENSE).
