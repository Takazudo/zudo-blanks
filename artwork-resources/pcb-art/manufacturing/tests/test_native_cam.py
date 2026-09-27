"""Focused regressions for the independent Gerber and Excellon parsers."""

from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import verify_native_cam as cam  # noqa: E402


class NativeCamParserTests(unittest.TestCase):
    def test_gerber_region_normalizes_kicad_negative_y(self):
        source = """%TF.FileFunction,Copper,L1,Top*%
%FSLAX46Y46*%
%MOMM*%
%ADD10C,0.050000*%
D10*
G36*
X0Y0D02*
G01*
X1000000Y0D01*
X1000000Y-1000000D01*
X0Y-1000000D01*
X0Y0D01*
G37*
M02*
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "square-F_Cu.gtl"
            path.write_text(source)
            parsed = cam.parse_gerber(path)
        self.assertEqual(parsed.function, "Copper,L1,Top")
        self.assertEqual(len(parsed.regions), 1)
        polygon = parsed.regions[0][1]
        self.assertAlmostEqual(polygon.area, 1.0)
        self.assertEqual(tuple(round(value, 6) for value in polygon.bounds), (0.0, 0.0, 1.0, 1.0))

    def test_excellon_normalizes_negative_y_and_decodes_routed_slot(self):
        source = """M48
; #@! TF.FileFunction,NonPlated,1,2,NPTH
FMAT,2
METRIC
T1C3.200
%
G90
G05
T1
X6.5Y-23.6
T1
G00X6.62Y-125.64
M15
G01X13.7Y-125.64
M16
M30
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board-NPTH.drl"
            path.write_text(source)
            parsed = cam.parse_excellon(path)
        self.assertEqual(parsed.fileFunction, "NonPlated,1,2,NPTH")
        self.assertEqual(parsed.tools, {1: 3.2})
        self.assertEqual(parsed.hits, [{"x": 6.5, "y": 23.6, "diameter": 3.2}])
        self.assertEqual(parsed.routes[0]["points"], [(6.62, 125.64), (13.7, 125.64)])
        self.assertAlmostEqual(parsed.routes[0]["diameter"], 3.2)

    def test_contour_signature_ignores_start_point_and_winding(self):
        clockwise = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        reverse = [(1, 1), (1, 0), (0, 0), (0, 1), (1, 1)]
        self.assertEqual(cam.contour_signature(clockwise), cam.contour_signature(reverse))

    def test_appearance_sheet_keeps_slots_when_a_top_cam_render_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "top.png"
            Image.new("RGB", (303, 368), (220, 220, 220)).save(source)
            slots = [({"id": f"top-{index}"}, source if index == 0 else None)
                     for index in range(5)]
            output = Path(directory) / "overview.png"
            cam.compose_cam_overview(slots, output)
            with Image.open(output) as image:
                self.assertEqual(image.size, (5 * 303 + 6 * 14, 368 + 2 * 14))


if __name__ == "__main__":
    unittest.main()
