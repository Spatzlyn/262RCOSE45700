"""Save API responses as JSON files for the frontend (python -m backend.tools.dump_examples).

examples/example_run/  synthetic EXAMPLE-RUN-001 (normal / format error / timeout / Draft / conflict)
examples/real_pilot/   real RUN-PILOT6-BASE-001 (model output is real; no GT yet)
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

OUT = Path(__file__).resolve().parents[1] / "examples"
CALLS = {
    "example_run": [("runs", "/api/runs"),
                    ("report", "/api/runs/EXAMPLE-RUN-001/report"),
                    ("items", "/api/runs/EXAMPLE-RUN-001/items"),
                    ("item_valid_action_fail", "/api/runs/EXAMPLE-RUN-001/items/example_001"),
                    ("item_format_error", "/api/runs/EXAMPLE-RUN-001/items/example_002"),
                    ("item_timeout", "/api/runs/EXAMPLE-RUN-001/items/example_003"),
                    ("item_draft_reference", "/api/runs/EXAMPLE-RUN-001/items/example_004"),
                    ("item_direction_conflict", "/api/runs/EXAMPLE-RUN-001/items/example_005"),
                    ("report_with_base", "/api/runs/EXAMPLE-RUN-001/report?base=EXAMPLE-RUN-001"),
                    ("versions", "/api/versions"), ("quality", "/api/quality"), ("catalog", "/api/items")],
    "real_pilot": [("run", "/api/runs/RUN-PILOT6-BASE-001"),
                   ("report", "/api/runs/RUN-PILOT6-BASE-001/report"),
                   ("items", "/api/runs/RUN-PILOT6-BASE-001/items"),
                   ("item_pilot_001", "/api/runs/RUN-PILOT6-BASE-001/items/pilot_001"),
                   ("progress", "/api/runs/RUN-PILOT6-BASE-001/progress"),
                   ("conditions_weather", "/api/runs/RUN-PILOT6-BASE-001/report/conditions?key=weather")],
}


def main():
    c = TestClient(app)
    for folder, calls in CALLS.items():
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        for name, url in calls:
            r = c.get(url)
            r.raise_for_status()
            body = {"_request": f"GET {url}", "_note": "synthetic example" if folder == "example_run"
                    else "real model output; GT not written, so GT-based metrics are N/A", **r.json()}
            (OUT / folder / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    print("wrote", sum(len(v) for v in CALLS.values()), "files under", OUT)


if __name__ == "__main__":
    main()
