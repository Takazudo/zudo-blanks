"""KiCad-native outline and project-rule checks for selected art boards."""

import json
import math
from pathlib import Path
import sys
import unittest

from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from generate_native import (  # noqa: E402
    EDGE_DRC_CONTOUR_REPAIR_BOARDS,
    EDGE_DRC_CONTOUR_REPAIR_MM,
    EDGE_MIN_SEGMENT_MM,
    native_edge_rings,
    project_content,
)
from repair_mask_candidate import board_id, export  # noqa: E402


class NativeEdgeTests(unittest.TestCase):
    def test_selected_contours_survive_short_segment_repair(self):
        data = json.loads((HERE / 'manufacturing-geometry.json').read_text())
        count = 0
        removed = 0
        for family in data['designs']:
            design = (next(d for d in family['variants'] if d.get('variantId') == 'wide')
                      if family['id'] == 'kumiko-void' else family)
            for layer in design['layers']:
                name = board_id(design, layer)
                with self.subTest(board=name):
                    drills = export.drill_specs(layer, data['spec'])
                    holes = export.split_functional_holes(layer, drills)
                    source = [Polygon(layer['outer']).exterior] + [p.exterior for p in holes]
                    threshold = (EDGE_DRC_CONTOUR_REPAIR_MM
                                 if name in EDGE_DRC_CONTOUR_REPAIR_BOARDS
                                 else EDGE_MIN_SEGMENT_MM)
                    ring_thresholds = ({3: .0031}
                                       if name == '01-spider-nest-L03-gold-enig-fill'
                                       else None)
                    collinear_rings = ({1}
                                       if name in ('13-fault-line-L08-red-mask-only',
                                                   '18-woven-maze-L07-black-mask-only')
                                       else None)
                    repaired, record = native_edge_rings(source, threshold,
                                                         ring_thresholds,
                                                         collinear_rings)
                    self.assertEqual(len(repaired), len(source))
                    self.assertLessEqual(record['maxDeviationMm'], .001)
                    self.assertLessEqual(record['areaDeltaMm2'], .02)
                    for ring in repaired:
                        points = export.ring_points(ring)
                        self.assertTrue(Polygon(points).is_valid)
                        self.assertGreaterEqual(min(math.dist(points[i - 1], points[i])
                                                    for i in range(len(points))), threshold - 1e-12)
                    count += 1
                    removed += record['removedShortSegments']
        self.assertEqual(count, 43)
        self.assertGreater(removed, 0)

    def test_manufacturing_relevant_drc_rules_are_enabled(self):
        project = json.loads(project_content('probe'))
        severities = project['board']['design_settings']['rule_severities']
        self.assertEqual(project['board']['design_settings']['drc_exclusions'], [])
        for name in ('copper_edge_clearance', 'solder_mask_bridge', 'shorting_items'):
            self.assertEqual(severities[name], 'error')


if __name__ == '__main__':
    unittest.main()
