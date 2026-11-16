"""Report API (FastAPI). Run: uvicorn backend.app.main:app --host 0.0.0.0 --port 8888

Read (no auth)
  GET  /api/health, /api/versions
  GET  /api/items, /api/items/{item_id}
  GET  /api/runs, /api/runs/{run_id}, /api/runs/{run_id}/progress
  GET  /api/runs/{run_id}/items, /api/runs/{run_id}/items/{item_id}
  GET  /api/runs/{run_id}/report[?base=<run_id>], /api/runs/{run_id}/report/conditions?key=
  GET  /api/compare?base=&target=
  GET  /api/runs/{run_id}/export?format=json|csv
  GET  /api/quality, /api/datasets, /api/datasets/{version}/leak-check
  GET  /api/images/{item_id}[?size=thumb]
Write (header X-API-Key = API_WRITE_KEY)
  POST /api/runs, /api/runs/{run_id}/cancel, /api/runs/{run_id}/rescore
  POST /api/runs/{run_id}/statement-reviews, /api/datasets/{version}/freeze
Worker (header X-API-Key = WORKER_KEY)
  GET  /api/jobs/next?worker=, POST /api/jobs/{run_id}/{item_id}/result?worker=
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.app import jobs, store
from backend.scorer import quality
from backend.scorer.score import SCORER_VERSION, aggregate, check_format, load_schema

API_VERSION = "0.2.0"
IMAGE_ROOT = Path(os.environ.get("IMAGE_ROOT", "/data/aihub_71784/images"))
SMALL_N = 30  # condition subsets below this are marked exploratory

app = FastAPI(title="Road VLM Benchmark Report API", version=API_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


# ----------------------------------------------------------------------------- auth

def _check(env_name: str, given: str | None):
    expected = os.environ.get(env_name)
    if not expected:
        raise HTTPException(503, f"write API disabled: {env_name} is not set on the server")
    if not given or not secrets.compare_digest(given, expected):
        raise HTTPException(401, "invalid or missing X-API-Key")


def write_auth(x_api_key: str | None = Header(None)):
    _check("API_WRITE_KEY", x_api_key)


def worker_auth(x_api_key: str | None = Header(None)):
    _check("WORKER_KEY", x_api_key)


# ----------------------------------------------------------------------------- helpers

def _run_or_404(run_id):
    meta = store.run_meta(run_id)
    if meta is None:
        raise HTTPException(404, f"unknown run_id {run_id}")
    return meta


def _versions(meta, res):
    return {"api": API_VERSION, "scorer": SCORER_VERSION, "scorer_commit": res["scorer_commit"],
            "schema_sha256": store.schema_sha(), "model": meta.get("model"), "prompt": meta.get("prompt"),
            "data": meta.get("data_version"), "reference": res["reference_versions"],
            "result_hash": res["result_hash"], "bootstrap": res.get("bootstrap")}


def _image_url(item):
    return f"/api/images/{item['item_id']}" if item and item.get("image_relpath") else None


def _thumb_url(item):
    return f"/api/images/{item['item_id']}?size=thumb" if item and item.get("image_relpath") else None


def _run_status(run_id, meta):
    p = jobs.progress(run_id)
    return {"status": (p or {}).get("status", meta.get("status")), "provisional": (p or {}).get("provisional", False)}


# ----------------------------------------------------------------------------- basics

@app.get("/api/health")
def health():
    return {"status": "ok", "api_version": API_VERSION, "scorer_version": SCORER_VERSION,
            "image_root_exists": IMAGE_ROOT.exists(), "write_api_enabled": bool(os.environ.get("API_WRITE_KEY")),
            "worker_api_enabled": bool(os.environ.get("WORKER_KEY"))}


@app.get("/api/versions")
def versions():
    refs = store.references()
    return {"api": API_VERSION, "scorer": SCORER_VERSION, "scorer_commit": store.scorer_commit(),
            "schema_sha256": store.schema_sha(), "prompt_versions": jobs.prompt_versions(),
            "reference_versions": sorted({str(r.get("reference_version")) for r in refs.values()}),
            "reference_status_counts": _count(r.get("annotation_status", "Missing") for r in refs.values()),
            "split_versions": store.split_versions(), "bootstrap_b": store.BOOTSTRAP_B}


def _count(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


@app.get("/api/items")
def list_catalog(data_kind: str | None = None):
    refs = store.references()
    rows = [{**it, "annotation_status": (refs.get(i) or {}).get("annotation_status", "Missing"),
             "image_url": _image_url(it), "thumbnail_url": _thumb_url(it)}
            for i, it in store.items().items() if not data_kind or it.get("data_kind") == data_kind]
    return {"n": len(rows), "items": rows}


@app.get("/api/items/{item_id}")
def catalog_item(item_id: str):
    it = store.items().get(item_id)
    if it is None:
        raise HTTPException(404, f"unknown item_id {item_id}")
    ref = store.references().get(item_id) or {}
    return {"input": it, "image_url": _image_url(it), "thumbnail_url": _thumb_url(it),
            "annotation_status": ref.get("annotation_status", "Missing"),
            "reference_version": ref.get("reference_version"),
            "runs": [r for r in store.run_ids() if any(q["item_id"] == item_id for q in store.requests(r))]}


# ----------------------------------------------------------------------------- runs (read)

@app.get("/api/runs")
def list_runs():
    rows = []
    for rid in store.run_ids():
        meta = store.run_meta(rid)
        res = store.result(rid)
        s = res["summary"]
        rows.append({"run_id": rid, "data_kind": meta.get("data_kind"), "label": meta.get("label"),
                     "model_id": (meta.get("model") or {}).get("model_id"), **_run_status(rid, meta),
                     "n_requests": s["n_requests"], "prediction_status_counts": s["prediction_status_counts"],
                     "n_scored_items": s["n_scored_items"], "excluded_items": s["excluded_items"],
                     "v1_valid": s["metrics"]["v1_valid"]["value"]})
    return {"runs": rows}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    return {"run": meta, **_run_status(run_id, meta), "versions": _versions(meta, res)}


@app.get("/api/runs/{run_id}/progress")
def run_progress(run_id: str):
    _run_or_404(run_id)
    return jobs.progress(run_id)


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
        it = its.get(r["item_id"])
        rows.append({"item_id": r["item_id"], "data_kind": r["data_kind"],
                     "prediction_status": r["prediction_status"], "annotation_status": r["annotation_status"],
                     "scored": r["scored"], "excluded_reason": r["excluded_reason"],
                     "relations": r["relations"],
                     "action_eval": {"pass": ae.get("pass"), "pass_status": ae.get("pass_status"),
                                     "fail_reasons": ae.get("fail_reasons", []),
                                     "excluded_reason": ae.get("excluded_reason")},
                     "image_url": _image_url(it), "thumbnail_url": _thumb_url(it)})
    return {"run_id": run_id, "data_kind": meta.get("data_kind"), **_run_status(run_id, meta),
            "versions": _versions(meta, res),
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
    fmt = check_format(item_id, pred, load_schema())
    review = next((r for r in store.statement_reviews(run_id) if r.get("item_id") == item_id), None)
    return {
        "run_id": run_id, "item_id": item_id, "data_kind": row["data_kind"], "versions": _versions(meta, res),
        "run": {"run_id": run_id, "label": meta.get("label"), "model": meta.get("model"),
                "prompt": meta.get("prompt"), "decoding": meta.get("decoding")},
        # model input (what the model saw)
        "input": item, "image_url": _image_url(item), "image_size": (item or {}).get("image_size"),
        # raw model output, kept even when it failed
        "prediction": {"status": row["prediction_status"], "format_errors": row["format_errors"],
                       "raw_text": (pred or {}).get("raw_text"), "output_text": (pred or {}).get("output_text"),
                       "error": (pred or {}).get("error"), "parsed": fmt["parsed"] if fmt["valid"] else None,
                       "meta": {k: v for k, v in (pred or {}).items() if k not in ("raw_text", "output_text", "parsed")}},
        # GT and C: viewer only, never part of model input
        "reference": store.references().get(item_id) or {"item_id": item_id, "annotation_status": "Missing"},
        "scoring": {"scored": row["scored"], "excluded_reason": row["excluded_reason"],
                    "relations": row["relations"], "attributes": row.get("attributes"),
                    "action_eval": row["action_eval"], "diagnostics": row["diagnostics"],
                    "statement_review": review or {"status": "not_submitted",
                                                   "reason": "V13/V14 come from human statement review only"}},
    }


@app.get("/api/runs/{run_id}/report")
def report(run_id: str, base: str | None = None):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    s = res["summary"]
    body = {"run_id": run_id, "base_run_id": base, "data_kind": meta.get("data_kind"), **_run_status(run_id, meta),
            "versions": _versions(meta, res), "n_requests": s["n_requests"],
            "n_groups": len({g for g in store.group_of(store.requests(run_id)).values() if g}),
            "prediction_status_counts": s["prediction_status_counts"], "n_scored_items": s["n_scored_items"],
            "excluded": {"items": s["excluded_items"], "actions": s["excluded_from_actions"]},
            "metrics": s["metrics"]}
    if base:
        _run_or_404(base)
        cmp = store.compare(base, run_id)
        v10 = cmp["metrics"].get("v10_action_pass_rate", {})
        body["comparison"] = {**cmp, "core": {
            "v10_delta": v10.get("delta"), "v10_delta_ci95": v10.get("delta_ci95"),
            "judgement": v10.get("judgement", "not_applicable"),
            "v5_judgement": cmp["metrics"].get("v5_relation_macro_f1", {}).get("judgement", "not_applicable")}}
    else:
        body["comparison"] = {"status": "not_requested", "reason": "pass ?base=<run_id> to compare"}
    return body


@app.get("/api/compare")
def compare_items(base: str, target: str):
    _run_or_404(base)
    _run_or_404(target)
    rb, rt = store.result(base), store.result(target)
    tb = {r["item_id"]: r for r in rt["items"]}
    rows = []
    for r in rb["items"]:
        t = tb.get(r["item_id"])
        rows.append({"item_id": r["item_id"], "annotation_status": r["annotation_status"],
                     "base": {"prediction_status": r["prediction_status"], "relations": r["relations"],
                              "action_pass": r["action_eval"].get("pass"),
                              "fail_reasons": r["action_eval"].get("fail_reasons", [])},
                     "target": None if t is None else {
                         "prediction_status": t["prediction_status"], "relations": t["relations"],
                         "action_pass": t["action_eval"].get("pass"),
                         "fail_reasons": t["action_eval"].get("fail_reasons", [])},
                     "image_url": f"/api/images/{r['item_id']}"})
    return {"base_run_id": base, "target_run_id": target, "n": len(rows), "items": rows,
            "summary": store.compare(base, target)}


@app.get("/api/runs/{run_id}/report/conditions")
def report_conditions(run_id: str, key: str = Query(..., description="e.g. weather, time, road, scenario")):
    meta = _run_or_404(run_id)
    res = store.result(run_id)
    reqs = store.requests(run_id)
    its = store.items()
    groups = {}
    for row, q in zip(res["items"], reqs):
        cond = (its.get(q["item_id"], {}).get("conditions") or {})
        value = cond.get(key)
        groups.setdefault("(missing)" if value is None else value, []).append((row, q))
    out = {}
    for value, pairs in sorted(groups.items()):
        m = aggregate([p[0] for p in pairs], [p[1] for p in pairs])["metrics"]
        out[value] = {"n_requests": len(pairs), "exploratory": len(pairs) < SMALL_N,
                      "metrics": {k: {f: m[k].get(f) for f in ("status", "value", "numerator", "n", "reason")}
                                  for k in ("v1_valid", "v5_relation_macro_f1", "v6_present_recall",
                                            "v8_unknown_recall", "v10_action_pass_rate")}}
    return {"run_id": run_id, "data_kind": meta.get("data_kind"), "key": key,
            "condition_source": "item metadata (fixed before inference, same set for every model)",
            "small_n_threshold": SMALL_N, "values": out}


@app.get("/api/runs/{run_id}/export")
def export(run_id: str, format: str = Query("json", pattern="^(json|csv)$")):
    _run_or_404(run_id)
    res = store.result(run_id)
    if format == "json":
        return JSONResponse(res, headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'})
    buf = io.StringIO()
    w = csv.writer(buf)
    head = ["item_id", "data_kind", "prediction_status", "annotation_status", "scored", "excluded_reason"]
    for r in ("R1", "R2", "R3", "R4"):
        head += [f"{r}_expected", f"{r}_predicted", f"{r}_match"]
    head += ["action_pass", "action_pass_status", "fail_reasons", "format_errors"]
    w.writerow(head)
    for it in res["items"]:
        row = [it["item_id"], it["data_kind"], it["prediction_status"], it["annotation_status"], it["scored"],
               it["excluded_reason"]]
        for r in ("R1", "R2", "R3", "R4"):
            rel = it["relations"][r]
            row += [rel["expected"], rel["predicted"], rel["match"]]
        ae = it["action_eval"]
        row += [ae.get("pass"), ae.get("pass_status"), "|".join(ae.get("fail_reasons", [])),
                " | ".join(it["format_errors"])]
        w.writerow(row)
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'})


# ----------------------------------------------------------------------------- quality / datasets

@app.get("/api/quality")
def label_quality():
    return {"l1_l2": quality.agreement(store.annotation_rounds()),
            "l3": quality.coverage(store.references(), store.items())}


@app.get("/api/datasets")
def datasets():
    out = []
    for v in store.split_versions():
        sp = store.split(v)
        fz = store.STORE / "splits" / f"{v}.freeze.json"
        out.append({"version": v, "counts": _count(sp.get("assignments", {}).values()), "frozen": fz.exists()})
    return {"datasets": out}


@app.get("/api/datasets/{version}/leak-check")
def leak_check(version: str):
    sp = store.split(version)
    if sp is None:
        raise HTTPException(404, f"unknown split version {version}")
    return quality.leak_check(sp, store.items())


@app.post("/api/datasets/{version}/freeze", dependencies=[Depends(write_auth)])
def freeze(version: str, split_name: str = "test"):
    sp = store.split(version)
    if sp is None:
        raise HTTPException(404, f"unknown split version {version}")
    path = store.STORE / "splits" / f"{version}.freeze.json"
    man = quality.freeze_manifest(sp, store.items(), store.references(), store.scorer_commit(), store.schema_sha(),
                                  split_name)
    if not man["frozen"]:
        raise HTTPException(409, man)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        same = all(old.get(k) == man.get(k) for k in ("item_ids", "items_sha256", "references_sha256"))
        if not same:
            raise HTTPException(409, {"error": "already frozen with different contents", "frozen": old})
        return old
    man["frozen_at"] = jobs.iso(jobs.now())
    store.write_json(path, man)
    return man


# ----------------------------------------------------------------------------- runs (write) + jobs

@app.post("/api/runs", dependencies=[Depends(write_auth)])
def create_run(spec: dict = Body(..., examples=[{"label": "Pilot 6 rerun on A10G",
                                                  "item_ids": ["pilot_001"], "prompt_version": "prompt_v1"}])):
    out = jobs.create_run(spec)
    if not out["created"]:
        raise HTTPException(422, out)
    return out


@app.post("/api/runs/{run_id}/cancel", dependencies=[Depends(write_auth)])
def cancel_run(run_id: str):
    _run_or_404(run_id)
    out = jobs.cancel(run_id)
    if out is None:
        raise HTTPException(409, "imported run has no queue")
    return out


@app.post("/api/runs/{run_id}/rescore", dependencies=[Depends(write_auth)])
def rescore(run_id: str):
    _run_or_404(run_id)
    res = store.score(run_id)
    return {"run_id": run_id, "result_hash": res["result_hash"], "scorer_version": res["scorer_version"]}


@app.post("/api/runs/{run_id}/statement-reviews", dependencies=[Depends(write_auth)])
def add_statement_review(run_id: str, review: dict = Body(...)):
    _run_or_404(run_id)
    if review.get("item_id") not in {q["item_id"] for q in store.requests(run_id)}:
        raise HTTPException(422, "item_id is not in this run's request list")
    if not review.get("reviewer"):
        raise HTTPException(422, "reviewer is required (human review only)")
    for s in review.get("statements", []):
        if not isinstance(s.get("error"), bool) or not s.get("text"):
            raise HTTPException(422, "each statement needs text and a boolean error")
    p = store.run_dir(run_id) / "statement_reviews.jsonl"
    rows = [r for r in store.statement_reviews(run_id) if r.get("item_id") != review["item_id"]] + [review]
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return {"run_id": run_id, "item_id": review["item_id"], "n_reviews": len(rows)}


@app.get("/api/jobs/next", dependencies=[Depends(worker_auth)])
def job_next(worker: str):
    job = jobs.next_job(worker)
    return job or Response(status_code=204)


@app.post("/api/jobs/{run_id}/{item_id}/result", dependencies=[Depends(worker_auth)])
def job_result(run_id: str, item_id: str, worker: str, body: dict = Body(...)):
    code, out = jobs.submit(run_id, item_id, worker, body)
    if code != 200:
        raise HTTPException(code, out)
    return out


# ----------------------------------------------------------------------------- images

@app.get("/api/images/{item_id}")
def image(item_id: str, size: str | None = Query(None, pattern="^thumb$")):
    item = store.items().get(item_id)
    if not item or not item.get("image_relpath"):
        raise HTTPException(404, "no image for this item")
    root = IMAGE_ROOT.resolve()
    src = None
    for cand in (root / item["image_relpath"], root / item["image_file"]):
        p = cand.resolve()
        if p.is_relative_to(root) and p.is_file():
            src = p
            break
    if src is None:
        raise HTTPException(404, f"image file not found under IMAGE_ROOT ({item['image_file']})")
    if size != "thumb":
        return FileResponse(src, media_type="image/png")
    key = hashlib.sha256(f"{src}:{src.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    thumb = store.STORE / "cache" / "thumbs" / f"{item_id}_{key}.jpg"
    if not thumb.exists():
        from PIL import Image
        thumb.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            im2 = im.convert("RGB")
            im2.thumbnail((320, 320))
            im2.save(thumb, "JPEG", quality=80)
    return FileResponse(thumb, media_type="image/jpeg")
