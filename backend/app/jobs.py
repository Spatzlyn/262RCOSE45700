"""Inference queue: fixed request list per Run, one GPU worker pulls jobs.

States per request: queued -> running -> done | failed | timeout | cancelled.
Every request ends with a prediction file, including failures (spec §3): nothing disappears.
The first response is kept; a second result for the same request is rejected.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app import store

LOCK = threading.Lock()
PROMPTS = Path(__file__).resolve().parents[1] / "worker" / "prompts"
DEFAULT_MODEL = {"model_id": "google/gemma-4-E4B-it", "revision": "4ecc2ba63bcac23ba4a767fc87025b1450f84c9c",
                 "quantization": "nf4", "adapter": None}
DEFAULT_DECODING = {"max_new_tokens": 4096, "do_sample": False, "seed": 42, "image_max_soft_tokens": 280,
                    "enable_thinking": False}
FINAL = {"done", "failed", "timeout", "cancelled"}


def now():
    return datetime.now(timezone.utc)


def iso(t):
    return t.isoformat(timespec="seconds")


def prompt_versions() -> list[str]:
    return sorted(p.name for p in PROMPTS.iterdir() if (p / "prompt.json").exists()) if PROMPTS.exists() else []


def _jobs_path(run_id):
    return store.run_dir(run_id) / "jobs.json"


def _load(run_id):
    p = _jobs_path(run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def create_run(spec: dict) -> dict:
    its = store.items()
    ids = spec.get("item_ids") or []
    errors = []
    if not ids:
        errors.append("item_ids is empty")
    if len(set(ids)) != len(ids):
        errors.append("item_ids has duplicates")
    for i in ids:
        if i not in its:
            errors.append(f"unknown item_id {i}")
        elif not its[i].get("image_relpath"):
            errors.append(f"{i} has no input image")
    pv = spec.get("prompt_version", "prompt_v1")
    if pv not in prompt_versions():
        errors.append(f"unknown prompt_version {pv}; available {prompt_versions()}")
    model = {**DEFAULT_MODEL, **(spec.get("model") or {})}
    if model["quantization"] not in ("nf4", "bf16"):
        errors.append("model.quantization must be nf4 or bf16")
    if errors:
        return {"created": False, "errors": errors}
    run_id = spec.get("run_id") or f"RUN-{now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    with LOCK:
        if store.run_meta(run_id):
            return {"created": False, "errors": [f"run_id {run_id} already exists"]}
        prompt_meta = json.loads((PROMPTS / pv / "prompt.json").read_text(encoding="utf-8"))
        run = {"run_id": run_id, "data_kind": "real", "label": spec.get("label") or run_id,
               "created_at": iso(now()), "created_via": "api", "status": "queued",
               "model": model, "prompt": {"version": pv, **prompt_meta},
               "decoding": {**DEFAULT_DECODING, **(spec.get("decoding") or {})},
               "timeout_s": int(spec.get("timeout_s", 900)),
               "data_version": {"image_sha256": {i: its[i].get("image_sha256") for i in ids}},
               "reference_version": None, "worker_environment": None}
        store.write_json(store.run_dir(run_id) / "run.json", run)
        store.write_json(store.run_dir(run_id) / "requests.json", [{"item_id": i, "data_kind": "real"} for i in ids])
        store.write_json(_jobs_path(run_id), {i: {"state": "queued", "attempts": 0, "lease_until": None,
                                                 "worker": None, "updated_at": iso(now())} for i in ids})
    return {"created": True, "run_id": run_id, "n_requests": len(ids)}


def _finish_prediction(run_id, item_id, record):
    p = store.run_dir(run_id) / "predictions" / f"{item_id}.json"
    if p.exists():
        return False
    store.write_json(p, {"item_id": item_id, **record})
    return True


def _expire(run_id, jobs, t):
    run = store.run_meta(run_id)
    for iid, j in jobs.items():
        if j["state"] == "running" and j["lease_until"] and datetime.fromisoformat(j["lease_until"]) < t:
            _finish_prediction(run_id, iid, {"status": "timeout", "raw_text": None, "parsed": None,
                                             "error": f"worker lease expired (timeout_s={run['timeout_s']})"})
            j.update(state="timeout", updated_at=iso(t))


def _refresh_status(run_id, jobs):
    run = store.run_meta(run_id)
    states = [j["state"] for j in jobs.values()]
    if run["status"] != "cancelled":
        run["status"] = ("done" if all(s in FINAL for s in states)
                         else "running" if any(s in ("running",) or s in FINAL for s in states) else "queued")
        store.write_json(store.run_dir(run_id) / "run.json", run)


def progress(run_id: str) -> dict | None:
    jobs = _load(run_id)
    run = store.run_meta(run_id)
    if run is None:
        return None
    if jobs is None:  # imported run: everything already final
        preds = store.predictions(run_id)
        counts = {"done": len(preds)}
        return {"run_id": run_id, "status": "imported", "counts": counts, "n_requests": len(store.requests(run_id))}
    with LOCK:
        _expire(run_id, jobs, now())
        store.write_json(_jobs_path(run_id), jobs)
        _refresh_status(run_id, jobs)
    counts = {}
    for j in jobs.values():
        counts[j["state"]] = counts.get(j["state"], 0) + 1
    run = store.run_meta(run_id)
    return {"run_id": run_id, "status": run["status"], "n_requests": len(jobs), "counts": counts,
            "provisional": run["status"] != "done",
            "note": "requests without a final prediction are scored as not_returned until they finish"}


def cancel(run_id: str) -> dict | None:
    jobs = _load(run_id)
    if jobs is None:
        return None
    with LOCK:
        n = 0
        for iid, j in jobs.items():
            if j["state"] == "queued":
                _finish_prediction(run_id, iid, {"status": "cancelled", "raw_text": None, "parsed": None,
                                                 "error": "cancelled before inference"})
                j.update(state="cancelled", updated_at=iso(now()))
                n += 1
        store.write_json(_jobs_path(run_id), jobs)
        run = store.run_meta(run_id)
        run["status"] = "cancelled"
        store.write_json(store.run_dir(run_id) / "run.json", run)
    return {"run_id": run_id, "cancelled": n, "note": "running requests finish normally"}


def next_job(worker: str) -> dict | None:
    t = now()
    with LOCK:
        runs = [store.run_meta(r) for r in store.run_ids()]
        runs = sorted((r for r in runs if r and r.get("status") in ("queued", "running")),
                      key=lambda r: r["created_at"])
        its = store.items()
        for run in runs:
            jobs = _load(run["run_id"])
            if jobs is None:
                continue
            _expire(run["run_id"], jobs, t)
            for q in store.requests(run["run_id"]):
                j = jobs[q["item_id"]]
                if j["state"] != "queued":
                    continue
                j.update(state="running", attempts=j["attempts"] + 1, worker=worker, updated_at=iso(t),
                         lease_until=iso(t + timedelta(seconds=run["timeout_s"] + 300)))
                store.write_json(_jobs_path(run["run_id"]), jobs)
                _refresh_status(run["run_id"], jobs)
                return {"run_id": run["run_id"], "item_id": q["item_id"], "input": its[q["item_id"]],
                        "model": run["model"], "prompt": run["prompt"], "decoding": run["decoding"],
                        "timeout_s": run["timeout_s"], "lease_until": j["lease_until"]}
            store.write_json(_jobs_path(run["run_id"]), jobs)
            _refresh_status(run["run_id"], jobs)
    return None


def submit(run_id: str, item_id: str, worker: str, body: dict) -> tuple[int, dict]:
    status = body.get("status")
    if status not in ("ok", "timeout", "error"):
        return 422, {"error": "status must be ok, timeout or error"}
    with LOCK:
        jobs = _load(run_id)
        if jobs is None or item_id not in jobs:
            return 404, {"error": "unknown run/item"}
        j = jobs[item_id]
        if j["state"] != "running" or j["worker"] != worker:
            return 409, {"error": f"job is {j['state']} (worker {j['worker']}); first response is kept"}
        rec = {k: body.get(k) for k in ("status", "raw_text", "output_text", "error", "generation_seconds",
                                        "generated_tokens", "input_audit", "started_at_utc", "finished_at_utc")}
        rec.update({"parsed": None, "worker": worker})
        if not _finish_prediction(run_id, item_id, rec):
            return 409, {"error": "prediction already stored; first response is kept"}
        j.update(state={"ok": "done", "timeout": "timeout", "error": "failed"}[status], updated_at=iso(now()),
                 lease_until=None)
        store.write_json(_jobs_path(run_id), jobs)
        run = store.run_meta(run_id)
        if body.get("environment") and not run.get("worker_environment"):
            run["worker_environment"] = body["environment"]
            store.write_json(store.run_dir(run_id) / "run.json", run)
        _refresh_status(run_id, jobs)
    return 200, {"run_id": run_id, "item_id": item_id, "state": j["state"]}
