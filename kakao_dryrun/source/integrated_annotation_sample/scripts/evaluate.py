#!/usr/bin/env python3
"""Run label, action, geometry and role-aware evidence diagnostics.

This remains a sample diagnostic, not a production benchmark. Draft and
incomplete references never produce official V3/V4 scores. Entity IDs are
matched by class/type and geometry, not by their spelling. Unobservable
reference geometry is explicitly deferred, never counted as a match.
"""
import argparse
import json
import sys
from validate import ROOT, polygon_errors, read_json, read_jsonl, resolve, validate_prediction

EPS = 1e-12


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))/2


def _polygon(entity):
    poly = entity.get("polygon_xy_norm")
    if poly is not None:
        if polygon_errors(poly, "geometry"):
            return None
        result = [tuple(p) for p in poly]
        if result[0] == result[-1]:
            result.pop()
        return result
    box = entity.get("bbox_xyxy_norm")
    if box is None or len(box) != 4:
        return None
    x1,y1,x2,y2 = box
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        return None
    return [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]


def _triangulate(poly):
    """Ear clipping of a validated simple polygon (including concave ones)."""
    ps = list(poly)
    signed = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ps,ps[1:]+ps[:1]))
    if signed < 0:
        ps.reverse()
    # Collinear vertices do not affect area and can obstruct ear selection.
    changed = True
    while changed and len(ps) > 3:
        changed = False
        for i in range(len(ps)):
            if abs(_cross(ps[i-1],ps[i],ps[(i+1)%len(ps)])) < EPS:
                del ps[i]
                changed = True
                break
    triangles = []
    while len(ps) > 3:
        found = False
        for i in range(len(ps)):
            a,b,c = ps[i-1],ps[i],ps[(i+1)%len(ps)]
            if _cross(a,b,c) <= EPS:
                continue
            other = [p for j,p in enumerate(ps) if j not in {(i-1)%len(ps),i,(i+1)%len(ps)}]
            if any(_cross(a,b,p) >= -EPS and _cross(b,c,p) >= -EPS and
                   _cross(c,a,p) >= -EPS for p in other):
                continue
            triangles.append([a,b,c])
            del ps[i]
            found = True
            break
        if not found:
            return None
    if len(ps) == 3 and _area(ps) > EPS:
        triangles.append(ps)
    return triangles or None


def _convex_intersection(subject, clip):
    result = list(subject)
    for a,b in zip(clip,clip[1:]+clip[:1]):
        source, result = result, []
        if not source:
            break
        prev = source[-1]
        prev_dist = _cross(a,b,prev)
        for cur in source:
            cur_dist = _cross(a,b,cur)
            pin, cin = prev_dist >= -EPS, cur_dist >= -EPS
            if pin != cin:
                denominator = prev_dist-cur_dist
                if abs(denominator) > EPS:
                    t = prev_dist/denominator
                    result.append((prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])))
            if cin:
                result.append(cur)
            prev,prev_dist = cur,cur_dist
    return result


def geometry_iou(a, b):
    """Exact simple-polygon/box IoU; None means unmeasurable, never zero."""
    pa,pb = _polygon(a),_polygon(b)
    if pa is None or pb is None:
        return None
    ta,tb = _triangulate(pa),_triangulate(pb)
    if ta is None or tb is None:
        return None
    intersection = sum(_area(poly) for x in ta for y in tb
                       for poly in [_convex_intersection(x,y)] if len(poly) >= 3)
    union = _area(pa)+_area(pb)-intersection
    return min(1.0,max(0.0,intersection/union)) if union > EPS else None


