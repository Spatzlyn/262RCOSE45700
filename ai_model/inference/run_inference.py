# -*- coding: utf-8 -*-
"""Path-only launcher for the unchanged, actually used Pilot inference entry."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

PACKAGE=Path(__file__).resolve().parent
REVISION='4ecc2ba63bcac23ba4a767fc87025b1450f84c9c'
SOURCE_SHA='1437366263bec4ebc82cea42c543f0e290f220b8110c00d4c8d03f2f627e6fe8'

def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_package():
    manifest=json.loads((PACKAGE/'package_manifest.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path=(PACKAGE/row['file']).resolve()
        if not path.is_relative_to(PACKAGE) or not path.is_file():
            raise ValueError('Missing or invalid package path: '+row['file'])
        if file_sha(path)!=row['sha256']:raise ValueError('Package file hash changed: '+row['file'])
    source=PACKAGE/'source/run_gemma_pilot_smoke.py'
    if file_sha(source)!=SOURCE_SHA:raise ValueError('Actual inference source hash mismatch')
    config=json.loads((PACKAGE/'runtime_inputs/config.json').read_text(encoding='utf-8'))
    expected={'name':'nf4_prompt_v1_first','model_id':'google/gemma-4-E4B-it',
              'revision':REVISION,'quant':'nf4','dtype':'bfloat16','soft_tokens':280,
              'max_new_tokens':4096,'seed':42,'do_sample':False,'enable_thinking':False,
              'batch_size':1,'image_count':1,'cpu_offload':False,'adapter_source_run':None}
    for key,value in expected.items():
        if config.get(key)!=value:raise ValueError('Fixed Base field changed: '+key)
    return source

def load_original():
    source=verify_package()
    spec=importlib.util.spec_from_file_location('original_pilot_entry',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def verify_checkpoint_report(workspace,model_dir):
    report_path=workspace/'pilot-1115/model_download_verification.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    expected=json.loads((PACKAGE/'runtime_inputs/model_file_hashes.json').read_text(encoding='utf-8'))
    if report.get('revision')!=REVISION or report.get('all_match_history') is not True:
        raise ValueError('Fixed checkpoint verification report missing or invalid')
    if Path(report['local_path']).resolve()!=model_dir:
        raise ValueError('Verification report model path differs from --model-dir')
    actual={row['file']:row for row in report['files']}
    for row in expected:
        found=actual.get(row['file'],{})
        if found.get('sha256')!=row['sha256'] or found.get('matches_history') is not True:
            raise ValueError('Checkpoint report hash mismatch: '+row['file'])
        if (model_dir/row['file']).stat().st_size!=row['size_bytes']:
            raise ValueError('Checkpoint file size changed: '+row['file'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-only',action='store_true',help='Check package only; no model import, download or inference')
    p.add_argument('--workspace',type=Path,help='Private work directory holding pilot-1115/private/Pilot/images')
    p.add_argument('--model-dir',type=Path,help='Verified local fixed snapshot; default WORKSPACE/models/gemma-4-E4B-it/REVISION')
    p.add_argument('--image',type=Path)
    p.add_argument('--item-id',default='pilot_001')
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    original=load_original()
    if args.check_only:
        print(json.dumps({'package_valid':True,'actual_source_sha256':SOURCE_SHA,
                          'model_imported':False,'model_executed':False,'network_used':False}))
        return 0
    if not args.workspace or not args.image or not args.out:
        p.error('--workspace, --image and --out are required for inference')
    workspace=args.workspace.resolve()
    model_dir=args.model_dir.resolve() if args.model_dir else workspace/'models/gemma-4-E4B-it'/REVISION
    image=args.image.resolve();out=args.out.resolve()
    if out.exists():p.error('Output exists. Never overwrite completed runs or retries.')
    if image.parent!=(workspace/'pilot-1115/private/Pilot/images').resolve() or image.suffix.lower()!='.png':
        p.error('Use a PNG in WORKSPACE/pilot-1115/private/Pilot/images')
    verify_checkpoint_report(workspace,model_dir)
    # The original Base code remains byte-identical. Only path globals change.
    original.ROOT=workspace
    original.RUNTIME=PACKAGE/'runtime_inputs'
    original.MODEL=model_dir
    original_argv=sys.argv
    try:
        sys.argv=[str(PACKAGE/'source/run_gemma_pilot_smoke.py'),'--image',str(image),
                  '--item-id',args.item_id,'--out',str(out)]
        result=original.main()
    finally:sys.argv=original_argv
    # This is a new output directory created by this invocation, never an old run.
    if (out/'status.json').exists():
        provenance={'launcher_sha256':file_sha(Path(__file__)),'original_source_sha256':SOURCE_SHA,
                    'path_only_wrapper':True,'base_parameters_modified':False,
                    'original_historical_infer_py':False,'package_manifest_sha256':file_sha(PACKAGE/'package_manifest.json')}
        target=out/'launcher_provenance.json'
        if target.exists():raise RuntimeError('Refusing provenance overwrite')
        target.write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':sys.exit(main())
