"""Create read-only review containers, never queue or generate model predictions."""
import json
from backend.app import store, jobs
from backend.scorer.v11.contract import VERSION


def main():
    ids = sorted(r for r in store.references(VERSION) if r.startswith("pilot_"))
    assert len(ids) == 6
    for letter in ("a", "b"):
        prompt = f"prompt_v11_{letter}"
        rid = f"RUN-PILOT6-V11-{letter.upper()}-PREVIEW"
        if store.run_meta(rid):
            continue
        meta = json.loads((jobs.PROMPTS / prompt / "prompt.json").read_text(encoding="utf-8"))
        run = {"run_id": rid, "data_kind": "real", "label": "v1.1 " + letter.upper() + " 검토용 · 추론 미실행",
               "schema_version": VERSION, "status": "review_only", "model": jobs.DEFAULT_MODEL,
               "prompt": meta, "decoding": jobs.DEFAULT_DECODING,
               "reference_version": "1.1-pm-ai-draft-20261120", "split_version": "v11-pilot-dev",
               "data_version": {"items": "pilot6-v11", "image_sha256": {i: store.items()[i]["image_sha256"] for i in ids}}}
        store.write_json(store.run_dir(rid) / "run.json", run)
        store.write_json(store.run_dir(rid) / "requests.json", [{"item_id": i, "data_kind": "real"} for i in ids])


if __name__ == "__main__":
    main()
