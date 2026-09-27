"""Finished-union checks for indexed hidden copper joins."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import unittest

import shapely
from shapely.strtree import STRtree

HERE=Path(__file__).resolve().parents[1]


class CopperCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (HERE/'copper-repair-candidate.json').exists():
            subprocess.run([sys.executable,str(HERE/'repair_copper_candidate.py')],check=True)
        cls.report=json.loads((HERE/'copper-repair-candidate.json').read_text())
        cls.ledger=json.loads((HERE/'copper-repair-ledger.json').read_text())
        cls.masks=json.loads((HERE/'mask-repair-candidate.json').read_text())

    def test_input_bindings_and_join_inventory(self):
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.report['sourceGeometrySha256'],
                         digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(self.report['maskCandidateSha256'],
                         digest(HERE/'mask-repair-candidate.json'))
        compact={**self.report,
                 'boards':[{k:v for k,v in b.items() if k!='afterCopperWkbHex'}
                           for b in self.report['boards']]}
        self.assertEqual(compact,self.ledger)
        self.assertEqual(len(self.report['boards']),11)
        self.assertEqual(sum(b['joinCount'] for b in self.report['boards']),533)
        self.assertEqual(sum(b['insetAnchorJoinCount'] for b in self.report['boards']),20)
        self.assertEqual([b['joinCount'] for b in self.report['boards']],
                         [88,0,0,0,113,0,1,282,31,16,2])

    def test_final_unions_and_local_reach(self):
        masks={b['boardId']:b for b in self.masks['boards']}
        for board in self.report['boards']:
            with self.subTest(board=board['boardId']):
                copper=shapely.from_wkb(bytes.fromhex(board['afterCopperWkbHex']))
                mask=shapely.from_wkb(bytes.fromhex(masks[board['boardId']]['afterMaskWkbHex']))
                self.assertTrue(copper.is_valid)
                self.assertLess(mask.difference(copper).area,.00001)
                parts=list(shapely.get_parts(copper))
                tree=STRtree(parts)
                close=[]
                for i,part in enumerate(parts):
                    close.extend((i,int(j)) for j in tree.query(part.buffer(.249))
                                 if int(j)>i and part.distance(parts[int(j)])<.249)
                self.assertEqual(close,[])
                self.assertEqual(board['joinCount'],len(board['records']))
                self.assertTrue(all(r['centerlineLengthMm']<=.60 for r in board['records']))
                self.assertTrue(all(r['nominalWidthMm']>=.25 for r in board['records']))
                self.assertTrue(all(r['centerlineLengthMm']>0 for r in board['records']))
                self.assertTrue(all(r['route'] in ('direct','inset anchors',
                                                   'safe-clipped inset anchors')
                                    for r in board['records']))
                clipped=[r for r in board['records']
                         if r['route']=='safe-clipped inset anchors']
                self.assertTrue(all(0<r['safetyClipAreaMm2']<=.002 for r in clipped))
                self.assertEqual(board['insetAnchorJoinCount'],
                                 sum(r['route']!='direct' for r in board['records']))


if __name__=='__main__':
    unittest.main()
