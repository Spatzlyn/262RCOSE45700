"""Write the synthetic EXAMPLE-RUN-001 into backend/store (data_kind = "example").

Every value here is made up for screen development and exception tests. It is not a model
result and the references are not real GT.
  python -m backend.tools.make_example_run
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "store"
RUN_ID = "EXAMPLE-RUN-001"
EX = "example"


def rel(state, objs=(), regs=(), roles=None, reason="example"):
    return {"state": state, "object_ids": list(objs), "region_ids": list(regs), "reason": reason,
            "roles": roles}


def prediction(item_id):
    return {
        "item_id": item_id,
        "track1": {
            "attributes": {"traffic_direction": "Two-way", "direction_match": "Not applicable",
                           "sidewalk_left": "A", "sidewalk_right": "A"},
            "objects": [
                {"object_id": "obj_1", "class": "car", "bbox_xyxy_norm": [0.40, 0.40, 0.60, 0.70],
                 "semantic_role": "actor", "placement": "travel_space", "truncated": "A"},
                {"object_id": "obj_2", "class": "pedestrian", "bbox_xyxy_norm": [0.10, 0.45, 0.15, 0.70],
                 "semantic_role": "actor", "placement": "roadside", "truncated": "A"},
                {"object_id": "obj_3", "class": "truck", "bbox_xyxy_norm": [0.80, 0.30, 0.95, 0.60],
                 "semantic_role": "actor", "placement": "roadside", "truncated": "A"}],
            "relations": {
                "R1": rel("P", ["obj_1"], roles={"actor_ids": ["obj_1"], "obstacle_ids": []}),
                "R2": rel("A", roles={"actor_ids": [], "entrance_candidate_id": None}),
                "R3": rel("A", roles={"occluder_ids": [], "occluded_region_id": None}),
                "R4": rel("A", roles={"restricting_object_ids": []})},
            "actions": [
                {"code": "YIELD_IF_OCCUPIED", "condition": "while_corridor_occupied", "based_on": ["R1"],
                 "reason": "example"},
                {"code": "ADVANCE_WITH_MONITORING", "condition": "no_condition", "based_on": ["R2"],
                 "reason": "example"}],
            "unknowns": [], "regions": []},
        "track2": {"status": "missing_input", "target_object_id": None},
        "track3": {"status": "missing_input", "speed_change": None, "direction_change": None}}


def reference(item_id, status="Reviewed", direction_match="Not applicable"):
    return {
        "item_id": item_id, "data_kind": EX, "annotation_status": status, "reference_version": "example-ref-0.1",
        "evidence_reviewed": True, "object_coverage_complete": True,
        "attributes": {"traffic_direction": "Two-way", "direction_match": direction_match,
                       "sidewalk_left": "A", "sidewalk_right": "A"},
        "objects": [
            {"object_id": "G_car", "class": "car", "bbox_xyxy_norm": [0.41, 0.42, 0.61, 0.71],
             "semantic_role": "actor", "placement": "travel_space"},
            {"object_id": "G_ped", "class": "pedestrian", "bbox_xyxy_norm": [0.11, 0.46, 0.16, 0.72],
             "semantic_role": "actor", "placement": "entrance"}],
        "regions": [
            {"region_id": "G_C", "type": "driving_area", "bbox_xyxy_norm": None,
             "polygon_xy_norm": [[0.2, 0.95], [0.8, 0.95], [0.55, 0.35], [0.45, 0.35]], "geometry_status": "reviewed"},
            {"region_id": "G_entrance", "type": "entrance_region", "bbox_xyxy_norm": [0.05, 0.40, 0.20, 0.75],
             "polygon_xy_norm": None, "geometry_status": "reviewed"},
            {"region_id": "G_hidden", "type": "occluded_road_region", "bbox_xyxy_norm": None,
             "polygon_xy_norm": None, "geometry_status": "unmeasurable_hidden_extent"}],
        "relations": {
            "R1": {"state": "P", "object_ids": ["G_car"], "region_ids": ["G_C"], "reason": "example"},
            "R2": {"state": "U", "object_ids": ["G_ped"], "region_ids": ["G_entrance"], "reason": "example"},
            "R3": {"state": "A", "object_ids": [], "region_ids": [], "reason": "example"},
            "R4": {"state": "A", "object_ids": [], "region_ids": [], "reason": "example"}},
        "accepted_evidence_sets_by_relation": {
            "R1": [{"object_ids": ["G_car"], "region_ids": []}],
            "R2": [{"object_ids": ["G_ped"], "region_ids": ["G_entrance"]}]},
        "action_rules": {
            "required_groups": [
                {"alternatives": [
                    {"code": "YIELD_IF_OCCUPIED", "condition": "while_corridor_occupied", "based_on": ["R1"]},
                    {"code": "HOLD_UNTIL_CLEAR", "condition": "while_corridor_occupied", "based_on": ["R1"]}]},
                {"alternatives": [
                    {"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_resolving_uncertainty",
                     "based_on": ["R2"]}]}],
            "allowed_pairs": [
                {"code": "YIELD_IF_OCCUPIED", "condition": "while_corridor_occupied"},
                {"code": "HOLD_UNTIL_CLEAR", "condition": "while_corridor_occupied"},
                {"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_resolving_uncertainty"}],
            "forbidden_pairs": [{"code": "ADVANCE_WITH_MONITORING", "condition": "no_condition"}]}}


def main():
    run_dir = STORE / "runs" / RUN_ID
    (run_dir / "predictions").mkdir(parents=True, exist_ok=True)
    cases = [
        ("example_001", "valid output, Reviewed GT (U in R2), action fails", "ok", "Reviewed", "Not applicable"),
        ("example_002", "format error (truncated JSON)", "ok_broken", "Reviewed", "Not applicable"),
        ("example_003", "timeout", "timeout", "Reviewed", "Not applicable"),
        ("example_004", "valid output, GT still Draft -> excluded", "ok", "Draft", "Not applicable"),
        ("example_005", "valid output, Direction Match=Conflicting -> excluded from V10-V12 only", "ok",
         "Reviewed", "Conflicting"),
    ]
    items, refs, requests = [], [], []
    for iid, note, pstat, rstat, dm in cases:
        items.append({"item_id": iid, "data_kind": EX, "image_file": None, "image_relpath": None,
                      "image_sha256": None, "image_size": {"width": 1920, "height": 1080},
                      "source_group_id": f"example_group_{iid[-1]}", "note": note,
                      "task": "track1_current_scene", "input_type": "single_image"})
        refs.append(reference(iid, rstat, dm))
        requests.append({"item_id": iid, "data_kind": EX})
        text = json.dumps(prediction(iid), ensure_ascii=False)
        if pstat == "timeout":
            rec = {"item_id": iid, "status": "timeout", "raw_text": None, "parsed": None,
                   "error": "generation exceeded 600 s (example)"}
        elif pstat == "ok_broken":
            rec = {"item_id": iid, "status": "ok", "raw_text": text[:180], "parsed": None}
        else:
            rec = {"item_id": iid, "status": "ok", "raw_text": text, "parsed": None}
        (run_dir / "predictions" / f"{iid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                                            encoding="utf-8")
    run = {"run_id": RUN_ID, "data_kind": EX, "label": "Example run for screen development (synthetic)",
           "model": {"model_id": "example-model", "revision": None, "quantization": None, "adapter_loaded": False},
           "prompt": {"version": "example"}, "decoding": {"seed": 0},
           "data_version": {"items": "example-items-0.1"}, "reference_version": "example-ref-0.1",
           "notes": "Synthetic. Not a model result; references are not real GT."}
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, rows in (("items.jsonl", items), ("references.jsonl", refs)):
        path = STORE / name
        old = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []
        ids = {r["item_id"] for r in rows}
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in [r for r in old if r["item_id"] not in ids] + rows), encoding="utf-8")
    print(f"wrote {RUN_ID} with {len(cases)} example items")


if __name__ == "__main__":
    main()
