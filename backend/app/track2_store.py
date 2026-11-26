"""Track 2 storage (separate from Track 1 so Track 1 run lists and scores are untouched).

store/track2/
  items.jsonl                  one row per (clip, decision time): video path, decision time, neutral candidates
  references.jsonl             current GT per item (Draft / Reviewed / Missing)
  reference_history/<item>/<version>.json
  runs/<run_id>/run.json, requests.json, predictions/<item_id>.json   {"select": {...}, "box": {...}, "input_record": {...}}
  frames/<item_id>.jpg, <item_id>_numbered.jpg   decision frame and candidate-numbered frame (not in git)
  results/                     generated
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app import store
from backend.scorer import track2
from backend.scorer.score import canonical_hash


def root() -> Path:
    return store.STORE / "track2"


def _jsonl(p: Path):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def write_jsonl(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def items() -> dict:
    return {r["item_id"]: r for r in _jsonl(root() / "items.jsonl")}


def references() -> dict:
    return {r["item_id"]: r for r in _jsonl(root() / "references.jsonl")}


def run_ids() -> list[str]:
    d = root() / "runs"
    return sorted(p.name for p in d.iterdir() if (p / "run.json").exists()) if d.exists() else []


def run_meta(run_id):
    p = root() / "runs" / run_id / "run.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def requests(run_id):
    return json.loads((root() / "runs" / run_id / "requests.json").read_text(encoding="utf-8"))


def predictions(run_id):
    d = root() / "runs" / run_id / "predictions"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.json")} if d.exists() else {}


def _fingerprint(run_id):
    reqs = requests(run_id)
    refs, its = references(), items()
    return {"scorer_version": track2.SCORER_VERSION, "scorer_commit": store.scorer_commit(),
            "items_hash": canonical_hash({q["item_id"]: its.get(q["item_id"]) for q in reqs}),
            "reference_hash": canonical_hash({q["item_id"]: refs.get(q["item_id"]) for q in reqs}),
            "prediction_hash": canonical_hash(predictions(run_id)), "bootstrap_b": track2.BOOT_B}


def score(run_id, write=True):
    reqs = requests(run_id)
    refs = references()
    body = track2.score_run(reqs, items(), refs, predictions(run_id))
    fp = _fingerprint(run_id)
    body.update({"run_id": run_id, "scorer_commit": fp["scorer_commit"], "fingerprint": fp,
                 "reference_versions": sorted({str((refs.get(q["item_id"]) or {}).get("reference_version"))
                                               for q in reqs})})
    if write:
        store.write_json(root() / "results" / f"{run_id}.json", body)
    return body


def result(run_id):
    p = root() / "results" / f"{run_id}.json"
    if p.exists():
        cached = json.loads(p.read_text(encoding="utf-8"))
        if cached.get("fingerprint") == _fingerprint(run_id):
            return cached
    return score(run_id)
