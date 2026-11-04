"""Score model predictions on the benchmark.

Usage:
  python evaluator/evaluate.py --pred predictions.jsonl [--gold data/gold.jsonl] [--out report.json]

predictions.jsonl: one line per item, {"id": "t1_01", "answer": ...}
  answer may be structured (dict / int / list) or the model's raw text; raw text is parsed:
    task 1  speed and direction option words, e.g. "크게 느려짐, 직진" or {"speed": ..., "direction": ...}
    task 2  a pedestrian number or "없음"
    task 3  four numbers [x1, y1, x2, y2] on the key frame, or "없음"
  missing or unparsable answers count as wrong (and are reported separately).

Metrics
  task 1  speed accuracy, direction accuracy, both correct
  task 2  accuracy (all / risk items / hard risk items / 없음 items)
          hard = the pedestrian lowest in the image (closest-looking) is not the answer
  task 3  risk items: mean IoU (0 when no box), Acc@IoU>=0.5; 없음 items: accuracy of answering 없음
Only the Python standard library is used.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GOLD = os.path.join(HERE, "..", "data", "gold.jsonl")
SPEED = ["크게 느려짐", "크게 빨라짐", "그대로", "멈춤"]      # longer phrases first when matching text
DIRECTION = ["좌회전", "우회전", "직진"]
NONE_WORDS = ("없음", "none", "no pedestrian")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def is_none(a):
    return isinstance(a, str) and any(w in a.strip().lower() for w in NONE_WORDS)


def first_option(text, options):
    hits = [(text.find(o), o) for o in options if o in text]
    return min(hits)[1] if hits else None


def parse_t1(a):
    if isinstance(a, dict):
        return a.get("speed"), a.get("direction")
    if isinstance(a, str):
        try:
            return parse_t1(json.loads(a))
        except (ValueError, TypeError):
            return first_option(a, SPEED), first_option(a, DIRECTION)
    return None, None


def parse_t2(a):
    if isinstance(a, bool):
        return None
    if isinstance(a, int):
        return a
    if isinstance(a, str):
        if is_none(a):
            return "없음"
        m = re.search(r"\d+", a)
        return int(m.group()) if m else None
    return None


def parse_t3(a):
    if isinstance(a, list) and len(a) == 4 and all(isinstance(v, (int, float)) for v in a):
        return [float(v) for v in a]
    if isinstance(a, str):
        if is_none(a):
            return "없음"
        nums = re.findall(r"-?\d+(?:\.\d+)?", a)
        if len(nums) >= 4:
            return [float(v) for v in nums[:4]]
    return None


def iou(a, b):
    a = [min(a[0], a[2]), min(a[1], a[3]), max(a[0], a[2]), max(a[1], a[3])]
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def ratio(hits, n):
    return {"correct": hits, "total": n, "acc": round(hits / n, 4) if n else None}


def evaluate(gold, preds):
    pred = {p["id"]: p.get("answer") for p in preds}
    rep = {"n_items": len(gold), "n_predicted": sum(g["id"] in pred for g in gold),
           "unparsable": [], "per_item": []}

    t1 = [g for g in gold if g["task"] == 1]
    sp = dr = both = 0
    for g in t1:
        s, d = parse_t1(pred.get(g["id"]))
        if s is None and d is None:
            rep["unparsable"].append(g["id"])
        ok_s, ok_d = s == g["answer"]["speed"], d == g["answer"]["direction"]
        sp += ok_s; dr += ok_d; both += ok_s and ok_d
        rep["per_item"].append({"id": g["id"], "pred": {"speed": s, "direction": d}, "gold": g["answer"],
                                "correct": ok_s and ok_d})
    rep["task1"] = {"speed": ratio(sp, len(t1)), "direction": ratio(dr, len(t1)), "both": ratio(both, len(t1))}

    t2 = [g for g in gold if g["task"] == 2]
    res = {"all": [0, 0], "risk": [0, 0], "hard": [0, 0], "none": [0, 0]}
    for g in t2:
        p = parse_t2(pred.get(g["id"]))
        if p is None:
            rep["unparsable"].append(g["id"])
        ok = p == g["answer"] if g["answer"] == "없음" else p == int(g["answer"])
        groups = ["all", "none"] if g["answer"] == "없음" else ["all", "risk"] + (["hard"] if g["meta"].get("hard") else [])
        for k in groups:
            res[k][0] += ok; res[k][1] += 1
        rep["per_item"].append({"id": g["id"], "pred": p, "gold": g["answer"], "correct": ok})
    rep["task2"] = {k: ratio(*v) for k, v in res.items()}

    t3 = [g for g in gold if g["task"] == 3]
    ious, hit50, none_ok, n_risk, n_none = [], 0, 0, 0, 0
    for g in t3:
        p = parse_t3(pred.get(g["id"]))
        if p is None:
            rep["unparsable"].append(g["id"])
        if g["answer"] == "없음":
            n_none += 1
            ok = p == "없음"
            none_ok += ok
            rep["per_item"].append({"id": g["id"], "pred": p, "gold": "없음", "correct": ok})
        else:
            n_risk += 1
            v = iou(p, g["answer"]) if isinstance(p, list) else 0.0
            ious.append(v); hit50 += v >= 0.5
            rep["per_item"].append({"id": g["id"], "pred": p, "gold": g["answer"], "iou": round(v, 4),
                                    "correct": v >= 0.5})
    rep["task3"] = {"risk_mean_iou": round(sum(ious) / len(ious), 4) if ious else None,
                    "risk_acc_at_iou_0.5": ratio(hit50, n_risk), "none": ratio(none_ok, n_none)}
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=DEFAULT_GOLD)
    ap.add_argument("--out")
    args = ap.parse_args()
    rep = evaluate(load_jsonl(args.gold), load_jsonl(args.pred))
    summary = {k: rep[k] for k in ("n_items", "n_predicted", "task1", "task2", "task3", "unparsable")}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
