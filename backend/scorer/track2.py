"""Track 2 (future event target prediction) scoring — spec App. D.1.

Item  = one (clip, decision time t). Model input: frames up to t only.
GT    = reviewed first-contact time tc, horizon H, target candidate IDs Y, target box B at t.
tau   = tc - t.  Positive: 0 < tau <= H.  Negative: no contact in (t, t+H] and observed until t+H.
Scored denominator (Selection & Localization): Reviewed, Positive for H, exactly one target, target visible at t.

Selection    TargetAcc = mean 1[y_hat in Y]      (invalid / missing answer = wrong)
Localization mIoU = mean IoU(B_hat, B), Acc.5 = mean 1[IoU >= 0.5]   (unreadable box -> IoU 0)
Both are reported overall and per residual-time bin; several decision times of one clip form one
Source Group (group bootstrap for intervals). Selection and Localization are reported separately.

Parsing is strict like Track 1: one JSON object, no code-fence repair. A fence-wrapped answer is invalid.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

SCORER_VERSION = "backend-track2-0.1.0"
DEFAULT_H = 2.0
BINS = [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0)]
BOOT_B = int(os.environ.get("BOOTSTRAP_B", "2000"))
SEED = 20261125


# --------------------------------------------------------------------------- parsing

def _load_object(text):
    try:
        value = json.loads((text or "").strip())
    except (json.JSONDecodeError, TypeError) as exc:
        return None, f"JSON parse error: {exc}"
    if not isinstance(value, dict):
        return None, "output is not a JSON object"
    return value, None


def parse_selection(record: dict | None, candidate_ids: list[int]) -> dict:
    if record is None:
        return {"status": "not_returned", "valid": False, "target_id": None, "errors": ["no selection output"]}
    if record.get("status") in ("timeout", "error", "cancelled"):
        return {"status": record["status"], "valid": False, "target_id": None,
                "errors": [record.get("error") or record["status"]]}
    obj, err = _load_object(record.get("output_text", record.get("raw_text")))
    if err:
        return {"status": "invalid", "valid": False, "target_id": None, "errors": [err]}
    tid = obj.get("target_id")
    errors = []
    if set(obj) - {"target_id"}:
        errors.append(f"unexpected fields {sorted(set(obj) - {'target_id'})}")
    if not isinstance(tid, int) or isinstance(tid, bool):
        errors.append("target_id must be an integer")
    elif tid not in candidate_ids:
        errors.append(f"target_id {tid} is not a shown candidate")
    return {"status": "valid" if not errors else "invalid", "valid": not errors,
            "target_id": tid if isinstance(tid, int) and not isinstance(tid, bool) else None, "errors": errors}


def parse_box(record: dict | None, width: int, height: int) -> dict:
    if record is None:
        return {"status": "not_returned", "valid": False, "bbox_xyxy_px": None, "errors": ["no box output"]}
    if record.get("status") in ("timeout", "error", "cancelled"):
        return {"status": record["status"], "valid": False, "bbox_xyxy_px": None,
                "errors": [record.get("error") or record["status"]]}
    obj, err = _load_object(record.get("output_text", record.get("raw_text")))
    if err:
        return {"status": "invalid", "valid": False, "bbox_xyxy_px": None, "errors": [err]}
    box = obj.get("bbox_xyxy")
    errors = []
    if set(obj) - {"bbox_xyxy"}:
        errors.append(f"unexpected fields {sorted(set(obj) - {'bbox_xyxy'})}")
    if (not isinstance(box, list) or len(box) != 4
            or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in box)):
        errors.append("bbox_xyxy must be four finite numbers")
        box = None
    else:
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            errors.append(f"bbox_xyxy must be ordered pixels inside {width}x{height}")
    return {"status": "valid" if not errors else "invalid", "valid": not errors,
            "bbox_xyxy_px": box if not errors else None, "errors": errors}


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


# --------------------------------------------------------------------------- GT

def ground_truth(item: dict, ref: dict | None) -> dict:
    """Event label and eligibility. Returns {label, tau, eligible, excluded_reason, ...}."""
    ref = ref or {}
    out = {"annotation_status": ref.get("annotation_status", "Missing"),
           "reference_version": ref.get("reference_version"), "horizon_s": ref.get("horizon_s", DEFAULT_H),
           "label": "Missing", "tau_s": None, "bin": None, "eligible": False, "excluded_reason": None}
    if ref.get("annotation_status") != "Reviewed":
        out["excluded_reason"] = "reference_missing" if not ref else f"reference_not_reviewed ({ref.get('annotation_status')})"
        return out
    t, h, tc = item["decision_time_s"], out["horizon_s"], ref.get("event_time_s")
    if tc is None:
        end = ref.get("observation_end_s", item.get("duration_s"))
        if ref.get("no_event_in_clip") and end is not None and end >= t + h:
            out.update(label="Negative", excluded_reason="negative_not_in_target_denominator")
        else:
            out["excluded_reason"] = "event_time_missing"
        return out
    tau = round(tc - t, 6)
    out["tau_s"] = tau
    if tau <= 0:
        out.update(label="AfterEvent", excluded_reason="decision_time_not_before_event")
        return out
    if tau > h:
        out.update(label="Negative", excluded_reason="negative_not_in_target_denominator")
        return out
    out["label"] = "Positive"
    out["bin"] = next(f"({lo},{hi}]" for lo, hi in BINS if lo < tau <= hi) if tau <= BINS[-1][1] else f"({BINS[-1][1]},{h}]"
    targets = ref.get("target_candidate_ids") or []
    if len(targets) != 1 or ref.get("n_targets", len(targets)) != 1:
        out["excluded_reason"] = "not_single_target"
    elif not ref.get("target_visible", False):
        out["excluded_reason"] = "target_not_visible_at_t"
    elif not ref.get("target_box_xyxy_px"):
        out["excluded_reason"] = "target_box_missing"
    else:
        out["eligible"] = True
    return out


# --------------------------------------------------------------------------- per item

def score_item(item: dict, ref: dict | None, pred: dict | None) -> dict:
    pred = pred or {}
    cand_ids = [c["candidate_id"] for c in item.get("candidates", [])]
    sel = parse_selection(pred.get("select"), cand_ids)
    box = parse_box(pred.get("box"), item["width"], item["height"])
    gt = ground_truth(item, ref)
    row = {"item_id": item["item_id"], "clip_id": item["clip_id"], "source_group_id": item.get("source_group_id"),
           "decision_time_s": item["decision_time_s"], "data_kind": item.get("data_kind", "real"),
           "gt": gt, "selection": {**sel, "allowed": None, "correct": None},
           "localization": {**box, "gt_box": None, "iou": None, "acc50": None}}
    if gt["eligible"]:
        allowed = ref["target_candidate_ids"]
        row["selection"].update(allowed=allowed, correct=bool(sel["valid"] and sel["target_id"] in allowed))
        gbox = ref["target_box_xyxy_px"]
        u = iou(box["bbox_xyxy_px"], gbox) if box["valid"] else 0.0
        row["localization"].update(gt_box=gbox, iou=round(u, 6), acc50=u >= 0.5)
        # same-person check between the two independent queries (analysis only)
        if sel["valid"] and box["valid"]:
            chosen = next((c for c in item["candidates"] if c["candidate_id"] == sel["target_id"]), None)
            row["selection_box_agree_iou"] = round(iou(chosen["bbox_xyxy_px"], box["bbox_xyxy_px"]), 6) if chosen else None
    return row


def baselines(item: dict, ref: dict) -> dict:
    """Selection baselines on the same candidates: bottom-most, largest, uniform random (expected)."""
    cands = item.get("candidates", [])
    if not cands:
        return {}
    bottom = max(cands, key=lambda c: c["bbox_xyxy_px"][3])["candidate_id"]
    area = lambda b: (b[2] - b[0]) * (b[3] - b[1])
    largest = max(cands, key=lambda c: area(c["bbox_xyxy_px"]))["candidate_id"]
    allowed = set(ref["target_candidate_ids"])
    return {"bottom_most": bottom in allowed, "largest": largest in allowed,
            "random_expected": len(allowed & {c["candidate_id"] for c in cands}) / len(cands)}


# --------------------------------------------------------------------------- aggregate

def _metric(values, reason):
    n = len(values)
    if n == 0:
        return {"status": "not_applicable", "value": None, "n": 0, "reason": reason}
    return {"status": "computed", "value": round(float(np.mean(values)), 6), "numerator": round(float(np.sum(values)), 6),
            "n": n, "reason": None}


def _summ(rows, items_by_id, refs, reason):
    el = [r for r in rows if r["gt"]["eligible"]]
    out = {"target_acc": _metric([float(r["selection"]["correct"]) for r in el], reason),
           "miou": _metric([r["localization"]["iou"] for r in el], reason),
           "acc50": _metric([float(r["localization"]["acc50"]) for r in el], reason)}
    bl = [baselines(items_by_id[r["item_id"]], refs[r["item_id"]]) for r in el]
    out["baselines"] = {k: _metric([float(b[k]) for b in bl if b], reason)
                        for k in ("bottom_most", "largest", "random_expected")}
    return out


def _bootstrap(rows, key_fn, B=BOOT_B, seed=SEED):
    el = [r for r in rows if r["gt"]["eligible"]]
    groups = sorted({r["source_group_id"] for r in el})
    if any(g is None for g in groups) or len(groups) < 2:
        return None, "fewer than two Source Groups (clips): interval is N/A"
    by = {g: [key_fn(r) for r in el if r["source_group_id"] == g] for g in groups}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B):
        sample = [groups[i] for i in rng.integers(0, len(groups), len(groups))]
        xs = [v for g in sample for v in by[g]]
        vals.append(float(np.mean(xs)))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return [round(float(lo), 6), round(float(hi), 6)], None


def aggregate(rows: list[dict], items_by_id: dict, refs: dict) -> dict:
    no_ref = "no Reviewed Positive item with a single visible target"
    overall = _summ(rows, items_by_id, refs, no_ref)
    for key, fn in (("target_acc", lambda r: float(r["selection"]["correct"])),
                    ("miou", lambda r: r["localization"]["iou"]),
                    ("acc50", lambda r: float(r["localization"]["acc50"]))):
        if overall[key]["status"] == "computed":
            ci, why = _bootstrap(rows, fn)
            overall[key].update(ci95=ci, ci_status="group_bootstrap" if ci else "not_applicable", ci_reason=why)
    by_bin = {}
    for lo, hi in BINS:
        label = f"({lo},{hi}]"
        sub = [r for r in rows if r["gt"]["bin"] == label]
        s = _summ(sub, items_by_id, refs, f"no eligible item with tau in {label}")
        s["exploratory"] = True
        by_bin[label] = s
    excluded, labels, fmt = {}, {}, {"selection": {}, "localization": {}}
    for r in rows:
        labels[r["gt"]["label"]] = labels.get(r["gt"]["label"], 0) + 1
        if not r["gt"]["eligible"]:
            excluded[r["gt"]["excluded_reason"]] = excluded.get(r["gt"]["excluded_reason"], 0) + 1
        for k in fmt:
            st = r[k]["status"]
            fmt[k][st] = fmt[k].get(st, 0) + 1
    return {"n_requests": len(rows), "n_eligible": sum(r["gt"]["eligible"] for r in rows),
            "n_source_groups": len({r["source_group_id"] for r in rows if r["gt"]["eligible"]}),
            "labels": labels, "excluded": excluded, "format_status": fmt,
            "overall": overall, "by_residual_time": by_bin,
            "event_prediction": {"status": "not_computed",
                                 "reason": "outputs have no event_prediction field and no observed Negatives yet"},
            "lead_time": {"status": "not_computed",
                          "reason": "needs event + target predictions at consecutive decision times (0.5 s apart)"}}


def score_run(requests: list[dict], items: dict, refs: dict, preds: dict) -> dict:
    from .score import canonical_hash
    rows = [score_item(items[q["item_id"]], refs.get(q["item_id"]), preds.get(q["item_id"])) for q in requests]
    summary = aggregate(rows, items, refs)
    return {"scorer_version": SCORER_VERSION, "track": "track2", "items": rows, "summary": summary,
            "result_hash": canonical_hash({"items": rows, "summary": summary})}
