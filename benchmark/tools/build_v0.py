"""Build the 10-item v0 benchmark (image frames only) into the team repo.

Task 1 ego motion (AI Hub 472, scenario 13 Validation): 2 s of front-camera frames (20 frames, 0.1 s apart)
       -> speed {멈춤, 그대로, 크게 느려짐, 크게 빨라짐} + direction {직진, 좌회전, 우회전}
       GT from GPS over the window (start -> end speed, heading change):
         멈춤 max < 4 km/h | 크게 느려짐/빨라짐 change >= 8 km/h and >= 30 % | 그대로 change <= 3 km/h
         좌/우회전 heading change > 20 deg (heading grows on left turns) | 직진 <= 4 deg; anything between is not used
Task 2 pick the riskiest pedestrian (AI Hub 597 pedestrian-accident blackbox clips, bb_1_*):
       frames from the clip start to "now" (5 fps) + the "now" frame with numbered boxes -> number
Task 3 box the riskiest pedestrian: same kind of input without boxes -> [x1, y1, x2, y2] on the key frame
Tasks 2/3 reuse reviewed risk moments of data/bench_v1 (accident pedestrian in the late part of its visible
span, numbering shuffled). v0 has no "없음" (no risky pedestrian) items.

Run from the project root:  python scripts/build_hpbench.py repo/262RCOSE45700/benchmark
"""
import json, os, shutil, sys
from collections import defaultdict

import cv2
import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "repo/262RCOSE45700/benchmark"
SRC472 = os.path.join("data", "raw", "472", "src13", "13_전방 보행자_val")
EGO472 = "data/raw/472/ego13.jsonl"
V597 = "data/raw/597/videos"
BENCH_V1 = "data/bench_v1"
W = 960

T1_PICK = [("063", "크게 느려짐", "직진"), ("053", "멈춤", "직진"), ("023", "그대로", "좌회전"), ("073", "크게 빨라짐", "우회전")]
# reviewed-ok risk moments only (no "없음" items in v0). t3 reuses the hard t2_01 moment so task 3 has
# one item the closest-looking rule gets wrong.
T2_FROM = ["t2_01", "t2_02", "t2_04"]
T3_FROM = ["t3_03", "t3_07", "t3_01"]

SPEED_OPTS = ["멈춤", "그대로", "크게 느려짐", "크게 빨라짐"]
DIR_OPTS = ["직진", "좌회전", "우회전"]


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, img):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    with open(p, "wb") as f:
        f.write(buf.tobytes())


# ------------------------------------------------------------------ task 1
def t1_label(rows):
    v0, v1 = rows[0]["speed"] * 3.6, rows[-1]["speed"] * 3.6
    vmax, vmin = max(r["speed"] for r in rows) * 3.6, min(r["speed"] for r in rows) * 3.6
    dh = rows[-1]["heading"] - rows[0]["heading"]
    if vmax < 4:
        sp = "멈춤"
    elif v0 - v1 >= 8 and v0 - v1 >= 0.3 * v0:
        sp = "크게 느려짐"
    elif v1 - v0 >= 8 and v1 - v0 >= 0.3 * max(v0, 1):
        sp = "크게 빨라짐"
    elif abs(v1 - v0) <= 3 and vmin >= 4:
        sp = "그대로"
    else:
        sp = None
    d = "좌회전" if dh > 20 else "우회전" if dh < -20 else "직진" if abs(dh) <= 4 else None
    return sp, d, {"speed_kmh_start": round(v0, 1), "speed_kmh_end": round(v1, 1), "heading_change_deg": round(dh, 1)}


