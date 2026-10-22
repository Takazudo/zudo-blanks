"""Bounded nine-board Woven Maze order selection, grouped accounting and mutation checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from order_profiles import load_profile, order_manifest

PROFILE = HERE / 'order-profiles/woven-maze.json'
MANIFEST = HERE.parent / 'pcb/manifest.json'


class WovenProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile, self.boards = load_profile(PROFILE)

    def reject(self, profile=None, inventory=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'profile.json'
            path.write_text(json.dumps(self.profile if profile is None else profile))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(json.loads(MANIFEST.read_text()) if inventory is None else inventory))
            with self.assertRaises(ValueError):
                load_profile(path, manifest_path=manifest)

    def test_exact_order_and_settings(self):
        order = order_manifest(self.profile, 'individual', self.boards)
        self.assertEqual((order['selectedBoardCount'], order['packageCount'],
                          order['requestedCompleteStacks'], order['completeStackYield']), (9, 9, 25, 25))
        self.assertEqual((order['producedBoardCount'], order['surplusFinishedBoards']), (225, 0))
        self.assertEqual(order['hardwareForRequestedStacks'], {'screws': 100, 'nuts': 100, 'spacers': 800})
        expected = ['black-enig-art'] + ['white-mask-only', 'black-mask-only'] * 4
        for layer, (package, suffix) in enumerate(zip(order['packages'], expected), 1):
            self.assertEqual(package['id'], f'18-woven-maze-L{layer:02d}-{suffix}')
            self.assertEqual(package['memberIds'], [package['id']])
            self.assertEqual(package['quantity'], 25)
            self.assertEqual(package['finish'], 'ENIG' if layer == 1 else 'lead-free HASL')
            self.assertEqual(package['color'], 'white' if layer % 2 == 0 else 'black')
            self.assertEqual((package['widthMm'], package['heightMm']), (101.3, 128.5 if layer == 1 else 94.3))
            self.assertEqual((package['material'], package['thicknessMm'], package['copperLayers'],
                              package['copperOz'], package['silkscreen']), ('FR-4', 1.6, 2, 1, False))

    def test_grouped_two_same_mask_sheets_and_standalone_top(self):
        order = order_manifest(self.profile, 'grouped', self.boards)
        self.assertEqual((order['packageCount'], order['orderedSheetsAndStandaloneUnits'],
                          order['usefulBoardCount'], order['producedBoardCount'],
                          order['wasteCells'], order['surplusFinishedBoards'],
                          order['requestedCompleteStacks'], order['completeStackYield']),
                         (3, 75, 225, 225, 0, 0, 25, 25))
        self.assertEqual(set(order['supplyByBoardId'].values()), {25})
        self.assertEqual(set(order['surplusByBoardId'].values()), {0})
        white, black, top = order['packages']
        for sheet, color, parity in ((white, 'white', 0), (black, 'black', 1)):
            self.assertEqual(sheet['id'], f'lower-panel-{color}-hasl')
            self.assertEqual(sheet['kind'], 'scored_lower_grid')
            self.assertEqual(sheet['memberIds'],
                             [f'18-woven-maze-L{n:02d}-{color}-mask-only' for n in range(2+parity, 10, 2)])
            self.assertEqual((sheet['columns'], sheet['rows'], sheet['railMm'], sheet['unusedCells']), (2, 2, 5, 0))
            self.assertEqual((sheet['widthMm'], sheet['heightMm']), (212.6, 198.6))
            self.assertEqual((sheet['quantity'], sheet['distinctDesigns'], sheet['producedPieces']), (25, 4, 100))
            self.assertEqual(set(sheet['copiesPerSheet'].values()), {1})
            self.assertEqual((sheet['color'], sheet['finish']), (color, 'lead-free HASL'))
        self.assertEqual((top['id'], top['kind'], top['memberIds'], top['quantity']),
                         ('18-woven-maze-L01-black-enig-art', 'routed_standalone_top',
                          ['18-woven-maze-L01-black-enig-art'], 25))
        self.assertEqual((top['finish'], top['widthMm'], top['heightMm']), ('ENIG', 101.3, 128.5))
        self.assertEqual(order_manifest(self.profile, 'individual', self.boards)['packageCount'], 9)

    def test_grouped_membership_and_grid_mutations_rejected(self):
        top = '18-woven-maze-L01-black-enig-art'
        mutations = {
            'top in sheet': lambda g: g[1]['memberIds'].__setitem__(0, top),
            'mixed masks': lambda g: (g[0]['memberIds'].__setitem__(0, '18-woven-maze-L03-black-mask-only'),
                                      g[1]['memberIds'].__setitem__(0, '18-woven-maze-L02-white-mask-only')),
            'missing member': lambda g: g[0]['memberIds'].pop(),
            'duplicate member': lambda g: g[0]['memberIds'].__setitem__(3, g[0]['memberIds'][0]),
            'excluded series': lambda g: g[0]['memberIds'].__setitem__(0, '01-spider-nest-L02-white-mask-only'),
            'enig finish': lambda g: g[1].update(finish='ENIG'),
            'wrong grid': lambda g: g[0].update(columns=4, rows=1),
            'float grid': lambda g: g[0].update(columns=2.0),
            'blank cells': lambda g: g[0].update(rows=3),
            'third sheet': lambda g: g.append(dict(g[0], id='white-extra')),
            'one sheet': lambda g: g.pop(),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                profile = copy.deepcopy(self.profile)
                mutate(profile['variants']['grouped']['groups'])
                self.reject(profile)
        profile = copy.deepcopy(self.profile)
        profile['railMm'] = 5.0
        self.reject(profile)

    def test_missing_duplicate_reordered_or_unrelated_boards_rejected(self):
        for kind in ('missing', 'duplicate', 'reordered', 'unrelated'):
            with self.subTest(kind=kind):
                profile = copy.deepcopy(self.profile)
                ids = profile['series']['woven-maze']['boardIds']
                if kind == 'missing':
                    ids.pop()
                elif kind == 'duplicate':
                    ids[-1] = ids[0]
                elif kind == 'reordered':
                    ids.reverse()
                else:
                    ids[-1] = '01-spider-nest-L01-black-enig-art'
                self.reject(profile)

    def test_changed_quantity_or_grouping_rejected(self):
        for count in (0, 24, 26, 25.0, True, '25'):
            profile = copy.deepcopy(self.profile)
            profile['series']['woven-maze']['stacks'] = count
            self.reject(profile)
        for quantities in ([], [5, 25], [30], [25.0]):
            profile = copy.deepcopy(self.profile)
            profile['supplierQuantities'] = quantities
            self.reject(profile)
        profile = copy.deepcopy(self.profile)
        profile['variants']['individual']['groups'] = [{'memberIds': list(self.boards)}]
        self.reject(profile)
        profile = copy.deepcopy(self.profile)
        profile['variants']['split-red'] = {'groups': []}
        self.reject(profile)
        with self.assertRaises(ValueError):
            order_manifest(self.profile, 'split-red', self.boards)
        profile = copy.deepcopy(self.profile)
        del profile['variants']['grouped']
        self.reject(profile)

    def test_extra_keys_and_non_object_profile_rejected(self):
        for mutate in (lambda p: p['series']['woven-maze'].update(extra=1),
                       lambda p: p['series'].update({'coral-vault': p['series']['woven-maze']}),
                       lambda p: p['variants']['individual'].update(columns=1)):
            profile = copy.deepcopy(self.profile)
            mutate(profile)
            self.reject(profile)
        self.reject([self.profile])

    def test_inventory_membership_and_configuration_rejected(self):
        original = json.loads(MANIFEST.read_text())
        for key, value in [('maskColor', 'red'), ('finish', 'mask-only'),
                           ('thicknessMm', 2), ('layerNumber', 2),
                           ('boardBoundsMm', [0, 0, 100, 128.5]),
                           ('nativeBoard', 'panels/unrelated.kicad_pcb')]:
            inventory = copy.deepcopy(original)
            board = next(b for b in inventory['boards'] if b['id'] == '18-woven-maze-L01-black-enig-art')
            board[key] = value
            self.reject(inventory=inventory)
        for board_id, key, value in [('18-woven-maze-L02-white-mask-only', 'maskColor', 'black'),
                                     ('18-woven-maze-L09-black-mask-only', 'boardBoundsMm', [0, 0, 101.3, 128.5]),
                                     ('18-woven-maze-L05-black-mask-only', 'finish', 'enig-art'),
                                     ('18-woven-maze-L03-black-mask-only', 'layerNumber', None)]:
            with self.subTest(board_id=board_id, key=key):
                inventory = copy.deepcopy(original)
                board = next(b for b in inventory['boards'] if b['id'] == board_id)
                if value is None:
                    del board[key]
                else:
                    board[key] = value
                self.reject(inventory=inventory)
        inventory = copy.deepcopy(original)
        inventory['boards'].append(copy.deepcopy(next(b for b in inventory['boards'] if b['designId'] == 'woven-maze')))
        self.reject(inventory=inventory)

    def test_existing_four_series_remains_separate(self):
        profile, boards = load_profile()
        self.assertEqual(len(boards), 34)
        self.assertFalse(set(boards) & set(self.boards))
        self.assertEqual(order_manifest(profile, 'split-red', boards)['packageCount'], 13)


if __name__ == '__main__':
    unittest.main()
