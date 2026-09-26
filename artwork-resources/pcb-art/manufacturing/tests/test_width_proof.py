"""Bind the class-aware width gate and the indexed width-enforcement edits."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import shapely
from shapely.geometry import LineString

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import repair_mask_candidate as mask_repair  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WidthProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof=json.loads((HERE/'width-proof.json').read_text())
        cls.masks=json.loads((HERE/'mask-repair-candidate.json').read_text())
        cls.copper=json.loads((HERE/'copper-repair-candidate.json').read_text())

    def test_gate_is_bound_and_passes_every_enig_board(self):
        self.assertEqual(self.proof['manufacturingGeometrySha256'],digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(self.proof['maskCandidateSha256'],digest(HERE/'mask-repair-candidate.json'))
        self.assertEqual(self.proof['copperCandidateSha256'],digest(HERE/'copper-repair-candidate.json'))
        self.assertEqual(self.proof['policyErratum'],'process-classes-2026-09-25')
        self.assertEqual(len(self.proof['boards']),11)
        for board in self.proof['boards']:
            with self.subTest(board=board['boardId']):
                self.assertTrue(board['passed'],board['failureCounts'])
                expected=.25 if board['boardId'].startswith('01-spider-nest-') else .13
                self.assertEqual(board['blackInkWidthMm'],expected)
        self.assertTrue(self.proof['passed'])
        self.assertTrue(all(not b['unresolvedWidthFailures'] for b in self.masks['boards']))
        self.assertTrue(all(not b['unresolvedCopperWidthFailures'] for b in self.copper['boards']))

    def test_every_width_edit_is_indexed_local_and_spares_rim_cores(self):
        policy=json.loads((HERE/'policy.json').read_text())
        reach=policy['rulesMm']['localMaskCorrectionReachMax']
        for board in self.masks['boards']:
            edits=[r for r in board['records'] if r.get('operation','').startswith(
                ('retreat gold to open','widen indexed sub-width gold','cap indexed sub-width gold'))]
            self.assertEqual(len(edits),board['widthEnforcementEdits'])
            for record in edits:
                with self.subTest(board=board['boardId'],operation=record['operation']):
                    edit=shapely.from_wkb(bytes.fromhex(record['editWkbHex']))
                    chord=LineString(record['chordMm'])
                    self.assertLess(edit.difference(chord.buffer(reach)).area,1e-6)
                    self.assertEqual(hashlib.sha256(shapely.normalize(edit).wkb).hexdigest(),
                                     record.get('goldRemovedWkbSha256',record.get('goldAddedWkbSha256')))

    def test_rim_cores_survive(self):
        geometry=json.loads((HERE/'manufacturing-geometry.json').read_text())
        masks={b['boardId']:b for b in self.masks['boards']}
        for family in geometry['designs']:
            design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                    if family['id']=='kumiko-void' else family)
            layer=design['layers'][0]
            name=mask_repair.board_id(design,layer)
            if name not in masks:
                continue
            mask=shapely.from_wkb(bytes.fromhex(masks[name]['afterMaskWkbHex']))
            self.assertLess(mask_repair.rim_cores(design,layer).difference(mask).area,1e-5)


if __name__=='__main__':
    unittest.main()
