# -*- coding: utf-8 -*-
"""Verify an existing fixed local snapshot. Does not download or load a model."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REVISION='4ecc2ba63bcac23ba4a767fc87025b1450f84c9c'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir',required=True,type=Path)
    p.add_argument('--workspace',required=True,type=Path)
    args=p.parse_args()
    root=Path(__file__).resolve().parent;model=args.model_dir.resolve()
    target=args.workspace.resolve()/'pilot-1115/model_download_verification.json'
    if target.exists():p.error('Verification report already exists; preserving the original')
    expected=json.loads((root/'runtime_inputs/model_file_hashes.json').read_text(encoding='utf-8'))
    records=[]
    for row in expected:
        path=model/row['file']
        if not path.is_file():p.error('Missing checkpoint file: '+row['file'])
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
        ok=path.stat().st_size==row['size_bytes'] and h.hexdigest()==row['sha256']
        records.append({'file':row['file'],'size_bytes':path.stat().st_size,'sha256':h.hexdigest(),'matches_history':ok})
        print(row['file'],ok,flush=True)
    report={'repo_id':'google/gemma-4-E4B-it','revision':REVISION,'local_path':str(model),
            'all_match_history':all(row['matches_history'] for row in records),'files':records}
    if not report['all_match_history']:
        print('CHECK_FAILED: no verification report written',file=sys.stderr);return 1
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:f.write(json.dumps(report,indent=2)+'\n')
    print('CHECK_COMPLETE',target)
    return 0

if __name__=='__main__':sys.exit(main())
