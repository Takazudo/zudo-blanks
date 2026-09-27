"""Small deterministic checks for panel translation and exact order accounting."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_lower_panels import chunks, move, outer_line, line
from verify_lower_panels import checked_reused_drc, order_manifest, sha
from verify_lower_panels import REPO


class LowerPanelTests(unittest.TestCase):
    def test_translation_keeps_local_pad_offset_and_rekeys_uuids(self):
        graphic = '  (gr_poly (pts (xy 1 2) (xy 3 2) (xy 3 4)) (layer "F.Cu") (uuid "old"))\n'
        footprint = ('  (footprint "NPTH" (at 6.5 23.6) (uuid "parent")\n'
                     '    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (uuid "child")))\n')
        shifted = move(graphic, 5, -12.1, 'package:member')
        self.assertIn('(xy 6 -10.1)', shifted)
        self.assertNotIn('(uuid "old")', shifted)
        shifted_footprint = move(footprint, 5, -12.1, 'package:member')
        self.assertIn('(at 11.5 11.5)', shifted_footprint)
        self.assertIn('(at 0 0)', shifted_footprint)
        self.assertEqual(shifted_footprint, move(footprint, 5, -12.1, 'package:member'))

    def test_score_is_drawing_and_decorative_edge_is_not_removed(self):
        border = line((0, 0), (10, 0), "Dwgs.User", "score")
        self.assertIn('(layer "Dwgs.User")', border)
        self.assertNotIn('Edge.Cuts', border)
        self.assertTrue(outer_line('  (gr_line (start 0 17.1) (end 101.3 17.1) (layer "Edge.Cuts"))\n'))
        self.assertFalse(outer_line('  (gr_line (start 1 18) (end 2 19) (layer "Edge.Cuts"))\n'))

    def test_order_has_exact_board_yield_and_waste(self):
        policy = json.loads((HERE / 'policy.json').read_text())
        inventory = json.loads((HERE.parent / 'pcb/manifest.json').read_text())
        selected = {b['id']: b for b in inventory['boards'] if b['category'] == 'selected'}
        self.assertEqual(len(selected), 43)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'packages').mkdir()
            individual = {'boards': []}
            for group in policy['panelGroups']:
                if len(group['memberIds']) == 1:
                    board_id = group['memberIds'][0]
                    path = root / 'packages' / (board_id + '.zip')
                    path.write_bytes(board_id.encode())
                    individual['boards'].append({'id': board_id, 'category': 'selected',
                        'nativeBoardSha256': sha(REPO / selected[board_id]['nativeBoard']),
                        'drcReport': {'selectedAcceptance': 'pass'},
                        'cam': {'status': 'pass', 'packageZip': {'name': path.name, 'sha256': sha(path)}}})
            for board in selected.values():
                if board['layerNumber'] != 1:
                    continue
                path = root / 'packages' / (board['id'] + '.zip')
                path.write_bytes(board['id'].encode())
                individual['boards'].append({'id': board['id'], 'category': 'selected',
                    'nativeBoardSha256': sha(REPO / board['nativeBoard']),
                    'drcReport': {'selectedAcceptance': 'pass'},
                    'cam': {'status': 'pass', 'packageZip': {'name': path.name, 'sha256': sha(path)}}})
            panels = [{'id': 'lower-panel-' + g['id'], 'groupId': g['id']}
                      for g in policy['panelGroups'] if len(g['memberIds']) > 1]
            panel_results = [{'id': p['id'], 'zip': {'sha256': 'dummy'}} for p in panels]
            order = order_manifest(panels, policy, selected, individual, panel_results, root)
            self.assertEqual(order['packageCount'], 13)
            self.assertEqual(order['orderedSheetsAndStandaloneUnits'], 325)
            self.assertEqual(order['usefulBoardCount'], 1075)
            self.assertEqual(order['wasteCells'], 75)
            self.assertEqual(set(order['usefulYieldByBoardId'].values()), {25})
            self.assertEqual(order['hardware']['spacers'], 3800)

    def test_reused_drc_rejects_missing_changed_or_failing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            panel = root / 'lower-panel-test.kicad_pcb'
            panel.write_text('native panel')
            report = root / 'drc.json'
            clean = {'source': panel.name, 'coordinate_units': 'mm',
                     'included_severities': ['error', 'warning', 'exclusion'],
                     'kicad_version': '10.0.0', 'violations': [], 'unconnected_items': []}
            report.write_text(json.dumps(clean))
            record = {'id': 'lower-panel-test', 'nativeBoardSha256': sha(panel)}
            entry = {'nativeBoardSha256': sha(panel), 'reportPath': str(report),
                     'reportSha256': sha(report)}
            self.assertEqual(checked_reused_drc(record, panel, entry)[1], clean)
            with self.assertRaisesRegex(ValueError, 'board hash mismatch'):
                checked_reused_drc(record, panel, {**entry, 'nativeBoardSha256': 'bad'})
            with self.assertRaisesRegex(ValueError, 'missing or hash mismatch'):
                checked_reused_drc(record, panel, {**entry, 'reportPath': str(root / 'missing.json')})
            failing = {**clean, 'violations': [{'type': 'invalid_outline'}]}
            report.write_text(json.dumps(failing))
            with self.assertRaisesRegex(ValueError, 'violations'):
                checked_reused_drc(record, panel, {**entry, 'reportSha256': sha(report)})


if __name__ == '__main__':
    unittest.main()
