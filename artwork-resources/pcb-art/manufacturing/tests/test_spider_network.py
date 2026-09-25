"""Validate the complete decision envelope, not pending production artwork."""
import importlib.util
import json
from pathlib import Path
import unittest

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('network_probe', HERE/'probe_spider_network.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SpiderNetworkDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((HERE/'policy.json').read_text())
        cls.rule = next(r for r in cls.policy['errata'] if r['id'] == 'spider-l01-complete-network-2026-09-25')
        cls.raw = (HERE/cls.rule['evidence']).read_bytes()
        cls.saved = json.loads(cls.raw)
        cls.measured, cls.before, cls.initial, cls.final = probe.measure()

    def test_reproduction_and_input_bindings(self):
        # JSON round trip normalizes tuples from live geometry coordinates.
        self.assertEqual(json.loads(json.dumps(self.measured)), self.saved)
        self.assertEqual(probe.digest(self.raw), self.rule['evidenceSha256'])
        for file_key, hash_key in [('baseEvidence', 'baseEvidenceSha256'), ('surveyInput', 'surveyInputSha256')]:
            self.assertEqual(probe.digest((HERE/self.rule[file_key]).read_bytes()), self.rule[hash_key])
        self.assertEqual(probe.digest((HERE/'probe_spider_network.py').read_bytes()), self.saved['probeScriptSha256'])
        self.assertEqual(self.saved['approvedSourceSha256'], probe.SOURCE_SHA)

    def test_survey_freezes_complete_sustained_set(self):
        runs = self.saved['survey']['interiorRuns']
        self.assertEqual(sum(r['thresholdMm'] == .13 for r in runs), 38)
        self.assertEqual(sum(r['thresholdMm'] == .25 for r in runs), 46)
        self.assertEqual({r['sourceStrokeIndex0'] for r in runs}, set(probe.NEW_STROKES))
        self.assertEqual({r['sourceStrokeIndex0'] for r in self.saved['survey']['rimTransitionFlags']}, {74, 75, 80, 88, 91})
        self.assertTrue(all(r['lengthMm'] >= 1 and r['sampleSpacingMm'] <= .2 for r in runs))
        self.assertEqual(len({r['inkComponentNormalizedWkbSha256'] for r in runs if r['thresholdMm'] == .13}), 12)

    def test_exact_network_and_old_rib_counted_once(self):
        paths = self.saved['paths']
        self.assertEqual([p['sourceStrokeIndices0'] for p in paths], [[i] for i in probe.NEW_STROKES]+[[7, 8]])
        ribbons = unary_union([LineString(p['pointsMm']).buffer(1, cap_style=2, join_style=2) for p in paths])
        self.assertLess(self.before.union(ribbons).symmetric_difference(self.initial).area, 1e-5)
        self.assertEqual(probe.normsha(self.initial.difference(self.before)), self.rule['initialAdditionNormalizedWkbSha256'])
        self.assertAlmostEqual(self.saved['earlierRibAdditionAreaMm2IncludedOnce'], 6.074302254386678)
        self.assertEqual(self.rule['supersedesMaterialAndGuideScopeOf'], 'spider-l01-rib-width-2026-09-25')
        self.assertTrue(self.rule['earlierRibIncludedExactlyOnce'])

    def test_cleanup_shapes_and_unaffected_apertures(self):
        self.assertEqual(self.rule['affectedOriginalGeometryHoleIndices0'], [0, 1, 2, 3, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18])
        allowed = {r['initialApertureNormalizedWkbSha256'] for r in self.saved['toolAccess']
                   if r['originalGeometryHoleIndex0'] in self.rule['affectedOriginalGeometryHoleIndices0']}
        deltas = []
        for ring in self.initial.interiors:
            aperture = Polygon(ring)
            if probe.normsha(aperture) in allowed:
                sweep = aperture.buffer(-.5, quad_segs=64).buffer(.5, quad_segs=64).intersection(aperture)
                deltas.append(aperture.difference(sweep))
        self.assertEqual(len(deltas), 15)
        expected = unary_union(deltas)
        self.assertEqual(probe.normsha(expected), self.rule['routingCleanupNormalizedWkbSha256'])
        # Boolean recomposition can change vertex ordering/roundoff. Check the
        # final body's actual geometric delta rather than equating its bytes.
        self.assertLess(self.final.difference(self.initial).symmetric_difference(expected).area, 1e-5)
        self.assertEqual(probe.normsha(self.final), self.rule['finalBodyNormalizedWkbSha256'])
        for row in self.saved['toolAccess']:
            if row['originalGeometryHoleIndex0'] in [4, 8, 9, 10]:
                self.assertEqual(row['cleanupAreaMm2'], 0)
                self.assertEqual(row['initialApertureNormalizedWkbSha256'], row['finalApertureNormalizedWkbSha256'])
            self.assertEqual(row['toolCenterComponents'], 1)
            self.assertEqual(row['finalToolCenterComponents'], 1)
            self.assertLess(row['plungeDiskOutsideApertureAreaMm2'], 1e-5)
        for metric, bound in [('initialAdditionAreaMm2', 'maximumInitialAdditionAreaMm2'),
                              ('routingCleanupAreaMm2', 'maximumAdditionalRoutingCleanupAreaMm2'),
                              ('combinedAdditionAreaMm2', 'maximumCombinedAdditionAreaMm2')]:
            self.assertLessEqual(self.saved[metric], self.rule[bound])
            self.assertLess(self.rule[bound]-self.saved[metric], .00001002)

    def test_mechanical_invariants_and_real_aperture_budget(self):
        self.assertTrue(all(self.saved['mechanicalChecks'].values()))
        self.assertEqual(len(self.final.interiors), 27)
        self.assertLess(self.saved['cumulativeApertureLossFraction'], .02)
        self.assertAlmostEqual(self.saved['cumulativeApertureLossFraction'], .012157010497576892)
        self.assertLess(self.before.difference(self.final).area, 1e-5)

    def test_fifty_exact_guide_portions_fit_without_unbounded_move(self):
        portions = self.saved['guidePortions']
        self.assertEqual(len(portions), 50)
        safe = self.final.buffer(-.35, quad_segs=64)
        for p in portions:
            original = LineString(p['originalEdgeMm'])
            for endpoint in p['originalPortionMm']:
                self.assertLess(original.distance(Point(endpoint)), 1e-8)
            proposed = LineString(p['nominalRelocatedPortionMm'])
            self.assertLessEqual(proposed.hausdorff_distance(LineString(p['originalPortionMm'])), .141)
            self.assertLess(proposed.buffer(.1255, quad_segs=64).difference(safe).area, 1e-5)
            self.assertEqual(abs(p['nominalCenterOffsetMm']), .5165)
        self.assertEqual(len(self.saved['crossSections']), 125)
        self.assertTrue(all(s['afterMaterialWidthMm'] >= 1.999 for s in self.saved['crossSections']))

    def test_no_width_relaxation_or_implicit_production_approval(self):
        for key in ['minimumVisibleGoldWidth', 'minimumMaskWeb', 'minimumCopperWidth', 'minimumSeparateCopperGap']:
            self.assertEqual(self.policy['rulesMm'][key], .25)
        self.assertEqual(self.rule['minimumRequiredMaskClearanceMm'], .35)
        self.assertFalse(self.rule['productionApproval'])
        self.assertFalse(self.rule['newTrappedMaskPocketsAllowed'])
        self.assertFalse(self.rule['newGoldConnectionsAllowed'])
        self.assertTrue(self.rule['priorChannelPatchGeometryMustRemainUnchanged'])
        old = json.loads((HERE/'spider-channel-erratum.json').read_text())
        self.assertEqual(self.saved['priorChannelPatchesRetainedUnchanged'],
                         [probe.normsha(shapely.from_wkb(bytes.fromhex(p['wkbHex']))) for p in old['implementationExample']['patches']])
        self.assertGreater(self.saved['priorPatchOverlapWithNetworkEnvelopeAreaMm2'], 0)
        self.assertIn('positive gold and negative mask widths including all connected branches transitions terminals and outer-rim flags', self.rule['requiredGates'])


if __name__ == '__main__':
    unittest.main()
