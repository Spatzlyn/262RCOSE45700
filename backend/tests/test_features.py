"""Bootstrap/comparison, V13/V14 input, L1–L3, leak check/freeze, inference queue, auth, imports.

All write tests run against a temporary copy of backend/store.
"""
import copy
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from backend.app import main, store
from backend.scorer import quality, stats
from backend.scorer.score import aggregate, load_schema, score_run, statement_metrics
from backend.tools import import_references as imp

SCHEMA = load_schema()
WRITE, WORKER = "test-write-key", "test-worker-key"


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    dst = tmp_path / "store"
    shutil.copytree(store.STORE, dst, ignore=shutil.ignore_patterns("results", "cache"))
    monkeypatch.setattr(store, "STORE", dst)
    monkeypatch.setenv("API_WRITE_KEY", WRITE)
    monkeypatch.setenv("WORKER_KEY", WORKER)
    return dst


@pytest.fixture()
def client(tmp_store):
    return TestClient(main.app)


def example():
    reqs = store.requests("EXAMPLE-RUN-001")
    refs = store.references()
    return reqs, store.predictions("EXAMPLE-RUN-001"), {q["item_id"]: refs[q["item_id"]] for q in reqs}


# ---------------------------------------------------------------- bootstrap / comparison

def big_run(n_groups=12, per_group=2, flip=()):
    """Synthetic scored rows: each item is a copy of example_001 (valid, Reviewed)."""
    reqs, preds, refs = example()
    base = score_run(reqs[:1], preds, refs, schema=SCHEMA, bootstrap_b=0)["items"][0]
    rows, rq, groups = [], [], {}
    for g in range(n_groups):
        for k in range(per_group):
            iid = f"g{g}_{k}"
            r = copy.deepcopy(base)
            r["item_id"] = iid
            if iid in flip:
                r["action_eval"].update({"pass": True, "fail_reasons": [], "forbidden_hit": False,
                                         "matched_required_groups": r["action_eval"]["required_groups"]})
            rows.append(r)
            rq.append({"item_id": iid})
            groups[iid] = f"grp{g}"
    return rows, rq, groups


def test_group_bootstrap_is_deterministic_and_group_level():
    rows, rq, groups = big_run()
    a = stats.group_bootstrap(rows, rq, groups, aggregate, B=300, seed=1)
    b = stats.group_bootstrap(rows, rq, groups, aggregate, B=300, seed=1)
    assert a == b
    assert a["v6_present_recall"]["n_groups"] == 12


def test_bootstrap_na_without_groups_or_single_group():
    rows, rq, _ = big_run()
    out = stats.group_bootstrap(rows, rq, {}, aggregate, B=50)
    assert out["v6_present_recall"]["ci_status"] == "not_applicable"
    assert "source_group_id missing" in out["v6_present_recall"]["ci_reason"]
    one = {q["item_id"]: "same" for q in rq}
    assert "only one Source Group" in stats.group_bootstrap(rows, rq, one, aggregate, B=50)["v4_evidence"]["ci_reason"]


def test_paired_comparison_improved_only_when_interval_excludes_zero():
    base, rq, groups = big_run()
    flip_all = {q["item_id"] for q in rq}
    tgt, _, _ = big_run(flip=flip_all)
    out = stats.paired_comparison(base, rq, tgt, rq, groups, aggregate, B=300)
    v10 = out["metrics"]["v10_action_pass_rate"]
    assert v10["delta"] == 1.0 and v10["judgement"] == "improved"
    same = stats.paired_comparison(base, rq, base, rq, groups, aggregate, B=300)
    assert same["metrics"]["v10_action_pass_rate"]["judgement"] == "not_confirmed"


def test_comparison_needs_same_request_list():
    base, rq, groups = big_run()
    out = stats.paired_comparison(base, rq, base[:-1], rq[:-1], groups, aggregate, B=10)
    assert out["status"] == "not_applicable"


# ---------------------------------------------------------------- V13 / V14

def test_statement_metrics_only_from_human_reviews():
    na = statement_metrics(None, 5)
    assert na["v13_statement_error_rate"]["status"] == "not_computed"
    reviews = [{"item_id": "a", "reviewer": "r", "explanation_present": True, "review_complete": True,
                "statements": [{"text": "x", "error": True}, {"text": "y", "error": False}]},
               {"item_id": "b", "reviewer": "r", "explanation_present": True, "review_complete": True,
                "statements": [{"text": "z", "error": False}]},
               {"item_id": "c", "reviewer": "r", "explanation_present": True, "review_complete": False,
                "statements": [{"text": "w", "error": True}]}]
    m = statement_metrics(reviews, 4)
    assert m["v13_statement_error_rate"]["value"] == round(1 / 3, 6)
    assert m["v14_answer_with_error_rate"]["value"] == 0.5
    assert m["explanation_completion_rate"]["value"] == 0.5


# ---------------------------------------------------------------- L1–L3, leak, freeze

def test_agreement_l1_kappa_and_pe1():
    rounds = [{"item_id": i, "annotator": a, "fields": {"R1": v, "R3": "A"}}
              for i, (va, vb) in enumerate([("P", "P"), ("A", "A"), ("P", "A"), ("U", "U")])
              for a, v in (("A", va), ("B", vb))]
    out = quality.agreement(rounds)["fields"]
    assert out["R1"]["l1"] == 0.75 and out["R1"]["l2_kappa"] is not None
    assert out["R3"]["l2_kappa"] is None and out["R3"]["l2_status"] == "not_applicable"
    assert quality.agreement([])["status"] == "not_computed"


