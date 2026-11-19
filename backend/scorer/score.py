"""Track 1 scorer: format check -> grounding -> relations/attributes -> actions -> aggregation.

Rules follow Role_Backend.pdf §3-6 (spec wins if they differ).

Status values used everywhere:
  metric.status: "computed" | "not_applicable" (denominator 0 / spec condition unmet)
                 | "not_computed" (feature or input not available yet)
  A metric that is not "computed" always has value=None and a non-empty reason.
  Nothing is ever filled with 0 or an example score.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from .validate import validate_prediction

SCORER_VERSION = "backend-scorer-0.2.1"
SCHEMA_PATH = Path(__file__).with_name("prediction.schema.json")
RELATIONS = ["R1", "R2", "R3", "R4"]
STATES = ["P", "A", "U"]
ATTR_FIELDS = ["sidewalk_left", "sidewalk_right", "traffic_direction", "direction_match"]
RELATIONS_ONLY = "relations_only"
IOU_THRESHOLDS = [0.3, 0.5, 0.7]
# Pairs that cannot both hold for the same condition (hold/yield vs advance).
STOP_CODES = {"HOLD_UNTIL_CLEAR", "YIELD_IF_OCCUPIED"}
GO_CODES = {"ADVANCE_WITH_MONITORING"}
CONDITION_STATES = {
    "while_corridor_occupied": ("R1", {"P"}),
    "while_actor_near_entrance": ("R2", {"P"}),
    "before_entering_occluded_area": ("R3", {"P"}),
    "before_passing_restricted_section": ("R4", {"P", "U"}),
}
UNCERTAIN_RELATIONS = ("R1", "R2", "R3")
FAIL_REASON_CODES = ["invalid", "missing_required", "forbidden", "unsupported",
                     "contradiction", "reference_inconsistent"]


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def canonical_hash(obj) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- format (V1, V2)

def check_format(request_item_id: str, record: dict | None, schema: dict) -> dict:
    """record = {"status": "ok"|"timeout"|"error", "raw_text": str|None, "parsed": obj|None}.

    A request with no record at all is kept and marked "not_returned" (counted invalid).
    """
    if record is None:
        return {"prediction_status": "not_returned", "valid": False,
                "errors": ["no prediction record for a fixed request"], "parsed": None}
    if record.get("status") == "timeout":
        return {"prediction_status": "timeout", "valid": False,
                "errors": [record.get("error") or "generation timed out"], "parsed": None}
    if record.get("status") == "cancelled":
        return {"prediction_status": "cancelled", "valid": False,
                "errors": [record.get("error") or "cancelled before inference"], "parsed": None}
    if record.get("status") == "error":
        return {"prediction_status": "invalid", "valid": False,
                "errors": [record.get("error") or "generation failed"], "parsed": None}
    parsed = record.get("parsed")
    if parsed is None:
        # output_text = generated text decoded with special tokens skipped (e.g. no trailing <turn|>).
        # No other repair (fence stripping, truncation fixes) is applied: such output stays invalid.
        text = record.get("output_text")
        if text is None:
            text = record.get("raw_text")
        try:
            parsed = json.loads(text or "")
        except (json.JSONDecodeError, TypeError) as exc:
            return {"prediction_status": "invalid", "valid": False,
                    "errors": [f"JSON parse error: {exc}"], "parsed": None}
    try:
        errors = validate_prediction(parsed, schema)
    except (KeyError, TypeError, AttributeError) as exc:  # malformed beyond schema checks
        errors = [f"validator exception: {type(exc).__name__}: {exc}"]
    if not errors and parsed.get("item_id") != request_item_id:
        errors.append(f"item_id mismatch: request {request_item_id}, output {parsed.get('item_id')}")
    return {"prediction_status": "valid" if not errors else "invalid", "valid": not errors,
            "errors": errors, "parsed": parsed}


# --------------------------------------------------------------------------- references

def reference_gate(ref: dict | None) -> tuple[bool, str | None]:
    """Only Reviewed references are scored. Returns (usable, exclusion_reason)."""
    if ref is None or ref.get("annotation_status") in (None, "Missing"):
        return False, "reference_missing"
    if ref.get("annotation_status") != "Reviewed":
        return False, f"reference_not_reviewed ({ref.get('annotation_status')})"
    return True, None


def ref_state(ref: dict, rel: str):
    """GT state for a relation, or None when that cell is Missing. U is a valid answer."""
    value = (ref.get("relations") or {}).get(rel)
    if isinstance(value, dict):
        value = value.get("state")
    return value if value in STATES else None


# --------------------------------------------------------------------------- grounding (V3, V4)

def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_boxes(preds: list, refs: list, thr: float, kind_key: str = "class") -> dict:
    """One-to-one matching: maximise #pairs first, then IoU sum (weight M + IoU, Hungarian).

    Only same class (or region type) and IoU >= thr can pair. Greedy is not used.
    """
    pid = "object_id" if kind_key == "class" else "region_id"
    if not preds or not refs:
        return {"pairs": [], "unmatched_prediction_ids": [p[pid] for p in preds],
                "unmatched_reference_ids": [r[pid] for r in refs]}
    n, m = len(preds), len(refs)
    big_m = min(n, m) + 1.0
    weight = np.zeros((n, m))
    ious = np.zeros((n, m))
    for i, p in enumerate(preds):
        for j, r in enumerate(refs):
            if p.get(kind_key) != r.get(kind_key):
                continue
            v = iou(p["bbox_xyxy_norm"], r["bbox_xyxy_norm"])
            ious[i, j] = v
            if v >= thr:
                weight[i, j] = big_m + v
    rows, cols = linear_sum_assignment(weight, maximize=True)
    pairs = [{"prediction_id": preds[i][pid], "reference_id": refs[j][pid],
              "class": preds[i].get(kind_key), "iou": round(float(ious[i, j]), 6)}
             for i, j in zip(rows, cols) if weight[i, j] > 0]
    pairs.sort(key=lambda x: x["prediction_id"])
    used_p = {x["prediction_id"] for x in pairs}
    used_r = {x["reference_id"] for x in pairs}
    return {"pairs": pairs,
            "unmatched_prediction_ids": [p[pid] for p in preds if p[pid] not in used_p],
            "unmatched_reference_ids": [r[pid] for r in refs if r[pid] not in used_r]}


def grounding(pred_track: dict | None, ref: dict) -> dict:
    out = {"objects": {}, "regions": {}}
    pred_objs = (pred_track or {}).get("objects", [])
    ref_objs = [o for o in ref.get("objects", []) if o.get("bbox_xyxy_norm")]
    for thr in IOU_THRESHOLDS:
        out["objects"][str(thr)] = match_boxes(pred_objs, ref_objs, thr)
    pred_regs = [r for r in (pred_track or {}).get("regions", []) if r.get("bbox_xyxy_norm")]
    ref_regs = ref.get("regions", [])
    measurable = [r for r in ref_regs if r.get("bbox_xyxy_norm") and r.get("type") != "driving_area"]
    out["regions"]["unmeasurable_reference_ids"] = [
        r["region_id"] for r in ref_regs if not r.get("bbox_xyxy_norm") and r.get("type") != "driving_area"]
    for thr in IOU_THRESHOLDS:
        out["regions"][str(thr)] = match_boxes(pred_regs, measurable, thr, kind_key="type")
    return out


def evidence_check(pred_track: dict | None, valid: bool, ref: dict, ground: dict) -> dict:
    """V4 per relation: mapped prediction evidence set == one accepted GT set."""
    obj_map = {p["prediction_id"]: p["reference_id"] for p in ground["objects"]["0.5"]["pairs"]}
    reg_map = {p["prediction_id"]: p["reference_id"] for p in ground["regions"]["0.5"]["pairs"]}
    result = {}
    for rel in RELATIONS:
        gt = ref_state(ref, rel)
        if gt not in ("P", "U"):
            result[rel] = {"status": "not_applicable", "reason": "GT state is not P/U" if gt else "GT relation missing"}
            continue
        if not ref.get("evidence_reviewed", False):
            result[rel] = {"status": "excluded", "reason": "evidence_not_reviewed"}
            continue
        if not valid:
            result[rel] = {"status": "fail", "reason": "invalid_output"}
            continue
        prel = pred_track["relations"][rel]
        mapped, unmatched = set(), []
        for oid in prel["object_ids"]:
            (mapped.add(obj_map[oid]) if oid in obj_map else unmatched.append(oid))
        for rid in prel["region_ids"]:
            (mapped.add(reg_map[rid]) if rid in reg_map else unmatched.append(rid))
        accepted = ref.get("accepted_evidence_sets_by_relation", {}).get(rel) or [{
            "object_ids": ref.get("reference_object_ids_by_relation", {}).get(rel, []),
            "region_ids": ref.get("reference_region_ids_by_relation", {}).get(rel, [])}]
        sets = [set(a.get("object_ids", [])) | set(a.get("region_ids", [])) for a in accepted]
        ok = not unmatched and mapped in sets
        result[rel] = {"status": "pass" if ok else "fail",
                       "reason": None if ok else ("unmatched_evidence_ids" if unmatched else "evidence_set_differs"),
                       "mapped_ids": sorted(mapped), "unmatched_prediction_ids": unmatched}
    return result


# --------------------------------------------------------------------------- actions (V10-V12)

def _pair(a):
    return (a["code"], a["condition"])


def condition_errors(action, own, ref):
    """Check Appendix B.1 conditions against both GT and the cited model relations."""
    code, condition = _pair(action)
    label = f"{code}/{condition}"
    cited = set(action["based_on"])
    if condition in CONDITION_STATES:
        relation, states = CONDITION_STATES[condition]
        states_label = "/".join(sorted(states))
        own_error = (None if relation in cited and own.get(relation) in states
                     else f"{label} requires based_on {relation} and model {relation}={states_label}")
        ref_error = (None if ref_state(ref, relation) in states
                     else f"{label} requires GT {relation}={states_label}")
        return own_error, ref_error
    if condition == "before_resolving_uncertainty":
        required = {r for r in UNCERTAIN_RELATIONS if ref_state(ref, r) == "U"}
        own_uncertainty = {r for r in UNCERTAIN_RELATIONS if own.get(r) == "U" and r in cited}
        own_error = (None if own_uncertainty and required <= own_uncertainty
                     else f"{label} requires based_on and model U for all relevant relations")
        ref_error = None if required else f"{label} requires GT U in R1/R2/R3"
        return own_error, ref_error
    return None, None


def action_eval(pred_track: dict | None, valid: bool, ref: dict) -> dict:
    if ref.get("review_scope") == RELATIONS_ONLY:
        return {"pass": None, "pass_status": "excluded", "excluded_reason": "reference_relations_only",
                "fail_reasons": [], "errors": []}
    rules = ref.get("action_rules")
    dm = (ref.get("attributes") or {}).get("direction_match")
    if dm == "Conflicting":
        return {"pass": None, "pass_status": "excluded", "excluded_reason": "direction_conflict",
                "fail_reasons": [], "errors": []}
    if not rules:
        return {"pass": None, "pass_status": "excluded", "excluded_reason": "action_rules_missing",
                "fail_reasons": [], "errors": []}
    groups = rules.get("required_groups", [])
    allowed = {_pair(p) for p in rules.get("allowed_pairs", [])}
    forbidden = {_pair(p) for p in rules.get("forbidden_pairs", [])}
    base = {"required_groups": len(groups), "excluded_reason": None}
    if not valid:
        return {**base, "pass": False, "pass_status": "computed", "fail_reasons": ["invalid"],
                "errors": ["invalid output counts as failure"], "matched_required_groups": 0,
                "required_group_hits": [False] * len(groups),
                "forbidden_pairs_hit": [], "unsupported_pairs": [], "forbidden_hit": False}
    actions = pred_track["actions"]
    preds = {_pair(a) for a in actions}
    reasons, errors = [], []
    forb = sorted(preds & forbidden)
    unsup = sorted(preds - allowed - forbidden)
    if forb:
        reasons.append("forbidden"); errors.append(f"forbidden pairs: {forb}")
    if unsup:
        reasons.append("unsupported"); errors.append(f"pairs outside allowed/forbidden: {unsup}")
    # Appendix B.1: no_condition is scene-wide and does not require a P/U relation.
    # Allowed/forbidden pairs and incompatible actions still apply to it.
    own = {r: pred_track["relations"][r]["state"] for r in RELATIONS}
    contra, ref_bad = [], []
    consistent_actions = []
    for a in actions:
        if a["condition"] == "no_condition":
            consistent_actions.append(a)
            continue
        own_error, ref_error = condition_errors(a, own, ref)
        if own_error:
            contra.append(own_error)
        if ref_error:
            ref_bad.append(ref_error)
        own_absent = [r for r in a["based_on"] if own.get(r) == "A"]
        ref_absent = [r for r in a["based_on"] if ref_state(ref, r) == "A"]
        label = f"{a['code']}/{a['condition']}"
        contra.extend(f"{label} based_on {r} but model judged {r}=A" for r in own_absent)
        ref_bad.extend(f"{label} based_on {r} but GT {r}=A" for r in ref_absent)
        if not (own_error or ref_error or own_absent or ref_absent):
            consistent_actions.append(a)
    group_hits = [
        any(_pair(a) == _pair(alt) and set(alt.get("based_on", [])) <= set(a["based_on"])
            for alt in group["alternatives"] for a in consistent_actions)
        for group in groups
    ]
    if not all(group_hits):
        reasons.append("missing_required")
        errors.extend(f"required group {i} not satisfied" for i, hit in enumerate(group_hits) if not hit)
    conds = {}
    for a in actions:
        conds.setdefault(a["condition"], set()).add(a["code"])
    for c, codes in conds.items():
        if codes & STOP_CODES and codes & GO_CODES:
            contra.append(f"stop and advance together under {c}")
    unconditional = conds.get("no_condition", set())
    for c, codes in conds.items():
        if c != "no_condition" and ((codes & STOP_CODES and unconditional & GO_CODES) or
                                    (codes & GO_CODES and unconditional & STOP_CODES)):
            contra.append(f"conditional and unconditional stop/advance overlap under {c}")
    if contra:
        reasons.append("contradiction"); errors.extend(contra)
    if ref_bad:
        reasons.append("reference_inconsistent"); errors.extend(ref_bad)
    return {**base, "pass": not reasons, "pass_status": "computed", "fail_reasons": reasons,
            "errors": errors, "matched_required_groups": sum(group_hits), "required_group_hits": group_hits,
            "forbidden_pairs_hit": [list(p) for p in forb], "unsupported_pairs": [list(p) for p in unsup],
            "forbidden_hit": bool(forb)}


# --------------------------------------------------------------------------- per item

def score_item(request: dict, record: dict | None, ref: dict | None, schema: dict) -> dict:
    fmt = check_format(request["item_id"], record, schema)
    track = fmt["parsed"]["track1"] if fmt["valid"] else None
    usable, excl = reference_gate(ref)
    out = {"item_id": request["item_id"], "data_kind": request.get("data_kind", "real"),
           "prediction_status": fmt["prediction_status"], "format_errors": fmt["errors"],
           "annotation_status": (ref or {}).get("annotation_status", "Missing"),
           "reference_version": (ref or {}).get("reference_version"),
           "scored": usable, "excluded_reason": excl}
    rel_rows = {}
    for r in RELATIONS:
        gt = ref_state(ref, r) if usable else None
        pr = track["relations"][r]["state"] if track else None
        rel_rows[r] = {"expected": gt if usable else "Missing", "predicted": pr,
                       "match": (gt == pr) if (usable and gt is not None) else None}
    out["relations"] = rel_rows
    blockers = []
    if not usable:
        blockers.append(excl)
        out.update({"diagnostics": {"grounding": None, "evidence": None,
                                    "benchmark": {"eligible": False, "blockers": blockers}},
                    "action_eval": {"pass": None, "pass_status": "excluded", "excluded_reason": excl,
                                    "fail_reasons": [], "errors": []}})
        return out
    partial = ref.get("review_scope") == RELATIONS_ONLY
    ground = None if partial else grounding(track, ref)
    if partial:
        evidence = {r: {"status": "excluded", "reason": "evidence_not_reviewed"}
                    for r in RELATIONS if rel_rows[r]["expected"] in ("P", "U")}
        blockers.append("reference_relations_only")
    else:
        evidence = evidence_check(track, fmt["valid"], ref, ground)
    out["diagnostics"] = {"grounding": ground, "evidence": evidence,
                          "benchmark": {"eligible": not partial, "blockers": blockers}}
    attributes = {} if partial else ref.get("attributes") or {}
    out["attributes"] = {f: {"expected": attributes.get(f),
                             "predicted": track["attributes"][f] if track else None} for f in ATTR_FIELDS}
    out["action_eval"] = action_eval(track, fmt["valid"], ref)
    return out


# --------------------------------------------------------------------------- aggregation

def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((centre - half) / den, 6), round((centre + half) / den, 6)]


def ratio(k, n, reason_if_zero, ci=False, ci_reason="filled by group bootstrap when applicable"):
    if n == 0:
        return {"status": "not_applicable", "value": None, "numerator": 0, "n": 0,
                "reason": reason_if_zero, "ci95": None, "ci_status": "not_applicable"}
    return {"status": "computed", "value": round(k / n, 6), "numerator": k, "n": n, "reason": None,
            "ci95": wilson(k, n) if ci else None,
            "ci_status": "wilson" if ci else "not_computed", "ci_reason": None if ci else ci_reason}


def not_computed(reason):
    return {"status": "not_computed", "value": None, "n": None, "reason": reason,
            "ci95": None, "ci_status": "not_computed"}


def f1(tp, fp, fn):
    d = 2 * tp + fp + fn
    return None if d == 0 else 2 * tp / d


def aggregate(results: list[dict], requests: list[dict]) -> dict:
    n_req = len(requests)
    valid = sum(r["prediction_status"] == "valid" for r in results)
    status_counts = {}
    for r in results:
        status_counts[r["prediction_status"]] = status_counts.get(r["prediction_status"], 0) + 1
    scored = [r for r in results if r["scored"]]
    excluded = {}
    for r in results:
        if not r["scored"]:
            excluded[r["excluded_reason"]] = excluded.get(r["excluded_reason"], 0) + 1
    no_ref = "no Reviewed reference in this run" if not scored else None
    m = {"v1_valid": ratio(valid, n_req, "no requests", ci=True),
         "v2_invalid": ratio(n_req - valid, n_req, "no requests", ci=True)}

    # V3 (objects, per threshold)
    v3 = {}
    for thr in map(str, IOU_THRESHOLDS):
        tp = fp = fn = 0
        for r in scored:
            grounding_rows = r["diagnostics"]["grounding"]
            if grounding_rows is None:
                continue
            g = grounding_rows["objects"][thr]
            tp += len(g["pairs"]); fp += len(g["unmatched_prediction_ids"]); fn += len(g["unmatched_reference_ids"])
        if not scored or tp + fn == 0:
            v3[thr] = {"status": "not_applicable", "value": None, "reason": no_ref or "no reviewed reference objects"}
        else:
            v3[thr] = {"status": "computed", "precision": tp / (tp + fp) if tp + fp else None,
                       "recall": tp / (tp + fn), "f1": f1(tp, fp, fn), "tp": tp, "fp": fp, "fn": fn,
                       "ci_status": "not_computed", "ci_reason": "see top-level ci95"}
    m["v3_grounding"] = {"status": v3["0.5"]["status"], "primary_iou": 0.5, "by_iou": v3,
                         "reason": v3["0.5"].get("reason")}

    # V4
    ev = [e for r in scored for e in r["diagnostics"]["evidence"].values() if e["status"] in ("pass", "fail")]
    m["v4_evidence"] = ratio(sum(e["status"] == "pass" for e in ev), len(ev),
                             no_ref or "no P/U relation with reviewed evidence")

    # V5-V9
    pairs = [(r["relations"][h]["expected"], r["relations"][h]["predicted"], h)
             for r in scored for h in RELATIONS if r["relations"][h]["expected"] in STATES]
    cells, missing_cells = {}, []
    for h in RELATIONS:
        for c in STATES:
            sub = [(y, yh) for y, yh, hh in pairs if hh == h]
            tp = sum(y == c and yh == c for y, yh in sub)
            fp = sum(y != c and yh == c for y, yh in sub)
            fn = sum(y == c and yh != c for y, yh in sub)
            support = sum(y == c for y, _ in sub)
            cells[f"{h}.{c}"] = {"f1": f1(tp, fp, fn) if support else None, "support": support,
                                 "tp": tp, "fp": fp, "fn": fn}
            if support == 0:
                missing_cells.append(f"{h}.{c}")
    supported = [v["f1"] for v in cells.values() if v["support"]]
    if not pairs:
        m["v5_relation_macro_f1"] = {"status": "not_applicable", "value": None, "reason": no_ref or "no relation GT",
                                     "cells": cells}
    elif missing_cells:
        m["v5_relation_macro_f1"] = {
            "status": "not_applicable", "value": None, "cells": cells,
            "reason": f"V5 needs reviewed GT in all 12 cells; empty: {missing_cells}",
            "supported_class_macro_f1": {"value": round(sum(supported) / len(supported), 6),
                                         "n_cells": len(supported)}}
    else:
        m["v5_relation_macro_f1"] = {"status": "computed", "value": round(sum(supported) / 12, 6), "cells": cells,
                                     "reason": None, "ci95": None, "ci_status": "not_computed",
                                     "ci_reason": "see top-level ci95"}
    cnt = lambda cond: sum(1 for y, yh, _ in pairs if cond(y, yh))
    m["v6_present_recall"] = ratio(cnt(lambda y, yh: y == "P" and yh == "P"), cnt(lambda y, yh: y == "P"),
                                   no_ref or "no GT=P")
    m["v7_false_positive_rate"] = ratio(cnt(lambda y, yh: y == "A" and yh == "P"), cnt(lambda y, yh: y == "A"),
                                        no_ref or "no GT=A")
    m["v8_unknown_recall"] = ratio(cnt(lambda y, yh: y == "U" and yh == "U"), cnt(lambda y, yh: y == "U"),
                                   no_ref or "no GT=U")
    m["v9_over_abstention"] = ratio(cnt(lambda y, yh: y in "PA" and yh == "U"), cnt(lambda y, yh: y in "PA"),
                                    no_ref or "no GT in {P,A}")

    # A1, A2
    a1_fields = {}
    for fld in ATTR_FIELDS:
        rows = [(r["attributes"][fld]["expected"], r["attributes"][fld]["predicted"]) for r in scored
                if r["attributes"][fld]["expected"] is not None]
        if fld == "direction_match":
            rows = [x for x in rows if x[0] != "Not applicable"]
        values = sorted({y for y, _ in rows})
        per = {v: f1(sum(y == v and yh == v for y, yh in rows), sum(y != v and yh == v for y, yh in rows),
                     sum(y == v and yh != v for y, yh in rows)) for v in values}
        a1_fields[fld] = {"value": round(sum(per.values()) / len(per), 6) if per else None,
                          "per_value_f1": per, "support": {v: sum(y == v for y, _ in rows) for v in values}}
    fv = [f["value"] for f in a1_fields.values() if f["value"] is not None]
    m["a1_attribute_f1"] = ({"status": "computed", "value": round(sum(fv) / len(fv), 6), "fields": a1_fields,
                             "ci_status": "not_computed", "ci_reason": "see top-level ci95"}
                            if fv else {"status": "not_applicable", "value": None,
                                        "reason": no_ref or "no attribute GT", "fields": a1_fields})
    na = [r for r in scored if r["attributes"]["direction_match"]["expected"] == "Not applicable"]
    m["a2_direction_na_violation"] = ratio(
        sum(r["attributes"]["direction_match"]["predicted"] in ("Consistent", "Conflicting") for r in na),
        len(na), no_ref or "no GT direction_match=Not applicable")

    # V10-V12 (denominator fixed by references, independent of predictions)
    act = [r for r in scored if r["action_eval"]["pass_status"] == "computed"]
    dir_conf = sum(1 for r in scored if r["action_eval"].get("excluded_reason") == "direction_conflict")
    m["v10_action_pass_rate"] = ratio(sum(r["action_eval"]["pass"] for r in act), len(act),
                                      no_ref or "no scene eligible for action scoring", ci=True)
    total_groups = sum(r["action_eval"]["required_groups"] for r in act)
    m["v11_required_group_recall"] = ratio(sum(r["action_eval"]["matched_required_groups"] for r in act),
                                           total_groups, no_ref or "no required groups")
    m["v12_forbidden_rate"] = ratio(sum(r["action_eval"]["forbidden_hit"] for r in act), len(act),
                                    no_ref or "no scene eligible for action scoring", ci=True)
    m.update(statement_metrics(None, n_req))
    m["l1_l3_label_quality"] = not_computed("see GET /api/quality (needs two-annotator pre-consensus records)")
    excluded_actions = {"direction_conflict": dir_conf}
    return {"n_requests": n_req, "prediction_status_counts": status_counts, "n_scored_items": len(scored),
            "excluded_items": excluded, "excluded_from_actions": excluded_actions, "metrics": m}


def statement_metrics(reviews: list[dict] | None, n_requests: int) -> dict:
    """V13/V14 from human statement reviews only (spec App. A.7). Never judged automatically.

    review = {"item_id", "reviewer", "explanation_present": bool, "review_complete": bool,
              "statements": [{"text": str, "error": bool, "error_type": str|None}]}
    """
    if not reviews:
        reason = "statement_review_missing: no human statement reviews submitted; not judged automatically"
        return {"v13_statement_error_rate": not_computed(reason), "v14_answer_with_error_rate": not_computed(reason),
                "explanation_completion_rate": not_computed(reason)}
    done = [r for r in reviews if r.get("explanation_present") and r.get("review_complete") and r.get("statements")]
    k = sum(len(r["statements"]) for r in done)
    e = sum(bool(s.get("error")) for r in done for s in r["statements"])
    return {"v13_statement_error_rate": ratio(e, k, "no reviewed statements"),
            "v14_answer_with_error_rate": ratio(sum(any(s.get("error") for s in r["statements"]) for r in done),
                                                len(done), "no fully reviewed explanation", ci=True),
            "explanation_completion_rate": ratio(len(done), n_requests, "no requests", ci=True)}


def score_run(requests, predictions: dict, references: dict, schema=None, group_of: dict | None = None,
              statement_reviews: list | None = None, bootstrap_b: int | None = None, seed: int | None = None) -> dict:
    from . import stats
    schema = schema or load_schema()
    items = [score_item(q, predictions.get(q["item_id"]), references.get(q["item_id"]), schema) for q in requests]
    summary = aggregate(items, requests)
    summary["metrics"].update(statement_metrics(statement_reviews, len(requests)))
    b = stats.DEFAULT_B if bootstrap_b is None else bootstrap_b
    sd = stats.DEFAULT_SEED if seed is None else seed
    cis = stats.group_bootstrap(items, requests, group_of or {}, aggregate, B=b, seed=sd)
    for key, ci in cis.items():
        metric = summary["metrics"][key]
        if metric.get("status") == "computed":
            metric.update(ci)
        else:
            metric.update({"ci95": None, "ci_status": "not_applicable", "ci_reason": "metric not computed"})
    body = {"scorer_version": SCORER_VERSION, "bootstrap": {"B": b, "seed": sd}, "items": items, "summary": summary}
    body["result_hash"] = canonical_hash({"items": items, "summary": summary})
    return body
