"""Bridge the revised contract to the existing Report, IoU and statistics APIs."""
from __future__ import annotations

from .. import score
from .contract import CORE, AUX, FIELDS, STATES, VERSION, all_observations
from .policy import check_actions, policy

SCORER_VERSION = "backend-scorer-0.3.0-v11-review"


def _action_row(track, ref, valid):
    result = check_actions({"track1": track} if valid else None, ref, valid)
    if result["status"] != "computed":
        reason = result["reason"]
        return {"pass": None, "pass_status": "excluded",
                "excluded_reason": "direction_conflict" if reason == "direction_conflicting" else reason,
                "fail_reasons": [], "errors": []}
    groups = result["required_group_count"]
    missing = result["missing_required_groups"]
    fail = []
    if not valid:
        fail.append("invalid")
    if missing:
        fail.append("missing_required")
    if result.get("unsupported_count"):
        fail.append("unsupported")
    if result.get("contradiction_count"):
        fail.append("contradiction")
    return {"pass": result["value"], "pass_status": "computed", "excluded_reason": None,
            "fail_reasons": fail, "errors": fail, "required_groups": groups,
            "matched_required_groups": groups - missing,
            "required_group_hits": result.get("required_group_hits", [False] * groups),
            "forbidden_hit": None}


def _evidence(track, ref, ground, rows):
    eligible = set(ref.get("evidence_reviewed_fields", []))
    accepted = ref.get("accepted_evidence_sets_by_relation", {})
    result = {}
    for field in CORE:
        gt = rows[field]["expected"]
        if gt not in ("P", "U"):
            continue
        if ground is None or field not in eligible:
            result[field] = {"status": "excluded", "reason": "evidence_not_reviewed"}
            continue
        expected = ref["relations"][field]
        sets = accepted.get(field) or [{"object_ids": expected["object_ids"], "region_ids": expected["region_ids"]}]
        unmeasurable = set(ground["regions"]["unmeasurable_reference_ids"])
        # A reference region with no measurable box cannot establish an exact ID match.
        if any(set(group["region_ids"]) & unmeasurable for group in sets):
            result[field] = {"status": "excluded", "reason": "reference_region_not_measurable"}
            continue
        if track is None:
            result[field] = {"status": "fail", "reason": "invalid_output"}
            continue
        pred = track["relations"][field]
        maps = {kind: {p["prediction_id"]: p["reference_id"] for p in ground[bucket]["0.5"]["pairs"]}
                for kind, bucket in (("object_ids", "objects"), ("region_ids", "regions"))}
        mapped = {kind: {maps[kind][i] for i in pred[kind] if i in maps[kind]} for kind in maps}
        unmatched = [i for kind in maps for i in pred[kind] if i not in maps[kind]]
        ok = not unmatched and pred["state"] == gt and any(
            all(mapped[k] == set(group[k]) for k in maps) for group in sets)
        result[field] = {"status": "pass" if ok else "fail", "reason": None if ok else "evidence_set_differs",
                         "mapped_ids": sorted(set().union(*mapped.values())), "unmatched_prediction_ids": unmatched}
    return result


def _display_rules(ref):
    if not ref.get("actions_reviewed") or not ref.get("objects_reviewed"):
        return None
    if not set((*CORE, "bottleneck")).issubset(ref.get("reviewed_fields", [])):
        return None
    groups, optional = policy(ref)
    def rule(pair):
        code, condition, ids = pair
        return {"code": code, "condition": condition, "based_on": sorted(ids)}
    def sorted_rules(pairs):
        return [rule(p) for p in sorted(pairs, key=lambda p: (p[0], p[1], sorted(p[2])))]
    return {"required_groups": [{"alternatives": sorted_rules(group)} for group in groups],
            "allowed_pairs": sorted_rules(set().union(*groups, optional)), "forbidden_pairs": []}


def score_item_v11(request, record, ref, schema):
    fmt = score.check_format(request["item_id"], record, schema)
    track = fmt["parsed"]["track1"] if fmt["valid"] else None
    ref = ref or {}
    reviewed = set(ref.get("reviewed_fields", []))
    usable = ref.get("schema_version") == VERSION and ref.get("annotation_status") == "Reviewed" and bool(reviewed)
    exclude = None if usable else "reference_not_reviewed" if ref else "reference_missing"
    if ref and ref.get("schema_version") != VERSION:
        exclude = "reference_version_mismatch"
    expected = all_observations(ref) if usable else {}
    pred = all_observations(track) if track else {}
    rows = {}
    for field in FIELDS:
        state = expected.get(field, {}).get("state") if field in reviewed else None
        # NA is a valid conditional field label for display, not a scored class.
        gt = state if state in STATES else None
        value = pred.get(field, {}).get("state")
        rows[field] = {"expected": gt if usable else "Missing", "predicted": value,
                       "match": gt == value if usable and gt is not None else None}
    out = {"item_id": request["item_id"], "data_kind": request.get("data_kind", "real"),
           "prediction_status": fmt["prediction_status"], "format_errors": fmt["errors"],
           "annotation_status": ref.get("annotation_status", "Missing"), "reference_version": ref.get("reference_version"),
           "schema_version": VERSION, "scored": usable, "excluded_reason": exclude,
           "relations": {k: rows[k] for k in CORE}, "context": {k: rows[k] for k in AUX}}
    ground = score.grounding(track, ref) if usable and ref.get("objects_reviewed") else None
    evidence = _evidence(track, ref, ground, rows) if usable else {}
    attributes = ref.get("attributes") or {}
    accepted_attrs = set(ref.get("attributes_reviewed_fields", [])) if usable else set()
    out["attributes"] = {k: {"expected": attributes.get(k) if k in accepted_attrs else None,
                             "predicted": track["attributes"][k] if track else None} for k in score.ATTR_FIELDS}
    blockers = []
    if not usable:
        blockers.append(exclude)
    elif set(FIELDS) - reviewed or not ref.get("objects_reviewed") or not ref.get("actions_reviewed"):
        blockers.append("reference_partial_review")
    out["diagnostics"] = {"grounding": ground, "evidence": evidence,
                          "benchmark": {"eligible": not blockers, "blockers": blockers}}
    out["action_eval"] = _action_row(track, ref, fmt["valid"]) if usable else {
        "pass": None, "pass_status": "excluded", "excluded_reason": exclude, "fail_reasons": [], "errors": []}
    return out


def aggregate_v11(results, requests):
    summary = score.aggregate(results, requests, relations=CORE)
    summary["schema_version"] = VERSION
    summary["context_metrics"] = {}
    for field in AUX:
        rows = [r["context"][field] for r in results if r["context"][field]["expected"] in STATES]
        summary["context_metrics"][field] = score.ratio(sum(r["match"] is True for r in rows), len(rows),
                                                        "no reviewed applicable field")
    return summary
