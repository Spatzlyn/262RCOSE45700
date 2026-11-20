"""Validation and import prerequisites for version-specific reviewed references."""
from jsonschema import Draft202012Validator
from .contract import VERSION, CORE, AUX, FIELDS, STATES, observation, merged_visibility, CLASSES, BBOX, POLYGON, REGION_TYPES, LOCATIONS, ORIENTATIONS


def check_reference(ref, items):
    errors = []
    if ref.get("item_id") not in items:
        errors.append("unknown item_id")
    elif ref.get("image_sha256") != items[ref["item_id"]].get("image_sha256"):
        errors.append("image hash does not match catalog")
    if ref.get("schema_version") != VERSION:
        errors.append("v1.1 schema version required")
    status = ref.get("annotation_status")
    if status not in ("Draft", "Reviewed", "Missing"):
        errors.append("invalid annotation_status")
    if not ref.get("reference_version"):
        errors.append("reference version required")
    if not ref.get("reference_version", "").replace("-", "").replace("_", "").replace(".", "").isalnum():
        errors.append("invalid reference version identifier")
    if status == "Missing":
        return errors
    fields = ref.get("reviewed_fields", [])
    if not isinstance(fields, list) or any(k not in FIELDS for k in fields):
        return errors + ["unknown reviewed field"]
    if status == "Reviewed" and (not fields or not ref.get("reviewers")):
        errors.append("Reviewed requires approved fields and human reviewer record")
    if status == "Draft" and (fields or ref.get("objects_reviewed") or ref.get("actions_reviewed")):
        errors.append("Draft cannot have reviewed fields or review flags")
    objects = ref.get("objects", [])
    regions = ref.get("regions", [])
    object_ids, region_ids = {o.get("object_id") for o in objects}, {r.get("region_id") for r in regions}
    if None in object_ids or None in region_ids or len(object_ids) != len(objects) or len(region_ids) != len(regions):
        errors.append("missing/duplicate evidence ID")
    if object_ids & region_ids:
        errors.append("object and region IDs must be distinct")
    for o in objects:
        box = o.get("bbox_xyxy_norm")
        if o.get("class") not in CLASSES or not Draft202012Validator(BBOX).is_valid(box) or box[0]>=box[2] or box[1]>=box[3]:
            errors.append("object class or box is invalid")
        if o.get("location") not in (*LOCATIONS, None) or o.get("orientation") not in (*ORIENTATIONS, None):
            errors.append("invalid object location/orientation")
    for r in regions:
        box, poly = r.get("bbox_xyxy_norm"), r.get("polygon_xy_norm")
        if r.get("type") not in REGION_TYPES:
            errors.append("invalid region type")
        if box is not None and (not Draft202012Validator(BBOX).is_valid(box) or box[0]>=box[2] or box[1]>=box[3]):
            errors.append("invalid reference region box")
        if poly is not None and not Draft202012Validator(POLYGON).is_valid(poly):
            errors.append("invalid reference region polygon")
    if not Draft202012Validator(POLYGON).is_valid(ref.get("driving_area")):
        errors.append("D must contain normalized polygon points")
    obs = {**ref.get("relations", {}), **ref.get("context", {})}
    for key in FIELDS:
        row = obs.get(key)
        if not isinstance(row, dict) or not Draft202012Validator(observation(key)).is_valid(row):
            errors.append(f"{key}: invalid observation")
            continue
        if set(row["object_ids"]) - object_ids or set(row["region_ids"]) - region_ids:
            errors.append(f"{key}: undeclared evidence ID")
        if row["state"] in ("A", "NA") and (row["object_ids"] or row["region_ids"]):
            errors.append(f"{key}: negative/NA evidence must be empty")
        if row["state"] == "P" and not (row["object_ids"] or row["region_ids"]):
            errors.append(f"{key}: positive requires evidence")
    if errors:
        return errors
    if obs["R3"]["state"] != merged_visibility(obs["forward_occlusion"]["state"], obs["lateral_occlusion"]["state"]):
        errors.append("R3 rollup inconsistent")
    expected_actor = {"A": "NA", "U": "U"}.get(obs["R2"]["state"])
    if expected_actor and obs["connection_actor"]["state"] != expected_actor:
        errors.append("connection_actor conditional state inconsistent")
    if obs["R2"]["state"] == "P" and obs["connection_actor"]["state"] == "NA":
        errors.append("connection_actor applies to connection P")
    if ref.get("evidence_reviewed_fields") and not set(ref["evidence_reviewed_fields"]).issubset(set(fields) & set(CORE)):
        errors.append("evidence fields must have approved core states")
    if ref.get("actions_reviewed") and not set((*CORE, "bottleneck")).issubset(fields):
        errors.append("action approval requires all action condition fields")
    return errors
