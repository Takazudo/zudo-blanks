"""Four-series selection, sheet partition, and quantity accounting contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from order_profiles import groups_for, load_profile, order_manifest


class FourSeriesProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile, self.boards = load_profile()

    def assert_invalid(self, profile, message):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, message):
                load_profile(path)

    def test_exact_source_membership(self):
        expected = set()
        specs = [
            ('03-coral-vault', ['black-enig-art', 'green-mask-only', 'purple-mask-only',
             'gold-enig-fill', 'red-mask-only', 'yellow-mask-only', 'red-mask-only', 'blue-mask-only']),
            ('13-fault-line', ['black-enig-art'] + ['red-mask-only', 'black-mask-only'] * 4),
            ('17-kumiko-void-wide', ['black-enig-art'] +
             ['red-mask-only', 'green-mask-only', 'black-enig-art'] * 2 + ['red-mask-only', 'green-mask-only']),
            ('01-spider-nest', ['black-enig-art', 'white-mask-only', 'gold-enig-fill',
             'white-mask-only', 'gold-enig-fill', 'white-mask-only', 'gold-enig-fill', 'red-mask-only']),
        ]
        for prefix, finishes in specs:
            expected.update(f'{prefix}-L{layer:02d}-{finish}' for layer, finish in enumerate(finishes, 1))
        self.assertEqual(set(self.boards), expected)
        self.assertEqual(len(expected), 34)
        self.assertEqual(sum(b['layerNumber'] == 1 for b in self.boards.values()), 4)
        for excluded in ('strip-mine', 'woven-maze', '17-kumiko-void-L'):
            self.assertFalse(any(excluded in bid for bid in expected))

    def test_default_variant_totals_and_unchanged_top_purchase_units(self):
        for variant, count, units, waste in [('individual', 34, 850, 0), ('grouped', 12, 300, 50),
                                              ('split-red', 13, 325, 0)]:
            with self.subTest(variant=variant):
                result = order_manifest(self.profile, variant, self.boards)
                self.assertEqual((result['packageCount'], result['orderedSheetsAndStandaloneUnits'],
                                  result['wasteCells']), (count, units, waste))
                self.assertEqual(result['selectedBoardCount'], 34)
                self.assertEqual(result['usefulBoardCount'], 850)
                self.assertEqual(result['producedBoardCount'], 850)
                self.assertEqual(result['requestedCompleteStacks'], 100)
                self.assertEqual(result['completeStackYield'], 100)
                self.assertEqual(result['surplusFinishedBoards'], 0)
                self.assertEqual(result['hardwareForRequestedStacks'], {'screws': 400, 'nuts': 400, 'spacers': 3000})
                self.assertEqual(set(result['supplyByBoardId'].values()), {25})
                tops = [p for p in result['packages'] if p['kind'] == 'routed_standalone_top']
                self.assertEqual(len(tops), 4)
                self.assertTrue(all(len(p['memberIds']) == 1 and p['widthMm'] == 101.3 and
                                    p['heightMm'] == 128.5 and p['quantity'] == 25 for p in tops))
                self.assertTrue(all(value is None for value in result['quote'].values()))

    def test_exact_red_split_and_compact_dimensions(self):
        groups = {g['id']: g for g in groups_for(self.profile, 'split-red', self.boards)}
        self.assertEqual(groups['red-hasl-six']['memberIds'], [
            '01-spider-nest-L08-red-mask-only', '03-coral-vault-L05-red-mask-only',
            '03-coral-vault-L07-red-mask-only', '17-kumiko-void-wide-L02-red-mask-only',
            '17-kumiko-void-wide-L05-red-mask-only', '17-kumiko-void-wide-L08-red-mask-only'])
        self.assertEqual(groups['red-hasl-fault']['memberIds'], [
            f'13-fault-line-L{layer:02d}-red-mask-only' for layer in (2, 4, 6, 8)])
        for gid, dimensions in {'red-hasl-six': (212.6, 292.9), 'red-hasl-fault': (212.6, 198.6),
                                'white-hasl': (111.3, 292.9), 'black-enig': (313.9, 198.6)}.items():
            self.assertEqual((groups[gid]['widthMm'], groups[gid]['heightMm']), dimensions)
            self.assertEqual(groups[gid]['railMm'], 5)
        red = next(g for g in groups_for(self.profile, 'grouped', self.boards) if g['id'] == 'red-hasl')
        self.assertEqual((len(red['memberIds']), red['widthMm'], red['heightMm'], red['unusedCells']),
                         (10, 313.9, 387.2, 2))

    def test_color_and_finish_are_both_partition_keys(self):
        groups = groups_for(self.profile, 'grouped', self.boards)
        counts = {(g['color'], g['finish']): len(g['memberIds']) for g in groups}
        self.assertEqual(counts, {('white', 'lead-free HASL'): 3, ('black', 'ENIG'): 6,
                         ('red', 'lead-free HASL'): 10, ('green', 'lead-free HASL'): 4,
                         ('purple', 'lead-free HASL'): 1, ('yellow', 'lead-free HASL'): 1,
                         ('blue', 'lead-free HASL'): 1, ('black', 'lead-free HASL'): 4})
        for key, value in [('color', 'red'), ('finish', 'ENIG')]:
            profile = copy.deepcopy(self.profile)
            profile['variants']['grouped']['groups'][0][key] = value
            self.assert_invalid(profile, 'Incompatible color or finish')

    def test_missing_duplicate_and_excluded_members_fail(self):
        for replacement in (None, '03-coral-vault-L02-green-mask-only', '09-strip-mine-L08-white-mask-only'):
            profile = copy.deepcopy(self.profile)
            ids = profile['series']['coral-vault']['boardIds']
            if replacement is None:
                ids.pop()
            else:
                ids[-1] = replacement
            self.assert_invalid(profile, 'exact source ID membership')
        profile = copy.deepcopy(self.profile)
        profile['variants']['grouped']['groups'].pop()
        self.assert_invalid(profile, 'Missing or duplicate lower group membership')
        profile = copy.deepcopy(self.profile)
        profile['variants']['grouped']['groups'].append(copy.deepcopy(profile['variants']['grouped']['groups'][0]))
        self.assert_invalid(profile, 'Missing or duplicate lower group membership')
        profile = copy.deepcopy(self.profile)
        profile['variants']['grouped']['groups'][0]['memberIds'][0] = '01-spider-nest-L01-black-enig-art'
        self.assert_invalid(profile, 'Only selected lowers')

    def test_unequal_demands_round_per_purchase_source(self):
        for name, count in [('coral-vault', 10), ('fault-line', 26), ('kumiko-void', 15), ('spider-nest', 5)]:
            self.profile['series'][name]['stacks'] = count
        for variant, produced, surplus, units, waste in [
                ('individual', 525, 36, 525, 0), ('grouped', 675, 186, 185, 60), ('split-red', 585, 96, 200, 0)]:
            with self.subTest(variant=variant):
                result = order_manifest(self.profile, variant, self.boards)
                self.assertEqual(result['usefulBoardCount'], 489)
                self.assertEqual(result['producedBoardCount'], produced)
                self.assertEqual(result['surplusFinishedBoards'], surplus)
                self.assertEqual(result['orderedSheetsAndStandaloneUnits'], units)
                self.assertEqual(result['wasteCells'], waste)
                self.assertEqual(result['requestedCompleteStacks'], 56)
                self.assertEqual(result['completeStackYield'], 60)
                self.assertEqual(result['hardwareForRequestedStacks'], {'screws': 224, 'nuts': 224, 'spacers': 1732})
                self.assertEqual({s: v['completeStacks'] for s, v in result['designs'].items()},
                                 {'coral-vault': 10, 'fault-line': 30, 'kumiko-void': 15, 'spider-nest': 5})
                self.assertEqual(result['surplusByBoardId']['13-fault-line-L01-black-enig-art'], 4)

    def test_invalid_quantities_layouts_and_rails_fail(self):
        for quantity in (0, -1, 1.5, True, '25'):
            profile = copy.deepcopy(self.profile)
            profile['series']['coral-vault']['stacks'] = quantity
            self.assert_invalid(profile, 'positive integers')
        for quantities in ([], [25, 5], [5, 5], [True], [0]):
            profile = copy.deepcopy(self.profile)
            profile['supplierQuantities'] = quantities
            self.assert_invalid(profile, 'Supplier quantities')
        for columns, rows in ((0, 3), (1, 2), (True, 3), (1, 6)):
            profile = copy.deepcopy(self.profile)
            profile['variants']['grouped']['groups'][0].update(columns=columns, rows=rows)
            self.assert_invalid(profile, 'Invalid grid capacity|dimensions exceed')
        profile = copy.deepcopy(self.profile)
        profile['railMm'] = 4
        self.assert_invalid(profile, 'fixed 5 mm rails')
        self.profile['series']['coral-vault']['stacks'] = 1001
        for variant in ('individual', 'grouped', 'split-red'):
            with self.assertRaisesRegex(ValueError, 'No supplier quantity covers'):
                order_manifest(self.profile, variant, self.boards)
        with self.assertRaisesRegex(ValueError, 'Unknown variant'):
            order_manifest(self.profile, 'bogus', self.boards)


class NativePanelMutationTests(unittest.TestCase):
    """Regenerate from committed sources, then reject plausible native damage."""

    @classmethod
    def setUpClass(cls):
        from build_lower_panels import build
        from order_profiles import DEFAULT_PROFILE
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.output = Path(cls.directory.name)
        result = build(cls.output, profile=DEFAULT_PROFILE, variant='split-red',
                       evidence_path=cls.output / 'evidence.json')
        cls.records = result['panels']
        _, cls.boards = load_profile()
        cls.record = next(r for r in cls.records if r['groupId'] == 'red-hasl-fault')
        cls.panel = cls.output / cls.record['nativeBoard']
        cls.original = cls.panel.read_text()

    def assert_native_rejected(self, text, message):
        from verify_lower_panels import native_partition
        path = self.output / 'mutated.kicad_pcb'
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, message):
            native_partition(path, self.record, self.boards)

    def test_fresh_translation_only_panels_pass(self):
        from verify_lower_panels import native_partition
        self.assertEqual(len(self.records), 6)
        for record in self.records:
            with self.subTest(panel=record['id']):
                _, evidence = native_partition(self.output / record['nativeBoard'], record, self.boards)
                self.assertTrue(evidence['sheetMaterialConnected'])
                self.assertEqual(evidence['npthMounts'], len(record['placements']) * 4)

    def test_routed_contour_edit_rejected(self):
        from verify_native_cam import GR_LINE_RE
        line = next(m for m in GR_LINE_RE.finditer(self.original) if m.group(5) == 'Edge.Cuts')
        start, end = line.span(1)
        changed = self.original[:start] + str(float(line.group(1)) + .1) + self.original[end:]
        self.assert_native_rejected(changed, 'native routed contours changed')

    def test_drill_size_edit_rejected(self):
        from verify_native_cam import NPTH_PAD_RE
        pad = NPTH_PAD_RE.search(self.original)
        self.assertIsNotNone(pad)
        start, end = pad.span(7)
        changed = self.original[:start] + str(float(pad.group(7)) + .1) + self.original[end:]
        self.assert_native_rejected(changed, 'translated NPTH pads changed')

    def test_score_coordinate_edit_rejected(self):
        from verify_native_cam import GR_LINE_RE
        score = next(m for m in GR_LINE_RE.finditer(self.original) if m.group(5) == 'Dwgs.User')
        start, end = score.span(2)
        changed = self.original[:start] + str(float(score.group(2)) + .1) + self.original[end:]
        self.assert_native_rejected(changed, 'Native scores differ')

    def test_score_evidence_edit_rejected(self):
        from verify_lower_panels import native_partition
        record = copy.deepcopy(self.record)
        record['scoreYMm'][0] += .1
        with self.assertRaisesRegex(ValueError, 'Invalid score coordinate record'):
            native_partition(self.panel, record, self.boards)


if __name__ == '__main__':
    unittest.main()
