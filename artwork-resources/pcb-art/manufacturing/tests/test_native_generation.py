"""Selected native candidate registration without claiming KiCad/CAM validation."""
import hashlib
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[2]


class NativeGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((HERE/'native-generation.json').read_text())
        cls.approved=json.loads((HERE.parent/'pcb/manifest.json').read_text())

    def test_selected_files_and_projects_are_bound_to_candidates(self):
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(self.report['selectedBoardCount'],43)
        self.assertEqual(self.report['manufacturingGeometrySha256'],
                         digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(self.report['maskCandidateSha256'],
                         digest(HERE/'mask-repair-candidate.json'))
        self.assertEqual(self.report['copperLedgerSha256'],
                         digest(HERE/'copper-repair-ledger.json'))
        self.assertEqual(len({b['boardId'] for b in self.report['boards']}),43)
        self.assertEqual(sum(b['npthRoundCount'] for b in self.report['boards']),172)
        self.assertEqual(sum(b['npthSlotCount'] for b in self.report['boards']),20)
        for board in self.report['boards']:
            with self.subTest(board=board['boardId']):
                pcb=ROOT/board['nativeBoard']
                project=ROOT/board['project']
                self.assertEqual(digest(pcb),board['sha256'])
                self.assertEqual(digest(project),board['projectSha256'])
                project_data=json.loads(project.read_text())
                rules=project_data['board']['design_settings']['rules']
                self.assertEqual(rules['min_copper_edge_clearance'],.30)
                self.assertEqual(rules['solder_mask_to_copper_clearance'],0.0)
                self.assertEqual(project_data['schematic']['top_level_sheets'],[])
                native=pcb.read_text()
                self.assertEqual(native.count('np_thru_hole'),
                                 board['npthRoundCount']+board['npthSlotCount'])
                self.assertNotIn('(layer "B.Cu") (uuid',native)
                self.assertNotIn('(layer "B.Mask") (uuid',native)

    def test_standard_alternatives_remain_approved_and_non_orderable(self):
        digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
        alternatives=[b for b in self.approved['boards'] if b['category']=='alternatives']
        self.assertEqual(len(alternatives),9)
        for board in alternatives:
            self.assertEqual(digest(ROOT/board['nativeBoard']),board['nativeBoardSha256'])
        self.assertTrue(all('standard' not in b['boardId'] for b in self.report['boards']))


if __name__=='__main__':
    unittest.main()
