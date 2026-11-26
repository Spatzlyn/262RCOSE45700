"""Export Track 2 scoring for a run: official (Reviewed GT only) + Draft-target diagnostic (not official).

  python -m backend.tools.export_track2_scoring <out_dir> <run_id>

Draft-target diagnostic: compares predictions with the AI Hub isObjectA pedestrian on every decision time,
ignoring the event time (tc / H / tau are not reviewed yet). It answers "did the model point at the accident
pedestrian?", not the spec's "will collide within H seconds" question, so it is never an official TargetAcc.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

from backend.app import track2_store as t2
from backend.scorer import track2


def main():
    out, run_id = Path(sys.argv[1]), sys.argv[2]
    out.mkdir(parents=True, exist_ok=True)
    res = t2.score(run_id, write=False)
    meta, its, refs, preds = t2.run_meta(run_id), t2.items(), t2.references(), t2.predictions(run_id)
    rows = []
    for r in res["items"]:
        it, ref, p = its[r["item_id"]], refs.get(r["item_id"]) or {}, preds.get(r["item_id"]) or {}
        tids = ref.get("target_candidate_ids") or []
        gbox = ref.get("target_box_xyxy_px")
        sel, box = r["selection"], r["localization"]
        u = track2.iou(box["bbox_xyxy_px"], gbox) if box["valid"] and gbox else (0.0 if gbox else None)
        bl = track2.baselines(it, ref) if tids else {}
        chosen = next((c for c in it["candidates"] if c["candidate_id"] == sel["target_id"]), None)
        rows.append({
            "item_id": r["item_id"], "clip_id": it["clip_id"], "decision_time_s": it["decision_time_s"],
            "n_candidates": len(it["candidates"]), "official_scored": r["gt"]["eligible"],
            "official_excluded_reason": r["gt"]["excluded_reason"], "reference_version": r["gt"]["reference_version"],
            "draft_target_ids": "|".join(map(str, tids)), "pred_target_id": sel["target_id"],
            "selection_status": sel["status"],
            "draft_select_correct": None if not tids else ("O" if sel["valid"] and sel["target_id"] in tids else "X"),
            "pred_box": json.dumps(box["bbox_xyxy_px"]), "draft_target_box": json.dumps(gbox),
            "box_status": box["status"], "draft_iou": None if u is None else round(u, 4),
            "draft_acc50": None if u is None else ("O" if u >= 0.5 else "X"),
            "select_box_same_person_iou": None if not (chosen and box["valid"]) else
                round(track2.iou(chosen["bbox_xyxy_px"], box["bbox_xyxy_px"]), 4),
            "baseline_bottom_most": None if not bl else ("O" if bl["bottom_most"] else "X"),
            "baseline_largest": None if not bl else ("O" if bl["largest"] else "X"),
            "baseline_random_expected": None if not bl else round(bl["random_expected"], 4),
            "select_source": p.get("select", {}).get("source"), "box_source": p.get("box", {}).get("source")})
    with open(out / "items_track2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def rate(xs):
        xs = [x for x in xs if x is not None]
        return {"value": round(float(np.mean(xs)), 4) if xs else None, "n": len(xs)}

    def summ(sub):
        return {"n_items": len(sub),
                "select_acc": rate([r["draft_select_correct"] == "O" for r in sub if r["draft_select_correct"]]),
                "miou": rate([r["draft_iou"] for r in sub]),
                "acc50": rate([r["draft_acc50"] == "O" for r in sub if r["draft_acc50"]]),
                "baseline_bottom_most": rate([r["baseline_bottom_most"] == "O" for r in sub if r["baseline_bottom_most"]]),
                "baseline_largest": rate([r["baseline_largest"] == "O" for r in sub if r["baseline_largest"]]),
                "baseline_random_expected": rate([r["baseline_random_expected"] for r in sub]),
                "multi_candidate_select_acc": rate([r["draft_select_correct"] == "O" for r in sub
                                                    if r["draft_select_correct"] and r["n_candidates"] > 1])}
    by_clip = {c: summ([r for r in rows if r["clip_id"] == c]) for c in sorted({r["clip_id"] for r in rows})}
    summary = {"run_id": run_id, "track": "track2", "scorer_version": res["scorer_version"],
               "scorer_commit": res["scorer_commit"], "result_hash": res["result_hash"],
               "reference_versions": res["reference_versions"], "response_policy": meta.get("response_policy"),
               "attempt_sources": meta.get("attempt_sources"),
               "official": {k: res["summary"][k] for k in ("n_requests", "n_eligible", "labels", "excluded",
                                                           "format_status")}
               | {"target_acc": res["summary"]["overall"]["target_acc"], "miou": res["summary"]["overall"]["miou"]},
               "draft_target_diagnostic": {"note": "AI Hub isObjectA target, event time ignored; NOT official",
                                           "overall": summ(rows), "by_clip": by_clip}}
    (out / "summary_track2.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{run_id}.official.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
