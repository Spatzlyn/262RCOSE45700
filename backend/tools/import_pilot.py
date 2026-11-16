"""Import the model team's Pilot 6 handoff into backend/store as one Run.

Reads straight from the git ref (default origin/work/model-1115), so nothing is copied by hand:
  python -m backend.tools.import_pilot [--ref origin/work/model-1115]

Writes:
  store/items.jsonl                      model input only (no C / GT)
  store/references.jsonl                 explicit Missing records (GT not written yet)
  store/runs/<RUN_ID>/run.json           settings + versions
  store/runs/<RUN_ID>/requests.json      fixed request list
  store/runs/<RUN_ID>/predictions/<item>.json   raw model text, unmodified
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store"
RUN_ID = "RUN-PILOT6-BASE-001"
BASE = "docs/model/pilot_1115"


def git_show(ref, path, binary=False):
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout
    return out if binary else out.decode("utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/work/model-1115")
    args = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", args.ref], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    meta = json.loads(git_show(args.ref, f"{BASE}/run_metadata.json"))
    summary_rows = git_show(args.ref, f"{BASE}/run_summary.csv").lstrip("﻿").splitlines()
    header = summary_rows[0].split(",")
    summary = {r["item_id"]: r for r in (dict(zip(header, line.split(","))) for line in summary_rows[1:])}

    run_dir = STORE / "runs" / RUN_ID
    (run_dir / "predictions").mkdir(parents=True, exist_ok=True)
    items, refs, requests = [], [], []
    for m in meta:
        iid = m["item_id"]
        fname = summary[iid]["image_filename"]
        sub = {"CK": "K", "CV": "V"}[fname[:2]]
        audit = m["input_audit_record"]
        items.append({
            "item_id": iid, "data_kind": "real", "image_file": fname, "image_relpath": f"{sub}/{fname}",
            "image_sha256": m["input_image_sha256"],
            "image_size": {"width": audit["width"], "height": audit["height"]},
            "source_dataset": "aihub_71784", "source_group_id": None,
            "task": "track1_current_scene", "input_type": "single_image"})
        refs.append({"item_id": iid, "data_kind": "real", "annotation_status": "Missing",
                     "reference_version": None, "reason": "GT not written yet (2026-11-16)"})
        requests.append({"item_id": iid, "data_kind": "real"})
        raw = git_show(args.ref, f"{BASE}/backend_handoff/{iid}_raw.txt")
        decoded = git_show(args.ref, f"{BASE}/backend_handoff/{iid}_decoded.txt")
        assert hashlib.sha256(raw.encode()).hexdigest() == m["original_file_sha256"]["raw_output.txt"], iid
        rec = {"item_id": iid, "status": "ok" if m["status_record"]["status"] == "completed" else "error",
               "raw_text": raw, "output_text": decoded, "parsed": None,
               "parse_note": ("scorer parses output_text (decoded, special tokens skipped; raw_text ends with "
                              "the <turn|> end-of-turn token). model-team parsed_output kept only as hash"),
               "model_team_parsed_sha256": m["original_file_sha256"]["parsed_output.json"],
               "source_run_id": m["run_id"],
               "generation_seconds": m["validation_record"]["generation_seconds"],
               "generated_tokens": m["validation_record"]["generated_tokens"],
               "retry_count": m["status_record"]["retry_count"],
               "started_at_utc": m["status_record"]["started_at_utc"],
               "finished_at_utc": m["status_record"]["finished_at_utc"]}
        (run_dir / "predictions" / f"{iid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                                            encoding="utf-8")
    m0 = meta[0]
    run = {
        "run_id": RUN_ID, "data_kind": "real", "label": "Pilot 6 Base (NF4, prompt v1, first response)",
        "source_run_ids": [m["run_id"] for m in meta],
        "source": {"git_ref": args.ref, "commit": commit, "path": BASE},
        "model": {"model_id": m0["model_id"], "revision": m0["model_revision"], "quantization": m0["quantization"],
                  "dtype": m0["dtype"], "adapter_loaded": m0["adapter_loaded"], "base_name": m0["base_name"]},
        "prompt": {"system_prompt_sha256": m0["system_prompt_utf8_sha256"], "schema_sha256": m0["schema_sha256"],
                   "version": "prompt_v1"},
        "decoding": {**m0["generation"], "seed": m0["seed"], "image_max_soft_tokens": m0["image_max_soft_tokens"],
                     "enable_thinking": m0["enable_thinking"]},
        "environment": {"python": m0["python_version"], "packages": m0["packages"], "gpu": m0.get("gpu")},
        "data_version": {"items": "pilot6", "image_sha256": {m["item_id"]: m["input_image_sha256"] for m in meta}},
        "label_version": None, "split_version": None, "reference_version": None,
        "notes": "No GT exists yet: only V1/V2 are scored; every other metric is returned as N/A with a reason."}
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=1), encoding="utf-8")

    # merge into shared jsonl files, replacing older rows for the same item_id
    for name, rows in (("items.jsonl", items), ("references.jsonl", refs)):
        path = STORE / name
        old = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
        ids = {r["item_id"] for r in rows}
        write_jsonl(path, [r for r in old if r["item_id"] not in ids] + rows)
    print(f"imported {len(items)} items into {RUN_ID} from {args.ref}@{commit[:7]}")


if __name__ == "__main__":
    main()
