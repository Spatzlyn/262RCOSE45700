#!/usr/bin/env python3
"""Regression tests for matching, evidence references, and sample-only scoring.

Synthetic fixtures deliberately avoid using the sample answer as ground truth.
Run from the package directory: python scripts/test_evaluation.py
"""
import copy
import unittest

from evaluate import check_actions, diagnostic_evaluation, geometry_iou, match_entities
from validate import ROOT, read_json, region_errors, validate_prediction


def obj(object_id, box, cls="car", role="actor", placement="travel_space"):
    return {
        "object_id": object_id,
        "class": cls,
        "bbox_xyxy_norm": box,
        "semantic_role": role,
        "placement": placement,
        "truncated": "A",
    }


def fixtures():
    """A visible actor, an entrance actor, and an explicitly unmeasurable region."""
    objects = [
        obj("car", [0.2, 0.2, 0.4, 0.5]),
        obj("person", [0.6, 0.3, 0.7, 0.7], "pedestrian", placement="entrance"),
        obj("cone", [0.8, 0.6, 0.9, 0.8], "traffic_cone", "obstacle", "roadside"),
    ]
    regions = [
        {
            "region_id": "entrance",
            "type": "entrance_candidate_review_region",
            "bbox_xyxy_norm": [0.5, 0.2, 0.8, 0.8],
            "polygon_xy_norm": None,
            "geometry_status": "approximate_review_ROI",
        },
        {
            "region_id": "hidden",
            "type": "occluded_road_region",
            "bbox_xyxy_norm": None,
            "polygon_xy_norm": None,
            "geometry_status": "hidden_extent_not_observable",
        },
    ]
    relations = {
        "R1": {"state": "P", "object_ids": ["car"], "region_ids": [],
               "roles": {"actor_ids": ["car"], "obstacle_ids": []}, "reason": "Visible contact overlaps the reference area."},
        "R2": {"state": "U", "object_ids": ["person"], "region_ids": ["entrance"],
               "roles": {"actor_ids": ["person"], "entrance_candidate_id": "entrance"}, "reason": "Entrance boundary needs review."},
        "R3": {"state": "P", "object_ids": ["car"], "region_ids": ["hidden"],
               "roles": {"occluder_ids": ["car"], "occluded_region_id": "hidden"}, "reason": "The actor blocks part of the road."},
        "R4": {"state": "P", "object_ids": ["car"], "region_ids": [],
               "roles": {"restricting_object_ids": ["car"]}, "reason": "The actor limits visible passage space."},
    }
    actions = [
        {"code": "YIELD_IF_OCCUPIED", "condition": "while_corridor_occupied", "based_on": ["R1"], "reason": "Yield while occupied."},
        {"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_resolving_uncertainty", "based_on": ["R2"], "reason": "Resolve the entrance relation."},
        {"code": "VERIFY_BEFORE_ADVANCE", "condition": "before_entering_occluded_area", "based_on": ["R3"], "reason": "Check the occluded area."},
        {"code": "VERIFY_PASSAGE", "condition": "before_passing_restricted_section", "based_on": ["R4"], "reason": "Check passage clearance."},
    ]
    prediction = {
        "item_id": "synthetic_001",
        "track1": {
            "attributes": {"traffic_direction": "Unknown", "direction_match": "Unknown", "sidewalk_left": "U", "sidewalk_right": "U"},
            "objects": objects,
            "regions": regions,
            "relations": relations,
            "actions": actions,
            "unknowns": ["Hidden extent is not observable."],
        },
        "track2": {"status": "missing_input", "target_object_id": None},
        "track3": {"status": "missing_input", "speed_change": None, "direction_change": None},
    }
    evidence = {rid: [{key: copy.deepcopy(rel[key]) for key in ("object_ids", "region_ids", "roles")}]
                for rid, rel in relations.items()}
    reference = {
        "item_id": prediction["item_id"],
        "annotation_status": "Draft",
        "human_review_completed": False,
        "benchmark_eligible": False,
        "object_coverage_complete": False,
        "relations": {rid: rel["state"] for rid, rel in relations.items()},
        "accepted_evidence_sets_by_relation": evidence,
        "action_rules": {
            "required_groups": [{"alternatives": [{k: copy.deepcopy(a[k]) for k in ("code", "condition", "based_on")}]} for a in actions],
            "allowed_pairs": [{"code": a["code"], "condition": a["condition"]} for a in actions],
            "forbidden_pairs": [{"code": "ADVANCE_WITH_MONITORING", "condition": "while_corridor_occupied"}],
        },
    }
    annotation = {
        "annotation_status": "Draft", "human_review_completed": False,
        "source_annotations_complete": False,
        "objects": copy.deepcopy(objects), "regions": copy.deepcopy(regions),
        "track1": {"relations": copy.deepcopy(relations)},
    }
    for entity in annotation["objects"] + annotation["regions"]:
        entity["annotation_status"] = "Draft"
    return prediction, reference, annotation


