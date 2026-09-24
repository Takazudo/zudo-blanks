"""Check the frozen decision against immutable intake evidence and package yields."""
import collections
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent


class FrozenDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((HERE/'policy.json').read_text())
        cls.manifest = json.loads((ROOT/'pcb/manifest.json').read_text())
        cls.review = json.loads((ROOT/'validation/fabrication-review.json').read_text())
        cls.probe = json.loads((HERE/'decision-probe.json').read_text())

    def test_immutable_inputs(self):
        for file, expected in self.policy['sourceHashes'].items():
            with self.subTest(file=file):
                self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), expected)
        self.assertEqual(self.policy['sourceHashes'], self.probe['sourceHashes'])
        self.assertEqual(hashlib.sha256((HERE/'policy.json').read_bytes()).hexdigest(),self.probe['policySha256'])
        self.assertEqual(hashlib.sha256((HERE/'probe_decision.py').read_bytes()).hexdigest(),self.probe['probeScriptSha256'])

    def test_all_and_only_known_wide_closures(self):
        expected = {i['issueId']:i for i in self.review['apertureIssues'] if i['variantId']=='wide'}
        actions = self.policy['selectedApertureActions']
        self.assertEqual(len(actions),56)
        self.assertEqual({a['issueId'] for a in actions},set(expected))
        for action in actions:
            original=expected[action['issueId']]
            self.assertEqual(action['geometryHoleIndex0'],original['geometryHoleIndex0'])
            self.assertEqual(action['boundsMm'],original['boundsMm'])
            self.assertEqual(action['layerNumber'],original['layer'])
        self.assertEqual(set(self.probe['knownClosures']),set(expected))
        self.assertEqual(self.policy['resolvedByClosure']['kumiko-void-wide-L01-THIN-68-101'],
                         'kumiko-void-wide-L01-H11')
        self.assertAlmostEqual(sum(a['originalAreaMm2'] for a in actions),139.19764395,7)

    def test_alternatives_not_orderable(self):
        expected={i['issueId'] for i in self.review['apertureIssues'] if i['variantId']=='standard'}
        self.assertEqual(len(expected),8)
        self.assertEqual(set(self.policy['alternativeUnresolvedIssueIds']),expected)
        self.assertEqual(self.policy['selectedKumiko'],'wide')
        self.assertEqual(sum(b['category']=='alternatives' for b in self.manifest['boards']),9)

    def test_exact_color_finish_groups(self):
        selected={b['id']:b for b in self.manifest['boards'] if b['category']=='selected' and b['layerNumber']>1}
        members=[b for g in self.policy['panelGroups'] for b in g['memberIds']]
        self.assertEqual(len(members),len(set(members)))
        self.assertEqual(set(members),set(selected))
        counts={}
        for group in self.policy['panelGroups']:
            counts[(group['color'],group['finish'])]=len(group['memberIds'])
            for bid in group['memberIds']:
                self.assertEqual(selected[bid]['maskColor'],group['color'])
                self.assertEqual(selected[bid]['finish']=='mask-only',group['finish']=='lead-free HASL')
        self.assertEqual(counts,{('white','lead-free HASL'):7,('black','ENIG'):6,
            ('red','lead-free HASL'):10,('green','lead-free HASL'):4,
            ('purple','lead-free HASL'):1,('yellow','lead-free HASL'):1,
            ('blue','lead-free HASL'):1,('black','lead-free HASL'):8})

    def test_panel_dimensions_score_spacing_and_waste(self):
        for group in self.policy['panelGroups']:
            c,r,rail=group['columns'],group['rows'],group['railMm']
            self.assertAlmostEqual(group['widthMm'],c*101.3+2*rail)
            self.assertAlmostEqual(group['heightMm'],r*94.3+2*rail)
            self.assertEqual(group['unusedCells'],c*r-len(group['memberIds']))
            self.assertLessEqual(len(group['memberIds']),10)
            if rail:
                self.assertEqual(rail,5)
                for count,pitch,side in [(c,101.3,group['widthMm']),(r,94.3,group['heightMm'])]:
                    self.assertLessEqual(side,475)
                    self.assertGreaterEqual(side,70)
                    scores=[rail+n*pitch for n in range(count+1)]
                    self.assertLessEqual(len(scores),25)
                    self.assertTrue(all(b-a>=3 for a,b in zip(scores,scores[1:])))
        self.assertEqual(sum(g['unusedCells'] for g in self.policy['panelGroups']),3)

    def test_exact_finished_yield(self):
        yields=collections.Counter()
        for group in self.policy['panelGroups']:
            self.assertEqual(group['quantity'],25)
            for bid in group['memberIds']:
                yields[bid]+=group['quantity']
        tops=[b for b in self.manifest['boards'] if b['category']=='selected' and b['layerNumber']==1]
        self.assertEqual(len(tops),5)
        for board in tops:
            yields[board['id']]+=25
        self.assertEqual(len(yields),43)
        self.assertEqual(set(yields.values()),{25})
        self.assertEqual(sum(yields.values()),1075)

    def test_probe_covers_every_selected_board_and_border(self):
        self.assertTrue(self.probe['passed'])
        self.assertEqual(len(self.probe['boards']),43)
        self.assertTrue(all(b['supportDisksBridgesFloorBackingConnectivity'] for b in self.probe['boards']))
        self.assertTrue(all(b['minimumDistinctBoundaryMaterialMm']>=.999 for b in self.probe['boards']))
        top_comparisons=[c for c in self.probe['comparisons'] if 'topBorderSourceCount' in c]
        self.assertEqual(len(top_comparisons),5)
        self.assertTrue(all(c['topBorderSourceCount']==9 and c['nineClosedBorderCores025MmPreserved'] for c in top_comparisons))
        for board in self.probe['boards']:
            limit=.035 if board['board']=='kumiko-void-L01' else .02
            self.assertLessEqual(board['removedApertureAreaFraction'],limit)

    def test_mechanical_constants_and_rules(self):
        m=self.policy['mechanical'];r=self.policy['rulesMm']
        self.assertEqual(m['screwCentersMm'],[[6.5,23.6],[94.8,23.6],[6.5,104.9],[94.8,104.9]])
        self.assertEqual(m['railSlotCentersMm'],self.manifest['spec']['slots'])
        self.assertEqual(m['railSlotDimensionsMm'],[10.28,3.2])
        self.assertEqual(r['supportDiskRadiusBeforeDrilling'],3.05)
        self.assertEqual(r['minimumSeparateCopperGap'],.25)
        self.assertEqual(r['minimumMaskWeb'],.25)
        self.assertGreaterEqual(r['lowerCopperToOuterEdge'],.4)
        self.assertFalse(self.policy['material']['platedHoles'])


if __name__=='__main__':
    unittest.main()
