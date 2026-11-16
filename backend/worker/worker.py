"""GPU inference worker: pulls jobs from the Report API, runs the VLM, posts the raw result back.

Runs on the host (needs the GPU), not in the API container:
  API_URL=http://127.0.0.1:8888 WORKER_KEY=... IMAGE_ROOT=/data/aihub_71784/images \
  MODEL_DIR=/data/models/gemma-4-E4B-it ~/infer/.venv/bin/python -m backend.worker.worker

Input building, model loading and generation follow the model team's run_gemma_pilot_smoke.py
(work/model-1115, sha256 1437366263bec4eb…): same messages, processor settings, BF16 casting, greedy decoding. Nothing is repaired here: raw text goes back as generated; the API scorer decides validity.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = os.environ.get("API_URL", "http://127.0.0.1:8888").rstrip("/")
KEY = os.environ.get("WORKER_KEY", "")
IMAGE_ROOT = Path(os.environ.get("IMAGE_ROOT", "/data/aihub_71784/images"))
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/data/models/gemma-4-E4B-it"))
PROMPTS = Path(__file__).resolve().parent / "prompts"
WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-gpu0")
POLL_S = float(os.environ.get("POLL_S", "5"))
ATTN = {"text_config": "sdpa", "vision_config": "sdpa", "audio_config": "eager"}
REFERENCE_SOURCE = "work/model-1115 ai_model/inference/source/run_gemma_pilot_smoke.py sha256 1437366263bec4eb"

sha = lambda b: hashlib.sha256(b).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")


def call(method, path, body=None):
    req = urllib.request.Request(f"{API}{path}", method=method, headers={"X-API-Key": KEY,
                                                                         "Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body, ensure_ascii=False).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, (json.loads(r.read()) if r.status == 200 else None)


def load_prompt(version):
    d = PROMPTS / version
    meta = json.loads((d / "prompt.json").read_text(encoding="utf-8"))
    system = (d / "system.txt").read_bytes().replace(b"\r\n", b"\n")
    task = (d / "task.txt").read_bytes().replace(b"\r\n", b"\n")
    if sha(system) != meta["system_sha256"] or sha(task) != meta["task_sha256"]:
        raise RuntimeError(f"prompt files for {version} do not match prompt.json hashes")
    return meta, system.decode("utf-8"), task.decode("utf-8")


def build_messages(job, image_ref):
    """Same construction as the model team's run_gemma_pilot_smoke.py (sha 14373662…): reuse the historical
    task, change only item_id, re-serialize with json.dumps(ensure_ascii=False)."""
    meta, system, task_text = load_prompt(job["prompt"]["version"])
    prefix, encoded = task_text.split("\n", 1)
    task = json.loads(encoded)
    task["item_id"] = job["item_id"]
    allowed = {"item_id", "view", "intent", "task", "input_type", "evaluation_area_definition",
               "available_evidence", "question"}
    if set(task) - allowed:
        raise RuntimeError("unexpected field in historical input task")
    return [{"role": "system", "content": system},
            {"role": "user", "content": [{"type": "image", "url": str(image_ref)},
                                         {"type": "text", "text": prefix + "\n" + json.dumps(task, ensure_ascii=False)}]}]


class Model:
    def __init__(self):
        self.key = None
        self.model = self.proc = None

    def ensure(self, spec):
        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Gemma4ForConditionalGeneration
        key = (spec["model_id"], spec["revision"], spec["quantization"], spec.get("adapter"))
        if key == self.key:
            return
        if spec.get("adapter"):
            raise RuntimeError("adapter loading is not implemented yet")
        cfg = json.loads((MODEL_DIR / "config.json").read_text())
        self.model = None
        torch.cuda.empty_cache()
        kw = {"dtype": torch.bfloat16, "device_map": {"": "cuda:0"}, "local_files_only": True,
              "trust_remote_code": False, "attn_implementation": ATTN}
        if spec["quantization"] == "nf4":
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                           bnb_4bit_use_double_quant=True,
                                                           bnb_4bit_compute_dtype=torch.bfloat16)
        proc = AutoProcessor.from_pretrained(MODEL_DIR, local_files_only=True, trust_remote_code=False)
        proc.image_seq_length = 280
        proc.image_processor.max_soft_tokens = 280
        proc.image_processor.image_seq_length = 280
        self.proc = proc
        self.model = Gemma4ForConditionalGeneration.from_pretrained(MODEL_DIR, **kw)
        self.model.eval()
        self.key = key
        self.env = environment(cfg, spec)


def environment(cfg, spec):
    import bitsandbytes
    import torch
    import transformers
    return {"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda,
            "transformers": transformers.__version__, "bitsandbytes": bitsandbytes.__version__,
            "gpu": torch.cuda.get_device_name(0), "model_dir": str(MODEL_DIR),
            "model_revision_expected": spec["revision"], "worker": WORKER_ID,
            "model_type": cfg.get("model_type")}


def run_job(m: Model, job):
    import torch
    from PIL import Image
    from transformers import set_seed
    started = utc()
    item = job["input"]
    img_path = (IMAGE_ROOT / item["image_relpath"]).resolve()
    data = img_path.read_bytes()
    if item.get("image_sha256") and sha(data) != item["image_sha256"]:
        return {"status": "error", "error": "input image sha256 mismatch", "started_at_utc": started,
                "finished_at_utc": utc()}
    m.ensure(job["model"])
    dec = job["decoding"]
    soft = int(dec.get("image_max_soft_tokens", 280))
    messages = build_messages(job, img_path)
    rendered = m.proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                          enable_thinking=dec.get("enable_thinking", False))
    if img_path.name in rendered:
        raise RuntimeError("source filename leaked into the rendered prompt")
    with Image.open(img_path) as opened:
        rgb = opened.convert("RGB")
    inputs = m.proc(text=rendered, images=rgb, return_tensors="pt", images_kwargs={"max_soft_tokens": soft})
    audit = {"image_sha256": sha(data), "rendered_prompt_sha256_lf": sha(rendered.encode()),
             "rendered_prompt_sha256_crlf": sha(rendered.replace("\n", "\r\n").encode()),
             "input_tokens": int(inputs["input_ids"].shape[1]),
             "pixel_values_shape": list(inputs["pixel_values"].shape) if "pixel_values" in inputs else None,
             "labels_read": False, "reference_read": False, "reference_source": REFERENCE_SOURCE}
    set_seed(int(dec.get("seed", 42)))
    inputs = {k: v.to("cuda:0") if hasattr(v, "to") else v for k, v in inputs.items()}
    # same as the original: keep integer tensors, cast floating tensors (pixel values) to BF16
    inputs = {k: v.to(torch.bfloat16) if hasattr(v, "is_floating_point") and v.is_floating_point() else v
              for k, v in inputs.items()}
    t0 = time.time()
    with torch.inference_mode():
        out = m.model.generate(**inputs, max_new_tokens=dec.get("max_new_tokens", 4096),
                               do_sample=dec.get("do_sample", False), max_time=float(job["timeout_s"]))
    torch.cuda.synchronize()
    secs = time.time() - t0
    gen = out[0, inputs["input_ids"].shape[1]:]
    eos = m.model.generation_config.eos_token_id
    eos = set(eos if isinstance(eos, list) else [eos])
    ended = len(gen) > 0 and int(gen[-1]) in eos
    hit_time = not ended and len(gen) < dec.get("max_new_tokens", 4096) and secs >= job["timeout_s"] * 0.98
    return {"status": "timeout" if hit_time else "ok",
            "error": f"generation stopped at max_time={job['timeout_s']}s" if hit_time else None,
            "raw_text": m.proc.tokenizer.decode(gen.cpu(), skip_special_tokens=False),
            "output_text": m.proc.tokenizer.decode(gen.cpu(), skip_special_tokens=True),
            "generation_seconds": round(secs, 3), "generated_tokens": int(len(gen)),
            "input_audit": audit, "environment": m.env, "started_at_utc": started, "finished_at_utc": utc()}


def main():
    if not KEY:
        sys.exit("WORKER_KEY is not set")
    m = Model()
    print(f"worker {WORKER_ID} polling {API}", flush=True)
    while True:
        try:
            code, job = call("GET", f"/api/jobs/next?worker={WORKER_ID}")
        except (urllib.error.URLError, OSError) as exc:
            print(f"api unreachable: {exc}", flush=True)
            time.sleep(POLL_S * 2)
            continue
        if code == 204 or not job:
            time.sleep(POLL_S)
            continue
        print(f"job {job['run_id']}/{job['item_id']}", flush=True)
        try:
            result = run_job(m, job)
        except Exception as exc:  # report the failure; the request stays in the list as failed
            traceback.print_exc()
            result = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "finished_at_utc": utc()}
        try:
            call("POST", f"/api/jobs/{job['run_id']}/{job['item_id']}/result?worker={WORKER_ID}", result)
            print(f"  -> {result['status']} {result.get('generation_seconds')}s", flush=True)
        except urllib.error.HTTPError as exc:
            print(f"  result rejected: {exc.code} {exc.read()[:300]}", flush=True)


if __name__ == "__main__":
    main()
