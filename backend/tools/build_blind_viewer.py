"""Build the portable human-only annotation form from the 3 selected photos."""
import argparse, base64, hashlib, io, json
from pathlib import Path
from PIL import Image

def main():
    p=argparse.ArgumentParser();p.add_argument('--images',type=Path,required=True);p.add_argument('--forms',type=Path,default=Path('data_v11'));a=p.parse_args()
    rows=[json.loads(x) for x in (a.forms/'independent_blind_3.jsonl').read_text(encoding='utf-8').splitlines()]
    images=[]
    for r in rows:
        path=a.images/r['image_file']
        if not path.is_file():
            path=a.images/r['image_file'][1]/r['image_file']
        if not path.is_file():
            raise FileNotFoundError(f"Missing image: {r['image_file']}")
        if hashlib.sha256(path.read_bytes()).hexdigest()!=r['image_sha256']:
            raise ValueError(f"Image SHA-256 mismatch: {r['image_file']}")
        with Image.open(path) as im:
            buf=io.BytesIO();im.convert('RGB').save(buf,format='JPEG',quality=90)
        images.append({'id':r['item_id'],'filename':r['image_file'],'sha256':r['image_sha256'],
                       'group':r['source_group_id'],'bytes':base64.b64encode(buf.getvalue()).decode()})
    template=(a.forms/'blind_labeling_template.html').read_text(encoding='utf-8')
    (a.forms/'Pilot3_v11_Blind_Labeling.html').write_text(template.replace('__IMAGES__',json.dumps(images)),encoding='utf-8')
    print('3 photos; no prior labels included')

if __name__=='__main__': main()