def test_leak_check_and_freeze():
    items = {"a": {"source_group_id": "g1"}, "b": {"source_group_id": "g1"}, "c": {"source_group_id": "g2"}}
    bad = quality.leak_check({"version": "v", "assignments": {"a": "train", "b": "test", "c": "test"}}, items)
    assert not bad["passed"] and bad["group_split_check"]["groups_in_multiple_splits"] == {"g1": ["test", "train"]}
    ok_split = {"version": "v", "assignments": {"a": "train", "b": "train", "c": "test"}}
    assert quality.leak_check(ok_split, items)["passed"]
    refs = {"c": {"item_id": "c", "annotation_status": "Draft"}}
    assert not quality.freeze_manifest(ok_split, items, refs, "x", "y")["frozen"]
    refs["c"]["annotation_status"] = "Reviewed"
    man = quality.freeze_manifest(ok_split, items, refs, "x", "y")
    assert man["frozen"] and man["item_ids"] == ["c"]
    late = {"a": {"source_group_id": "g", "decision_time": 10, "input_frames": [{"timestamp": 11}]}}
    assert quality.leak_check({"assignments": {"a": "test"}}, late)["timestamp_check"]["status"] == "fail"


# ---------------------------------------------------------------- auth + queue

def test_write_endpoints_need_key(client):
    assert client.post("/api/runs/EXAMPLE-RUN-001/rescore").status_code == 401
    assert client.post("/api/runs/EXAMPLE-RUN-001/rescore", headers={"X-API-Key": WRITE}).status_code == 200
    assert client.get("/api/jobs/next", params={"worker": "w"}, headers={"X-API-Key": WRITE}).status_code == 401


def test_queue_keeps_every_request_and_first_response(client):
    h, hw = {"X-API-Key": WRITE}, {"X-API-Key": WORKER}
    r = client.post("/api/runs", headers=h, json={"run_id": "RUN-T", "item_ids": ["pilot_001", "pilot_002",
                                                                                  "pilot_003"]})
    assert r.status_code == 200, r.text
    job = client.get("/api/jobs/next", params={"worker": "w1"}, headers=hw).json()
    assert job["item_id"] == "pilot_001" and job["prompt"]["version"] == "prompt_v1"
    assert "relations" not in json.dumps(job["input"])  # no GT in model input
    text = store.predictions("RUN-PILOT6-BASE-001")["pilot_001"]["output_text"]
    ok = client.post("/api/jobs/RUN-T/pilot_001/result", params={"worker": "w1"}, headers=hw,
                     json={"status": "ok", "raw_text": text + "<turn|>", "output_text": text})
    assert ok.status_code == 200
    again = client.post("/api/jobs/RUN-T/pilot_001/result", params={"worker": "w1"}, headers=hw,
                        json={"status": "ok", "raw_text": "x", "output_text": "x"})
    assert again.status_code == 409
    job2 = client.get("/api/jobs/next", params={"worker": "w1"}, headers=hw).json()
    client.post(f"/api/jobs/RUN-T/{job2['item_id']}/result", params={"worker": "w1"}, headers=hw,
                json={"status": "timeout", "error": "max_time"})
    client.post("/api/runs/RUN-T/cancel", headers=h)
    prog = client.get("/api/runs/RUN-T/progress").json()
    assert prog["counts"] == {"done": 1, "timeout": 1, "cancelled": 1} and prog["status"] == "cancelled"
    rep = client.get("/api/runs/RUN-T/report").json()
    assert rep["n_requests"] == 3
    assert rep["prediction_status_counts"] == {"valid": 1, "timeout": 1, "cancelled": 1}


def test_create_run_validates_items(client):
    r = client.post("/api/runs", headers={"X-API-Key": WRITE}, json={"item_ids": ["nope"]})
    assert r.status_code == 422


# ---------------------------------------------------------------- read endpoints

def test_catalog_conditions_export_versions(client):
    assert client.get("/api/items").json()["n"] == 11
    cond = client.get("/api/runs/RUN-PILOT6-BASE-001/report/conditions", params={"key": "weather"}).json()
    assert set(cond["values"]) == {"clear", "rainy"} and all(v["exploratory"] for v in cond["values"].values())
    csv_text = client.get("/api/runs/RUN-PILOT6-BASE-001/export", params={"format": "csv"}).content.decode("utf-8-sig")
    assert csv_text.splitlines()[0].startswith("item_id,") and len(csv_text.splitlines()) == 7
    v = client.get("/api/versions").json()
    assert v["prompt_versions"] == ["prompt_v1"]
    q = client.get("/api/quality").json()
    assert q["l1_l2"]["status"] == "not_computed" and q["l3"]["n_reviewed"] == 4


def test_report_with_base(client):
    rep = client.get("/api/runs/EXAMPLE-RUN-001/report", params={"base": "EXAMPLE-RUN-001"}).json()
    assert rep["comparison"]["status"] == "computed"
    assert rep["comparison"]["core"]["judgement"] in ("not_confirmed", "not_applicable")


# ---------------------------------------------------------------- imports

def test_import_references_validates_and_versions(tmp_store, tmp_path):
    good = dict(store.references()["example_001"], item_id="pilot_001", reference_version="t-1")
    bad = {"item_id": "pilot_002", "annotation_status": "Reviewed", "relations": {"R1": "X"}}
    f = tmp_path / "refs.jsonl"
    f.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
    out = imp.import_references(f, dry=False)
    assert not out["ok"] and "pilot_002" in out["errors"]
    f.write_text(json.dumps(good) + "\n", encoding="utf-8")
    assert imp.import_references(f, dry=False)["ok"]
    assert store.references()["pilot_001"]["annotation_status"] == "Reviewed"
    changed = dict(good, relations={**good["relations"], "R3": {"state": "P"}})
    f.write_text(json.dumps(changed) + "\n", encoding="utf-8")
    assert not imp.import_references(f, dry=False)["ok"]  # same version, different content
