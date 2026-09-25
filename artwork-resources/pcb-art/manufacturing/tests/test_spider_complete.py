"""Reproduce the corrected decision; final 68-portion artwork remains a gate."""
import importlib.util
import json
from pathlib import Path
import unittest

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('complete_probe', HERE/'probe_spider_complete.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SpiderCompleteDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((HERE/'policy.json').read_text())
        cls.rule = next(r for r in cls.policy['errata'] if r['id'] == 'spider-l01-unfiltered-network-2026-09-25')
        cls.raw = (HERE/cls.rule['evidence']).read_bytes()
        cls.saved = json.loads(cls.raw)
        cls.measured, cls.before, cls.initial, cls.final, cls.term_before, cls.term_after = probe.measure()

    def test_exact_reproduction_and_frozen_bindings(self):
        self.assertEqual(json.loads(json.dumps(self.measured)), self.saved)
        self.assertEqual(probe.digest(self.raw), self.rule['evidenceSha256'])
        for key in ['baseEvidence', 'surveyInput']:
            self.assertEqual(probe.digest((HERE/self.saved[key]).read_bytes()), self.saved[key+'Sha256'])
        self.assertEqual(probe.digest((HERE/'spider-complete-input.json').read_bytes()), self.saved['terminal']['inputSha256'])
        self.assertEqual(probe.digest((HERE/'probe_spider_complete.py').read_bytes()), self.saved['probeScriptSha256'])
        self.assertEqual(probe.digest((HERE/'probe_spider_network.py').read_bytes()), self.saved['baseProbeSha256'])
        self.assertEqual(probe.digest((HERE.parent/'tools/export_kicad.py').read_bytes()), self.saved['exporterSha256'])
        self.assertEqual(self.rule['supersedesMaterialAndGuideScopeOf'], 'spider-l01-complete-network-2026-09-25')

    def test_unfiltered_survey_includes_wide_central_gold(self):
        runs = self.saved['survey']['interiorRuns']
        self.assertEqual(sum(r['thresholdMm'] == .25 for r in runs), 64)
        self.assertEqual(sum(r['thresholdMm'] == .13 for r in runs), 48)
        self.assertEqual({r['sourceStrokeIndex0'] for r in runs}, set(self.saved['newCentralStrokeIndices0']))
        self.assertTrue(any(r['centralGoldWidthRangeMm'][0] > .31 for r in runs))
        expected = {0:(-1,109),1:(-1,106),11:(1,96),12:(1,100),13:(-1,99),14:(-1,102),
                    19:(1,108),20:(1,107),21:(-1,113),22:(-1,110),23:(1,113),24:(1,110),
                    33:(1,103),38:(1,103),41:(1,103)}
        for index,(side,guide) in expected.items():
            self.assertTrue(any(r['sourceStrokeIndex0'] == index and r['side'] == side and r['guideStrokeIndex0'] == guide for r in runs))
        self.assertEqual({r['sourceStrokeIndex0'] for r in self.saved['survey']['rimTransitionFlags']}, {74,75,80,88,91})

    def test_exact_34_path_material_and_single_pass_cleanup(self):
        paths = self.saved['paths']
        flat = [i for p in paths for i in p['sourceStrokeIndices0']]
        self.assertEqual(len(flat),34)
        self.assertEqual(len(set(flat)),34)
        self.assertEqual(set(flat), set(self.rule['centralStrokeIndices0']))
        self.assertEqual([p['sourceStrokeIndices0'] for p in paths if 7 in p['sourceStrokeIndices0']], [[7,8]])
        ribbons = unary_union([LineString(p['pointsMm']).buffer(1,cap_style=2,join_style=2) for p in paths])
        self.assertLess(self.before.union(ribbons).symmetric_difference(self.initial).area, 1e-5)
        self.assertEqual(probe.normsha(self.initial.difference(self.before)), self.rule['initialAdditionNormalizedWkbSha256'])
        hashes = {r['initialApertureNormalizedWkbSha256'] for r in self.saved['toolAccess']}
        apertures = [Polygon(r) for r in self.initial.interiors if probe.normsha(Polygon(r)) in hashes]
        self.assertEqual(len(apertures), 19)
        cleanup = unary_union([a.difference(a.buffer(-.5,quad_segs=64).buffer(.5,quad_segs=64).intersection(a)) for a in apertures])
        self.assertEqual(probe.normsha(cleanup), self.rule['routingCleanupNormalizedWkbSha256'])
        self.assertLess(self.final.difference(self.initial).symmetric_difference(cleanup).area,1e-5)
        self.assertEqual(probe.normsha(self.final), self.rule['finalBodyNormalizedWkbSha256'])
        self.assertAlmostEqual(self.saved['initialAdditionAreaMm2'],112.96093500162256)
        self.assertAlmostEqual(self.saved['routingCleanupAreaMm2'],3.4291956867197886)
        self.assertAlmostEqual(self.saved['combinedAdditionAreaMm2'],116.39013068788422)
        for metric,bound in [('initialAdditionAreaMm2','maximumInitialAdditionAreaMm2'),
                             ('routingCleanupAreaMm2','maximumAdditionalRoutingCleanupAreaMm2'),
                             ('combinedAdditionAreaMm2','maximumCombinedAdditionAreaMm2')]:
            self.assertLessEqual(self.saved[metric],self.rule[bound])
            self.assertLess(self.rule[bound]-self.saved[metric],.00001002)

    def test_mechanical_invariants_and_source_edge_local_splices(self):
        self.assertTrue(all(self.saved['mechanicalChecks'].values()))
        self.assertEqual(len(self.final.interiors),27)
        self.assertAlmostEqual(self.saved['cumulativeApertureLossFraction'],.01810397556587784)
        self.assertLess(self.saved['cumulativeApertureLossFraction'],.02)
        self.assertEqual(len(self.saved['crossSections']),215)
        self.assertEqual(len(self.saved['guidePortions']),68)
        self.assertEqual(len(self.saved['sourceEdgeLocalMiters']),19)
        self.assertEqual(len(self.saved['previouslyMeasuredThirteenMiters']),13)
        self.assertAlmostEqual(max(m['displacementMm'] for m in self.saved['sourceEdgeLocalMiters']),.18380900185138133)
        for p in self.saved['guidePortions']:
            line = LineString(p['originalEdgeMm'])
            self.assertTrue(all(line.distance(Point(x)) < 1e-8 for x in p['originalPortionMm']))
            self.assertLessEqual(p['maximumNominalDisplacementMm'],.5)
            self.assertLess(p['nominalGoldOutsideMaskSafeAreaMm2'],1e-5)

    def test_only_three_geometry_bound_terminal_caps(self):
        terminal = self.saved['terminal']
        self.assertTrue(all(terminal['checks'].values()))
        caps = terminal['caps']
        self.assertEqual(len(caps),3)
        self.assertEqual([c['normalizedWkbSha256'] for c in caps],self.rule['terminalException']['capNormalizedWkbSha256'])
        polygons = [shapely.from_wkb(bytes.fromhex(c['wkbHex'])) for c in caps]
        self.assertEqual([probe.normsha(q) for q in polygons],self.rule['terminalException']['capNormalizedWkbSha256'])
        endpoint = Point(terminal['guide103OriginalEndpointMm'])
        patch = unary_union(polygons)
        self.assertLess(patch.difference(endpoint.buffer(.55,quad_segs=64)).area,1e-8)
        self.assertAlmostEqual(patch.area,.04765467720707662)
        self.assertAlmostEqual(patch.difference(endpoint.buffer(.5,quad_segs=64)).area,.0005846737483827139)
        self.assertLess(terminal['serializedInkDiskUnionDifferenceAreaMm2'],1e-5)
        self.assertLess(terminal['serializedInkDiskUnionHausdorffMm'],.001)
        self.assertLess(terminal['completeTerminalDiskUnionDifferenceAreaMm2'],1e-5)
        self.assertLess(terminal['completeTerminalDiskUnionHausdorffMm'],.001)
        self.assertEqual(terminal['inkComponentsAfterCurve'],terminal['inkComponentsAfterCaps'])
        self.assertEqual(len(probe.polygons(self.term_before)),len(probe.polygons(self.term_after)))
        self.assertLess(self.term_after.difference(self.term_before).difference(self.final.buffer(-.35,quad_segs=64)).area,1e-5)

    def test_no_broader_permission_or_process_relaxation(self):
        self.assertFalse(self.rule['productionApproval'])
        self.assertTrue(self.rule['priorChannelPatchGeometryMustRemainUnchanged'])
        self.assertFalse(self.rule['terminalException']['interchangeableAreaAllowance'])
        self.assertEqual(self.rule['maximumGuideTransitionDisplacementMm'],.5)
        self.assertEqual(self.rule['minimumRequiredMaskClearanceMm'],.35)
        for key in ['minimumVisibleGoldWidth','minimumMaskWeb','minimumCopperWidth','minimumSeparateCopperGap']:
            self.assertEqual(self.policy['rulesMm'][key],.25)
        self.assertEqual(self.rule['terminalException']['cubicControlPointsMm'],self.saved['terminal']['cubicControlPointsMm'])


if __name__ == '__main__':
    unittest.main()
