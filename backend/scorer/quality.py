"""Reference quality (L1–L3), leak check (§8) and Test freeze.

Input formats (files under backend/store, written by the data part or tools/import_references.py):

annotation_rounds.jsonl — pre-consensus records, one line per (item, annotator):
  {"item_id": "pilot_001", "annotator": "A", "stage": "pre_consensus",
   "fields": {"R1": "P", "R2": "U", "R3": "A", "R4": "A", "sidewalk_left": "A", ...}}

splits/<version>.json:
  {"version": "split-0.1", "assignments": {"pilot_001": "test", ...}}
  items.jsonl rows may carry "source_group_id", and for temporal inputs
  "decision_time" and "input_frames": [{"timestamp": ...}] (Track 1 single images have none).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict

from .score import RELATIONS_ONLY
from .v11.contract import VERSION as V11, CORE, FIELDS

RELATIONS = ["R1", "R2", "R3", "R4"]
STATES = ["P", "A", "U"]


def _h(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                          .encode()).hexdigest()


# ------------------------------------------------------------------ L1, L2

def agreement(rounds: list[dict]) -> dict:
    pre = [r for r in rounds if r.get("stage", "pre_consensus") == "pre_consensus"]
    if not pre:
        return {"status": "not_computed", "reason": "no pre-consensus annotation records submitted", "fields": {}}
    by_item = defaultdict(dict)
    for r in pre:
        by_item[r["item_id"]][r["annotator"]] = r.get("fields", {})
    fields = sorted({f for r in pre for f in r.get("fields", {})})
    out = {}
    for f in fields:
        pairs = []
        for iid, anns in by_item.items():
            names = sorted(a for a, v in anns.items() if v.get(f) is not None)
            if len(names) >= 2:
                pairs.append((anns[names[0]][f], anns[names[1]][f]))
        n = len(pairs)
        if n == 0:
            out[f] = {"n_double": 0, "l1": None, "l2_kappa": None, "status": "not_applicable",
                      "reason": "no item annotated by two annotators"}
            continue
        po = sum(a == b for a, b in pairs) / n
        ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
        pe = sum(ca[c] / n * cb[c] / n for c in set(ca) | set(cb))
        kappa = None if pe == 1 else (po - pe) / (1 - pe)
        out[f] = {"n_double": n, "l1": round(po, 6), "pe": round(pe, 6),
                  "l2_kappa": None if kappa is None else round(kappa, 6),
                  "l2_status": "not_applicable" if kappa is None else "computed",
                  "l2_reason": "pe = 1 (both annotators always chose the same single value)" if kappa is None else None,
                  "status": "computed"}
    return {"status": "computed", "reason": None, "fields": out}


# ------------------------------------------------------------------ L3

def _state(ref, rel):
    v = (ref.get("relations") or {}).get(rel)
    return v.get("state") if isinstance(v, dict) else v


def coverage(references: dict, items: dict, schema_version="1.0") -> dict:
    reviewed = [r for r in references.values() if r.get("annotation_status") == "Reviewed"]
    cells = {}
    for h in CORE if schema_version == V11 else RELATIONS:
        for c in STATES:
            ids = [r["item_id"] for r in reviewed if _state(r, h) == c
                   and (schema_version != V11 or h in r.get("reviewed_fields", []))]
            groups = {items.get(i, {}).get("source_group_id") for i in ids} - {None}
            cells[f"{h}.{c}"] = {"n_items": len(ids), "n_source_groups": len(groups)}
    return {"n_reviewed": len(reviewed),
            "n_source_groups": len({items.get(r["item_id"], {}).get("source_group_id") for r in reviewed} - {None}),
            "cells": cells, "empty_cells": [k for k, v in cells.items() if v["n_items"] == 0]}


# ------------------------------------------------------------------ leak check

def leak_check(split: dict, items: dict) -> dict:
    assign = split.get("assignments", {})
    group_splits = defaultdict(set)
    no_group = []
    for iid, sp in assign.items():
        g = items.get(iid, {}).get("source_group_id")
        if g:
            group_splits[g].add(sp)
        else:
            no_group.append(iid)
    cross = {g: sorted(s) for g, s in group_splits.items() if len(s) > 1}
    late, temporal = [], 0
    for iid in assign:
        it = items.get(iid, {})
        if it.get("decision_time") is None or not it.get("input_frames"):
            continue
        temporal += 1
        bad = [f["timestamp"] for f in it["input_frames"] if f["timestamp"] > it["decision_time"]]
        if bad:
            late.append({"item_id": iid, "decision_time": it["decision_time"], "late_frames": bad})
    unknown = [iid for iid in assign if iid not in items]
    passed = not cross and not late and not no_group and not unknown
    return {"version": split.get("version"), "passed": passed,
            "group_split_check": {"status": "fail" if cross else ("incomplete" if no_group else "pass"),
                                  "groups_in_multiple_splits": cross, "items_without_source_group": no_group},
            "timestamp_check": {"status": "fail" if late else ("not_applicable" if temporal == 0 else "pass"),
                                "n_temporal_items": temporal, "violations": late},
            "unknown_items": unknown,
            "limits": "Only the two automatic checks above; leaks outside their scope are not detected."}


def freeze_manifest(split: dict, items: dict, references: dict, scorer_commit: str, schema_sha: str,
                    split_name: str = "test") -> dict:
    """Refuses (returns errors) unless the leak check passes and every test item has a Reviewed reference."""
    ids = sorted(i for i, s in split.get("assignments", {}).items() if s == split_name)
    errors = []
    leak = leak_check(split, items)
    if not leak["passed"]:
        errors.append("leak check did not pass")
    if not ids:
        errors.append(f"no items assigned to '{split_name}'")
    not_reviewed = [i for i in ids if (references.get(i) or {}).get("annotation_status") != "Reviewed"]
    if not_reviewed:
        errors.append(f"{len(not_reviewed)} {split_name} item(s) without a Reviewed reference")
    partial = [i for i in ids if (references.get(i) or {}).get("review_scope") == RELATIONS_ONLY]
    if split.get("schema_version") == V11:
        partial = [i for i in ids if (r := references.get(i) or {}).get("annotation_status") == "Reviewed"
                   and (r.get("schema_version") != V11 or not set(FIELDS).issubset(r.get("reviewed_fields", []))
                        or not r.get("objects_reviewed") or not r.get("actions_reviewed")
                        or not {"sidewalk_left", "sidewalk_right", "traffic_direction", "direction_match"}
                        .issubset(r.get("attributes_reviewed_fields", []))
                        or any(_state(r, h) in ("P", "U") and h not in r.get("evidence_reviewed_fields", []) for h in CORE))]
    if partial:
        errors.append(f"{len(partial)} {split_name} item(s) with a partial reference")
    if errors:
        return {"frozen": False, "errors": errors, "not_reviewed": not_reviewed,
                "partial_references": partial, "leak_check": leak}
    return {"frozen": True, "version": split.get("version"), "schema_version": split.get("schema_version", "1.0"),
            "split": split_name, "item_ids": ids,
            "items_sha256": _h([items[i] for i in ids]), "references_sha256": _h([references[i] for i in ids]),
            "scorer_commit": scorer_commit, "schema_sha256": schema_sha, "leak_check": leak}
