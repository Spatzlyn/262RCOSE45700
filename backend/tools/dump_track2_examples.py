"""Track 2 example API responses for the frontend (synthetic review + synthetic predictions, temp store).

  python -m backend.tools.dump_track2_examples
Writes backend/examples/track2/*.json. Nothing here is a real result: the first-contact frame (64 for
clip 180227) is an assumed value and the predictions are made up to cover correct / wrong / invalid cases.
"""
import json
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main, store, track2_store as t2
from backend.tools import track2_data

OUT = Path(__file__).resolve().parents[1] / "examples" / "track2"
CLIP = "bb_1_180227_pedestrian_123_016"


def main_():
    real = store.STORE
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "store"
        shutil.copytree(real, dst, ignore=shutil.ignore_patterns("results", "cache"))
        store.STORE = dst
        try:
            f = Path(tmp) / "rev.jsonl"
            f.write_text(json.dumps({"clip_id": CLIP, "reference_version": "t2-EXAMPLE-not-real",
                                     "reviewers": ["example"], "event_time_status": "Reviewed", "event_frame": 64,
                                     "targets_confirmed": True, "horizon_s": 2.0}) + "\n", encoding="utf-8")
            track2_data.cmd_review(type("A", (), {"file": str(f), "dry_run": False})())
            refs = t2.references()
            its = sorted(i for i, it in t2.items().items() if it["clip_id"] == CLIP)
            preds = {}
            for k, iid in enumerate(its):
                tgt, gb = refs[iid]["target_candidate_ids"][0], refs[iid]["target_box_xyxy_px"]
                shifted = [gb[0] + 40, gb[1] + 20, gb[2] + 40, gb[3] + 20]
                preds[iid] = [
                    {"select": {"status": "ok", "output_text": json.dumps({"target_id": tgt})},
                     "box": {"status": "ok", "output_text": json.dumps({"bbox_xyxy": shifted})}},
                    {"select": {"status": "ok", "output_text": json.dumps({"target_id": 1 if tgt != 1 else 2})},
                     "box": {"status": "ok", "output_text": json.dumps({"bbox_xyxy": [10, 10, 60, 120]})}},
                    {"select": {"status": "ok", "output_text": "```json\n{\"target_id\": %d}\n```" % tgt},
                     "box": {"status": "timeout", "error": "generation timed out (example)"}},
                ][k % 3]
            rd = t2.root() / "runs" / "T2-EXAMPLE-RUN"
            for iid, p in preds.items():
                store.write_json(rd / "predictions" / f"{iid}.json", p)
            store.write_json(rd / "run.json", {"run_id": "T2-EXAMPLE-RUN", "track": "track2", "data_kind": "example",
                                               "label": "Track 2 example (synthetic GT and predictions)"})
            store.write_json(rd / "requests.json", [{"item_id": i, "data_kind": "example"} for i in its])
            c = TestClient(main.app)
            calls = [("items", "/api/track2/items"), ("runs", "/api/track2/runs"),
                     ("report", "/api/track2/runs/T2-EXAMPLE-RUN/report"),
                     ("run_items", "/api/track2/runs/T2-EXAMPLE-RUN/items")]
            calls += [(f"run_item_{i[-4:]}", f"/api/track2/runs/T2-EXAMPLE-RUN/items/{i}") for i in its[3:6]]
            OUT.mkdir(parents=True, exist_ok=True)
            for name, url in calls:
                r = c.get(url)
                r.raise_for_status()
                body = {"_request": f"GET {url}",
                        "_note": "SYNTHETIC example: assumed contact frame 64 and made-up predictions, not a result",
                        **r.json()}
                (OUT / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"wrote {len(calls)} files to {OUT}")
        finally:
            store.STORE = real


if __name__ == "__main__":
    main_()
