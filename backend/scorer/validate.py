#!/usr/bin/env python3
"""Validate package integrity and model-output structure without dependencies.

Implements the JSON Schema keywords used by this sample, not a general-purpose
JSON Schema engine. Semantic checks validate references and coordinate ranges;
they do not certify that a predicted box matches the visible object.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RELATIONS = {"R1", "R2", "R3", "R4"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def validate_schema(value, schema, root=None, path="$", errors=None):
    if root is None:
        root = schema
    if errors is None:
        errors = []
    if isinstance(schema, bool):
        if not schema:
            errors.append(f"{path}: forbidden by schema")
        return errors
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            errors.append(f"{path}: unsupported external schema reference")
            return errors
        target = root
        for key in ref[2:].split("/"):
            target = target[key.replace("~1", "/").replace("~0", "~")]
        validate_schema(value, target, root, path, errors)
    typemap = {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }
    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(typemap.get(t, False) for t in types):
            errors.append(f"{path}: wrong type, expected {types}")
            return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: incorrect constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value outside enum")
    for branch in schema.get("allOf", []):
        validate_schema(value, branch, root, path, errors)
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            matches = sum(not validate_schema(value, s, root, path, []) for s in schema[keyword])
            if (keyword == "anyOf" and matches < 1) or (keyword == "oneOf" and matches != 1):
                errors.append(f"{path}: {keyword} failed")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], root, f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unexpected field")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], root, f"{path}.{key}", errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(f"{path}: incorrect array length")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True, ensure_ascii=False) for x in value}) != len(value):
            errors.append(f"{path}: duplicate array entries")
        for index, item in enumerate(value):
            if isinstance(schema.get("items"), dict):
                validate_schema(item, schema["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            errors.append(f"{path}: incorrect string length")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
    if typemap["number"]:
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            errors.append(f"{path}: number outside range")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: number below exclusive minimum")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: number above exclusive maximum")
        if value != value or abs(value) == float("inf"):
            errors.append(f"{path}: non-finite number")
    return errors


def object_errors(objects, prefix):
    errors = []
    ids = []
    for index, obj in enumerate(objects):
        ids.append(obj.get("object_id"))
        box = obj.get("bbox_xyxy_norm")
        if not isinstance(box, list) or len(box) != 4 or any(not isinstance(v, (float, int)) or isinstance(v, bool) for v in box):
            errors.append(f"{prefix}[{index}]: invalid bbox")
        elif not (all(0 <= v <= 1 for v in box) and box[0] < box[2] and box[1] < box[3]):
            errors.append(f"{prefix}[{index}]: bbox must be normalized ordered XYXY")
    if len(ids) != len(set(ids)) or None in ids:
        errors.append(f"{prefix}: object_id values must be present and unique")
    return errors


def polygon_errors(points, prefix):
    """Reject degenerate/self-crossing polygons before geometry is compared."""
    errors = []
    if not isinstance(points, list) or len(points) < 3:
        return [f"{prefix}: polygon needs at least three points"]
    if any(not isinstance(p, list) or len(p) != 2 or
           any(not isinstance(v, (int, float)) or isinstance(v, bool) or
               not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in points):
        return [f"{prefix}: polygon points must be finite normalized XY"]
    ps = points[:-1] if points[0] == points[-1] else points
    if len({tuple(p) for p in ps}) < 3:
        return [f"{prefix}: polygon needs three distinct points"]
    area2 = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(ps, ps[1:]+ps[:1]))
    if abs(area2) < 1e-12:
        errors.append(f"{prefix}: polygon has zero area")
    def orient(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on_segment(a, b, p):
        return (abs(orient(a,b,p)) <= 1e-12 and
                min(a[0],b[0])-1e-12 <= p[0] <= max(a[0],b[0])+1e-12 and
                min(a[1],b[1])-1e-12 <= p[1] <= max(a[1],b[1])+1e-12)
    n = len(ps)
    for i in range(n):
        a,b = ps[i],ps[(i+1)%n]
        if a == b:
            errors.append(f"{prefix}: repeated adjacent point")
        for j in range(i+1,n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            c,d = ps[j],ps[(j+1)%n]
            o1,o2,o3,o4 = orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
            if ((o1*o2 < 0 and o3*o4 < 0) or on_segment(a,b,c) or
                on_segment(a,b,d) or on_segment(c,d,a) or on_segment(c,d,b)):
                errors.append(f"{prefix}: polygon self-intersects")
    return errors


def region_errors(regions, prefix):
    errors, ids = [], []
    for index, region in enumerate(regions):
        ids.append(region.get("region_id"))
        box, poly = region.get("bbox_xyxy_norm"), region.get("polygon_xy_norm")
        box_valid = False
        if box is not None:
            box_issues = object_errors([{"object_id":"geometry", "bbox_xyxy_norm":box}], f"{prefix}[{index}]")
            errors.extend(box_issues)
            box_valid = not box_issues
        if poly is not None:
            errors.extend(polygon_errors(poly, f"{prefix}[{index}]"))
        if box is None and poly is None and not region.get("geometry_status"):
            errors.append(f"{prefix}[{index}]: missing geometry needs an explicit status")
        if box_valid and poly is not None and not polygon_errors(poly, prefix):
            if any(not (box[0]-1e-6 <= x <= box[2]+1e-6 and box[1]-1e-6 <= y <= box[3]+1e-6) for x,y in poly):
                errors.append(f"{prefix}[{index}]: polygon extends outside its bounding box")
    if len(ids) != len(set(ids)) or None in ids:
        errors.append(f"{prefix}: region_id values must be present and unique")
    return errors


def validate_prediction(prediction, schema):
    errors = validate_schema(prediction, schema)
    if errors:
        return errors
    track = prediction["track1"]
    objects = track["objects"]
    errors.extend(object_errors(objects, "track1.objects"))
    errors.extend(region_errors(track["regions"], "track1.regions"))
    lookup = {obj["object_id"]:obj for obj in objects}
    ids = set(lookup)
    regions = {r["region_id"]:r for r in track["regions"]}
    if ids & set(regions):
        errors.append("track1: object_id and region_id namespaces must be disjoint")
    class_roles = {"car":"actor", "truck":"actor", "powered_two_wheeler":"actor", "bicycle":"actor",
                   "pedestrian":"actor", "traffic_cone":"obstacle", "stored_items":"obstacle",
                   "bag_or_bundle":"obstacle", "speed_bump":"road_feature"}
    for obj in objects:
        if obj["class"] in class_roles and obj["semantic_role"] != class_roles[obj["class"]]:
            errors.append(f"{obj['object_id']}: semantic_role disagrees with class")
    for relation_id, relation in track["relations"].items():
        if not set(relation["object_ids"]).issubset(ids):
            errors.append(f"{relation_id}: object_ids contains an unknown prediction object")
        if relation["state"] == "P" and not relation["object_ids"]:
            errors.append(f"{relation_id}: Present needs at least one visible supporting object")
        if not set(relation["region_ids"]).issubset(regions):
            errors.append(f"{relation_id}: region_ids contains an unknown prediction region")
        roles = relation["roles"]
        role_objects = set()
        role_regions = set()
        for key, value in roles.items():
            if key.endswith("_ids"):
                role_objects.update(value)
            elif value is not None:
                role_regions.add(value)
        if role_objects != set(relation["object_ids"]):
            errors.append(f"{relation_id}: role object IDs must exactly cover object_ids")
        if role_regions != set(relation["region_ids"]):
            errors.append(f"{relation_id}: role region IDs must exactly cover region_ids")
        for oid in roles.get("actor_ids", []):
            if oid in lookup and lookup[oid]["semantic_role"] != "actor":
                errors.append(f"{relation_id}: actor role requires an actor object")
        for oid in roles.get("obstacle_ids", []):
            if oid in lookup and lookup[oid]["semantic_role"] != "obstacle":
                errors.append(f"{relation_id}: obstacle role requires an obstacle object")
        if relation_id == "R1" and set(roles["actor_ids"]) & set(roles["obstacle_ids"]):
            errors.append("R1: actor and obstacle roles overlap")
        if relation_id in {"R2","R3"} and relation["state"] in {"P","U"}:
            key = "entrance_candidate_id" if relation_id == "R2" else "occluded_region_id"
            region_id = roles[key]
            if region_id is None:
                errors.append(f"{relation_id}: Present/Unknown needs a declared candidate/occluded region")
            elif region_id in regions:
                allowed = {"entrance_region","entrance_candidate_review_region"} if relation_id == "R2" else {"occluded_road_region"}
                if regions[region_id]["type"] not in allowed:
                    errors.append(f"{relation_id}: region type disagrees with evidence role")
        if relation["state"] == "A" and (relation["object_ids"] or relation["region_ids"]):
            errors.append(f"{relation_id}: Absent has no positive supporting evidence IDs")
    for action in track["actions"]:
        if not set(action["based_on"]).issubset(RELATIONS):
            errors.append("action: based_on contains an unknown relation")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", default="expected/prediction.example.json")
    parser.add_argument("--prediction-only", action="store_true")
    args = parser.parse_args()
    schema = read_json(ROOT / "schema/prediction.schema.json")
    prediction = read_json(resolve(args.prediction))
    errors = validate_prediction(prediction, schema)
    summary = {"prediction_file": str(resolve(args.prediction)), "validation_invokes_model": False}
    if not args.prediction_only:
        items = read_jsonl(ROOT / "data/items.jsonl")
        annotations = read_jsonl(ROOT / "data/annotations.jsonl")
        references = read_jsonl(ROOT / "data/references.jsonl")
        item_ids = [item["item_id"] for item in items]
        if len(set(item_ids)) != len(item_ids):
            errors.append("items: duplicate item_id")
        for item in items:
            path = (ROOT / item["image_path"]).resolve()
            if not path.is_relative_to((ROOT / "images").resolve()) or not path.is_file():
                errors.append(f"{item['item_id']}: missing or invalid input image")
        if prediction["item_id"] not in item_ids:
            errors.append("prediction: item_id not present in items")
        for ann in annotations:
            errors.extend(object_errors(ann["objects"], f"annotations.{ann['view']}.objects"))
            errors.extend(region_errors(ann.get("regions",[]), f"annotations.{ann['view']}.regions"))
            for rid, rel in (ann.get("track1", {}).get("relations") or {}).items():
                if rel is None:
                    continue
                obj_ids = {o["object_id"] for o in ann["objects"]}
                reg_ids = {r["region_id"] for r in ann.get("regions",[])}
                if not set(rel.get("object_ids",[])).issubset(obj_ids):
                    errors.append(f"annotations.{ann['view']}.{rid}: dangling object evidence")
                if not set(rel.get("region_ids",[])).issubset(reg_ids):
                    errors.append(f"annotations.{ann['view']}.{rid}: dangling region evidence")
        for reference in references:
            if reference["item_id"] not in item_ids:
                errors.append("reference: item_id not present in items")
            rules = reference["action_rules"]
            allowed = {(p["code"], p["condition"]) for p in rules["allowed_pairs"]}
            forbidden = {(p["code"], p["condition"]) for p in rules["forbidden_pairs"]}
            if allowed & forbidden:
                errors.append("reference: allowed and forbidden pairs overlap")
            for group in rules["required_groups"]:
                if not group["alternatives"]:
                    errors.append("reference: required group has no alternative")
                for alt in group["alternatives"]:
                    if (alt["code"], alt["condition"]) not in allowed:
                        errors.append("reference: required alternative is not allowed")
        summary.update({"items": len(items), "annotated_views": len(annotations), "annotated_objects": sum(len(a["objects"]) for a in annotations), "reference_statuses": sorted({r["annotation_status"] for r in references})})
    summary.update({"valid": not errors, "errors": errors, "scope": "structure_coordinates_references_only; visual_truth_not_verified"})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
