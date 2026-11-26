"""Register a model-team Track 1 v1.1 handoff folder (채점_목록.csv + runs/*.json + <arm>/<item>/...) as one Run.

  python -m backend.tools.import_track1_handoff --ref origin/work/model-ab-1123 \
      --base "ai_model/track1/파일럿_6건_채점_인계_20261125" --run-id v11_a_rev6_pilot6

Checks: raw_output.txt sha256 = 채점_목록.csv, decoded_output.txt JSON == parsed_output.json, image hash = catalog,
all source runs share one prompt version / prompt hashes / model revision. The scorer reads decoded_output.txt
as is (first response, no repair). Each item keeps its source run id.
"""
import argparse
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

from backend.app import store

ROOT = Path(__file__).resolve().parents[2]


def show(ref, path) -> bytes:
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout


def ls(ref, path):
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-tree", "--name-only", f"{ref}:{path}"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [x for x in out.splitlines() if x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", a.ref], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    rows = list(csv.DictReader(io.StringIO(show(a.ref, f"{a.base}/채점_목록.csv").decode("utf-8-sig"))))
    srcs = {name: json.loads(show(a.ref, f"{a.base}/runs/{name}/run.json")) for name in ls(a.ref, f"{a.base}/runs")}
    keys = {(s["version"], s["system_sha256"], s["task_sha256"], s["model_revision"], s["schema_version"])
            for s in srcs.values()}
    if len(keys) != 1:
        raise SystemExit(f"source runs disagree on prompt/model: {keys}")
    version, sys_sha, task_sha, revision, schema = keys.pop()
    items = store.items()
    rd = store.run_dir(a.run_id)
    if (rd / "run.json").exists():
        raise SystemExit(f"{a.run_id} already exists")
    reqs = []
    for r in sorted(rows, key=lambda x: x["item_id"]):
        iid = r["item_id"]
        folder = f"{a.base}/{Path(r['prediction_path']).parent.as_posix()}"
        raw, dec = show(a.ref, f"{folder}/raw_output.txt"), show(a.ref, f"{folder}/decoded_output.txt")
        parsed = json.loads(show(a.ref, f"{folder}/parsed_output.json"))
        status = json.loads(show(a.ref, f"{folder}/status.json"))
        val = json.loads(show(a.ref, f"{folder}/output_validation.json"))
        if hashlib.sha256(raw).hexdigest() != r["raw_output_sha256"]:
            raise SystemExit(f"{iid}: raw_output sha256 mismatch")
        try:
            same = json.loads(dec.decode("utf-8")) == parsed
        except json.JSONDecodeError:
            same = False
        src = r["source_run_id"]
        if iid not in srcs[src]["items"]:
            raise SystemExit(f"{iid}: not listed in source run {src}")
        rec = {"item_id": iid, "status": "ok", "raw_text": raw.decode("utf-8"), "output_text": dec.decode("utf-8"),
               "parsed": None, "parse_note": "decoded_output.txt used unchanged (first response)",
               "decoded_equals_parsed_output_json": same, "source_run_id": src,
               "model_team_status": status.get("status"), "model_team_validation": val,
               "generation_seconds": float(r["generation_seconds"]), "generated_tokens": int(r["generated_tokens"]),
               "retry_count": status.get("retry_count"), "finished_at_utc": r["finished_at_utc"],
               "raw_output_sha256": r["raw_output_sha256"]}
        store.write_json(rd / "predictions" / f"{iid}.json", rec)
        reqs.append({"item_id": iid, "data_kind": "real"})
    run = {"run_id": a.run_id, "data_kind": "real", "schema_version": schema, "status": "imported",
           "label": a.label or f"v1.1 Pilot 6 · {version} · first response",
           "source": {"git_ref": commit, "path": a.base, "source_run_ids": sorted(srcs)},
           "model": {"model_id": "google/gemma-4-E4B-it", "revision": revision, "quantization": "nf4", "adapter": None},
           "prompt": {"version": version, "schema_version": schema, "system_sha256": sys_sha, "task_sha256": task_sha,
                      "parent": next(iter(srcs.values())).get("parent")},
           "decoding": {"max_new_tokens": 4096, "do_sample": False, "seed": 42, "image_max_soft_tokens": 280,
                        "enable_thinking": False},
           "data_version": {"items": "pilot6-v11", "image_sha256": {q["item_id"]: items[q["item_id"]]["image_sha256"]
                                                                   for q in reqs}},
           "split_version": "v11-pilot-dev"}
    store.write_json(rd / "run.json", run)
    store.write_json(rd / "requests.json", reqs)
    print(json.dumps({"ok": True, "run_id": a.run_id, "n": len(reqs), "prompt": version, "source_runs": sorted(srcs),
                      "commit": commit[:7]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
