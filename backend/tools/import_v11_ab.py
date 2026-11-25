"""Register the model team's v1.1 Pilot A/B handoff as two real Runs (first responses, unmodified).

  python -m backend.tools.import_v11_ab [--ref 8e0a62838d0df742dd146c122c86eeb9582c34e3]

Source: <ref>:docs/model/v11_ab_handoff/ (실행기록.json + {A,B}/pilot_00x/{raw_output,decoded_output,status,
output_validation}). Every file is checked against the sha256 in 실행기록.json before import.
The scorer parses decoded_output.txt (the model team's actual parser input) as is: no fence stripping,
so the first-response invalid_output state is kept (handoff request).
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from backend.app import store

ROOT = Path(__file__).resolve().parents[2]
BASE = "docs/model/v11_ab_handoff"
DEFAULT_REF = "8e0a62838d0df742dd146c122c86eeb9582c34e3"
ARMS = {"A": "prompt_v11_a", "B": "prompt_v11_b"}


def show(ref, path) -> bytes:
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=DEFAULT_REF)
    args = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", args.ref], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    record = json.loads(show(args.ref, f"{BASE}/실행기록.json").decode("utf-8"))
    by_run = {}
    for r in record["records"]:
        by_run.setdefault(r["run_id"], []).append(r)
    items = store.items()
    for run_id, rows in by_run.items():
        arm = rows[0]["arm"]
        pv = ARMS[arm]
        prompt_meta = json.loads((ROOT / "backend/worker/prompts" / pv / "prompt.json").read_text(encoding="utf-8"))
        cfg0 = rows[0]["config"]
        if cfg0["system_prompt_utf8_sha256"] != prompt_meta["system_sha256"]:
            raise SystemExit(f"{run_id}: system prompt hash differs from backend {pv}")
        rd = store.run_dir(run_id)
        (rd / "predictions").mkdir(parents=True, exist_ok=True)
        reqs = []
        for r in sorted(rows, key=lambda x: x["item_id"]):
            iid = r["item_id"]
            folder = f"{BASE}/{arm}/{iid}"
            files = {name: show(args.ref, f"{folder}/{name}") for name in r["files_sha256"]}
            for name, data in files.items():
                if hashlib.sha256(data).hexdigest() != r["files_sha256"][name]:
                    raise SystemExit(f"{run_id}/{iid}/{name}: sha256 mismatch")
            if r["config"]["input_image_sha256"] != items[iid]["image_sha256"]:
                raise SystemExit(f"{iid}: image hash differs from item catalog")
            status = json.loads(files["status.json"])
            val = json.loads(files["output_validation.json"])
            rec = {"item_id": iid,
                   # generation finished; validity is decided by the scorer from output_text
                   "status": "ok" if status.get("phase") == "finished" else "error",
                   "raw_text": files["raw_output.txt"].decode("utf-8"),
                   "output_text": files["decoded_output.txt"].decode("utf-8"),
                   "parsed": None,
                   "parse_note": "decoded_output.txt = model team's parser input, used unchanged (no fence stripping)",
                   "model_team_status": status.get("status"), "model_team_parse_error": val.get("parse_error"),
                   "generation_seconds": val.get("generation_seconds"), "generated_tokens": val.get("generated_tokens"),
                   "retry_count": status.get("retry_count"), "format_repair": val.get("format_repair"),
                   "started_at_utc": status.get("started_at_utc"), "finished_at_utc": status.get("finished_at_utc"),
                   "source_files_sha256": r["files_sha256"]}
            store.write_json(rd / "predictions" / f"{iid}.json", rec)
            reqs.append({"item_id": iid, "data_kind": "real"})
        run = {"run_id": run_id, "data_kind": "real", "schema_version": "1.1-review", "status": "imported",
               "label": f"v1.1 Pilot 6 · prompt {arm} · first response (model team, RTX 4070 laptop)",
               "source": {"git_ref": commit, "path": BASE, "record_source_commit": record.get("source_commit")},
               "model": {"model_id": cfg0["base_config"]["model_id"], "revision": cfg0["model_revision"],
                         "quantization": "nf4", "adapter": None},
               "prompt": {"version": pv, "schema_version": "1.1-review",
                          "system_sha256": cfg0["system_prompt_utf8_sha256"], "task_sha256": prompt_meta["task_sha256"],
                          "schema_sha256": cfg0["schema_sha256"]},
               "decoding": {**cfg0["generation"], "seed": cfg0["seed"],
                            "image_max_soft_tokens": cfg0["image_max_soft_tokens"],
                            "enable_thinking": cfg0["enable_thinking"]},
               "environment": {"python": cfg0["python"], "platform": cfg0["platform"], "gpu": cfg0.get("gpu"),
                               "packages": cfg0.get("packages"), "script_sha256": cfg0["script_sha256"]},
               "data_version": {"items": "pilot6-v11",
                                "image_sha256": {r["item_id"]: r["config"]["input_image_sha256"] for r in rows}},
               "split_version": "v11-pilot-dev"}
        store.write_json(rd / "run.json", run)
        store.write_json(rd / "requests.json", reqs)
        print(f"imported {run_id} ({arm}, {len(reqs)} items) from {commit[:7]}")


if __name__ == "__main__":
    main()
