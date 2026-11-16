"""New local-only entry; fixed Base settings, one Pilot image, no references.

This is NOT the unpublished historical infer.py. Never reads Pilot/labels,
reference JSON, derived source boxes, or C geometry. Raw failures are retained.
"""
import argparse
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[3]
REVISION='4ecc2ba63bcac23ba4a767fc87025b1450f84c9c'
RUNTIME=ROOT/'pilot-1115/runtime_inputs'
MODEL=ROOT/'models/gemma-4-E4B-it'/REVISION

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(8*1024*1024),b''):h.update(part)
    return h.hexdigest()

def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def construct_messages(image, model_item_id, baseline):
    # Reuse the exact historical input task, changing only the neutral item ID.
    task_text=baseline[1]['content'][1]['text']
    prefix,encoded=task_text.split('\n',1)
    task=json.loads(encoded)
    task['item_id']=model_item_id
    allowed={'item_id','view','intent','task','input_type','evaluation_area_definition','available_evidence','question'}
    if set(task)-allowed:raise ValueError('Unexpected field in historical input task')
    return [{'role':'system','content':baseline[0]['content']},
            {'role':'user','content':[{'type':'image','url':str(image)},
            {'type':'text','text':prefix+'\n'+json.dumps(task,ensure_ascii=False)}]}]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',required=True,type=Path)
    p.add_argument('--item-id',default='pilot_001')
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    if not args.item_id.startswith('pilot_') or not args.item_id[6:].isdigit():
        p.error('Use a neutral item ID such as pilot_001; do not encode source metadata')
    image=args.image.resolve()
    allowed_images=(ROOT/'pilot-1115/private/Pilot/images').resolve()
    if image.parent!=allowed_images or image.suffix.lower()!='.png':
        p.error('Image must be a PNG in the prepared input-only image directory')
    if args.out.exists():p.error('Refusing to overwrite a run or retry')
    args.out.mkdir(parents=True)
    status={'run_id':args.out.name,'model_item_id':args.item_id,'started_at_utc':now(),
            'phase':'initializing','status':'running','model_generate_called':False,
            'implementation':'new_entry_not_original_infer_py','retry_count':0}
    save(args.out/'status.json',status)
    t=time.perf_counter()
    try:
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
        os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
        import torch
        import transformers
        from transformers import AutoProcessor, BitsAndBytesConfig, Gemma4ForConditionalGeneration, set_seed
        from PIL import Image
        if not torch.cuda.is_available():raise RuntimeError('CUDA is unavailable')
        if not torch.cuda.is_bf16_supported():raise RuntimeError('GPU BF16 not supported')
        download=json.loads((ROOT/'pilot-1115/model_download_verification.json').read_text(encoding='utf-8'))
        if not download['all_match_history'] or download['revision']!=REVISION:
            raise RuntimeError('Fixed checkpoint hash verification missing/failed')
        for row in download['files']:
            f=MODEL/row['file']
            if f.stat().st_size!=row['size_bytes']:raise RuntimeError('Model file size changed')
        config=json.loads((RUNTIME/'config.json').read_text(encoding='utf-8'))
        expected={'name':'nf4_prompt_v1_first','quant':'nf4','model_id':'google/gemma-4-E4B-it',
                  'revision':REVISION,'soft_tokens':280,'max_new_tokens':4096,'seed':42,
                  'do_sample':False,'enable_thinking':False,'batch_size':1,'image_count':1,
                  'cpu_offload':False,'adapter_source_run':None,'dtype':'bfloat16'}
        for key,value in expected.items():
            if config[key]!=value:raise ValueError('Fixed Base config mismatch: '+key)
        baseline=json.loads((RUNTIME/'baseline_messages.json').read_text(encoding='utf-8'))
        fixed_system=(RUNTIME/'modified_system_full.txt').read_text(encoding='utf-8')
        if baseline[0]['content']!=fixed_system:raise ValueError('Historical system Prompt mismatch')
        messages=construct_messages(image,args.item_id,baseline)
        save(args.out/'messages.json',messages)
        run_config={'base_config':config,'effective_new_entry':True,'device_map':{'':'cuda:0'},
                    'attn_implementation':{'text_config':'sdpa','vision_config':'sdpa','audio_config':'eager'},
                    'generation':{'max_new_tokens':4096,'do_sample':False},
                    'seed':42,'enable_thinking':False,'image_max_soft_tokens':280,
                    'cpu_offload':False,'adapter_loaded':False,
                    'model_revision':REVISION,'model_local_path':str(MODEL),
                    'script_sha256':sha(Path(__file__)),'historical_script_reproduced':False,
                    'python':sys.version,'platform':platform.platform(),
                    'packages':{x:importlib.metadata.version(x) for x in ['torch','torchvision','transformers','bitsandbytes','accelerate','huggingface-hub']},
                    'gpu':torch.cuda.get_device_name(0),'cuda_runtime':torch.version.cuda,
                    'input_image_sha256':sha(image),'system_prompt_utf8_sha256':hashlib.sha256(fixed_system.encode()).hexdigest(),
                    'schema_sha256':sha(RUNTIME/'prediction.schema.json'),
                    'environment_differs_from_historical_linux':True}
        save(args.out/'config.json',run_config)
        schema=json.loads((RUNTIME/'prediction.schema.json').read_text(encoding='utf-8'))
        # Preserve exact applied system Prompt and schema next to generated output.
        (args.out/'system_prompt.txt').write_text(fixed_system,encoding='utf-8')
        save(args.out/'schema.json',schema)
        status['phase']='processor_loading';save(args.out/'status.json',status)
        print('PHASE processor_loading',flush=True)
        processor=AutoProcessor.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False)
        processor.image_seq_length=280
        processor.image_processor.max_soft_tokens=280
        processor.image_processor.image_seq_length=280
        # Keep the checkpoint's selected processor backend and record it.
        if processor.__class__.__name__!='Gemma4Processor':raise RuntimeError('Unexpected processor class')
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        (args.out/'rendered_prompt.txt').write_text(text,encoding='utf-8')
        if image.name in text:raise RuntimeError('Source filename metadata leaked into rendered Prompt')
        forbidden=['C_polygon','bbox_xyxy_norm": [0.','F_742188','F_742190']
        if any(v in text for v in forbidden):raise RuntimeError('Unexpected reference content in Prompt')
        with Image.open(image) as opened:rgb=opened.convert('RGB');width,height=rgb.size
        inputs=processor(text=text,images=rgb,return_tensors='pt',images_kwargs={'max_soft_tokens':280})
        if inputs['input_ids'].shape[0]!=1:raise RuntimeError('Expected one input')
        save(args.out/'input_audit.json',{'model_item_id':args.item_id,'image_sha256':sha(image),
             'width':width,'height':height,'image_count':1,'source_filename_in_rendered_prompt':False,
             'labels_read':False,'reference_files_read':False,'C_geometry_read':False,
             'task_template':'same_historical_task_only_neutral_item_id_changed',
             'input_tokens':inputs['input_ids'].shape[-1],
             'tensor_shapes':{k:list(v.shape) for k,v in inputs.items() if hasattr(v,'shape')},
             'processor_class':processor.__class__.__name__,
             'image_processor_class':processor.image_processor.__class__.__name__,
             'image_max_soft_tokens':processor.image_processor.max_soft_tokens})
        set_seed(42)
        torch.cuda.reset_peak_memory_stats()
        status['phase']='model_loading';save(args.out/'status.json',status)
        print('PHASE model_loading NF4 GPU-only',flush=True)
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
             bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
        model=Gemma4ForConditionalGeneration.from_pretrained(MODEL,local_files_only=True,
             trust_remote_code=False,dtype=torch.bfloat16,quantization_config=quant,
             device_map={'':'cuda:0'},attn_implementation=run_config['attn_implementation'])
        model.eval()
        off=[str(p.device) for p in model.parameters() if p.device.type!='cuda']
        if off:raise RuntimeError('CPU/meta model parameters found despite GPU-only config')
        save(args.out/'loaded_model.json',{'device_map':getattr(model,'hf_device_map',None),
             'parameter_count':sum(p.numel() for p in model.parameters()),
             'allocated_bytes':torch.cuda.memory_allocated(),'reserved_bytes':torch.cuda.memory_reserved(),
             'attention':{name:getattr(getattr(model.config,name),'_attn_implementation',None)
                for name in ['text_config','vision_config','audio_config']}})
        inputs={k:v.to('cuda:0') if hasattr(v,'to') else v for k,v in inputs.items()}
        # Keep integer image positions/IDs intact, cast floating tensors to BF16.
        inputs={k:v.to(torch.bfloat16) if hasattr(v,'is_floating_point') and v.is_floating_point() else v for k,v in inputs.items()}
        status['phase']='generating';status['model_generate_called']=True;save(args.out/'status.json',status)
        print('PHASE generating max_new_tokens=4096 greedy seed=42',flush=True)
        start=time.perf_counter()
        with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=4096,do_sample=False)
        torch.cuda.synchronize()
        generated=output[0,inputs['input_ids'].shape[-1]:].detach().cpu()
        save(args.out/'generated_ids.json',generated.tolist())
        raw=processor.tokenizer.decode(generated,skip_special_tokens=False)
        decoded=processor.tokenizer.decode(generated,skip_special_tokens=True)
        (args.out/'raw_output.txt').write_text(raw,encoding='utf-8')
        (args.out/'decoded_output.txt').write_text(decoded,encoding='utf-8')
        result={'json_parse_success':False,'schema_valid':False,'retry_count':0,'format_repair':False,
                'official_benchmark':None,'scoring_performed':False,'reason':'no_reviewed_reference',
                'generation_seconds':time.perf_counter()-start,'generated_tokens':len(generated)}
        try:
            prediction=json.loads(decoded)
            save(args.out/'parsed_output.json',prediction)
            spec=importlib.util.spec_from_file_location('fixed_validator',RUNTIME/'validate.py')
            validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
            errors=validator.validate_prediction(prediction,schema)
            if prediction.get('item_id')!=args.item_id:errors.append('Output item_id differs from request')
            result.update(json_parse_success=True,schema_valid=not errors,schema_errors=errors)
        except json.JSONDecodeError as e:result['parse_error']=str(e)
        save(args.out/'output_validation.json',result)
        status.update(status='completed' if result['schema_valid'] else 'invalid_output',phase='finished')
        print('OUTPUT',json.dumps(result),flush=True)
    except Exception as e:
        status.update(status='failed',error_type=type(e).__name__,error_message=str(e))
        try:
            import torch
            if isinstance(e,torch.OutOfMemoryError):status['status']='oom'
        except ImportError:pass
        (args.out/'error_traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        print('FAILED '+status['phase']+' '+type(e).__name__+': '+str(e),flush=True)
        return 1
    finally:
        status['finished_at_utc']=now();status['wall_seconds']=time.perf_counter()-t
        try:
            import torch
            if torch.cuda.is_available():
                status['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
                status['cuda_peak_reserved_bytes']=torch.cuda.max_memory_reserved()
        except Exception:pass
        save(args.out/'status.json',status)
    return 0

if __name__=='__main__':sys.exit(main())
