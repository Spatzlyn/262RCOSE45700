"""Separate v1.1 evaluation entry point. Current v1.0 backend remains usable."""
from __future__ import annotations

from .contract import ACTION_FIELDS, CORE, FIELDS, STATES, VERSION, all_observations, validate


def rule(code, condition, *based_on):
    return (code, condition, frozenset(based_on))


def action_key(action):
    return rule(action["code"], action["condition"], *action["based_on"])


def policy(track):
    """Return required alternative groups and additional allowed pairs."""
    obs = all_observations(track)
    groups, optional = [], set()
    if obs["R1"]["state"] == "P":
        occupied = set(obs["R1"]["object_ids"])
        objects = [o for o in track["objects"] if o["object_id"] in occupied]
        fixed = [o for o in objects if o["semantic_role"] == "obstacle"
                 or (o["class"] in ("car", "truck") and o["placement"] == "roadside")]
        movable = [o for o in objects if o["semantic_role"] == "actor" and o not in fixed]
        if movable:
            groups.append({rule("YIELD_IF_OCCUPIED", "while_corridor_occupied", "R1"),
                           rule("HOLD_UNTIL_CLEAR", "while_corridor_occupied", "R1")})
        if fixed:
            groups.append({rule("VERIFY_PASSAGE", "before_passing_occupying_object", "R1")})
            optional.add(rule("HOLD_UNTIL_CLEAR", "while_corridor_occupied", "R1"))
    if obs["R2"]["state"] == "P":
        groups.append({rule("MONITOR_AHEAD", "at_connected_opening", "R2"),
                       rule("REDUCE_SPEED_IF_MOVING", "at_connected_opening", "R2")})
    if obs["R3"]["state"] == "P":
        groups.append({rule("VERIFY_BEFORE_ADVANCE", "before_entering_occluded_area", "R3")})
    if obs["bottleneck"]["state"] == "P":
        groups.append({rule("VERIFY_PASSAGE", "before_passing_restricted_section", "bottleneck")})
    uncertain = [key for key in ACTION_FIELDS if obs[key]["state"] == "U"]
    if uncertain:
        groups.append({rule("VERIFY_BEFORE_ADVANCE", "before_resolving_uncertainty", *uncertain)})
    if all(obs[key]["state"] == "A" for key in ACTION_FIELDS):
        groups.append({rule("MONITOR_AHEAD", "no_condition", *ACTION_FIELDS),
                       rule("ADVANCE_WITH_MONITORING", "no_condition", *ACTION_FIELDS)})
    return groups, optional


def no_score(reason):
    return {"status": "not_computed", "value": None, "reason": reason, "n": 0}


def check_actions(prediction, reference, valid):
    if not reference.get("actions_reviewed") or not reference.get("objects_reviewed"):
        return no_score("action_or_object_roles_not_reviewed")
    if not set(ACTION_FIELDS).issubset(reference.get("reviewed_fields", [])):
        return no_score("action_condition_fields_not_reviewed")
    if reference.get("attributes", {}).get("direction_match") == "Conflicting":
        return no_score("direction_conflicting")
    if "direction_match" not in reference.get("attributes_reviewed_fields", []) or reference.get("attributes", {}).get("direction_match") not in (
        "Consistent", "Unknown", "Not applicable"
    ):
        return no_score("direction_match_not_reviewed")
    robs = all_observations(reference)
    if any(robs.get(k, {}).get("state") not in STATES for k in ACTION_FIELDS):
        return no_score("action_condition_fields_missing")
    objs = {o["object_id"]: o for o in reference["objects"]}
    if robs["R1"]["state"] == "P":
        ids = robs["R1"]["object_ids"]
        if not ids or any(oid not in objs or objs[oid].get("semantic_role") not in ("actor", "obstacle")
                          or objs[oid].get("placement") not in ("roadside", "travel_space", "entrance", "unknown")
                          for oid in ids):
            return no_score("occupant_type_or_placement_not_reviewed")
    expected, optional = policy(reference)
    if not valid:
        return {"status": "computed", "value": False, "reason": "invalid_output", "n": 1,
                "missing_required_groups": len(expected), "required_group_count": len(expected)}
    own, own_optional = policy(prediction["track1"])
    actual = {action_key(action) for action in prediction["track1"]["actions"]}
    allowed = set().union(*expected, optional)
    own_allowed = set().union(*own, own_optional)
    missing = sum(not (actual & group) for group in expected)
    unsupported = actual - allowed
    contradictory = actual - own_allowed
    return {"status": "computed", "value": not (missing or unsupported or contradictory),
            "n": 1, "missing_required_groups": missing, "required_group_count": len(expected),
            "required_group_hits": [bool(actual & group) for group in expected],
            "unsupported_count": len(unsupported), "contradiction_count": len(contradictory)}


def score_item(prediction, reference):
    """Only reference fields explicitly accepted by a human reviewer enter scores."""
    if reference.get("schema_version") != VERSION:
        return {"item_id": reference.get("item_id"), "status": "excluded",
                "reason": "reference_version_mismatch", "fields": {}, "action": no_score("version_mismatch")}
    if reference.get("annotation_status") != "Reviewed":
        return {"item_id": reference["item_id"], "status": "excluded",
                "reason": "reference_not_reviewed", "fields": {}, "action": no_score("reference_not_reviewed")}
    errors = validate(prediction, reference["item_id"]) if prediction is not None else ["missing_output"]
    valid = not errors
    actual = all_observations(prediction["track1"]) if valid else {}
    expected = all_observations(reference)
    fields = {}
    for key in FIELDS:
        if key not in reference.get("reviewed_fields", []):
            continue
        gold = expected.get(key, {}).get("state")
        if gold not in STATES:
            # NA means the dependent field does not apply, not a negative or a fourth class.
            continue
        pred = actual.get(key, {}).get("state")
        fields[key] = {"expected": gold, "predicted": pred, "match": gold == pred}
    return {"item_id": reference["item_id"], "status": "compared", "valid": valid,
            "errors": errors, "fields": fields, "action": check_actions(prediction, reference, valid)}


def summarize(results):
    field_metrics, class_scores = {}, []
    for key in FIELDS:
        rows = [r["fields"][key] for r in results if key in r["fields"]]
        matches = sum(row["match"] for row in rows)
        field_metrics[key] = {"n": len(rows), "correct": matches,
                              "value": matches / len(rows) if rows else None,
                              "status": "computed" if rows else "not_computed"}
        if key not in CORE:
            continue
        for state in STATES:
            tp = sum(r["expected"] == state and r["predicted"] == state for r in rows)
            support = sum(r["expected"] == state for r in rows)
            fp = sum(r["expected"] != state and r["predicted"] == state for r in rows)
            class_scores.append({"field": key, "state": state, "support": support,
                                 "f1": 2 * tp / (support + tp + fp) if support else None})
    all_supported = all(c["support"] for c in class_scores)
    actions = [r["action"]["value"] for r in results if r["action"]["status"] == "computed"]
    return {
        "schema_version": VERSION, "n_requests": len(results),
        "excluded": sum(r["status"] == "excluded" for r in results),
        "field_metrics": field_metrics, "relation_classes": class_scores,
        "V5_core_macro_f1": {"status": "computed" if all_supported else "not_computed",
                              "value": sum(c["f1"] for c in class_scores) / 9 if all_supported else None,
                              "reason": None if all_supported else "requires reviewed support for all 9 R1-R3 states"},
        "V10_action_pass": {"status": "computed" if actions else "not_computed",
                            "value": sum(actions) / len(actions) if actions else None,
                            "n": len(actions)},
    }