def renamed(prediction):
    """Rename all model-local IDs while preserving structure and geometry."""
    prediction = copy.deepcopy(prediction)
    track = prediction["track1"]
    ids = {x["object_id"]: "pred_" + x["object_id"] for x in track["objects"]}
    ids.update({x["region_id"]: "pred_" + x["region_id"] for x in track["regions"]})
    for x in track["objects"]:
        x["object_id"] = ids[x["object_id"]]
    for x in track["regions"]:
        x["region_id"] = ids[x["region_id"]]
    for rel in track["relations"].values():
        for key in ("object_ids", "region_ids"):
            rel[key] = [ids[x] for x in rel[key]]
        for key, value in rel["roles"].items():
            rel["roles"][key] = [ids[x] for x in value] if isinstance(value, list) else ids[value]
    return prediction


class GeometryMatchingTests(unittest.TestCase):
    def test_geometry_identity_and_disjoint_boxes(self):
        a = obj("a", [0.1, 0.1, 0.3, 0.3])
        self.assertAlmostEqual(geometry_iou(a, a), 1.0)
        self.assertEqual(geometry_iou(a, obj("b", [0.6, 0.6, 0.9, 0.9])), 0.0)

    def test_missing_geometry_is_not_a_match(self):
        region = {"bbox_xyxy_norm": None, "polygon_xy_norm": None}
        self.assertIsNone(geometry_iou(region, region))

    def test_polygon_iou_preserves_shape_instead_of_using_its_box(self):
        square = {"bbox_xyxy_norm": [0, 0, 1, 1]}
        triangle = {"polygon_xy_norm": [[0, 0], [1, 0], [0, 1]]}
        self.assertAlmostEqual(geometry_iou(square, triangle), 0.5)
        triangle["polygon_xy_norm"].reverse()
        self.assertAlmostEqual(geometry_iou(square, triangle), 0.5)

    def test_concave_polygon_iou(self):
        outer = {"bbox_xyxy_norm": [0, 0, 0.8, 0.8]}
        l_shape = {"polygon_xy_norm": [[0, 0], [0.8, 0], [0.8, 0.2], [0.2, 0.2], [0.2, 0.8], [0, 0.8]]}
        self.assertAlmostEqual(geometry_iou(outer, l_shape), 0.4375)

    def test_id_rename_does_not_change_matching(self):
        reference = [obj("truth", [0.1, 0.1, 0.4, 0.4])]
        pred = [obj("arbitrary_model_id", [0.1, 0.1, 0.4, 0.4])]
        result = match_entities(pred, reference)
        self.assertEqual(result["mapping"], {"arbitrary_model_id": "truth"})

    def test_wrong_class_and_wrong_box_do_not_match(self):
        reference = [obj("truth", [0.1, 0.1, 0.4, 0.4])]
        for pred in [obj("truth", [0.1, 0.1, 0.4, 0.4], "truck"), obj("truth", [0.7, 0.7, 0.9, 0.9])]:
            with self.subTest(pred=pred):
                self.assertEqual(match_entities([pred], reference)["mapping"], {})

    def test_maximum_cardinality_precedes_local_iou(self):
        reference = [obj("a", [0, 0, 0.4, 0.4]), obj("b", [0.2, 0, 0.6, 0.4])]
        prediction = [obj("broad", [0, 0, 0.6, 0.4]), obj("specific", [0, 0, 0.4, 0.4])]
        result = match_entities(prediction, reference)
        self.assertEqual(result["mapping"], {"broad": "b", "specific": "a"})

    def test_maximum_total_iou_breaks_equal_cardinality_ties(self):
        reference = [obj("a", [0, 0, 0.4, 0.4]), obj("b", [0.2, 0, 0.6, 0.4])]
        prediction = [obj("p1", [0, 0, 0.45, 0.4]), obj("p2", [0.1, 0, 0.5, 0.4])]
        result = match_entities(prediction, reference, threshold=0.3)
        self.assertEqual(result["mapping"], {"p1": "a", "p2": "b"})


class PredictionValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = read_json(ROOT / "schema/prediction.schema.json")

    def test_valid_fixture_and_model_local_ids(self):
        prediction, _, _ = fixtures()
        self.assertEqual(validate_prediction(prediction, self.schema), [])
        self.assertEqual(validate_prediction(renamed(prediction), self.schema), [])

    def test_analysis_only_time_of_day_is_rejected(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["attributes"]["time_of_day"] = "Day"
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_dangling_object_id_is_rejected(self):
        prediction, _, _ = fixtures()
        rel = prediction["track1"]["relations"]["R1"]
        rel["object_ids"] = ["not_declared"]
        rel["roles"]["actor_ids"] = ["not_declared"]
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_dangling_region_id_is_rejected(self):
        prediction, _, _ = fixtures()
        rel = prediction["track1"]["relations"]["R3"]
        rel["region_ids"] = ["not_declared"]
        rel["roles"]["occluded_region_id"] = "not_declared"
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_actor_cannot_be_mislabeled_as_obstacle_role(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["relations"]["R1"]["roles"] = {"actor_ids": [], "obstacle_ids": ["car"]}
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_role_ids_must_match_evidence_list(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["relations"]["R1"]["roles"]["actor_ids"] = ["person"]
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_reference_driving_area_cannot_be_model_output(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["regions"].append({"region_id": "C", "type": "driving_area", "bbox_xyxy_norm": [0, 0, 1, 1], "polygon_xy_norm": None, "geometry_status": "Draft"})
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_unknown_role_key_is_rejected(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["relations"]["R3"]["roles"]["invented_role_ids"] = ["car"]
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_self_intersecting_region_is_rejected(self):
        prediction, _, _ = fixtures()
        region = prediction["track1"]["regions"][0]
        region["bbox_xyxy_norm"] = None
        region["polygon_xy_norm"] = [[0.1, 0.1], [0.8, 0.8], [0.1, 0.8], [0.8, 0.1]]
        self.assertTrue(validate_prediction(prediction, self.schema))
        self.assertIsNone(geometry_iou(region, region))

    def test_nonfinite_region_coordinate_is_rejected(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["regions"][0]["bbox_xyxy_norm"][0] = float("nan")
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_polygon_outside_declared_bbox_is_rejected(self):
        prediction, _, _ = fixtures()
        prediction["track1"]["regions"][0]["polygon_xy_norm"] = [[0, 0], [0.2, 0], [0, 0.2]]
        self.assertTrue(validate_prediction(prediction, self.schema))

    def test_region_with_short_box_and_valid_polygon_returns_error(self):
        malformed = {"region_id": "z", "bbox_xyxy_norm": [0, 0],
                     "polygon_xy_norm": [[0, 0], [1, 0], [0, 1]],
                     "geometry_status": "Draft"}
        self.assertTrue(region_errors([malformed], "annotation.regions"))


class ActionRegressionTests(unittest.TestCase):
    def test_required_actions_pass(self):
        prediction, reference, _ = fixtures()
        self.assertTrue(check_actions(prediction, reference)["pass"])

    def test_missing_occlusion_action_fails(self):
        prediction, reference, _ = fixtures()
        prediction["track1"]["actions"] = [a for a in prediction["track1"]["actions"] if a["condition"] != "before_entering_occluded_area"]
        self.assertFalse(check_actions(prediction, reference)["pass"])

    def test_unresolved_action_must_name_unresolved_relation(self):
        prediction, reference, _ = fixtures()
        prediction["track1"]["actions"][1]["based_on"] = ["R3"]
        self.assertFalse(check_actions(prediction, reference)["pass"])

    def test_forbidden_advance_fails(self):
        prediction, reference, _ = fixtures()
        prediction["track1"]["actions"].append({"code": "ADVANCE_WITH_MONITORING", "condition": "while_corridor_occupied", "based_on": ["R1"], "reason": "Contradictory action."})
        self.assertFalse(check_actions(prediction, reference)["pass"])


class EvidenceDiagnosticTests(unittest.TestCase):
    def test_evidence_is_invariant_to_model_ids(self):
        prediction, reference, annotation = fixtures()
        original = diagnostic_evaluation(prediction, reference, annotation)
        changed = diagnostic_evaluation(renamed(prediction), reference, annotation)
        for rid in ("R1", "R2", "R3", "R4"):
            self.assertEqual(original["evidence"][rid]["status"], changed["evidence"][rid]["status"])
        self.assertEqual(changed["evidence"]["R1"]["status"], "matched")
        self.assertEqual(changed["evidence"]["R2"]["status"], "matched")

    def test_unobservable_region_is_deferred_not_a_fake_match(self):
        prediction, reference, annotation = fixtures()
        report = diagnostic_evaluation(prediction, reference, annotation)
        self.assertEqual(report["evidence"]["R3"]["status"], "deferred")
        self.assertNotIn("hidden", report["grounding"]["regions"]["mapping"])
        self.assertIsNone(report["benchmark"]["V4"])

    def test_wrong_occluder_is_mismatch_even_if_hidden_region_is_unmeasurable(self):
        prediction, reference, annotation = fixtures()
        relation = prediction["track1"]["relations"]["R3"]
        relation["object_ids"] = ["person"]
        relation["roles"]["occluder_ids"] = ["person"]
        report = diagnostic_evaluation(prediction, reference, annotation)
        self.assertEqual(report["evidence"]["R3"]["status"], "mismatch")

    def test_matching_id_string_cannot_rescue_wrong_geometry(self):
        prediction, reference, annotation = fixtures()
        prediction["track1"]["objects"][0]["bbox_xyxy_norm"] = [0.01, 0.01, 0.05, 0.05]
        report = diagnostic_evaluation(prediction, reference, annotation)
        self.assertEqual(report["evidence"]["R1"]["status"], "mismatch")

    def test_draft_and_incomplete_reference_never_produce_benchmark_scores(self):
        prediction, reference, annotation = fixtures()
        report = diagnostic_evaluation(prediction, reference, annotation)
        self.assertFalse(report["benchmark"]["eligible"])
        self.assertIsNone(report["benchmark"]["V3"])
        self.assertIsNone(report["benchmark"]["V4"])
        self.assertTrue(report["benchmark"]["blockers"])

    def test_dry_run_does_not_promote_itself_by_changing_status_flags(self):
        prediction, reference, annotation = fixtures()
        reference.update(annotation_status="Reviewed", human_review_completed=True,
                         benchmark_eligible=True, object_coverage_complete=True)
        annotation.update(annotation_status="Reviewed", human_review_completed=True,
                          source_annotations_complete=True)
        report = diagnostic_evaluation(prediction, reference, annotation)
        self.assertFalse(report["benchmark"]["eligible"])
        self.assertIsNone(report["benchmark"]["V3"])
        self.assertIsNone(report["benchmark"]["V4"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
