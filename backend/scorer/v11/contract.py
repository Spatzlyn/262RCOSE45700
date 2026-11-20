"""Versioned Track 1 contract. Shared by prompt, scorer and review API."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

VERSION = "1.1-review"
STATES = ("P", "A", "U")
CORE = ("R1", "R2", "R3")
AUX = ("connection_actor", "forward_occlusion", "lateral_occlusion", "bottleneck")
FIELDS = CORE + AUX
ACTION_FIELDS = CORE + ("bottleneck",)
LABELS = {
    "R1": "경로 점유", "R2": "연결부", "R3": "시야 가림",
    "connection_actor": "연결부 이용자", "forward_occlusion": "전방 가림",
    "lateral_occlusion": "측방 가림", "bottleneck": "병목 (도로 속성)",
}
LOCATIONS = ("in_D", "adjacent", "outside", "unknown")
ORIENTATIONS = ("same", "opposite", "transverse", "unknown", "not_applicable")
CODES = ("VERIFY_BEFORE_ADVANCE", "REDUCE_SPEED_IF_MOVING", "YIELD_IF_OCCUPIED",
         "HOLD_UNTIL_CLEAR", "VERIFY_PASSAGE", "MONITOR_AHEAD", "ADVANCE_WITH_MONITORING")
CONDITIONS = ("while_corridor_occupied", "before_passing_occupying_object",
              "at_connected_opening", "before_entering_occluded_area",
              "before_passing_restricted_section", "before_resolving_uncertainty", "no_condition")
REGION_TYPES = ("connection", "occluded_forward", "occluded_lateral", "bottleneck")
CLASSES = ("car", "truck", "powered_two_wheeler", "bicycle", "pedestrian", "personal_mobility",
           "other", "traffic_cone", "stored_items", "bag_or_bundle", "speed_bump",
           "traffic_sign", "traffic_light")


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def enum(values):
    return {"type": "string", "enum": list(values)}


def array(items, **kwargs):
    return {"type": "array", "items": items, **kwargs}


STRING = {"type": "string", "minLength": 1}
IDS = array(STRING, uniqueItems=True)
COORD = {"type": "number", "minimum": 0, "maximum": 1}
BBOX = array(COORD, minItems=4, maxItems=4)
POINT = array(COORD, minItems=2, maxItems=2)
POLYGON = array(POINT, minItems=3)


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def observation(field):
    return obj({"state": enum((*STATES, "NA") if field == "connection_actor" else STATES),
                "object_ids": IDS, "region_ids": IDS, "reason": STRING})


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "생활도로 Track 1 v1.1 review",
    **obj({
        "schema_version": {"const": VERSION},
        "item_id": STRING,
        "track1": obj({
            "attributes": obj({
                "traffic_direction": enum(("One-way", "Two-way", "Unknown")),
                "direction_match": enum(("Consistent", "Conflicting", "Unknown", "Not applicable")),
                "sidewalk_left": enum(STATES), "sidewalk_right": enum(STATES),
            }),
            "objects": array(obj({
                "object_id": STRING, "class": enum(CLASSES), "bbox_xyxy_norm": BBOX,
                "semantic_role": enum(("actor", "obstacle", "road_feature")),
                "placement": enum(("roadside", "travel_space", "entrance", "unknown")),
                "truncated": enum(STATES), "location": enum(LOCATIONS),
                "orientation": enum(ORIENTATIONS),
            })),
            "regions": array(obj({
                "region_id": STRING, "type": enum(REGION_TYPES),
                "bbox_xyxy_norm": nullable(BBOX), "polygon_xy_norm": nullable(POLYGON),
                "geometry_status": STRING,
            })),
            "relations": obj({key: observation(key) for key in CORE}),
            "context": obj({key: observation(key) for key in AUX}),
            "actions": array(obj({
                "code": enum(CODES), "condition": enum(CONDITIONS),
                "based_on": array(enum(ACTION_FIELDS), minItems=1, uniqueItems=True),
                "reason": STRING,
            }), minItems=1),
            "unknowns": array(STRING),
        }),
        "track2": obj({"status": {"const": "missing_input"}, "target_object_id": {"type": "null"}}),
        "track3": obj({"status": {"const": "missing_input"}, "speed_change": {"type": "null"},
                       "direction_change": {"type": "null"}}),
    })
}


def all_observations(track):
    return {**track["relations"], **track["context"]}


def merged_visibility(forward, lateral):
    if "P" in (forward, lateral):
        return "P"
    return "A" if forward == lateral == "A" else "U"


def validate(value, item_id=None):
    errors = [".".join(map(str, e.absolute_path)) + ": " + e.message
              for e in Draft202012Validator(SCHEMA).iter_errors(value)]
    if errors:
        return errors
    if item_id is not None and value["item_id"] != item_id:
        errors.append("item_id mismatch")
    track = value["track1"]
    objects = {o["object_id"]: o for o in track["objects"]}
    regions = {r["region_id"]: r for r in track["regions"]}
    if len(objects) != len(track["objects"]) or len(regions) != len(track["regions"]):
        errors.append("duplicate object or region id")
    if objects.keys() & regions.keys():
        errors.append("object and region IDs must be distinct")
    for entry in [*objects.values(), *regions.values()]:
        bbox = entry["bbox_xyxy_norm"]
        if bbox and (bbox[0] >= bbox[2] or bbox[1] >= bbox[3]):
            errors.append("invalid bbox order")
    obs = all_observations(track)
    for key, row in obs.items():
        if set(row["object_ids"]) - objects.keys() or set(row["region_ids"]) - regions.keys():
            errors.append(f"{key}: undeclared evidence ID")
        if row["state"] in ("A", "NA") and (row["object_ids"] or row["region_ids"]):
            errors.append(f"{key}: negative/NA evidence must be empty")
        if row["state"] == "P" and not (row["object_ids"] or row["region_ids"]):
            errors.append(f"{key}: positive requires evidence")
    # Stop before resolving nonexistent identifiers.
    if errors:
        return errors
    for key, allowed in {
        "R2": {"connection"}, "forward_occlusion": {"occluded_forward"},
        "lateral_occlusion": {"occluded_lateral"}, "R3": {"occluded_forward", "occluded_lateral"},
        "bottleneck": {"bottleneck"}, "connection_actor": {"connection"},
    }.items():
        row = obs[key]
        if any(regions[r]["type"] not in allowed for r in row["region_ids"]):
            errors.append(f"{key}: wrong region type")
        if row["state"] == "P" and not row["region_ids"]:
            errors.append(f"{key}: positive requires region ID")
    occupied = {oid for oid, o in objects.items() if o["location"] == "in_D"
                and o["semantic_role"] in ("actor", "obstacle")}
    uncertain = {oid for oid, o in objects.items() if o["location"] == "unknown"
                 and o["semantic_role"] in ("actor", "obstacle")}
    if occupied and obs["R1"]["state"] != "P":
        errors.append("R1 must be P when a declared relevant object is in_D")
    if obs["R1"]["state"] == "P" and set(obs["R1"]["object_ids"]) != occupied:
        errors.append("R1 positive evidence must equal declared in_D actors/obstacles")
    if obs["R1"]["state"] == "A" and uncertain:
        errors.append("R1 A conflicts with unresolved relevant object position")
    if obs["R1"]["region_ids"]:
        errors.append("R1 evidence uses objects, not a GT D region")
    r2, actor = obs["R2"], obs["connection_actor"]
    if r2["state"] == "A" and actor["state"] != "NA":
        errors.append("connection_actor is NA when R2=A")
    if r2["state"] == "U" and actor["state"] != "U":
        errors.append("connection_actor is U when R2=U")
    if r2["state"] == "P" and actor["state"] == "NA":
        errors.append("connection_actor cannot be NA when R2=P")
    if actor["state"] == "P" and (
        not actor["object_ids"]
        or not set(actor["region_ids"]).issubset(r2["region_ids"])
        or any(objects[o]["semantic_role"] != "actor" for o in actor["object_ids"])
    ):
        errors.append("connection_actor P requires actor(s) and declared connection region(s)")
    forward, lateral = obs["forward_occlusion"], obs["lateral_occlusion"]
    if obs["R3"]["state"] != merged_visibility(forward["state"], lateral["state"]):
        errors.append("R3 must be the roll-up of forward and lateral visibility")
    positive_subtypes = [row for row in (forward, lateral) if row["state"] == "P"]
    if obs["R3"]["state"] == "P":
        for key in ("region_ids", "object_ids"):
            if set(obs["R3"][key]) != set().union(*(set(row[key]) for row in positive_subtypes)):
                errors.append(f"R3 positive evidence must match P subtypes ({key})")
    return errors


if __name__ == "__main__":
    path = Path(__file__).with_name("prediction.schema.json")
    path.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
