"""The corrected Coral copper must survive native 1 nm contour serialization."""
import json
from pathlib import Path
import sys
import unittest

import shapely

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from generate_native import native_parts_with_precision_repair  # noqa: E402


class NativePartitionTests(unittest.TestCase):
    def test_coral_copper_split_contours_are_valid_and_area_bound(self):
        report=json.loads((HERE/'copper-repair-candidate.json').read_text())
        board=next(b for b in report['boards']
                   if b['boardId']=='03-coral-vault-L01-black-enig-art')
        copper=shapely.from_wkb(bytes.fromhex(board['afterCopperWkbHex']))
        parts,fragments,repair=native_parts_with_precision_repair(copper)
        self.assertEqual(repair['repairedSplitPieceCount'],2)
        self.assertTrue(all(part.is_valid and not part.interiors for part in parts))
        self.assertLessEqual(fragments['areaMm2'],.000001)
        self.assertLessEqual(repair['serializedSymmetricDifferenceMm2'],.02)
        self.assertLessEqual(shapely.union_all(parts).symmetric_difference(copper).area,.02)


if __name__=='__main__':
    unittest.main()
