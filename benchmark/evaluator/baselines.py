"""Reference predictions for sanity checks and comparison (no model involved).

Usage: python evaluator/baselines.py --kind {gold,random,closest} --out preds.jsonl

  gold     the gold answers (evaluator must give 100 %)
  random   uniform random option / random pedestrian box (seeded)
  closest  task 2-3: the pedestrian lowest in the key frame (looks closest); task 1: "그대로, 직진"
           -> the rule a VLM has to beat for tasks 2-3
Baselines 'random' and 'closest' read pedestrian boxes from gold meta, i.e. they get the candidate boxes
for free; they are lower bounds for judgement, not for detection.
"""
import argparse, json, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "..", "data", "gold.jsonl")
SPEED = ["멈춤", "그대로", "크게 느려짐", "크게 빨라짐"]
DIRECTION = ["직진", "좌회전", "우회전"]


def predict(g, kind, rng):
    t, boxes = g["task"], g["meta"].get("pedestrian_boxes", [])
    if kind == "gold":
        return g["answer"]
    if t == 1:
        if kind == "random":
            return {"speed": rng.choice(SPEED), "direction": rng.choice(DIRECTION)}
        return {"speed": "그대로", "direction": "직진"}
    if kind == "random":
        k = rng.randrange(len(boxes))
    elif kind == "closest":
        k = max(range(len(boxes)), key=lambda i: boxes[i][3])
    else:
        raise ValueError(kind)
    return k + 1 if t == 2 else boxes[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["gold", "random", "closest"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    gold = [json.loads(l) for l in open(GOLD, encoding="utf-8") if l.strip()]
    with open(args.out, "w", encoding="utf-8") as f:
        for g in gold:
            f.write(json.dumps({"id": g["id"], "answer": predict(g, args.kind, rng)}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
