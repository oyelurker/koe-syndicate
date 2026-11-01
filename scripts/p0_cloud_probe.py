"""Verify that contained Cloud Run URLs reject anonymous requests."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import httpx

report_path = Path(__file__).resolve().parents[1] / "docs/p0-cloud-containment.json"
report = json.loads(report_path.read_text(encoding="utf-8-sig"))


def probe(service):
    response = httpx.get(service["url"] + "/health", timeout=20, follow_redirects=False)
    service["anonymousHealthStatus"] = response.status_code
    if response.status_code not in {401, 403, 404}:
        raise RuntimeError(f"Unexpected anonymous response from {service['service']}: {response.status_code}")
    print(service["service"], response.status_code, flush=True)
    return service


with ThreadPoolExecutor(max_workers=4) as pool:
    report["services"] = list(pool.map(probe, report["services"]))
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
