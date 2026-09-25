"""Check the bounded rib decision without claiming full fabrication readiness."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union

HERE=Path(__file__).resolve().parents[1]
module=importlib.util.spec_from_file_location('rib_probe',HERE/'probe_spider_rib.py')
probe=importlib.util.module_from_spec(module)
module.loader.exec_module(probe)


class SpiderRibDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((HERE/'policy.json').read_text())
        cls.rule=next(r for r in cls.policy['errata'] if r['id']=='spider-l01-rib-width-2026-09-25')
        cls.raw=(HERE/cls.rule['evidence']).read_bytes()
        cls.report=json.loads(cls.raw)
        cls.prior=json.loads((HERE/'spider-channel-erratum.json').read_text())
        cls.body=shapely.from_wkb(bytes.fromhex(cls.prior['candidateBodyWkbHex']))
        cls.ribbon=LineString(cls.rule['centerlineMm']).buffer(1,cap_style='flat',join_style='mitre')

    def test_input_and_probe_bindings(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),self.rule['evidenceSha256'])
        self.assertEqual(hashlib.sha256((HERE/'spider-channel-erratum.json').read_bytes()).hexdigest(),self.rule['baseEvidenceSha256'])
        self.assertEqual(probe.normsha(self.body),self.rule['baseBodyNormalizedWkbSha256'])
        self.assertEqual(self.report['approvedSourceSha256'],self.rule['approvedSourceSha256'])
        self.assertEqual(self.report['probeScriptSha256'],hashlib.sha256((HERE/'probe_spider_rib.py').read_bytes()).hexdigest())
        self.assertEqual(probe.measure(),self.report)

    def test_conflict_is_real_at_both_sections(self):
        for s in self.report['sections']:
            self.assertAlmostEqual(s['beforeMaterialWidthMm'],1.66118,places=4)
            self.assertLess(s['beforeAvailableArtworkWidthMm'],s['requiredArtworkWidthMm'])
            self.assertLess(s['beforeAvailableArtworkWidthMm'],s['requiredArtworkWidthAt013WebMm'])
            self.assertAlmostEqual(s['requiredArtworkWidthMm'],1.282)
            self.assertAlmostEqual(s['afterMaterialWidthMm'],2.0,places=6)

    def test_only_named_ribbon_and_apertures_are_authorized(self):
        self.assertEqual(self.rule['centerlineMm'],[[73.5804,43.9604],[66.0864,48.5094],[56.1526,54.5394]])
        added=self.ribbon.difference(self.body)
        self.assertEqual(probe.normsha(added),self.rule['initialAdditionNormalizedWkbSha256'])
        self.assertLessEqual(added.area,self.rule['maximumInitialAdditionAreaMm2'])
        self.assertEqual([r['originalGeometryHoleIndex0'] for r in self.report['affectedOriginalApertures']],[1,6,16])
        after=self.body.union(self.ribbon)
        self.assertLess(self.body.difference(after).area,.00001)
        self.assertEqual(after.bounds,self.body.bounds)
        self.assertEqual(len(after.interiors),len(self.body.interiors))
        self.assertTrue(all(self.report['localChecks'].values()))
        self.assertLess(self.report['cumulativeApertureLossFraction'],.02)

    def test_routing_cleanup_is_bounded_and_not_accepted_unchecked(self):
        affected=[r for r in self.report['diagnosticToolSweeps'] if r['originalGeometryHoleIndex0'] in [1,6,16]]
        self.assertEqual(len(affected),3)
        self.assertTrue(all(r['toolCenterComponents']==1 for r in affected))
        area=sum(r['unreachedAreaMm2'] for r in affected)
        self.assertGreater(area,0)
        self.assertAlmostEqual(area,self.report['affectedApertureRoutingCleanupAreaMm2'])
        self.assertLess(area,self.rule['maximumAdditionalRoutingCleanupAreaMm2'])
        self.assertLess(area+self.report['measuredInitialAdditionAreaMm2'],self.rule['maximumCombinedAdditionAreaMm2'])
        self.assertIn('rerun all affected cutter sweeps and plunge/toolpath access',self.rule['requiredGates'])
        self.assertFalse(self.rule['productionApproval'])

    def test_guide_budget_and_prior_channel_separation(self):
        guide=self.rule['guideGoldWidthMm'];central=self.rule['centralGoldWidthMm'];offset=.5165
        self.assertAlmostEqual(offset-guide/2-central/2,.251)
        self.assertAlmostEqual(1-offset-guide/2,.358)
        self.assertEqual({p['guideStrokeIndex0'] for p in self.rule['guidePortions']},{98,101,103})
        patches=[shapely.from_wkb(bytes.fromhex(p['wkbHex'])) for p in self.prior['implementationExample']['patches']]
        self.assertLess(self.ribbon.buffer(.5).intersection(unary_union(patches)).area,.00001)
        self.assertTrue(self.rule['priorChannelPatchGeometryMustRemainUnchanged'])
        self.assertIn('positive gold and negative mask widths including connected branches and guide transitions',self.rule['requiredGates'])


if __name__=='__main__':
    unittest.main()
