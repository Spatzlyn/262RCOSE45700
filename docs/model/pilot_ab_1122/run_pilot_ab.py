import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import run_gemma_pilot_smoke as engine

pilot = engine.ROOT / "pilot-1115"
docs = pilot / "submission/team_review_1122/docs/model/pilot_1122"
parser = argparse.ArgumentParser()
parser.add_argument("arm", choices=["A", "B"])
parser.add_argument("--check-only", action="store_true")
parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
args, extra = parser.parse_known_args()
if args.worker:
    engine.RUNTIME = args.worker
    sys.argv = [sys.argv[0], *extra]
    sys.exit(engine.main())
if extra:
    parser.error("unexpected arguments")
prompt = next(docs.glob(args.arm + "_*.txt"))
expected = {"A":"6580dd1892d446d16dc2c3d61d79f393abdc259d96b7ffee0989e98e797f4296",
            "B":"758344b0914ae557f22f89b35aba42730f4f77ccada8e2ee5b88232c33f9d85a"}
if engine.sha(prompt) != expected[args.arm]:
    sys.exit("Prompt hash mismatch")
template = engine.RUNTIME / "baseline_messages.json"
if engine.sha(template) != "46be1e7d26743faa500e25398a5f1acae970b40e3c033e05a7267221dc5e1d41":
    sys.exit("Input template hash mismatch")
messages = json.loads(template.read_text(encoding="utf-8"))
messages[0]["content"] = prompt.read_text(encoding="utf-8")
images = []
for i in range(1, 7):
    item = f"pilot_{i:03d}"
    audit = json.loads((pilot / "runs" / (item+"_smoke_01") / "input_audit.json").read_text(encoding="utf-8"))
    if not images:
        by_hash = {engine.sha(p):p for p in (pilot/"private/Pilot/images").glob("*.png")}
    image = by_hash[audit["image_sha256"]]
    engine.construct_messages(image, item, messages)
    images.append((item,image))
if args.check_only:
    print(args.arm, "six inputs and prompt verified")
    sys.exit(0)
out = pilot/"ab_diagnostics"/(args.arm+"_"+datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid4().hex[:8])
out.mkdir(parents=True, exist_ok=False)
runtime = out/"runtime"
runtime.mkdir()
for name in ["config.json","validate.py","prediction.schema.json"]:
    (runtime/name).write_bytes((engine.RUNTIME/name).read_bytes())
(runtime/"modified_system_full.txt").write_bytes(prompt.read_bytes())
engine.save(runtime/"baseline_messages.json",messages)
print(out, flush=True)
invalid = False
for item,image in images:
    dest = out/item
    subprocess.run([sys.executable,"-B",__file__,args.arm,"--worker",str(runtime),"--image",str(image),"--item-id",item,"--out",str(dest)],check=True)
    invalid |= json.loads((dest/"status.json").read_text(encoding="utf-8"))["status"] != "completed"
sys.exit(int(invalid))