def match_entities(predictions, references, id_key="object_id", class_key="class", threshold=0.5):
    """One-to-one assignment: maximize cardinality, then total IoU.

    Successive shortest augmenting paths compute min-cost maximum flow.
    This is global matching, not a greedy sort of overlapping boxes.
    """
    if not 0 <= threshold <= 1:
        raise ValueError("IoU threshold must be between zero and one")
    pids,rids = [p[id_key] for p in predictions],[r[id_key] for r in references]
    if len(set(pids)) != len(pids) or len(set(rids)) != len(rids):
        raise ValueError("Entity IDs must be unique within each side")
    np,nr = len(predictions),len(references)
    source,sink = np+nr,np+nr+1
    graph = [[] for _ in range(sink+1)]
    def add(u,v,cap,cost):
        f=[v,len(graph[v]),cap,cost]
        r=[u,len(graph[u]),0,-cost]
        graph[u].append(f)
        graph[v].append(r)
        return f
    for i in range(np):
        add(source,i,1,0.0)
    for j in range(nr):
        add(np+j,sink,1,0.0)
    candidates = []
    for i,p in enumerate(predictions):
        for j,r in enumerate(references):
            if p[class_key] != r[class_key]:
                continue
            iou = geometry_iou(p,r)
            if iou is not None and iou+EPS >= threshold:
                edge=add(i,np+j,1,-iou)
                candidates.append((i,j,iou,edge))
    while True:
        dist, parent = [float("inf")]*len(graph), [None]*len(graph)
        dist[source]=0.0
        for _ in range(len(graph)-1):
            changed=False
            for u,edges in enumerate(graph):
                if dist[u] == float("inf"):
                    continue
                for ei,e in enumerate(edges):
                    v,_,cap,cost=e
                    if cap and dist[u]+cost < dist[v]-EPS:
                        dist[v],parent[v]=dist[u]+cost,(u,ei)
                        changed=True
            if not changed:
                break
        if parent[sink] is None:
            break
        v=sink
        while v != source:
            u,ei=parent[v]
            e=graph[u][ei]
            e[2]-=1
            graph[v][e[1]][2]+=1
            v=u
    pairs=[{"prediction_id":pids[i],"reference_id":rids[j],"iou":round(iou,10)}
           for i,j,iou,edge in candidates if edge[2]==0]
    mapping={x["prediction_id"]:x["reference_id"] for x in pairs}
    used=set(mapping.values())
    return {"mapping":mapping,"pairs":pairs,"matched_count":len(pairs),
            "unmatched_prediction_ids":[x for x in pids if x not in mapping],
            "unmatched_reference_ids":[x for x in rids if x not in used],
            "unmeasurable_prediction_ids":[p[id_key] for p in predictions if geometry_iou(p,p) is None],
            "unmeasurable_reference_ids":[r[id_key] for r in references if geometry_iou(r,r) is None],
            "iou_threshold":threshold,"assignment":"maximum_cardinality_then_total_iou"}


def _role_objects(roles, mapping=None):
    result={}
    for key,ids in roles.items():
        if key.endswith("_ids"):
            result[key]=set(ids if mapping is None else [mapping.get(x,"<unmatched>"+x) for x in ids])
    # An omitted empty optional object role is equivalent to an empty array.
    return {k:v for k,v in result.items() if v}


def _role_regions(roles, mapping=None):
    return {k:(v if mapping is None or v is None else mapping.get(v,"<unmatched>"+v))
            for k,v in roles.items() if not k.endswith("_ids") and v is not None}


def diagnostic_evaluation(prediction, reference, annotation):
    track=prediction["track1"]
    objects=match_entities(track["objects"],annotation["objects"])
    ref_regions=[r for r in annotation.get("regions",[]) if r["type"] != "driving_area"]
    regions=match_entities(track["regions"],ref_regions,"region_id","type")
    region_lookup={r["region_id"]:r for r in ref_regions}
    object_lookup={r["object_id"]:r for r in annotation["objects"]}
    accepted=reference.get("accepted_evidence_sets_by_relation",{})
    evidence={}
    for rid,expected_state in reference["relations"].items():
        rel=track["relations"][rid]
        if expected_state not in {"P","U"}:
            evidence[rid]={"status":"not_applicable","reason":"V4 references only Present/Unknown relations"}
            continue
        alternatives=accepted.get(rid,[])
        if not alternatives:
            evidence[rid]={"status":"missing_reference","reason":"No accepted evidence sets have been declared"}
            continue
        pred_objects={objects["mapping"].get(x,"<unmatched>"+x) for x in rel["object_ids"]}
        pred_object_roles=_role_objects(rel["roles"],objects["mapping"])
        statuses=[]
        for alternative in alternatives:
            expected_objects=set(alternative.get("object_ids",[]))
            expected_regions=set(alternative.get("region_ids",[]))
            if not expected_objects.issubset(object_lookup) or not expected_regions.issubset(region_lookup):
                statuses.append(("missing_reference","Accepted set refers to undeclared reference entities"))
                continue
            if (pred_objects != expected_objects or
                pred_object_roles != _role_objects(alternative.get("roles",{}))):
                statuses.append(("mismatch","Object geometry/class assignment or object evidence roles differ"))
                continue
            unmeasurable=[x for x in expected_regions if geometry_iou(region_lookup[x],region_lookup[x]) is None]
            if unmeasurable:
                statuses.append(("deferred","Reference geometry is unobservable/unmeasurable: "+", ".join(sorted(unmeasurable))))
                continue
            pred_regions={regions["mapping"].get(x,"<unmatched>"+x) for x in rel["region_ids"]}
            if (pred_regions != expected_regions or
                _role_regions(rel["roles"],regions["mapping"]) != _role_regions(alternative.get("roles",{}))):
                statuses.append(("mismatch","Region geometry/type assignment or region evidence roles differ"))
            else:
                statuses.append(("matched","Geometry-matched entity sets and evidence roles match an accepted alternative"))
        precedence=["matched","deferred","missing_reference","mismatch"]
        status,reason=min(statuses,key=lambda x:precedence.index(x[0]))
        evidence[rid]={"status":status,"reason":reason,
                       "relation_state_matches":rel["state"]==expected_state,
                       "accepted_alternatives":len(alternatives)}
    blockers=[]
    if reference.get("annotation_status") != "Reviewed":
        blockers.append("reference_not_reviewed")
    if not reference.get("human_review_completed",False):
        blockers.append("independent_human_review_incomplete")
    if not reference.get("benchmark_eligible",False):
        blockers.append("reference_not_benchmark_eligible")
    if not reference.get("object_coverage_complete",False):
        blockers.append("object_coverage_incomplete")
    if any(row["status"] in {"deferred","missing_reference"} for row in evidence.values()):
        blockers.append("evidence_reference_not_fully_measurable")
    blockers.append("production_benchmark_aggregation_not_implemented")
    return {"grounding":{"objects":objects,"regions":regions},"evidence":evidence,
            "benchmark":{"eligible":False,"V3":None,"V4":None,"blockers":blockers},
            "interpretation":"Draft matching diagnostics only. Unmatched predictions are not false positives while reference coverage is incomplete."}


