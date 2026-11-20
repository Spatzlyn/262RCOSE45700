"""Integration regression using synthetic predictions only; no reported model results."""
import copy
import json
from backend.app import store
from backend.scorer.score import load_schema, score_run
from backend.scorer.v11.contract import VERSION, CORE, FIELDS, ACTION_FIELDS
from backend.tests.test_features import client, tmp_store, WRITE, WORKER

PREVIEW = "RUN-PILOT6-V11-A-PREVIEW"
BASE = "RUN-PILOT6-BASE-001"


def obs(s="A"):
    return {"state": s, "object_ids": [], "region_ids": [], "reason": "synthetic test"}


def prediction():
    return {"schema_version": VERSION, "item_id": "test", "track1": {
        "attributes": {"traffic_direction": "Unknown", "direction_match": "Unknown", "sidewalk_left": "A", "sidewalk_right": "A"},
        "objects": [], "regions": [], "relations": {k: obs() for k in CORE},
        "context": {"connection_actor": obs("NA"), "forward_occlusion": obs(), "lateral_occlusion": obs(), "bottleneck": obs()},
        "actions": [{"code": "MONITOR_AHEAD", "condition": "no_condition", "based_on": list(ACTION_FIELDS), "reason": "synthetic test"}], "unknowns": []},
        "track2": {"status": "missing_input", "target_object_id": None},
        "track3": {"status": "missing_input", "speed_change": None, "direction_change": None}}


def test_preview_not_scored_and_version_isolated(client):
    assert len(store.references(VERSION)) == 6
    assert all(x["annotation_status"] == "Draft" for x in store.references(VERSION).values())
    assert client.get(f"/api/runs/{PREVIEW}").json()["status"] == "review_only"
    report = client.get(f"/api/runs/{PREVIEW}/report").json()
    assert report["n_requests"] == 6 and report["n_scored_items"] == 0
    assert report["metrics"]["v1_valid"]["status"] == "not_computed"
    assert len(report["metrics"]["v5_relation_macro_f1"]["cells"]) == 9
    assert len(report["context_metrics"]) == 4
    assert client.get(f"/api/runs/{PREVIEW}/report/conditions?key=weather").json()["values"]["clear"]["metrics"]["v1_valid"]["status"] == "not_computed"
    detail = client.get(f"/api/runs/{PREVIEW}/items/pilot_002").json()
    assert detail["reference"]["driving_area"] and detail["prediction"]["parsed"] is None
    assert set(detail["scoring"]["relations"]) == set(CORE)
    assert client.get("/api/compare", params={"base": BASE, "target": PREVIEW}).json()["n"] == 0
    comp = client.get("/api/compare", params={"base": PREVIEW, "target": "RUN-PILOT6-V11-B-PREVIEW"}).json()
    assert comp["n"] == 6 and comp["summary"]["status"] == "not_applicable"
    assert len(client.get(f"/api/runs/{BASE}/report").json()["metrics"]["v5_relation_macro_f1"]["cells"]) == 12


def test_v11_catalog_and_queue(client):
    cat = client.get("/api/items", params={"data_kind": "real", "schema_version": VERSION}).json()
    assert cat["n"] == 12
    h = {"X-API-Key": WRITE}
    bad = client.post("/api/runs", headers=h, json={"item_ids": ["candidate_01009110"], "prompt_version": "prompt_v1"})
    assert bad.status_code == 422
    good = client.post("/api/runs", headers=h, json={"run_id": "TEST-V11", "item_ids": ["pilot_002"], "prompt_version": "prompt_v11_b"})
    assert good.status_code == 200
    assert store.run_version(store.run_meta("TEST-V11")) == VERSION
    client.post("/api/runs/TEST-V11/cancel", headers=h)
    assert client.get("/api/runs/TEST-V11/progress").json()["status"] == "cancelled"


