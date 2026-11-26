"""Track 2 Report API (read-only).

GET /api/track2/items                         decision-time items (input side only)
GET /api/track2/items/{item_id}               one item + Draft/Reviewed reference (viewer only)
GET /api/track2/runs                          Track 2 runs
GET /api/track2/runs/{run_id}/report          TargetAcc, mIoU, Acc.5 (overall + per residual time), baselines
GET /api/track2/runs/{run_id}/items           per-item rows (filters: eligible, correct, excluded_reason, clip_id)
GET /api/track2/runs/{run_id}/items/{item_id} detail: video, decision time, candidates, GT box, predicted box, IoU
GET /api/track2/videos/{clip_id}              source MP4 (VIDEO_ROOT), supports HTTP Range for seeking
GET /api/track2/frames/{item_id}[?numbered=1] decision frame (plain or with neutral candidate numbers)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.app import track2_store as t2
from backend.scorer import track2

router = APIRouter(prefix="/api/track2", tags=["track2"])
VIDEO_ROOT = Path(os.environ.get("VIDEO_ROOT", "/data/aihub_597/2.Validation"))


def _item_or_404(item_id):
    it = t2.items().get(item_id)
    if it is None:
        raise HTTPException(404, f"unknown Track 2 item {item_id}")
    return it


def _run_or_404(run_id):
    meta = t2.run_meta(run_id)
    if meta is None:
        raise HTTPException(404, f"unknown Track 2 run {run_id}")
    return meta


def _media(it):
    return {"video_url": f"/api/track2/videos/{it['clip_id']}",
            "frame_url": f"/api/track2/frames/{it['item_id']}" if it.get("frame_url_available") else None,
            "numbered_frame_url": f"/api/track2/frames/{it['item_id']}?numbered=1" if it.get("frame_url_available") else None}


def _versions(res):
    return {"scorer": track2.SCORER_VERSION, "scorer_commit": res["scorer_commit"],
            "reference": res["reference_versions"], "result_hash": res["result_hash"]}


@router.get("/items")
def items(clip_id: str | None = None):
    refs = t2.references()
    rows = [{**it, **_media(it), "annotation_status": (refs.get(i) or {}).get("annotation_status", "Missing")}
            for i, it in t2.items().items() if not clip_id or it["clip_id"] == clip_id]
    return {"n": len(rows), "items": rows}


@router.get("/items/{item_id}")
def item(item_id: str):
    it = _item_or_404(item_id)
    ref = t2.references().get(item_id) or {"item_id": item_id, "annotation_status": "Missing"}
    return {"input": it, **_media(it), "reference": ref, "gt": track2.ground_truth(it, ref)}


@router.get("/runs")
def runs():
    out = []
    for rid in t2.run_ids():
        meta, res = t2.run_meta(rid), t2.result(rid)
        s = res["summary"]
        out.append({"run_id": rid, "label": meta.get("label"), "data_kind": meta.get("data_kind"),
                    "n_requests": s["n_requests"], "n_eligible": s["n_eligible"],
                    "target_acc": s["overall"]["target_acc"]["value"], "miou": s["overall"]["miou"]["value"]})
    return {"runs": out}


@router.get("/runs/{run_id}/report")
def report(run_id: str):
    meta = _run_or_404(run_id)
    res = t2.result(run_id)
    return {"run_id": run_id, "run": meta, "versions": _versions(res), **res["summary"],
            "definitions": {"denominator": "Reviewed, Positive within H, single target visible at decision time",
                            "selection": "TargetAcc = share of items whose chosen candidate is the target",
                            "localization": "IoU of predicted vs GT box at decision time; unreadable box = 0",
                            "residual_time": "tau = first contact time - decision time"}}


@router.get("/runs/{run_id}/items")
def run_items(run_id: str, eligible: bool | None = None, correct: bool | None = None,
              excluded_reason: str | None = None, clip_id: str | None = None):
    _run_or_404(run_id)
    res = t2.result(run_id)
    its = t2.items()
    rows = []
    for r in res["items"]:
        if eligible is not None and r["gt"]["eligible"] != eligible:
            continue
        if correct is not None and r["selection"]["correct"] is not correct:
            continue
        if excluded_reason and r["gt"]["excluded_reason"] != excluded_reason:
            continue
        if clip_id and r["clip_id"] != clip_id:
            continue
        rows.append({"item_id": r["item_id"], "clip_id": r["clip_id"], "decision_time_s": r["decision_time_s"],
                     "label": r["gt"]["label"], "tau_s": r["gt"]["tau_s"], "bin": r["gt"]["bin"],
                     "eligible": r["gt"]["eligible"], "excluded_reason": r["gt"]["excluded_reason"],
                     "annotation_status": r["gt"]["annotation_status"],
                     "selection": {k: r["selection"][k] for k in ("status", "target_id", "allowed", "correct")},
                     "localization": {k: r["localization"][k] for k in ("status", "iou", "acc50")},
                     **_media(its[r["item_id"]])})
    return {"run_id": run_id, "versions": _versions(res), "n": len(rows), "items": rows}


@router.get("/runs/{run_id}/items/{item_id}")
def run_item(run_id: str, item_id: str):
    meta = _run_or_404(run_id)
    res = t2.result(run_id)
    row = next((r for r in res["items"] if r["item_id"] == item_id), None)
    if row is None:
        raise HTTPException(404, f"{item_id} is not in run {run_id}")
    it = t2.items()[item_id]
    pred = t2.predictions(run_id).get(item_id) or {}
    return {"run_id": run_id, "item_id": item_id, "versions": _versions(res), "run": meta,
            "input": it, **_media(it), "width": it["width"], "height": it["height"],
            "decision_time_s": it["decision_time_s"], "candidates": it["candidates"],
            "reference": t2.references().get(item_id) or {"annotation_status": "Missing"},
            "scoring": row,
            "prediction_raw": {k: {kk: v.get(kk) for kk in ("status", "output_text", "error")}
                               for k, v in pred.items() if k in ("select", "box")}}


@router.get("/videos/{clip_id}")
def video(clip_id: str):
    it = next((i for i in t2.items().values() if i["clip_id"] == clip_id), None)
    if it is None:
        raise HTTPException(404, f"unknown clip {clip_id}")
    root = VIDEO_ROOT.resolve()
    p = (root / it["video_relpath"]).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise HTTPException(404, "video file not found under VIDEO_ROOT")
    return FileResponse(p, media_type="video/mp4")


@router.get("/frames/{item_id}")
def frame(item_id: str, numbered: bool = Query(False)):
    _item_or_404(item_id)
    p = t2.root() / "frames" / f"{item_id}{'_numbered' if numbered else ''}.jpg"
    if not p.is_file():
        raise HTTPException(404, "frame image not prepared (run tools.track2_data build --frames)")
    return FileResponse(p, media_type="image/jpeg")
