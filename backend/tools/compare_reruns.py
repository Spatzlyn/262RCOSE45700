"""Run-to-run variation report between two runs over the same items (re-inference, not re-scoring).

  python -m backend.tools.compare_reruns <base_url> <run_a> <run_b>
e.g. python -m backend.tools.compare_reruns http://32.196.229.237:8888 RUN-PILOT6-BASE-001 RUN-PILOT6-A10G-002
"""
import json
import sys
import urllib.request


def get(base, path):
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=60) as r:
        return json.loads(r.read())


def main():
    base, a, b = sys.argv[1:4]
    ia = {r["item_id"]: r for r in get(base, f"/api/runs/{a}/items")["items"]}
    ib = {r["item_id"]: r for r in get(base, f"/api/runs/{b}/items")["items"]}
    rows = []
    for iid in sorted(set(ia) & set(ib)):
        da = get(base, f"/api/runs/{a}/items/{iid}")["prediction"]
        db = get(base, f"/api/runs/{b}/items/{iid}")["prediction"]
        pa, pb = da.get("parsed"), db.get("parsed")
        norm = lambda t: (t or "").replace("\r\n", "\n").strip()
        rows.append({
            "item_id": iid, "status": [da["status"], db["status"]],
            "tokens": [da["meta"].get("generated_tokens"), db["meta"].get("generated_tokens")],
            "seconds": [da["meta"].get("generation_seconds"), db["meta"].get("generation_seconds")],
            "output_identical": norm(da.get("output_text")) == norm(db.get("output_text")),
            "json_identical": pa is not None and pa == pb,
            "relations": {r: [ia[iid]["relations"][r]["predicted"], ib[iid]["relations"][r]["predicted"]]
                          for r in ("R1", "R2", "R3", "R4")},
            "n_objects": [len(pa["track1"]["objects"]) if pa else None, len(pb["track1"]["objects"]) if pb else None],
            "actions": [sorted(f"{x['code']}/{x['condition']}" for x in pa["track1"]["actions"]) if pa else None,
                        sorted(f"{x['code']}/{x['condition']}" for x in pb["track1"]["actions"]) if pb else None],
        })
    same_rel = sum(all(v[0] == v[1] for v in r["relations"].values()) for r in rows)
    print(json.dumps({"run_a": a, "run_b": b, "n": len(rows),
                      "identical_outputs": sum(r["output_identical"] for r in rows),
                      "identical_relations_all4": same_rel, "items": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
