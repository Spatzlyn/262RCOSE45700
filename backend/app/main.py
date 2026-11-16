"""Report API (FastAPI). Run: uvicorn backend.app.main:app --host 0.0.0.0 --port 8888

Endpoints this week (F3 -> F5):
  GET /api/health
  GET /api/runs                                   run list
  GET /api/runs/{run_id}                          run settings + versions
  GET /api/runs/{run_id}/items                    item list (filters: relation, fail_reason,
                                                  annotation_status, prediction_status, data_kind)
  GET /api/runs/{run_id}/items/{item_id}          item detail (input / prediction / reference / scoring)
  GET /api/runs/{run_id}/report                   summary metrics, N/A reasons, exclusions
  POST /api/runs/{run_id}/rescore                 re-score from stored files
  GET /api/images/{item_id}                       input image (viewer only)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app import store
from backend.scorer.score import SCORER_VERSION

API_VERSION = "0.1.0"
IMAGE_ROOT = Path(os.environ.get("IMAGE_ROOT", "/data/aihub_71784/images"))

app = FastAPI(title="Road VLM Benchmark Report API", version=API_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _run_or_404(run_id):
    meta = store.run_meta(run_id)
    if meta is None:
        raise HTTPException(404, f"unknown run_id {run_id}")
    return meta


def _versions(meta, res):
    return {"api": API_VERSION, "scorer": SCORER_VERSION, "scorer_commit": res["scorer_commit"],
            "model": meta.get("model"), "prompt": meta.get("prompt"), "data": meta.get("data_version"),
            "reference": res["reference_versions"], "result_hash": res["result_hash"]}


def _image_url(item):
    return f"/api/images/{item['item_id']}" if item and item.get("image_relpath") else None


@app.get("/api/health")
def health():
    return {"status": "ok", "api_version": API_VERSION, "scorer_version": SCORER_VERSION,
            "image_root_exists": IMAGE_ROOT.exists()}


@app.get("/api/runs")
def list_runs():
    rows = []
    for rid in store.run_ids():
        meta = store.run_meta(rid)
        res = store.result(rid)
        s = res["summary"]
        rows.append({"run_id": rid, "data_kind": meta.get("data_kind"), "label": meta.get("label"),
                     "model_id": (meta.get("model") or {}).get("model_id"), "n_requests": s["n_requests"],
                     "prediction_status_counts": s["prediction_status_counts"],
                     "n_scored_items": s["n_scored_items"], "excluded_items": s["excluded_items"],
                     "v1_valid": s["metrics"]["v1_valid"]["value"]})
    return {"runs": rows}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    return {"run": meta, "versions": _versions(meta, res)}


@app.get("/api/runs/{run_id}/items")
def list_items(run_id: str, relation: str | None = Query(None, pattern="^R[1-4]$"),
               fail_reason: str | None = None, annotation_status: str | None = None,
               prediction_status: str | None = None, data_kind: str | None = None):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    its = store.items()
    rows = []
    for r in res["items"]:
        if relation and r["relations"][relation]["match"] is not False:
            continue
        if fail_reason and fail_reason not in r["action_eval"].get("fail_reasons", []):
            continue
        if annotation_status and r["annotation_status"] != annotation_status:
            continue
        if prediction_status and r["prediction_status"] != prediction_status:
            continue
        if data_kind and r["data_kind"] != data_kind:
            continue
        ae = r["action_eval"]
        rows.append({"item_id": r["item_id"], "data_kind": r["data_kind"],
                     "prediction_status": r["prediction_status"], "annotation_status": r["annotation_status"],
                     "scored": r["scored"], "excluded_reason": r["excluded_reason"],
                     "relations": r["relations"],
                     "action_eval": {"pass": ae.get("pass"), "pass_status": ae.get("pass_status"),
                                     "fail_reasons": ae.get("fail_reasons", []),
                                     "excluded_reason": ae.get("excluded_reason")},
                     "image_url": _image_url(its.get(r["item_id"])),
                     "thumbnail_url": None})
    return {"run_id": run_id, "data_kind": meta.get("data_kind"), "versions": _versions(meta, res),
            "filters": {"relation": relation, "fail_reason": fail_reason, "annotation_status": annotation_status,
                        "prediction_status": prediction_status, "data_kind": data_kind},
            "n": len(rows), "items": rows}


@app.get("/api/runs/{run_id}/items/{item_id}")
def item_detail(run_id: str, item_id: str):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    row = next((r for r in res["items"] if r["item_id"] == item_id), None)
    if row is None:
        raise HTTPException(404, f"{item_id} is not in the request list of {run_id}")
    item = store.items().get(item_id)
    pred = store.predictions(run_id).get(item_id)
    from backend.scorer.score import check_format, load_schema
    fmt = check_format(item_id, pred, load_schema())
    return {
        "run_id": run_id, "item_id": item_id, "data_kind": row["data_kind"], "versions": _versions(meta, res),
        "run": {"run_id": run_id, "label": meta.get("label"), "model": meta.get("model"),
                "prompt": meta.get("prompt"), "decoding": meta.get("decoding")},
        # model input (what the model saw)
        "input": item, "image_url": _image_url(item), "image_size": (item or {}).get("image_size"),
        # raw model output, kept even when it failed
        "prediction": {"status": row["prediction_status"], "format_errors": row["format_errors"],
                       "raw_text": (pred or {}).get("raw_text"), "error": (pred or {}).get("error"),
                       "parsed": fmt["parsed"] if fmt["valid"] else None,
                       "meta": {k: v for k, v in (pred or {}).items()
                                if k not in ("raw_text", "output_text", "parsed")}},
                       "output_text": (pred or {}).get("output_text"),
        # GT and C: viewer only, never part of model input
        "reference": store.references().get(item_id) or {"item_id": item_id, "annotation_status": "Missing"},
        "scoring": {"scored": row["scored"], "excluded_reason": row["excluded_reason"],
                    "relations": row["relations"], "attributes": row.get("attributes"),
                    "action_eval": row["action_eval"], "diagnostics": row["diagnostics"],
                    "statement_review": {"status": "not_submitted",
                                         "reason": "V13/V14 come from human statement review only"}},
    }


@app.get("/api/runs/{run_id}/report")
def report(run_id: str):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    s = res["summary"]
    return {"run_id": run_id, "data_kind": meta.get("data_kind"), "versions": _versions(meta, res),
            "n_requests": s["n_requests"], "prediction_status_counts": s["prediction_status_counts"],
            "n_scored_items": s["n_scored_items"], "excluded": {"items": s["excluded_items"],
                                                                 "actions": s["excluded_from_actions"]},
            "metrics": s["metrics"], "comparison": s["comparison"]}


@app.post("/api/runs/{run_id}/rescore")
def rescore(run_id: str):
    _run_or_404(run_id)
    res = store.score(run_id)
    return {"run_id": run_id, "result_hash": res["result_hash"], "scorer_version": res["scorer_version"]}


@app.get("/api/images/{item_id}")
def image(item_id: str):
    item = store.items().get(item_id)
    if not item or not item.get("image_relpath"):
        raise HTTPException(404, "no image for this item")
    root = IMAGE_ROOT.resolve()
    for cand in (root / item["image_relpath"], root / item["image_file"]):
        p = cand.resolve()
        if p.is_relative_to(root) and p.is_file():
            return FileResponse(p, media_type="image/png")
    raise HTTPException(404, f"image file not found under IMAGE_ROOT ({item['image_file']})")
