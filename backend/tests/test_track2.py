"""Track 2 scoring rules (spec App. D.1) on a temporary store with synthetic reviews/predictions."""
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from backend.app import main, store, track2_store as t2
from backend.scorer import track2
from backend.tools import track2_data

CLIP = "bb_1_180227_pedestrian_123_016"   # target visible at label frames 31..62 (t = 2.0 .. 4.067 s)


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    dst = tmp_path / "store"
    shutil.copytree(store.STORE, dst, ignore=shutil.ignore_patterns("results", "cache", "frames"))
    monkeypatch.setattr(store, "STORE", dst)
    return dst


def review(tmp_path, **kw):
    row = {"clip_id": CLIP, "reference_version": "t2-test-1", "reviewers": ["tester"], "event_time_status": "Reviewed",
           "event_frame": 64, "targets_confirmed": True, "horizon_s": 2.0, **kw}
    f = tmp_path / "rev.jsonl"
    f.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return track2_data.cmd_review(type("A", (), {"file": str(f), "dry_run": False})())


def add_run(run_id, preds):
    rd = t2.root() / "runs" / run_id
    for iid, p in preds.items():
        store.write_json(rd / "predictions" / f"{iid}.json", p)
    store.write_json(rd / "run.json", {"run_id": run_id, "track": "track2", "data_kind": "example", "label": "test"})
    store.write_json(rd / "requests.json", [{"item_id": i} for i in preds])


def sel(tid):
    return {"status": "ok", "output_text": json.dumps({"target_id": tid})}


def box(b):
    return {"status": "ok", "output_text": json.dumps({"bbox_xyxy": b})}


def test_draft_is_never_scored(tmp_store):
    its = {i: it for i, it in t2.items().items() if it["clip_id"] == CLIP}
    res = track2.score_run([{"item_id": i} for i in its], t2.items(), t2.references(), {})
    assert res["summary"]["n_eligible"] == 0
    assert res["summary"]["overall"]["target_acc"]["status"] == "not_applicable"
    assert set(res["summary"]["excluded"]) == {"reference_not_reviewed (Draft)"}


def test_denominator_bins_and_invalid(tmp_store, tmp_path):
    assert review(tmp_path)["ok"]
    its = {i: it for i, it in t2.items().items() if it["clip_id"] == CLIP}
    refs = t2.references()
    tc = (64 - 1) / 15  # 4.2 s
    preds = {}
    for i, it in its.items():
        tgt = refs[i]["target_candidate_ids"][0]
        gbox = refs[i]["target_box_xyxy_px"]
        preds[i] = {"select": sel(tgt), "box": box(gbox)}
    first = "t2_180227_123_016_f055"  # t = 3.6 s, tau = 0.6 s -> Positive, in the denominator
    preds[first] = {"select": {"status": "ok", "output_text": "```json\n{\"target_id\": 1}\n```"},
                    "box": {"status": "ok", "output_text": "not json"}}
    add_run("T2-TEST", preds)
    res = t2.score("T2-TEST", write=False)
    s = res["summary"]
    rows = {r["item_id"]: r for r in res["items"]}
    for i, it in its.items():
        tau = round(tc - it["decision_time_s"], 6)
        g = rows[i]["gt"]
        assert g["tau_s"] == tau
        assert g["label"] == ("Positive" if 0 < tau <= 2.0 else "Negative")
    eligible = [r for r in rows.values() if r["gt"]["eligible"]]
    assert len(eligible) == s["n_eligible"] > 0
    # the fence-wrapped / unreadable item stays in the denominator as wrong with IoU 0
    assert rows[first]["gt"]["eligible"] and rows[first]["gt"]["bin"] == "(0.5,1.0]"
    assert rows[first]["selection"]["status"] == "invalid" and rows[first]["selection"]["correct"] is False
    assert rows[first]["localization"]["iou"] == 0.0 and rows[first]["localization"]["acc50"] is False
    n_ok = sum(r["selection"]["correct"] for r in eligible)
    assert s["overall"]["target_acc"]["numerator"] == n_ok
    assert sum(b["target_acc"]["n"] for b in s["by_residual_time"].values()) == s["n_eligible"]
    assert s["overall"]["target_acc"]["ci_status"] == "not_applicable"  # one clip = one Source Group
    again = t2.score("T2-TEST", write=False)
    assert again["result_hash"] == res["result_hash"]


def test_event_missing_and_after_event(tmp_store, tmp_path):
    assert review(tmp_path, event_time_status="Missing", event_frame=None)["ok"]
    its = [i for i, it in t2.items().items() if it["clip_id"] == CLIP]
    res = track2.score_run([{"item_id": i} for i in its], t2.items(), t2.references(), {})
    assert set(res["summary"]["excluded"]) == {"event_time_missing"}
    gt = track2.ground_truth({"decision_time_s": 5.0}, {"annotation_status": "Reviewed", "event_time_s": 4.0,
                                                        "horizon_s": 2.0})
    assert gt["label"] == "AfterEvent" and not gt["eligible"]


def test_parsers():
    assert track2.parse_selection(sel(3), [1, 2, 3])["valid"]
    assert not track2.parse_selection(sel(9), [1, 2, 3])["valid"]
    assert not track2.parse_selection({"status": "ok", "output_text": '{"target_id": true}'}, [1])["valid"]
    assert track2.parse_box(box([1, 2, 30, 40]), 1920, 1080)["valid"]
    assert not track2.parse_box(box([30, 2, 1, 40]), 1920, 1080)["valid"]
    assert not track2.parse_box(box([0, 0, 2000, 40]), 1920, 1080)["valid"]
    assert track2.parse_box({"status": "timeout"}, 10, 10)["status"] == "timeout"


def test_review_requires_human_and_confirmed_targets(tmp_store, tmp_path):
    out = review(tmp_path, reviewers=[], targets_confirmed=False)
    assert not out["ok"] and len(out["errors"][CLIP]) == 2


def test_api(tmp_store, tmp_path):
    review(tmp_path)
    its = [i for i, it in t2.items().items() if it["clip_id"] == CLIP]
    add_run("T2-API", {i: {"select": sel(1), "box": box([0, 0, 10, 10])} for i in its})
    c = TestClient(main.app)
    assert c.get("/api/track2/runs").json()["runs"][0]["run_id"] == "T2-API"
    rep = c.get("/api/track2/runs/T2-API/report").json()
    assert set(rep["by_residual_time"]) == {"(0.0,0.5]", "(0.5,1.0]", "(1.0,1.5]", "(1.5,2.0]"}
    d = c.get(f"/api/track2/runs/T2-API/items/{its[0]}").json()
    assert d["video_url"] == f"/api/track2/videos/{CLIP}" and d["candidates"]
    assert c.get("/api/track2/runs/T2-API/items", params={"eligible": True}).json()["n"] == rep["n_eligible"]
