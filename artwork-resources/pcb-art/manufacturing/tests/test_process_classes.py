"""Bind the process-class decision; re-measure only when a native candidate is supplied."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import unittest

import shapely
from shapely.geometry import Polygon, box

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('process_probe', HERE/'probe_process_classes.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProcessClassDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((HERE/'policy.json').read_text())
        cls.rule = next(r for r in cls.policy['errata'] if r['id'] == 'process-classes-2026-09-25')
        cls.raw = (HERE/cls.rule['evidence']).read_bytes()
        cls.saved = json.loads(cls.raw)

    def test_bindings(self):
        self.assertEqual(probe.digest(self.raw), self.rule['evidenceSha256'])
        self.assertEqual(probe.digest((HERE/self.rule['sources']).read_bytes()), self.rule['sourcesSha256'])
        self.assertEqual(probe.digest((HERE/'probe_process_classes.py').read_bytes()), self.saved['probeScriptSha256'])
        self.assertEqual(probe.digest((HERE.parent/'tools/export_kicad.py').read_bytes()), self.saved['exporterSha256'])
        self.assertEqual(self.saved['candidateFileSha256'], self.rule['measuredCandidateFileSha256'])
        self.assertEqual(self.saved['approvedSourceSha256'], self.policy['sourceHashes']['preview-source/assets/geometry.json'])

    def test_frozen_defaults_unchanged(self):
        for key in self.rule['unchangedRulesMmKeys']:
            self.assertEqual(self.policy['rulesMm'][key], .25)
        self.assertEqual(self.policy['rulesMm']['blackMaskPublishedFloor'], .13)
        self.assertEqual(self.rule['minimumVisibleGoldWidthMm'], .25)
        self.assertEqual(self.rule['blackMaskWeb'], {**self.rule['blackMaskWeb'], 'nonSpiderTopsMm': .13, 'spiderFamilyMm': .25})
        self.assertEqual(self.rule['retainedSpecialCopper']['sameConnectedComponentChannelMm'], .25)
        self.assertFalse(self.rule['productionApproval'])

    def test_named_pours_match_probe_and_evidence(self):
        self.assertEqual(set(self.rule['generalCopper']['namedFullGoldPourBoardIds']), probe.POURS)
        for board in self.saved['boards']:
            classes = {r['class'] for r in board['copperFeatures']}
            if board['boardId'] in probe.POURS:
                self.assertEqual(classes, {'general-solid-pour'})
            else:
                self.assertNotIn('general-solid-pour', classes)
            expected_black = .25 if board['boardId'].startswith('01-spider-nest-') else .13
            self.assertEqual(board['retainedBlackProjectScreenMm'], expected_black)
            self.assertEqual(board['minimumVisibleGoldWindowWidthMm'], .25)

    def test_convex_island_certificates_satisfy_rule(self):
        certified = [r for b in self.saved['boards'] for r in b['copperFeatures'] if r['class'] == 'general-isolated-convex-island']
        self.assertEqual(len(certified), 40)
        for row in certified:
            part = shapely.from_wkb(bytes.fromhex(row['geometryCertificateWkbHex']))
            self.assertEqual(probe.normsha(part), row['normalizedWkbSha256'])
            self.assertFalse(part.interiors)
            self.assertLessEqual(part.convex_hull.difference(part).area, self.policy['rulesMm']['numericAreaTolerance'])

    def test_classifier_and_spacing_rules(self):
        body = box(0, 0, 50, 50)
        self.assertEqual(probe.component_class('x', box(1, 1, 2, 2), body, {}), 'general-isolated-convex-island')
        ell = box(1, 1, 5, 2).union(box(1, 1, 2, 5))
        self.assertEqual(probe.component_class('x', ell, body, {}), 'retained-special-or-unresolved-network')
        ring = box(1, 1, 5, 5).difference(box(2, 2, 4, 4))
        self.assertEqual(probe.component_class('x', ring, body, {}), 'retained-special-or-unresolved-network')
        general, special = {'class': 'general-isolated-convex-island'}, {'class': 'retained-special-or-unresolved-network'}
        self.assertEqual(probe.copper_spacing_mm(general, general), .10)
        self.assertEqual(probe.copper_spacing_mm(general, special), .25)
        self.assertEqual(probe.copper_spacing_mm(general, same_connected_return=True), .25)

    def test_witnesses_remain_real_failures(self):
        witnesses = self.saved['remainingFailureWitnesses']
        self.assertEqual(len(witnesses), self.rule['remainingFailureWitnessCount'])
        for w in witnesses:
            crop = shapely.from_wkb(bytes.fromhex(w['cropWkbHex']))
            self.assertEqual(probe.normsha(crop), w['cropNormalizedWkbSha256'])
            self.assertLess(w['measuredCrossSectionMm'], w['thresholdMm'])
            self.assertIn('not waived', w['status'])

    @unittest.skipUnless(os.environ.get('PROCESS_CLASS_NATIVE_DIR'), 'set PROCESS_CLASS_NATIVE_DIR to the measured native manufacturing dir')
    def test_exact_remeasurement(self):
        report, _ = probe.measure(Path(os.environ['PROCESS_CLASS_NATIVE_DIR']))
        self.assertEqual(json.loads(json.dumps(report)), self.saved)


if __name__ == '__main__':
    unittest.main()
