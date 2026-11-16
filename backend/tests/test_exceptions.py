"""Exception-handling checks required for the 11/15 deliverable (Role_Backend §3, §5, §6).

Inputs are the synthetic EXAMPLE-RUN-001 cases plus small in-memory variations.
Run: python -m pytest backend/tests -q
"""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import store
from backend.app.main import app
from backend.scorer.score import load_schema, match_boxes, score_run
from backend.tools import make_example_run as ex

RUN = "EXAMPLE-RUN-001"
SCHEMA = load_schema()


@pytest.fixture(scope="module")
def example_inputs():
    reqs = store.requests(RUN)
    preds = store.predictions(RUN)
    refs = {q["item_id"]: store.references()[q["item_id"]] for q in reqs}
    return reqs, preds, refs


@pytest.fixture(scope="module")
def example_result(example_inputs):
    return score_run(*example_inputs, schema=SCHEMA)


def by_id(res, iid):
    return next(r for r in res["items"] if r["item_id"] == iid)


# 1. format errors / timeouts stay in the request list as failures --------------------------------

def test_invalid_and_timeout_are_kept_and_counted(example_result):
    ids = [r["item_id"] for r in example_result["items"]]
    assert ids == [f"example_00{i}" for i in range(1, 6)]
    assert by_id(example_result, "example_002")["prediction_status"] == "invalid"
    assert by_id(example_result, "example_003")["prediction_status"] == "timeout"
    m = example_result["summary"]["metrics"]
    assert m["v1_valid"]["n"] == 5 and m["v1_valid"]["numerator"] == 3
    assert m["v2_invalid"]["numerator"] == 2
    # invalid counts as action failure (V10/V11) and stays in the V12 denominator
    for iid in ("example_002", "example_003"):
        ae = by_id(example_result, iid)["action_eval"]
        assert ae["pass"] is False and ae["fail_reasons"] == ["invalid"]
    assert m["v12_forbidden_rate"]["n"] == 3


def test_missing_prediction_record_is_not_dropped(example_inputs):
    reqs, preds, refs = example_inputs
    preds = {k: v for k, v in preds.items() if k != "example_001"}
    res = score_run(reqs, preds, refs, schema=SCHEMA)
    assert by_id(res, "example_001")["prediction_status"] == "not_returned"
    assert res["summary"]["metrics"]["v1_valid"]["n"] == 5


# 2. Missing / unreviewed GT excluded, U is a valid answer ---------------------------------------

def test_missing_and_draft_references_are_excluded(example_inputs):
    reqs, preds, refs = example_inputs
    refs = dict(refs)
    refs["example_001"] = {"item_id": "example_001", "annotation_status": "Missing"}
    res = score_run(reqs, preds, refs, schema=SCHEMA)
    assert by_id(res, "example_001")["excluded_reason"] == "reference_missing"
    assert by_id(res, "example_004")["excluded_reason"].startswith("reference_not_reviewed")
    assert res["summary"]["n_scored_items"] == 3
    # excluded items are still in V1/V2 (requests), just not in GT-based metrics
    assert res["summary"]["metrics"]["v1_valid"]["n"] == 5


def test_unknown_is_scored_as_a_valid_answer(example_inputs):
    reqs, preds, refs = example_inputs
    preds = copy.deepcopy(preds)
    p = json.loads(preds["example_001"]["raw_text"])
    p["track1"]["regions"] = [{"region_id": "reg_1", "type": "entrance_region",
                               "bbox_xyxy_norm": [0.05, 0.40, 0.20, 0.75], "polygon_xy_norm": None,
                               "geometry_status": "visible"}]
    p["track1"]["relations"]["R2"] = {"state": "U", "object_ids": ["obj_2"], "region_ids": ["reg_1"], "reason": "x",
                                      "roles": {"actor_ids": ["obj_2"], "entrance_candidate_id": "reg_1"}}
    preds["example_001"]["raw_text"] = json.dumps(p)
    res = score_run(reqs, preds, refs, schema=SCHEMA)
    row = by_id(res, "example_001")
    assert row["prediction_status"] == "valid", row["format_errors"]
    assert row["relations"]["R2"] == {"expected": "U", "predicted": "U", "match": True}
    assert res["summary"]["metrics"]["v8_unknown_recall"]["numerator"] == 1
    # U with the right evidence (pedestrian + entrance region) passes V4 for R2
    assert row["diagnostics"]["evidence"]["R2"]["status"] == "pass"


