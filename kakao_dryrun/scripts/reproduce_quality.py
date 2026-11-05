#!/usr/bin/env python3
"""Re-evaluate saved model output on CPU, without filling fields or changing GT."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'source/integrated_annotation_sample'
sys.path.insert(0, str(DATA / 'scripts'))
from evaluate import diagnostic_evaluation, check_actions
from validate import validate_prediction

def read(path):
    return json.loads(path.read_text())

def validate_text(text, schema):
    try:
        prediction = json.loads(text)
    except ValueError as error:
        return None, [str(error)]
    return prediction, validate_prediction(prediction, schema)

def main():
    schema = read(DATA / 'schema/prediction.schema.json')
    reference = json.loads((DATA / 'data/references.jsonl').read_text().splitlines()[0])
    annotation = read(DATA / reference['annotation_path'])
    expected = read(ROOT / 'audit/output_comparison.json')
    results = []
    for row in expected:
        output_dir = (ROOT / row['metrics_path']).parent
        text = (output_dir / 'decoded_output.txt').read_text()
        stored = read(ROOT / row['metrics_path'])
        prediction, errors = validate_text(text, schema)
        strict_valid = prediction is not None and not errors
        recovered = False
        if prediction is None:
            match = re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*', text)
            if match:
                recovered = True
                prediction, errors = validate_text(match.group(1), schema)
        final_valid = prediction is not None and not errors
        assert strict_valid == row['strict_schema'], row['run']
        assert final_valid == row['after_fence_schema'], row['run']
        assert recovered == row['format_recovery'], row['run']
        score = {'objects': None, 'relations': None, 'action': None}
        if final_valid:
            old = stored.get('recovered_result', stored)
            diagnostics = diagnostic_evaluation(prediction, reference, annotation)
            actions = check_actions(prediction, reference)
            assert diagnostics == old['diagnostics'], row['run']
            assert actions == old['action_rules'], row['run']
            score = {'objects': diagnostics['grounding']['objects']['matched_count'],
                     'relations': sum(prediction['track1']['relations'][key]['state'] == value for key, value in reference['relations'].items()),
                     'action': actions['pass']}
            assert (score['objects'], score['relations'], score['action']) == (row['object_match'], row['relation_match'], row['action_pass'])
        else:
            assert row['object_match'] is None and row['relation_match'] is None and row['action_pass'] is None
        results.append({'run': row['run'], 'strict_schema': strict_valid,
                        'after_fence_schema': final_valid, 'quality': score,
                        'schema_errors': errors if not final_valid else []})
    export = read(ROOT / 'audit/export_manifest.json')
    for record in export['files']:
        path = ROOT / record['published_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['published_sha256'], record['published_path']
    mask = read(ROOT / 'audit/training_tokens_and_mask.json')
    assert mask['sequence_length'] == mask['prompt_masked_tokens'] + mask['supervised_tokens'] == 6040
    assert mask['mask_prompt_image_padding_all_excluded'] and mask['selected_logits_exact_causal_shift']
    print(json.dumps({'all_passed': True, 'runs_checked': len(results), 'GT_or_evaluator_changed': False,
                      'writes_performed': False, 'results': results}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
