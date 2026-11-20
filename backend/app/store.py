"""File-based storage. Layout (backend/store):

  items.jsonl              model input only (what the model may see)
  annotations.jsonl        scene attributes / evidence / review state (never sent to the model)
  references.jsonl         current GT per item (annotation_status: Reviewed | Draft | Missing)
  reference_history/<item>/<version>.json   every imported reference version (never overwritten)
  annotation_rounds.jsonl  two-annotator pre-consensus records (L1, L2)
  splits/<version>.json    split assignment; <version>.freeze.json = frozen Test manifest
  runs/<run_id>/run.json, requests.json, predictions/<item_id>.json   (raw outputs kept, incl. failures)
  runs/<run_id>/jobs.json  inference queue state (runs created through the API)
  runs/<run_id>/statement_reviews.jsonl   human statement reviews (V13, V14)
  results/, cache/         generated, never edited by hand
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from backend.scorer import stats
from backend.scorer.score import SCHEMA_PATH, SCORER_VERSION, aggregate, canonical_hash, score_run, load_schema
from backend.scorer.v11.contract import VERSION as V11
from backend.scorer.v11.adapter import SCORER_VERSION as SCORER_V11, aggregate_v11

STORE = Path(os.environ.get("BACKEND_STORE", Path(__file__).resolve().parents[1] / "store"))
BOOTSTRAP_B = int(os.environ.get("BOOTSTRAP_B", stats.DEFAULT_B))


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def items() -> dict:
    return {r["item_id"]: r for r in _jsonl(STORE / "items.jsonl")}


def reference_path(schema_version="1.0"):
    return STORE / ("references_v11.jsonl" if schema_version == V11 else "references.jsonl")


def references(schema_version="1.0") -> dict:
    return {r["item_id"]: r for r in _jsonl(reference_path(schema_version))}


def annotation_rounds() -> list[dict]:
    return _jsonl(STORE / "annotation_rounds.jsonl")


def run_ids() -> list[str]:
    d = STORE / "runs"
    return sorted(p.name for p in d.iterdir() if (p / "run.json").exists()) if d.exists() else []


def run_dir(run_id: str) -> Path:
    return STORE / "runs" / run_id


def run_meta(run_id: str) -> dict | None:
    p = run_dir(run_id) / "run.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def requests(run_id: str) -> list[dict]:
    return json.loads((run_dir(run_id) / "requests.json").read_text(encoding="utf-8"))


def predictions(run_id: str) -> dict:
    d = run_dir(run_id) / "predictions"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.json")} if d.exists() else {}


def statement_reviews(run_id: str) -> list[dict]:
    return _jsonl(run_dir(run_id) / "statement_reviews.jsonl")


def split_versions() -> list[str]:
    d = STORE / "splits"
    return sorted(p.stem for p in d.glob("*.json") if not p.name.endswith(".freeze.json")) if d.exists() else []


def split(version: str) -> dict | None:
    p = STORE / "splits" / f"{version}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_version(meta):
    return (meta or {}).get("schema_version", "1.0")


def schema_sha(schema_version="1.0") -> str:
    path = SCHEMA_PATH.parent / "v11" / "prediction.schema.json" if schema_version == V11 else SCHEMA_PATH
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scorer_commit() -> str:
    """Last commit that touched scorer/ or app/ (+dirty if they have local changes)."""
    env = os.environ.get("SCORER_COMMIT")
    if env:
        return env
    try:
        head = subprocess.run(["git", "log", "-1", "--format=%H", "--", "scorer", "app"], cwd=STORE.parent,
                              capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "scorer", "app"], cwd=STORE.parent,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def group_of(reqs) -> dict:
    its = items()
    return {q["item_id"]: its.get(q["item_id"], {}).get("source_group_id") for q in reqs}


def _input_fingerprint(run_id):
    reqs = requests(run_id)
    meta = run_meta(run_id)
    version = run_version(meta)
    refs = references(version)
    return {"scorer_version": SCORER_V11 if version == V11 else SCORER_VERSION,
            "schema_version": version, "schema_hash": schema_sha(version), "review_only": meta.get("status") == "review_only",
            "scorer_commit": scorer_commit(), "bootstrap_b": BOOTSTRAP_B,
            "reference_hash": canonical_hash({q["item_id"]: refs.get(q["item_id"]) for q in reqs}),
            "prediction_hash": canonical_hash(predictions(run_id)),
            "statement_review_hash": canonical_hash(statement_reviews(run_id)),
            "group_hash": canonical_hash(group_of(reqs))}


def score(run_id: str, write: bool = True) -> dict:
    """Re-score from stored predictions + references. Same inputs -> same result_hash."""
    reqs = requests(run_id)
    version = run_version(run_meta(run_id))
    refs = references(version)
    body = score_run(reqs, predictions(run_id), refs, schema=load_schema(version), group_of=group_of(reqs),
                     statement_reviews=statement_reviews(run_id), bootstrap_b=BOOTSTRAP_B)
    fp = _input_fingerprint(run_id)
    if fp["review_only"]:
        for r in body["items"]:
            r.update(scored=False, excluded_reason="inference_not_executed")
            for v in (*r["relations"].values(), *r.get("context", {}).values()):
                v.update(expected="Missing", match=None)
            r["action_eval"].update(**{"pass": None, "pass_status": "excluded", "excluded_reason": "inference_not_executed", "fail_reasons": [], "errors": []})
            r["diagnostics"] = {"grounding": None, "evidence": {}, "benchmark": {"eligible": False, "blockers": ["inference_not_executed"]}}
        previous_metrics = body["summary"]["metrics"]
        body["summary"] = aggregate_v11(body["items"], reqs)
        for k, v in previous_metrics.items():
            body["summary"]["metrics"].setdefault(k, v)
        mark_unexecuted(body["summary"]["metrics"])
        mark_unexecuted(body["summary"].get("context_metrics", {}))
        body["result_hash"] = canonical_hash({"items": body["items"], "summary": body["summary"]})
    body.update({"run_id": run_id, "scorer_commit": fp["scorer_commit"], "fingerprint": fp,
                 "reference_versions": sorted({str((refs.get(q["item_id"]) or {}).get("reference_version"))
                                               for q in reqs})})
    if write:
        write_json(STORE / "results" / f"{run_id}.json", body)
    return body


def mark_unexecuted(metrics):
    for m in metrics.values():
        m.update(status="not_computed", value=None, reason="review-only: inference not executed")
        # Retain the shape of the empty relation cells for display, but no scores or CI.
        for k in ("ci95", "ci_reason", "numerator", "n", "by_iou", "supported_class_macro_f1"):
            m.pop(k, None)


def result(run_id: str) -> dict:
    """Cached result if every input is unchanged, else re-score."""
    p = STORE / "results" / f"{run_id}.json"
    if p.exists():
        cached = json.loads(p.read_text(encoding="utf-8"))
        if cached.get("fingerprint") == _input_fingerprint(run_id):
            return cached
    return score(run_id)


def compare(base_id: str, target_id: str) -> dict:
    base_version = run_version(run_meta(base_id))
    target_version = run_version(run_meta(target_id))
    if base_version != target_version:
        return {"status": "not_applicable", "reason": "runs use different taxonomy/schema versions",
                "metrics": {}, "base_run_id": base_id, "target_run_id": target_id}
    if any(run_meta(r).get("status") == "review_only" for r in (base_id, target_id)):
        return {"status": "not_applicable", "reason": "review-only: inference not executed", "metrics": {},
                "base_run_id": base_id, "target_run_id": target_id}
    rb, rt = result(base_id), result(target_id)
    key = canonical_hash([rb["result_hash"], rt["result_hash"], BOOTSTRAP_B])
    p = STORE / "results" / f"compare__{base_id}__{target_id}.json"
    if p.exists():
        cached = json.loads(p.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return cached
    qb, qt = requests(base_id), requests(target_id)
    aggregator = aggregate_v11 if base_version == V11 else aggregate
    body = stats.paired_comparison(rb["items"], qb, rt["items"], qt, group_of(qb), aggregator, B=BOOTSTRAP_B)
    body.update({"key": key, "base_run_id": base_id, "target_run_id": target_id,
                 "base_result_hash": rb["result_hash"], "target_result_hash": rt["result_hash"]})
    write_json(p, body)
    return body
