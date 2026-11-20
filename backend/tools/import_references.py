"""Import data-part files into backend/store with validation (no API needed).

  python -m backend.tools.import_references references <file.jsonl>          # GT (Draft/Reviewed/Missing)
  python -m backend.tools.import_references rounds <file.jsonl>              # 2-annotator pre-consensus (L1, L2)
  python -m backend.tools.import_references statements <run_id> <file.jsonl> # human statement reviews (V13, V14)
  python -m backend.tools.import_references split <file.json>                # split assignment
  add --dry-run to validate only.

Every imported reference version is kept under store/reference_history/<item>/<version>.json and a
version that already exists with different content is refused (versions are immutable).
After importing, the API re-scores automatically (results are cached by input hash).
"""
import argparse
import json
import sys
from pathlib import Path

from backend.app import store
from backend.scorer.score import RELATIONS_ONLY, RELATIONS, ref_state
from backend.scorer.validate import object_errors
from backend.scorer.v11.contract import VERSION as V11
from backend.scorer.v11.reference import check_reference as check_reference_v11

STATUSES = {"Missing", "Draft", "Reviewed"}
STATES = {"P", "A", "U"}


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def check_reference(r, items):
    e = []
    iid = r.get("item_id")
    if iid not in items:
        e.append("unknown item_id")
    st = r.get("annotation_status")
    if st not in STATUSES:
        e.append(f"annotation_status must be one of {sorted(STATUSES)}")
    if st in ("Draft", "Reviewed") and not r.get("reference_version"):
        e.append("reference_version is required for Draft/Reviewed")
    scope = r.get("review_scope")
    if scope is not None and scope != RELATIONS_ONLY:
        e.append("review_scope must be relations_only when provided")
    for rel, v in (r.get("relations") or {}).items():
        s = v.get("state") if isinstance(v, dict) else v
        if rel not in ("R1", "R2", "R3", "R4") or (s is not None and s not in STATES):
            e.append(f"relations.{rel}: state must be P/A/U or null (Missing)")
    if scope == RELATIONS_ONLY and st == "Reviewed" and not any(ref_state(r, rel) for rel in RELATIONS):
        e.append("a Reviewed relations_only reference needs at least one confirmed relation")
    e += object_errors(r.get("objects", []), "objects")
    rules = r.get("action_rules")
    if rules:
        allowed = {(p["code"], p["condition"]) for p in rules.get("allowed_pairs", [])}
        forbidden = {(p["code"], p["condition"]) for p in rules.get("forbidden_pairs", [])}
        if allowed & forbidden:
            e.append("action_rules: allowed and forbidden overlap")
        for g in rules.get("required_groups", []):
            if not g.get("alternatives"):
                e.append("action_rules: required group without alternatives")
            for a in g.get("alternatives", []):
                if (a["code"], a["condition"]) not in allowed:
                    e.append("action_rules: required alternative not in allowed_pairs")
    dm = (r.get("attributes") or {}).get("direction_match")
    if dm is not None and dm not in ("Consistent", "Conflicting", "Unknown", "Not applicable"):
        e.append("attributes.direction_match has an unknown value")
    return e


def import_references(path, dry):
    items = store.items()
    rows = read_jsonl(path)
    versions = {r.get("schema_version", "1.0") for r in rows}
    if len(versions) != 1 or not versions.issubset({"1.0", V11}):
        return {"ok": False, "errors": {"file": ["use one explicit schema version per reference file"]}}
    version = next(iter(versions))
    validator = check_reference_v11 if version == V11 else check_reference
    errors = {r.get("item_id", f"line {i+1}"): validator(r, items) for i, r in enumerate(rows)}
    hist = store.STORE / ("reference_history_v11" if version == V11 else "reference_history")
    for r in rows:
        v = r.get("reference_version")
        if not r.get("item_id") or errors[r["item_id"]]:
            continue
        p = hist / r["item_id"] / f"{v}.json"
        if v and p.exists() and json.loads(p.read_text(encoding="utf-8")) != r:
            errors[r["item_id"]].append(f"reference_version {v} already exists with different content")
    bad = {k: v for k, v in errors.items() if v}
    if bad or dry:
        return {"ok": not bad, "dry_run": dry, "errors": bad, "n": len(rows)}
    for r in rows:
        if r.get("reference_version"):
            store.write_json(hist / r["item_id"] / f"{r['reference_version']}.json", r)
    cur = store.references(version)
    cur.update({r["item_id"]: r for r in rows})
    store.reference_path(version).write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in cur.values()), encoding="utf-8")
    return {"ok": True, "n": len(rows), "status_counts": {s: sum(r.get("annotation_status") == s for r in rows)
                                                          for s in STATUSES}}


def import_rounds(path, dry):
    items = store.items()
    rows = read_jsonl(path)
    bad = [f"line {i+1}" for i, r in enumerate(rows)
           if r.get("item_id") not in items or not r.get("annotator") or not isinstance(r.get("fields"), dict)
           or (r.get("schema_version") == V11 and (r.get("annotator_kind") != "human" or r.get("stage") != "pre_consensus"))]
    if bad or dry:
        return {"ok": not bad, "dry_run": dry, "errors": bad, "n": len(rows)}
    key = lambda r: (r.get("schema_version", "1.0"), r["item_id"], r["annotator"], r.get("stage", "pre_consensus"))
    cur = {key(r): r for r in store.annotation_rounds()}
    cur.update({key(r): r for r in rows})
    (store.STORE / "annotation_rounds.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in cur.values()), encoding="utf-8")
    return {"ok": True, "n": len(rows)}


def import_statements(run_id, path, dry):
    if not store.run_meta(run_id):
        return {"ok": False, "errors": [f"unknown run {run_id}"]}
    ids = {q["item_id"] for q in store.requests(run_id)}
    rows = read_jsonl(path)
    bad = [f"line {i+1}" for i, r in enumerate(rows)
           if r.get("item_id") not in ids or not r.get("reviewer")
           or any(not isinstance(s.get("error"), bool) for s in r.get("statements", []))]
    if bad or dry:
        return {"ok": not bad, "dry_run": dry, "errors": bad, "n": len(rows)}
    cur = {r["item_id"]: r for r in store.statement_reviews(run_id)}
    cur.update({r["item_id"]: r for r in rows})
    (store.run_dir(run_id) / "statement_reviews.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in cur.values()), encoding="utf-8")
    return {"ok": True, "n": len(rows)}


def import_split(path, dry):
    sp = json.loads(Path(path).read_text(encoding="utf-8"))
    items = store.items()
    errors = []
    if not sp.get("version"):
        errors.append("version is required")
    bad = [i for i, s in sp.get("assignments", {}).items() if i not in items or s not in ("train", "dev", "test")]
    if bad:
        errors.append(f"unknown items or split names: {bad[:10]}")
    if (store.STORE / "splits" / f"{sp.get('version')}.freeze.json").exists():
        errors.append("this split version is frozen; create a new version")
    if errors or dry:
        return {"ok": not errors, "dry_run": dry, "errors": errors}
    store.write_json(store.STORE / "splits" / f"{sp['version']}.json", sp)
    return {"ok": True, "version": sp["version"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["references", "rounds", "statements", "split"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.kind == "references":
        out = import_references(a.args[0], a.dry_run)
    elif a.kind == "rounds":
        out = import_rounds(a.args[0], a.dry_run)
    elif a.kind == "statements":
        out = import_statements(a.args[0], a.args[1], a.dry_run)
    else:
        out = import_split(a.args[0], a.dry_run)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