def check_actions(prediction, reference):
    actions = prediction["track1"]["actions"]
    predicted_relations = prediction["track1"]["relations"]
    rules = reference["action_rules"]
    allowed = {(p["code"], p["condition"]) for p in rules["allowed_pairs"]}
    forbidden = {(p["code"], p["condition"]) for p in rules["forbidden_pairs"]}
    pairs = [(a["code"], a["condition"]) for a in actions]
    errors = []
    if len(pairs) != len(set(pairs)):
        errors.append("duplicate action pair")
    if any(pair not in allowed for pair in pairs):
        errors.append("action pair outside reference allowed set")
    if set(pairs) & forbidden:
        errors.append("forbidden action pair")
    matched_groups = 0
    for index, group in enumerate(rules["required_groups"]):
        matched = any(
            action["code"] == alternative["code"]
            and action["condition"] == alternative["condition"]
            and set(alternative["based_on"]).issubset(action["based_on"])
            for action in actions for alternative in group["alternatives"]
        )
        matched_groups += matched
        if not matched:
            errors.append(f"required action group {index + 1} not met")
    expected = reference["relations"]
    for action in actions:
        for rid in action["based_on"]:
            if predicted_relations[rid]["state"] != expected[rid]:
                errors.append(f"action based_on {rid} disagrees with reference relation")
        condition = action["condition"]
        checks = {
            "while_corridor_occupied": ("R1", {"P"}),
            "while_actor_near_entrance": ("R2", {"P"}),
            "before_entering_occluded_area": ("R3", {"P"}),
            "before_passing_restricted_section": ("R4", {"P", "U"}),
        }
        if condition in checks:
            rid, states = checks[condition]
            if rid not in action["based_on"] or predicted_relations[rid]["state"] not in states:
                errors.append(f"action condition {condition} unsupported by its relation")
        elif condition == "before_resolving_uncertainty":
            unresolved = {r for r in ("R1", "R2", "R3") if predicted_relations[r]["state"] == "U"}
            if not unresolved or not unresolved.issubset(action["based_on"]):
                errors.append("unresolved action must name all unresolved R1/R2/R3 relations")
        elif condition == "no_condition":
            if any(predicted_relations[r]["state"] != "A" for r in expected):
                errors.append("unconditional action requires all relations Absent")
    return {"pass": not errors, "matched_required_groups": matched_groups, "required_groups": len(rules["required_groups"]), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", required=True)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--out", default="runs/smokecheck.json")
    args = parser.parse_args()
    prediction = read_json(resolve(args.prediction))
    errors = validate_prediction(prediction, read_json(ROOT / "schema/prediction.schema.json"))
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    refs = [r for r in read_jsonl(ROOT / "data/references.jsonl") if r["item_id"] == prediction["item_id"]]
    if len(refs) != 1:
        parser.error("prediction must match exactly one reference item")
    reference = refs[0]
    annotation = read_json(resolve(reference.get("annotation_path", "annotations/view_F.json")))
    diagnostics = diagnostic_evaluation(prediction, reference, annotation)
    if not args.allow_draft:
        parser.error("This sample provides diagnostics only, not a benchmark. Use --allow-draft; blockers: " +
                     ", ".join(diagnostics["benchmark"]["blockers"]))
    comparisons = {rid: {"expected": state, "predicted": prediction["track1"]["relations"][rid]["state"], "match": state == prediction["track1"]["relations"][rid]["state"]} for rid, state in reference["relations"].items()}
    report = {
        "item_id": prediction["item_id"], "mode": "sample_smokecheck",
        "reference_status": reference["annotation_status"], "independent_source_groups": 1,
        "relation_matches": sum(row["match"] for row in comparisons.values()),
        "relations_compared": len(comparisons), "relations": comparisons,
        "action_rules": check_actions(prediction, reference),
        "diagnostics": diagnostics,
        "not_measured": ["benchmark_V3", "benchmark_V4", "free_text_factuality", "footprint_truth", "unobservable_region_geometry", "future_prediction", "ego_motion", "generalization", "confidence_interval"],
        "interpretation": "Draft comparison for pipeline debugging. Not a human-reviewed benchmark score.",
    }
    output = resolve(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