def build_t1(items, gold):
    by = defaultdict(dict)
    for r in map(json.loads, open(EGO472, encoding="utf-8")):
        by[r["scene"]][r["frame"]] = r
    for k, (scene, sp_want, d_want) in enumerate(T1_PICK, 1):
        d = by[scene]
        wins = []
        for st in range(1, 180):
            fr = list(range(st, st + 20))
            if all(f in d for f in fr):
                sp, dr, ev = t1_label([d[f] for f in fr])
                if (sp, dr) == (sp_want, d_want):
                    wins.append((st, ev))
        st, ev = wins[len(wins) // 2]                        # middle of the matching windows
        iid = f"t1_{k:02d}"
        frames = []
        for i, n in enumerate(range(st, st + 20)):
            img = imread(os.path.join(SRC472, scene, "image0", f"13_{scene}_{n - 1:03d}.jpg"))  # label n = image n-1
            rel = f"frames/{iid}/{i:02d}.jpg"
            imwrite(os.path.join(OUT, rel), img)
            frames.append(rel)
        items.append({
            "id": iid, "task": 1, "task_name": "ego_motion",
            "frames": frames, "frame_interval_s": 0.1, "key_frame": None,
            "question": "다음은 내 차 전방 카메라로 0.1초 간격으로 찍은 사진 20장(2초)입니다. "
                        "이 2초 동안 내 차의 움직임을 고르세요.",
            "options": {"speed": SPEED_OPTS, "direction": DIR_OPTS},
            "answer_format": '{"speed": "<speed 보기 중 하나>", "direction": "<direction 보기 중 하나>"}'})
        gold.append({"id": iid, "task": 1, "answer": {"speed": sp_want, "direction": d_want},
                     "meta": {"source": "AIHub-472 scenario 13 (front pedestrian) Validation", "scene": scene,
                              "label_frames": [st, st + 19], **ev}})


# ------------------------------------------------------------------ task 2 / 3
def build_t23(items, gold):
    v1 = {x["id"]: x for x in map(json.loads, open(os.path.join(BENCH_V1, "items.jsonl"), encoding="utf-8"))}
    for task, src_ids in ((2, T2_FROM), (3, T3_FROM)):
        for k, sid in enumerate(src_ids, 1):
            s = v1[sid]
            iid = f"t{task}_{k:02d}"
            cap = cv2.VideoCapture(os.path.join(V597, s["clip"] + ".mp4"))
            now = s["seq"] - 1                                   # video frame = sequence_frame_number - 1
            idx = sorted(set(range(now % 3, now + 1, 3)) | {now})  # 5 fps, always ending on "now"
            frames, n, j = [], 0, 0
            ww, hh = s["image_size"]
            while n <= now:
                ok, img = cap.read()
                if not ok:
                    break
                if n in idx:
                    rel = f"frames/{iid}/{j:02d}.jpg"
                    imwrite(os.path.join(OUT, rel), cv2.resize(img, (ww, hh)))
                    frames.append(rel)
                    j += 1
                n += 1
            cap.release()
            key_rel = f"frames/{iid}/key.jpg"
            shutil.copyfile(os.path.join(BENCH_V1, s["image"]), os.path.join(OUT, key_rel))
            secs = round(now / 15, 1)
            if task == 2:
                n_ped = len(s["evidence"]["boxes"])
                q = (f"다음은 내 차 블랙박스로 처음부터 지금까지 {secs}초 동안 찍은 사진(0.2초 간격)과, 지금 장면에 보행자 "
                     "번호를 붙인 사진(key frame)입니다. 번호가 붙은 보행자 중 내 차에 가장 위험한 보행자는 몇 번입니까?")
                opts = [str(i) for i in range(1, n_ped + 1)]
                fmt = '"<번호>"'
            else:
                q = (f"다음은 내 차 블랙박스로 처음부터 지금까지 {secs}초 동안 찍은 사진(0.2초 간격)과, 지금 장면 사진"
                     f"(key frame, {ww}x{hh})입니다. key frame에서 내 차에 가장 위험한 보행자를 [x1, y1, x2, y2] 픽셀 "
                     "좌표로 표시하세요.")
                opts = None
                fmt = '[x1, y1, x2, y2] (key frame 픽셀 좌표)'
            items.append({"id": iid, "task": task,
                          "task_name": "pick_risky_pedestrian" if task == 2 else "box_risky_pedestrian",
                          "frames": frames, "frame_interval_s": 0.2, "key_frame": key_rel,
                          "key_frame_size": [ww, hh], "question": q, "options": opts, "answer_format": fmt})
            gold.append({"id": iid, "task": task, "answer": s["answer"],
                         "meta": {"source": "AIHub-597 pedestrian accident (no crosswalk) Validation, blackbox 1st person",
                                  "clip": s["clip"], "now_label_frame": s["seq"], "kind": s["tags"]["kind"],
                                  "hard": s["tags"]["hard"], "n_ped": s["tags"]["n_ped"],
                                  "pedestrian_boxes": s["evidence"]["boxes"],
                                  "closest_looking_no": s["evidence"]["closest_looking_no"]}})


def main():
    global OUT
    OUT = os.path.join(OUT, "data")              # everything (items, gold, frames) goes under <root>/data
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    items, gold = [], []
    build_t1(items, gold)
    build_t23(items, gold)
    with open(os.path.join(OUT, "items.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT, "gold.jsonl"), "w", encoding="utf-8") as f:
        for g in gold:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    for it, g in zip(items, gold):
        print(it["id"], len(it["frames"]), "frames ->", g["answer"])


if __name__ == "__main__":
    main()
