"""Export per-item v1.1 scoring for the model team (official + fence-stripped diagnostic).

  python -m backend.tools.export_v11_scoring <out_dir> <run_id> [<run_id> ...]

official   = stored first responses as is (decoded_output.txt). This is the only official result.
diagnostic = same outputs after removing outer whitespace and one leading/trailing Markdown code fence
             (the model team's offline method). For error analysis only; never an official score.
"""
import copy
import csv
import json
import sys
from pathlib import Path

from backend.app import store
from backend.scorer.score import canonical_hash, load_schema, score_run
from backend.scorer.v11.adapter import aggregate_v11
from backend.scorer.v11.contract import AUX, CORE

FIELDS = list(CORE) + list(AUX)


def strip_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t.strip()


def score(run_id, diagnostic):
    reqs = store.requests(run_id)
    version = store.run_version(store.run_meta(run_id))
    preds = store.predictions(run_id)
    if diagnostic:
        preds = copy.deepcopy(preds)
        for p in preds.values():
            p["output_text"] = strip_fence(p.get("output_text"))
    body = score_run(reqs, preds, store.references(version), schema=load_schema(version),
                     group_of=store.group_of(reqs), statement_reviews=store.statement_reviews(run_id),
                     bootstrap_b=store.BOOTSTRAP_B)
    body["summary"] = aggregate_v11(body["items"], reqs) | {"metrics": body["summary"]["metrics"]}
    body["result_hash"] = canonical_hash({"items": body["items"], "summary": body["summary"]})
    return body


def unvalidated_states(run_id, item_id):
    """States read from the fence-stripped JSON even when the contract check fails (analysis only)."""
    text = strip_fence(store.predictions(run_id)[item_id].get("output_text"))
    try:
        track = json.loads(text).get("track1") or {}
    except (json.JSONDecodeError, AttributeError):
        return {}
    obs = {**(track.get("relations") or {}), **(track.get("context") or {})}
    return {f: (obs.get(f) or {}).get("state") for f in FIELDS if isinstance(obs.get(f), dict)}


def rows_for(run_id, mode, body, meta, refs):
    out = []
    for it in body["items"]:
        ref = refs.get(it["item_id"]) or {}
        obs = {**it["relations"], **it.get("context", {})}
        row = {"run_id": run_id, "prompt": meta["prompt"]["version"], "mode": mode, "item_id": it["item_id"],
               "prediction_status": it["prediction_status"],
               "first_format_error": (it["format_errors"] or [""])[0], "n_format_errors": len(it["format_errors"]),
               "annotation_status": it["annotation_status"], "reference_version": it["reference_version"],
               "item_scored": it["scored"], "item_excluded_reason": it["excluded_reason"] or ""}
        n_scored = n_ok = 0
        for f in FIELDS:
            o = obs[f]
            scored = o["match"] is not None
            n_scored += scored
            n_ok += o["match"] is True
            row[f"{f}_gt"] = o["expected"]
            row[f"{f}_pred"] = o["predicted"] if o["predicted"] is not None else ""
            row[f"{f}_match"] = "" if not scored else ("O" if o["match"] else "X")
            row[f"{f}_excluded_reason"] = "" if scored else (
                "field_not_reviewed" if f not in ref.get("reviewed_fields", []) else "gt_not_scored_class")
        row["fields_scored"] = n_scored
        row["fields_correct"] = n_ok
        if mode != "official":
            raw = unvalidated_states(run_id, it["item_id"]) if it["prediction_status"] != "valid" else {}
            for f in FIELDS:
                row[f"{f}_pred_unvalidated"] = raw.get(f) or ""
        ev = it["diagnostics"].get("evidence") or {}
        row["evidence_V4"] = "; ".join(f"{k}:{v.get('reason') or v['status']}" for k, v in ev.items()) or \
            "excluded: evidence_not_reviewed (evidence_reviewed_fields=[])"
        row["grounding_V3"] = "excluded: objects_not_reviewed" if not ref.get("objects_reviewed") else "computed"
        ae = it["action_eval"]
        row["actions_V10_V12"] = (f"excluded: {ae.get('excluded_reason')}" if ae.get("pass_status") == "excluded"
                                  else f"pass={ae.get('pass')} {'|'.join(ae.get('fail_reasons', []))}")
        row["benchmark_blockers"] = "|".join(it["diagnostics"]["benchmark"]["blockers"])
        out.append(row)
    return out


def metric_table(body):
    s = body["summary"]
    m = s["metrics"]
    pick = lambda d: {k: d.get(k) for k in ("status", "value", "numerator", "n", "reason")}
    rel = {k: pick(m[k]) for k in ("v1_valid", "v2_invalid", "v5_relation_macro_f1", "v6_present_recall",
                                   "v7_false_positive_rate", "v8_unknown_recall", "v9_over_abstention",
                                   "v3_grounding", "v4_evidence", "v10_action_pass_rate", "v13_statement_error_rate")
           if k in m}
    sc = m["v5_relation_macro_f1"].get("supported_class_macro_f1")
    if sc:
        rel["v5_relation_macro_f1"]["supported_class_macro_f1"] = sc
    return {"prediction_status_counts": s["prediction_status_counts"], "n_requests": s["n_requests"],
            "n_scored_items": s["n_scored_items"], "metrics": rel,
            "context_metrics": {k: pick(v) for k, v in s.get("context_metrics", {}).items()}}


def main():
    out = Path(sys.argv[1])
    runs = sys.argv[2:]
    out.mkdir(parents=True, exist_ok=True)
    all_rows, summary = [], {"scorer_commit": store.scorer_commit(), "runs": {}}
    for run_id in runs:
        meta = store.run_meta(run_id)
        version = store.run_version(meta)
        refs = store.references(version)
        summary["runs"][run_id] = {"prompt": meta["prompt"]["version"], "schema_version": version,
                                   "reference_versions": sorted({str((refs.get(q["item_id"]) or {}).get(
                                       "reference_version")) for q in store.requests(run_id)})}
        for mode, diag in (("official", False), ("diagnostic_fence_stripped", True)):
            body = score(run_id, diag)
            summary["scorer_version"] = body["scorer_version"]
            summary["runs"][run_id][mode] = {"result_hash": body["result_hash"], **metric_table(body)}
            all_rows += rows_for(run_id, mode, body, meta, refs)
            (out / f"{run_id}.{mode}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    for mode in ("official", "diagnostic_fence_stripped"):
        rows = [r for r in all_rows if r["mode"] == mode]
        with open(out / f"items_{mode}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
