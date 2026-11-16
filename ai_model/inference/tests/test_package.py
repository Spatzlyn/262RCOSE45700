# -*- coding: utf-8 -*-
"""CPU-only package and input-isolation checks; never invokes original.main."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE))
from run_inference import load_original, SOURCE_SHA, file_sha

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.entry=load_original()
        self.baseline=json.loads((PACKAGE/'runtime_inputs/baseline_messages.json').read_text(encoding='utf-8'))

    def test_actual_used_source_preserved(self):
        self.assertEqual(file_sha(PACKAGE/'source/run_gemma_pilot_smoke.py'),SOURCE_SHA)

    def test_task_only_changes_neutral_id(self):
        baseline=copy.deepcopy(self.baseline)
        messages=self.entry.construct_messages(Path('source_weather.png'),'pilot_001',baseline)
        a=json.loads(baseline[1]['content'][1]['text'].split('\n',1)[1])
        b=json.loads(messages[1]['content'][1]['text'].split('\n',1)[1])
        a['item_id']='pilot_001'
        self.assertEqual(a,b)
        self.assertEqual(messages[0],baseline[0])
        self.assertNotIn('source_weather',messages[1]['content'][1]['text'])

    def test_reference_field_rejected(self):
        self.baseline[1]['content'][1]['text']='Task\n'+json.dumps({'item_id':'x','GT':'not allowed'})
        with self.assertRaises(ValueError):self.entry.construct_messages(Path('x.png'),'pilot_001',self.baseline)

    def test_no_model_package_imported(self):
        self.assertNotIn('torch',sys.modules)
        self.assertNotIn('transformers',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
