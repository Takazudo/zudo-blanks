"""Woven Maze 2x2 lower sheets: translation-only geometry, scores and corruption rejection."""
import copy
from pathlib import Path
import re
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_lower_panels import build
from order_profiles import load_profile
from verify_lower_panels import native_partition

PROFILE = HERE / 'order-profiles/woven-maze.json'


class WovenPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.record = build(cls.root / 'native', profile=PROFILE, variant='grouped',
                           evidence_path=cls.root / 'native-panels.json')
        cls.profile, cls.boards = load_profile(PROFILE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def panel(self, group):
        record = next(p for p in self.record['panels'] if p['groupId'] == group)
        return record, self.root / 'native' / record['nativeBoard']

    def corrupt(self, group, message, text_edit=None, record_edit=None):
        record, pcb = self.panel(group)
        record = copy.deepcopy(record)
        target = self.root / 'corrupt' / pcb.name
        target.parent.mkdir(exist_ok=True)
        text = pcb.read_text()
        target.write_text(text_edit(text) if text_edit else text)
        if record_edit:
            record_edit(record)
        with self.assertRaisesRegex(ValueError, message):
            native_partition(target, record, self.boards)

    def test_two_sheets_keep_exact_translated_members_scores_and_clearances(self):
        self.assertEqual(self.record['variant'], 'grouped')
        self.assertEqual([p['groupId'] for p in self.record['panels']], ['white-hasl', 'black-hasl'])
        for record in self.record['panels']:
            group = next(g for g in self.profile['variants']['grouped']['groups'] if g['id'] == record['groupId'])
            self.assertEqual([p['id'] for p in record['placements']], group['memberIds'])
            self.assertEqual([p['translationMm'] for p in record['placements']],
                             [[5, -12.1], [106.3, -12.1], [5, 82.2], [106.3, 82.2]])
            self.assertEqual((record['widthMm'], record['heightMm'], record['unusedCells']), (212.6, 198.6, 0))
            for got, want in ((record['scoreXMm'], [5, 106.3, 207.6]), (record['scoreYMm'], [5, 99.3, 193.6])):
                self.assertEqual(len(got), len(want))
                for a, b in zip(got, want):
                    self.assertAlmostEqual(a, b, places=6)
            clearance = record['minimumScoreClearanceMm']
            self.assertGreaterEqual(clearance['apertureMm'], .999)
            self.assertGreaterEqual(clearance['supportDiskMm'], .999)
            _, partition = native_partition(self.root / 'native' / record['nativeBoard'], record, self.boards)
            self.assertTrue(partition['sheetMaterialConnected'])
            self.assertEqual(partition['npthMounts'], 16)
            fab = (self.root / 'native' / Path(record['nativeBoard']).parent / 'FABRICATION.txt').read_text()
            self.assertIn('212.6 x 198.6 mm', fab)
            self.assertIn('lead-free HASL', fab)
            self.assertIn('order 25 sheets', fab)

    def test_removed_aperture_segment_rejected(self):
        def drop_aperture(text):
            lines = text.splitlines(keepends=True)
            index = next(i for i, l in enumerate(lines) if '(gr_line' in l and '"Edge.Cuts"' in l
                         and not re.search(r'\(start (0|212\.6) ', l))
            return ''.join(lines[:index] + lines[index+1:])
        self.corrupt('white-hasl', 'native routed contours changed', drop_aperture)

    def test_moved_npth_mount_rejected(self):
        def move_mount(text):
            match = re.search(r'\(footprint "[^"]*".*?\(at (-?[\d.]+) ', text, re.S)
            return text[:match.start(1)] + str(float(match[1]) + .1) + text[match.end(1):]
        self.corrupt('black-hasl', 'translated NPTH pads changed', move_mount)

    def test_missing_or_misplaced_score_rejected(self):
        def drop_score(text):
            lines = text.splitlines(keepends=True)
            index = next(i for i, l in enumerate(lines) if '"Dwgs.User"' in l and '(gr_line' in l)
            return ''.join(lines[:index] + lines[index+1:])
        self.corrupt('white-hasl', 'Native scores differ', drop_score)
        self.corrupt('white-hasl', 'Invalid score coordinate record', record_edit=lambda r: r['scoreXMm'].__setitem__(1, 106.0))

    def test_wrong_placement_or_member_rejected(self):
        self.corrupt('black-hasl', 'Placement differs', record_edit=lambda r: r['placements'][0]['translationMm'].__setitem__(0, 5.5))
        self.corrupt('black-hasl', 'Placement differs', record_edit=lambda r: r['placements'].reverse())
        self.corrupt('white-hasl', 'Source hash changed', record_edit=lambda r: r['placements'][0].update(sourceSha256='0' * 64))


if __name__ == '__main__':
    unittest.main()
