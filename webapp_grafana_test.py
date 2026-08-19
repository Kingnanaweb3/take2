"""
Take2 - Grafana query client (standalone test)
Queries verdict/flag data via Grafana's datasource proxy, using the
service-account Bearer token (same auth path the dashboard uses internally).
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GRAFANA_BASE = "https://valiantbeaver2622.grafana.net"
PROM_UID = "grafanacloud-prom"
SA_TOKEN = os.environ["GRAFANA_SA_TOKEN"]

QUERY_URL = f"{GRAFANA_BASE}/api/datasources/proxy/uid/{PROM_UID}/api/v1/query"


def query(promql: str) -> dict:
    resp = requests.get(
        QUERY_URL,
        params={"query": promql},
        headers={"Authorization": f"Bearer {SA_TOKEN}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    print("--- Testing Grafana query API (via datasource proxy) ---\n")

    tests = {
        "Verdict counts": 'sum by (verdict) (last_over_time(take2_verdict_count_total[7d]))',
        "Flags by agent": 'sum by (agent) (last_over_time(take2_flag_count_total[7d]))',
        "Total scenes": 'sum(last_over_time(take2_verdict_count_total[7d]))',
    }

    for label, promql in tests.items():
        try:
            data = query(promql)
            results = data.get("data", {}).get("result", [])
            print(f"{label}:")
            if not results:
                print("  (no data returned)")
            for r in results:
                metric = r.get("metric", {})
                value = r.get("value", [None, None])[1]
                tag = metric.get("verdict") or metric.get("agent") or "total"
                print(f"  {tag}: {value}")
            print()
        except requests.HTTPError as e:
            print(f"  ERROR ({e.response.status_code}): {e.response.text[:200]}\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")


if __name__ == "__main__":
    main()