def test_relation_cell_missing_is_dropped_not_scored(example_inputs):
    reqs, preds, refs = example_inputs
    refs = copy.deepcopy(refs)
    refs["example_001"]["relations"]["R3"] = None
    res = score_run(reqs, preds, refs, schema=SCHEMA)
    assert by_id(res, "example_001")["relations"]["R3"]["match"] is None
    base = score_run(*example_inputs, schema=SCHEMA)
    assert res["summary"]["metrics"]["v7_false_positive_rate"]["n"] == \
        base["summary"]["metrics"]["v7_false_positive_rate"]["n"] - 1


# 3. Direction Match = Conflicting excluded from V10-V12 only ------------------------------------

def test_direction_conflict_only_leaves_action_metrics(example_result):
    row = by_id(example_result, "example_005")
    assert row["scored"] is True
    assert row["action_eval"]["excluded_reason"] == "direction_conflict"
    s = example_result["summary"]
    assert s["excluded_from_actions"]["direction_conflict"] == 1
    # action denominators: 001, 002, 003 (004 Draft, 005 conflict)
    assert s["metrics"]["v10_action_pass_rate"]["n"] == 3
    # relation metrics still include 005: 4 scored items x R1(P) -> V6 n == 4
    assert s["metrics"]["v6_present_recall"]["n"] == 4


# 4. denominator 0 and incomplete V5 -> N/A with reason -----------------------------------------

def test_zero_denominator_is_na_with_reason():
    reqs = [{"item_id": "x"}]
    res = score_run(reqs, {}, {}, schema=SCHEMA)
    for key in ("v4_evidence", "v6_present_recall", "v10_action_pass_rate", "v12_forbidden_rate"):
        metric = res["summary"]["metrics"][key]
        assert metric["status"] == "not_applicable" and metric["value"] is None and metric["reason"]
    assert res["summary"]["metrics"]["v13_statement_error_rate"]["status"] == "not_computed"


def test_v5_na_when_any_of_12_cells_empty(example_result):
    v5 = example_result["summary"]["metrics"]["v5_relation_macro_f1"]
    assert v5["status"] == "not_applicable" and v5["value"] is None
    assert "12 cells" in v5["reason"]
    assert v5["supported_class_macro_f1"]["value"] is not None


# 5. re-scoring is deterministic ----------------------------------------------------------------

def test_rescore_same_inputs_same_hash(example_inputs):
    a = score_run(*example_inputs, schema=SCHEMA)
    b = score_run(*copy.deepcopy(example_inputs), schema=SCHEMA)
    assert a["result_hash"] == b["result_hash"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# grounding: Hungarian must beat greedy ---------------------------------------------------------

def test_matching_maximises_pair_count_not_greedy():
    # IoU: p1-r1 0.905, p1-r2 0.6, p2-r1 0.538, p2-r2 0.25.
    # Greedy (best IoU first) takes p1-r1 and then p2 has nothing -> 1 pair. Optimum: p1-r2, p2-r1.
    box = lambda x0, x1: [x0, 0.1, x1, 0.9]
    preds = [{"object_id": "p1", "class": "car", "bbox_xyxy_norm": box(0.32, 0.72)},
             {"object_id": "p2", "class": "car", "bbox_xyxy_norm": box(0.18, 0.58)}]
    refs = [{"object_id": "r1", "class": "car", "bbox_xyxy_norm": box(0.30, 0.70)},
            {"object_id": "r2", "class": "car", "bbox_xyxy_norm": box(0.42, 0.82)}]
    out = match_boxes(preds, refs, 0.5)
    assert {(x["prediction_id"], x["reference_id"]) for x in out["pairs"]} == {("p1", "r2"), ("p2", "r1")}


def test_class_mismatch_never_pairs():
    p = [{"object_id": "p", "class": "car", "bbox_xyxy_norm": [0, 0, 1, 1]}]
    r = [{"object_id": "r", "class": "truck", "bbox_xyxy_norm": [0, 0, 1, 1]}]
    assert match_boxes(p, r, 0.5)["pairs"] == []


# API ---------------------------------------------------------------------------------------------

def test_api_detail_separates_input_and_reference():
    c = TestClient(app)
    d = c.get(f"/api/runs/{RUN}/items/example_001").json()
    assert "reference" in d and "input" in d
    assert "relations" not in d["input"] and "objects" not in d["input"]
    assert d["data_kind"] == "example"
    t = c.get(f"/api/runs/{RUN}/items/example_003").json()
    assert t["prediction"]["status"] == "timeout" and t["prediction"]["parsed"] is None
    rows = c.get(f"/api/runs/{RUN}/items", params={"fail_reason": "invalid"}).json()["items"]
    assert {r["item_id"] for r in rows} == {"example_002", "example_003"}
