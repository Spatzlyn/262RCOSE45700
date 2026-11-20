"""Install the six reviewed-Draft references and version-specific candidate catalog."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from backend.app import store
from backend.scorer.v11.contract import VERSION, FIELDS
from backend.tools.import_references import import_references


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="pilot_1115 root")
    ap.add_argument("--drafts", type=Path, required=True, help="pilot_draft.json")
    ap.add_argument("--forms", type=Path, required=True)
    args = ap.parse_args()
    items = store.items()
    manifest = list(csv.DictReader((args.data / "pilot_manifest.csv").open(encoding="utf-8")))
    groups = {r["source_group_id"] for r in manifest if r["pilot_id"]}
    dev = {}
    blank = []
    for row in manifest:
        img = row["image_file"]
        iid = row["pilot_id"] or "candidate_" + img.split("_")[-2]
        source = args.data / ("Pilot" if row["pilot_id"] else "02_candidates") / "images" / img
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["image_sha256"], img
        if iid in items and items[iid].get("image_sha256") != row["image_sha256"]:
            raise ValueError(f"catalog conflict: {iid}")
        if iid not in items:
            items[iid] = {"item_id": iid, "data_kind": "real", "image_file": img,
                          "image_relpath": f"{img[1]}/{img}", "image_sha256": row["image_sha256"],
                          "image_size": {"width": 1920, "height": 1080}, "source_dataset": "aihub_71784",
                          "conditions": dict(zip(("scenario", "road", "time", "weather"), img.split("_")[1:5])),
                          "task": "track1_current_scene", "input_type": "single_image",
                          "schema_versions": [VERSION]}
        items[iid]["source_group_id"] = row["source_group_id"]
        if row["source_group_id"] in groups:
            dev[iid] = "dev"
        if not row["pilot_id"]:
            blank.append({"schema_version": VERSION, "item_id": iid, "image_file": img,
                          "image_sha256": row["image_sha256"], "source_group_id": row["source_group_id"],
                          "annotator": "", "annotator_kind": "human", "stage": "pre_consensus", "seconds": None,
                          "driving_area": [], "fields": dict.fromkeys(FIELDS),
                          "reasons": dict.fromkeys(FIELDS, ""), "regions": [], "objects": []})
    (store.STORE / "items.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in items.values()), encoding="utf-8")
    rows = json.loads(args.drafts.read_text(encoding="utf-8"))
    for r in rows:
        r["source_group_id"] = items[r["item_id"]]["source_group_id"]
    p = args.forms / "pilot6_v11_draft.jsonl"
    args.forms.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in rows), encoding="utf-8")
    result = import_references(p, False)
    if not result["ok"]:
        raise ValueError(result)
    store.write_json(store.STORE/"splits"/"v11-pilot-dev.json",
                     {"version": "v11-pilot-dev", "schema_version": VERSION, "assignments": dev})
    selected = [r for r in blank if r["item_id"] in ("candidate_01009110","candidate_01036668","candidate_01001486")]
    (args.forms / "independent_blind_3.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in selected), encoding="utf-8")
    (args.forms / "candidate_blank_all6.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in blank), encoding="utf-8")
    print(result, "candidate forms", len(blank), "dev group assignments", len(dev))


if __name__ == "__main__":
    main()
