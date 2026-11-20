"""Non-destructive v1.1 store migration. Run without --apply to review changes.

Stop API/worker and back up the mounted store before applying. Source is the
review package store; target is the *existing* deployment store.
"""
import argparse
import json
import shutil
from pathlib import Path


def read_jsonl(p):
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()] if p.exists() else []


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1]/"store")
    cli.add_argument("--target", type=Path, required=True)
    cli.add_argument("--apply", action="store_true")
    a = cli.parse_args()
    src, dest = a.source.resolve(), a.target.resolve()
    if src == dest or not (dest/"items.jsonl").exists():
        cli.error("target must be a different, existing deployment store")
    items = {x["item_id"]: x for x in read_jsonl(dest/"items.jsonl")}
    adds, updates = [], []
    for i in read_jsonl(src/"items.jsonl"):
        iid = i["item_id"]
        if i.get("data_kind") != "real" or not i.get("source_group_id"):
            continue
        if iid not in items:
            items[iid] = i
            adds.append(iid)
        else:
            row = items[iid]
            if row.get("image_sha256") != i.get("image_sha256"):
                raise SystemExit(f"image hash conflict: {iid}; no changes made")
            if row.get("source_group_id") not in (None, i["source_group_id"]):
                raise SystemExit(f"source group conflict: {iid}; no changes made")
            if not row.get("source_group_id"):
                row["source_group_id"] = i["source_group_id"]
                updates.append(iid)
            if "schema_versions" not in row and "schema_versions" in i:
                row["schema_versions"] = i["schema_versions"]
                if iid not in updates: updates.append(iid)
    path = dest/"references_v11.jsonl"
    refs = {r["item_id"]: r for r in read_jsonl(path)}
    new = []
    for r in read_jsonl(src/"references_v11.jsonl"):
        if r["item_id"] not in refs:
            refs[r["item_id"]] = r
            new.append(r["item_id"])
    paths = [src/"splits"/"v11-pilot-dev.json"]
    paths += list((src/"reference_history_v11").glob("*/*.json"))
    for rid in ("RUN-PILOT6-V11-A-PREVIEW", "RUN-PILOT6-V11-B-PREVIEW"):
        if not (dest/"runs"/rid).exists():
            paths += list((src/"runs"/rid).glob("*.json"))
    pending = [p for p in paths if not (dest/p.relative_to(src)).exists()]
    print(json.dumps({"apply": a.apply, "new_items": adds, "updated_metadata": updates,
                      "new_draft_refs": new, "new_files": [str(p.relative_to(src)) for p in pending]}, ensure_ascii=False, indent=2))
    if not a.apply:
        return
    def atomic_jsonl(target, rows):
        temp = target.with_suffix(target.suffix+".v11tmp")
        temp.write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in rows.values()), encoding="utf-8")
        temp.replace(target)
    if adds or updates: atomic_jsonl(dest/"items.jsonl", items)
    if new: atomic_jsonl(path, refs)
    for p in pending:
        out = dest/p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    print("v1.1 files installed; existing v1.0 refs and runs untouched")


if __name__ == "__main__":
    main()
