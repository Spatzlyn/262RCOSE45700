"""Track 2 data tools.

build      items + Draft references from AI Hub 597 frame labels (target = isObjectA pedestrian)
  python -m backend.tools.track2_data build --manifest data_handoff/track2/source_manifest.json \
      --labels <dir with one folder of frame JSONs per clip> [--frames <dir/<clip>/<seq:03d>.jpg>]
  Decision times = labeled frames where the isObjectA pedestrian is visible (boxes exist only there).
  Candidates = every pedestrian box on that frame, numbered 1..n left to right (neutral order).
  Draft target / box come from isObjectA. Event time is left Missing: the data part reviews it.

review     turn Drafts into Reviewed references from a clip-level review file (data part fills it)
  python -m backend.tools.track2_data review <clip_reviews.jsonl> [--dry-run]
  one line per clip: {"clip_id", "reference_version", "reviewers": [...],
                      "event_frame": <sequence_frame_number of first contact> | null,
                      "event_time_status": "Reviewed" | "Missing", "targets_confirmed": true,
                      "horizon_s": 2.0, "exclude_items": [], "target_overrides": {item_id: {...}}}

export     candidate list for the model team (same IDs they must draw on the numbered image)
  python -m backend.tools.track2_data export <out.json>

import-run register model outputs: <dir>/<item_id>/{select_raw.txt, box_raw.txt, input_record.json, ...}
  python -m backend.tools.track2_data import-run <run_id> <dir> --label "..." [--model-json run_meta.json]
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from backend.app import store, track2_store as t2

FPS = 15
N_FRAMES = 150


def _xyxy(b):
    x, y, w, h = b
    return [x, y, x + w, y + h]


def short(clip):
    p = clip.split("_")  # bb_1_160630_pedestrian_223_24150
    return f"{p[2]}_{p[4]}_{p[5]}"


def cmd_build(a):
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    version = f"t2-draft-aihub-isObjectA-{dt.date.today():%Y%m%d}"
    items, refs = [], []
    frames_out = t2.root() / "frames"
    for c in man["candidates"]:
        clip = c["clip_id"]
        labels = sorted((Path(a.labels) / clip).glob("*.json"))
        for lp in labels:
            lab = json.loads(lp.read_text(encoding="utf-8"))
            peds = [o for o in lab["objects"] if o["category"] == "pedestrian"]
            targets = [o for o in peds if o.get("isObjectA")]
            if not targets:
                continue
            seq = lab["sequence_frame_number"]
            peds = sorted(peds, key=lambda o: (o["bbox"][0] + o["bbox"][2] / 2, o["bbox"][1]))
            cands = [{"candidate_id": i + 1, "bbox_xyxy_px": _xyxy(o["bbox"]), "source": "aihub_frame_label"}
                     for i, o in enumerate(peds)]
            tids = [cands[i]["candidate_id"] for i, o in enumerate(peds) if o.get("isObjectA")]
            iid = f"t2_{short(clip)}_f{seq:03d}"
            t = round((seq - 1) / FPS, 6)
            items.append({"item_id": iid, "track": "track2", "data_kind": "real", "clip_id": clip,
                          "source_group_id": clip, "video_relpath": c["video"], "fps": FPS, "n_frames": N_FRAMES,
                          "duration_s": N_FRAMES / FPS, "label_frame": seq, "decision_frame_index": seq - 1,
                          "decision_time_s": t, "width": lab["width"], "height": lab["height"],
                          "candidates": cands, "candidate_order": "left_to_right_by_box_center",
                          "frame_url_available": False,
                          "input_rule": "frames with timestamp <= decision_time_s only (about every 0.2 s plus the last)"})
            refs.append({"item_id": iid, "track": "track2", "annotation_status": "Draft",
                         "reference_version": version, "event_time_s": None, "event_time_status": "Missing",
                         "horizon_s": 2.0, "target_candidate_ids": tids, "n_targets": len(tids),
                         "target_visible": True,
                         "target_box_xyxy_px": cands[tids[0] - 1]["bbox_xyxy_px"] if len(tids) == 1 else None,
                         "target_source": "aihub_isObjectA (draft, not human-confirmed)", "reviewers": []})
            if a.frames:
                src = Path(a.frames) / clip / f"{seq:03d}.jpg"
                if src.exists():
                    _render(src, cands, frames_out / f"{iid}.jpg", frames_out / f"{iid}_numbered.jpg")
                    items[-1]["frame_url_available"] = True
    old_refs = t2.references()
    keep = {r["item_id"]: r for r in refs}
    # never downgrade an existing Reviewed reference
    for iid, r in old_refs.items():
        if r.get("annotation_status") == "Reviewed":
            keep[iid] = r
    t2.write_jsonl(t2.root() / "items.jsonl", items)
    t2.write_jsonl(t2.root() / "references.jsonl", list(keep.values()))
    for r in refs:
        store.write_json(t2.root() / "reference_history" / r["item_id"] / f"{r['reference_version']}.json", r)
    by_clip = {}
    for it in items:
        by_clip[it["clip_id"]] = by_clip.get(it["clip_id"], 0) + 1
    return {"ok": True, "items": len(items), "by_clip": by_clip, "draft_version": version}


def _render(src, cands, plain_out, numbered_out):
    from PIL import Image, ImageDraw, ImageFont
    plain_out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        rgb = im.convert("RGB")
    rgb.save(plain_out, quality=92)
    draw = ImageDraw.Draw(rgb)
    try:
        font = ImageFont.truetype("arial.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    for c in cands:  # same neutral style for every candidate (no hint about the target)
        x1, y1, x2, y2 = c["bbox_xyxy_px"]
        draw.rectangle([x1, y1, x2, y2], outline=(255, 255, 0), width=3)
        tx, ty = x1, max(0, y1 - 40)
        draw.rectangle([tx, ty, tx + 40, ty + 38], fill=(0, 0, 0))
        draw.text((tx + 8, ty + 1), str(c["candidate_id"]), fill=(255, 255, 0), font=font)
    rgb.save(numbered_out, quality=92)


def cmd_review(a):
    rows = [json.loads(x) for x in Path(a.file).read_text(encoding="utf-8").splitlines() if x.strip()]
    its, refs = t2.items(), t2.references()
    errors, new = {}, []
    for r in rows:
        clip = r.get("clip_id")
        e = []
        clip_items = [i for i in its.values() if i["clip_id"] == clip]
        if not clip_items:
            e.append("unknown clip_id")
        if not r.get("reviewers"):
            e.append("reviewers required (human review)")
        if not r.get("reference_version"):
            e.append("reference_version required")
        if r.get("event_time_status") not in ("Reviewed", "Missing"):
            e.append("event_time_status must be Reviewed or Missing")
        if r.get("event_time_status") == "Reviewed" and not isinstance(r.get("event_frame"), int):
            e.append("event_frame (sequence_frame_number of first contact) required when Reviewed")
        if not r.get("targets_confirmed"):
            e.append("targets_confirmed must be true (isObjectA targets checked by a person)")
        if e:
            errors[clip] = e
            continue
        tc = None if r["event_time_status"] == "Missing" else round((r["event_frame"] - 1) / FPS, 6)
        for it in clip_items:
            if it["item_id"] in r.get("exclude_items", []):
                continue
            base = dict(refs.get(it["item_id"]) or {})
            ref = {**base, "annotation_status": "Reviewed", "reference_version": r["reference_version"],
                   "event_time_s": tc, "event_time_status": r["event_time_status"],
                   "event_frame": r.get("event_frame"), "horizon_s": r.get("horizon_s", 2.0),
                   "reviewers": r["reviewers"], "target_source": "aihub_isObjectA confirmed by reviewer",
                   **(r.get("target_overrides") or {}).get(it["item_id"], {})}
            hist = t2.root() / "reference_history" / it["item_id"] / f"{ref['reference_version']}.json"
            if hist.exists() and json.loads(hist.read_text(encoding="utf-8")) != ref:
                errors.setdefault(clip, []).append(f"{it['item_id']}: version exists with different content")
            new.append(ref)
    if errors or a.dry_run:
        return {"ok": not errors, "dry_run": a.dry_run, "errors": errors, "n": len(new)}
    for ref in new:
        refs[ref["item_id"]] = ref
        store.write_json(t2.root() / "reference_history" / ref["item_id"] / f"{ref['reference_version']}.json", ref)
    t2.write_jsonl(t2.root() / "references.jsonl", list(refs.values()))
    return {"ok": True, "reviewed_items": len(new)}


def cmd_export(a):
    rows = [{"item_id": i["item_id"], "clip_id": i["clip_id"], "video_relpath": i["video_relpath"],
             "decision_time_s": i["decision_time_s"], "decision_frame_index": i["decision_frame_index"],
             "candidate_ids": [c["candidate_id"] for c in i["candidates"]], "candidates": i["candidates"],
             "numbered_image": f"frames/{i['item_id']}_numbered.jpg" if i.get("frame_url_available") else None}
            for i in t2.items().values()]
    Path(a.out).write_text(json.dumps({"note": "Draw these candidate IDs on the decision frame; no GT inside.",
                                       "items": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "items": len(rows), "out": a.out}


def cmd_import_run(a):
    its = t2.items()
    base = Path(a.dir)
    rd = t2.root() / "runs" / a.run_id
    if (rd / "run.json").exists():
        return {"ok": False, "errors": [f"run {a.run_id} exists; use a new run_id"]}
    reqs, errors = [], []
    for sub in sorted(p for p in base.iterdir() if p.is_dir()):
        iid = sub.name
        if iid not in its:
            errors.append(f"{iid}: unknown item")
            continue
        rec = json.loads((sub / "input_record.json").read_text(encoding="utf-8")) if (sub / "input_record.json").exists() else {}
        it = its[iid]
        if rec and abs(float(rec.get("decision", it["decision_time_s"])) - it["decision_time_s"]) > 1e-3:
            errors.append(f"{iid}: decision time {rec.get('decision')} != {it['decision_time_s']}")
        if rec and sorted(rec.get("candidate_ids", [])) != sorted(c["candidate_id"] for c in it["candidates"]):
            errors.append(f"{iid}: candidate ids differ from item")
        pred = {"input_record": rec}
        for task in ("select", "box"):
            raw = sub / f"{task}_raw.txt"
            val = sub / f"{task}_validation.json"
            pred[task] = ({"status": "ok", "output_text": raw.read_text(encoding="utf-8"),
                           "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                           "model_team_validation": json.loads(val.read_text(encoding="utf-8")) if val.exists() else None}
                          if raw.exists() else {"status": "error", "error": f"{task}_raw.txt missing"})
        store.write_json(rd / "predictions" / f"{iid}.json", pred)
        reqs.append({"item_id": iid, "data_kind": "real"})
    if errors:
        return {"ok": False, "errors": errors}
    meta = json.loads(Path(a.model_json).read_text(encoding="utf-8")) if a.model_json else {}
    store.write_json(rd / "run.json", {"run_id": a.run_id, "track": "track2", "data_kind": "real",
                                       "label": a.label, "status": "imported", "source_dir": str(base), **meta})
    store.write_json(rd / "requests.json", reqs)
    return {"ok": True, "run_id": a.run_id, "n_requests": len(reqs)}


def cmd_import_handoff(a):
    """Model-team git handoff: <base>/{predictions.jsonl, 문항별_예측_및_출처.csv, outputs/<item>/...}."""
    import csv as _csv
    import io
    import subprocess
    root = Path(__file__).resolve().parents[2]
    show = lambda path: subprocess.run(["git", "show", f"{a.ref}:{path}"], cwd=root, capture_output=True,
                                       check=True).stdout
    commit = subprocess.run(["git", "rev-parse", a.ref], cwd=root, capture_output=True, text=True,
                            check=True).stdout.strip()
    rows = list(_csv.DictReader(io.StringIO(show(f"{a.base}/문항별_예측_및_출처.csv").decode("utf-8-sig"))))
    its = t2.items()
    rd = t2.root() / "runs" / a.run_id
    if (rd / "run.json").exists():
        return {"ok": False, "errors": [f"run {a.run_id} exists; use a new run_id"]}
    errors, preds, sources = [], {}, {"select": {}, "box": {}}
    for r in rows:
        iid = r["item_id"]
        it = its.get(iid)
        if it is None:
            errors.append(f"{iid}: unknown item")
            continue
        if abs(float(r["decision_time_s"]) - it["decision_time_s"]) > 1e-3 or int(r["decision_frame_index"]) != it["decision_frame_index"]:
            errors.append(f"{iid}: decision time/frame differs from item")
        if (int(r["width"]), int(r["height"])) != (it["width"], it["height"]):
            errors.append(f"{iid}: resolution {r['width']}x{r['height']} != item {it['width']}x{it['height']}")
        pred = {}
        for task in ("select", "box"):
            raw = show(f"{a.base}/{r[task + '_raw_path']}")
            val = show(f"{a.base}/{r[task + '_validation_path']}")
            if hashlib.sha256(raw).hexdigest() != r[task + "_raw_sha256"]:
                errors.append(f"{iid}/{task}: raw sha256 mismatch")
            src = r[task + "_source"]
            sources[task][src.split("/")[0]] = sources[task].get(src.split("/")[0], 0) + 1
            pred[task] = {"status": "ok", "output_text": raw.decode("utf-8"), "sha256": r[task + "_raw_sha256"],
                          "source": src, "model_team_validation": json.loads(val)}
        preds[iid] = pred
    if errors:
        return {"ok": False, "errors": errors}
    for iid, pred in preds.items():
        store.write_json(rd / "predictions" / f"{iid}.json", pred)
    store.write_json(rd / "run.json", {
        "run_id": a.run_id, "track": "track2", "data_kind": "real", "status": "imported", "label": a.label,
        "source": {"git_ref": commit, "path": a.base},
        "model": {"model_id": "google/gemma-4-E4B-it", "revision": "4ecc2ba63bcac23ba4a767fc87025b1450f84c9c"},
        "response_policy": a.response_policy, "attempt_sources": sources,
        "official": a.response_policy == "first_response"})
    store.write_json(rd / "requests.json", [{"item_id": i, "data_kind": "real"} for i in sorted(preds)])
    return {"ok": True, "run_id": a.run_id, "n_requests": len(preds), "attempt_sources": sources}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("--manifest", required=True); b.add_argument("--labels", required=True)
    b.add_argument("--frames")
    r = sp.add_parser("review"); r.add_argument("file"); r.add_argument("--dry-run", action="store_true")
    e = sp.add_parser("export"); e.add_argument("out")
    i = sp.add_parser("import-run"); i.add_argument("run_id"); i.add_argument("dir"); i.add_argument("--label", default="")
    i.add_argument("--model-json")
    h = sp.add_parser("import-handoff"); h.add_argument("run_id"); h.add_argument("--ref", required=True)
    h.add_argument("--base", required=True); h.add_argument("--label", default="")
    h.add_argument("--response-policy", default="first_response",
                   help="first_response | valid_responses_collected_across_attempts")
    a = ap.parse_args()
    out = {"build": cmd_build, "review": cmd_review, "export": cmd_export, "import-run": cmd_import_run,
           "import-handoff": cmd_import_handoff}[a.cmd](a)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
