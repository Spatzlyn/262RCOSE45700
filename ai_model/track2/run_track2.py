"""Two independent Track 2 predictions from frames at or before decision time."""
import argparse
import json
import os
from pathlib import Path
import hashlib
import av
from PIL import Image
HERE = Path(__file__).resolve().parent
REVISION = "4ecc2ba63bcac23ba4a767fc87025b1450f84c9c"

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def frames(path, decision):
    if decision < 0: raise ValueError("negative decision time")
    sampled=[]
    with av.open(str(path)) as clip:
        start=None
        last=None
        next_time=0
        crossed=False
        for f in clip.decode(video=0):
            if f.time is None: raise ValueError("frame timestamp required")
            if start is None: start=f.time
            t=float(f.time-start)
            if t>decision+1e-7:
                crossed=True
                break
            last=(t,f)
            if t+1e-7>=next_time:
                sampled.append((t,f.to_image().convert("RGB")))
                next_time=t+0.2
        if not last: raise ValueError("no eligible frame")
        if not crossed and decision-last[0]>0.2: raise ValueError("decision beyond clip")
        if sampled[-1][0]!=last[0]: sampled.append((last[0],last[1].to_image().convert("RGB")))
    return sampled

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",required=True,type=Path)
    p.add_argument("--decision",required=True,type=float,help="seconds from first displayed frame")
    p.add_argument("--numbered-key",required=True,type=Path,help="neutral numbered candidates on the same decision frame")
    p.add_argument("--ids",required=True,nargs="+",type=int)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--check-only",action="store_true")
    p.add_argument("--model-dir", type=Path, help="local verified Gemma snapshot")
    a=p.parse_args()
    if not a.check_only and (a.model_dir is None or not a.model_dir.is_dir()):
        p.error("provide an existing --model-dir")
    seq=frames(a.video,a.decision)
    plain=seq[-1][1]
    with Image.open(a.numbered_key) as im: marked=im.convert("RGB")
    if plain.size!=marked.size: raise ValueError("key frame size mismatch")
    if a.check_only:
        print(len(seq),plain.size,seq[-1][0])
        return
    os.environ["HF_HUB_OFFLINE"]="1"
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Gemma4ForConditionalGeneration, set_seed
    a.out.mkdir(parents=True,exist_ok=False)
    save(a.out/"input_record.json",dict(decision=a.decision,frame_times=[t for t,_ in seq],size=plain.size,video_sha256=sha(a.video),key_sha256=sha(a.numbered_key),expected_revision=REVISION, prompt_sha256=sha(HERE/"Track2_프롬프트.md"), candidate_ids=a.ids))
    proc=AutoProcessor.from_pretrained(a.model_dir,local_files_only=True)
    model=Gemma4ForConditionalGeneration.from_pretrained(a.model_dir,local_files_only=True,device_map={"":"cuda:0"},dtype=torch.bfloat16,attn_implementation={"text_config":"sdpa","vision_config":"sdpa","audio_config":"eager"},quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)).eval()
    questions=(HERE/"Track2_프롬프트.md").read_text(encoding="utf-8").splitlines()[1:]
    if len(questions) != 2: raise ValueError("expected two prompt lines")
    for task,key,q in zip(("select","box"),(marked,plain),questions):
        imgs=[im for _,im in seq[:-1]]+[key]
        content=[{"type":"image"} for im in imgs]+[{"type":"text","text":q}]
        prompt=proc.apply_chat_template([{"role":"user","content":content}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
        data=proc(text=prompt,images=imgs,return_tensors="pt").to(model.device)
        set_seed(42)
        with torch.inference_mode(): gen=model.generate(**data,max_new_tokens=128,do_sample=False)
        raw=proc.decode(gen[0,data.input_ids.shape[-1]:],skip_special_tokens=True)
        (a.out/(task+"_raw.txt")).write_text(raw,encoding="utf-8")
        try:
            obj=json.loads(raw)
            if task=="select": valid=type(obj["target_id"]) is int and obj["target_id"] in a.ids
            else:
                x,y,r,b=obj["bbox_xyxy"]
                valid=0<=x<r<=plain.width and 0<=y<b<=plain.height
        except (ValueError,KeyError,TypeError): valid=False
        save(a.out/(task+"_validation.json"),{"valid":valid})
if __name__=="__main__": main()