def test_v11_worker_prompt_and_synthetic_result(client):
    from backend.worker.worker import build_messages, load_prompt
    for prompt in ("prompt_v11_a", "prompt_v11_b"):
        assert load_prompt(prompt)[0]["schema_version"] == VERSION
    h, hw = {"X-API-Key": WRITE}, {"X-API-Key": WORKER}
    assert client.post("/api/runs", headers=h, json={"run_id": "TEST-WORKER", "item_ids": ["pilot_002"], "prompt_version": "prompt_v11_a"}).status_code == 200
    job = client.get("/api/jobs/next", params={"worker": "test-worker"}, headers=hw).json()
    assert job["prompt"]["version"] == "prompt_v11_a"
    assert not {"relations", "objects", "driving_area", "reference"} & job["input"].keys()
    msgs = build_messages(job, "test-image.png")
    assert '"item_id": "pilot_002"' in msgs[1]["content"][1]["text"]
    assert "v1.1-review" in msgs[0]["content"]
    pred = prediction(); pred["item_id"] = "pilot_002"
    raw = json.dumps(pred)
    out = client.post("/api/jobs/TEST-WORKER/pilot_002/result", params={"worker": "test-worker"}, headers=hw,
                      json={"status": "ok", "raw_text": raw, "output_text": raw})
    assert out.status_code == 200
    report = client.get("/api/runs/TEST-WORKER/report").json()
    assert report["prediction_status_counts"] == {"valid": 1} and report["n_scored_items"] == 0


def test_all_negative_action_and_draft_exclusion():
    pred = prediction()
    ref = {**copy.deepcopy(pred["track1"]), "schema_version": VERSION, "item_id": "test",
           "annotation_status": "Reviewed", "reviewed_fields": list(FIELDS), "objects_reviewed": True,
           "actions_reviewed": True, "attributes_reviewed_fields": ["direction_match"]}
    req = [{"item_id": "test", "data_kind": "example"}]
    record = {"test": {"status": "ok", "raw_text": json.dumps(pred), "output_text": json.dumps(pred)}}
    result = score_run(req, record, {"test": ref}, schema=load_schema(VERSION), bootstrap_b=0)
    row = result["items"][0]
    assert row["prediction_status"] == "valid" and row["action_eval"]["pass"] is True
    assert row["context"]["connection_actor"]["match"] is None
    assert result["summary"]["metrics"]["v12_forbidden_rate"]["status"] != "computed"
    ref["annotation_status"] = "Draft"
    result = score_run(req, record, {"test": ref}, schema=load_schema(VERSION), bootstrap_b=0)
    assert result["summary"]["n_scored_items"] == 0
    assert result["items"][0]["action_eval"]["pass"] is None


def test_wrong_conditional_basis_and_v11_rollup():
    pred = prediction()
    ref = {**copy.deepcopy(pred["track1"]), "schema_version": VERSION, "item_id": "test", "annotation_status": "Reviewed",
           "reviewed_fields": list(FIELDS), "objects_reviewed": True, "actions_reviewed": True,
           "attributes_reviewed_fields": ["direction_match"]}
    pred["track1"]["actions"][0]["based_on"] = ["R1"]
    req = [{"item_id": "test"}]
    record = {"test": {"status": "ok", "output_text": json.dumps(pred)}}
    row = score_run(req, record, {"test": ref}, schema=load_schema(VERSION), bootstrap_b=0)["items"][0]
    assert row["action_eval"]["pass"] is False
    pred["track1"]["context"]["forward_occlusion"] = obs("U")
    record["test"]["output_text"] = json.dumps(pred)
    row = score_run(req, record, {"test": ref}, schema=load_schema(VERSION), bootstrap_b=0)["items"][0]
    assert row["prediction_status"] != "valid"


def test_quality_leak_and_freeze_not_promoted(client):
    quality = client.get("/api/quality", params={"schema_version": VERSION}).json()
    assert quality["l1_l2"]["status"] == "not_computed" and quality["l3"]["n_reviewed"] == 0
    assert len(quality["l3"]["empty_cells"]) == 9
    split = store.split("v11-pilot-dev")
    assert len(split["assignments"]) == 7 and set(split["assignments"].values()) == {"dev"}
    assert client.get("/api/datasets/v11-pilot-dev/leak-check").json()["passed"] is True
    assert client.post("/api/datasets/v11-pilot-dev/freeze", headers={"X-API-Key": WRITE}).status_code == 409
