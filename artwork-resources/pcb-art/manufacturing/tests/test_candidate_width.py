"""Source-bound local width repairs for the practical native candidate."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import shapely
from shapely.geometry import box

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import repair_mask_candidate as mask_repair  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CandidateWidthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.masks=json.loads((HERE/'mask-repair-candidate.json').read_text())
        cls.copper=json.loads((HERE/'copper-repair-candidate.json').read_text())

    def test_current_candidates_are_bound_and_have_no_unresolved_local_widths(self):
        geometry_hash=digest(HERE/'manufacturing-geometry.json')
        self.assertEqual(self.masks['sourceGeometrySha256'],geometry_hash)
        self.assertEqual(self.copper['sourceGeometrySha256'],geometry_hash)
        self.assertEqual(self.copper['maskCandidateSha256'],
                         digest(HERE/'mask-repair-candidate.json'))
        self.assertEqual(len(self.masks['boards']),11)
        self.assertEqual(len(self.copper['boards']),11)
        self.assertEqual({b['boardId'] for b in self.masks['boards']},
                         {b['boardId'] for b in self.copper['boards']})
        for board in self.masks['boards']:
            with self.subTest(board=board['boardId']):
                self.assertEqual(board['unresolvedWidthFailures'],[])
        for board in self.copper['boards']:
            with self.subTest(board=board['boardId']):
                self.assertEqual(board['unresolvedCopperWidthFailures'],[])

    def test_every_mask_width_edit_is_indexed_local(self):
        policy=json.loads((HERE/'policy.json').read_text())
        reach=policy['rulesMm']['localMaskCorrectionReachMax']
        for board in self.masks['boards']:
            edits=[r for r in board['records'] if r.get('operation','').startswith(
                ('retreat gold to open','widen indexed sub-width gold','cap indexed sub-width gold'))]
            self.assertEqual(len(edits),board['widthEnforcementEdits'])
            for record in edits:
                with self.subTest(board=board['boardId'],operation=record['operation']):
                    edit=shapely.from_wkb(bytes.fromhex(record['editWkbHex']))
                    self.assertGreater(record['chordCount'],0)
                    # One record can contain many offending chords; chordMm
                    # only stores the worst. Its residue bounds cover all.
                    zone=box(*record['residueBoundsMm']).buffer(reach)
                    self.assertLess(edit.difference(zone).area,1e-6)
                    self.assertEqual(hashlib.sha256(shapely.normalize(edit).wkb).hexdigest(),
                                     record.get('goldRemovedWkbSha256',record.get('goldAddedWkbSha256')))

    def test_protected_top_rim_cores_survive(self):
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
