"""File-based storage. Layout (backend/store):

  items.jsonl        model input only (what the model may see)
  annotations.jsonl  scene attributes / evidence / review state (never sent to the model)
  references.jsonl   reviewed GT per item (annotation_status: Reviewed | Draft | Missing)
  runs/<run_id>/run.json, requests.json, predictions/<item_id>.json   (raw outputs kept, incl. failures)
  results/<run_id>.json   scorer output (regenerated, never edited by hand)
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from backend.scorer.score import SCORER_VERSION, canonical_hash, score_run

STORE = Path(os.environ.get("BACKEND_STORE", Path(__file__).resolve().parents[1] / "store"))


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def items() -> dict:
    return {r["item_id"]: r for r in _jsonl(STORE / "items.jsonl")}


def references() -> dict:
    return {r["item_id"]: r for r in _jsonl(STORE / "references.jsonl")}


def run_ids() -> list[str]:
    d = STORE / "runs"
    return sorted(p.name for p in d.iterdir() if (p / "run.json").exists()) if d.exists() else []


def run_meta(run_id: str) -> dict | None:
    p = STORE / "runs" / run_id / "run.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def requests(run_id: str) -> list[dict]:
    return json.loads((STORE / "runs" / run_id / "requests.json").read_text(encoding="utf-8"))


def predictions(run_id: str) -> dict:
    d = STORE / "runs" / run_id / "predictions"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.json")} if d.exists() else {}


def scorer_commit() -> str:
    env = os.environ.get("SCORER_COMMIT")
    if env:
        return env
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=STORE.parent, capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "scorer", "app"], cwd=STORE.parent,
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def score(run_id: str, write: bool = True) -> dict:
    """Re-score from stored predictions + references. Same inputs -> same result_hash."""
    reqs = requests(run_id)
    refs = references()
    body = score_run(reqs, predictions(run_id), refs)
    used_refs = {q["item_id"]: refs.get(q["item_id"]) for q in reqs}
    body.update({"run_id": run_id, "scorer_commit": scorer_commit(),
                 "reference_hash": canonical_hash(used_refs),
                 "prediction_hash": canonical_hash(predictions(run_id)),
                 "reference_versions": sorted({str((r or {}).get("reference_version")) for r in used_refs.values()})})
    if write:
        out = STORE / "results"
        out.mkdir(exist_ok=True)
        (out / f"{run_id}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    return body


def result(run_id: str) -> dict:
    """Cached result if present and inputs unchanged, else re-score."""
    p = STORE / "results" / f"{run_id}.json"
    if p.exists():
        cached = json.loads(p.read_text(encoding="utf-8"))
        reqs = requests(run_id)
        refs = references()
        if (cached.get("scorer_version") == SCORER_VERSION and cached.get("scorer_commit") == scorer_commit()
                and cached.get("reference_hash") == canonical_hash({q["item_id"]: refs.get(q["item_id"]) for q in reqs})
                and cached.get("prediction_hash") == canonical_hash(predictions(run_id))):
            return cached
    return score(run_id)
