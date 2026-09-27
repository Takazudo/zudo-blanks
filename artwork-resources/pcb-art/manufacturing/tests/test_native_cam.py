"""Focused regressions for the independent Gerber and Excellon parsers."""

import json
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

    def test_selected_drc_disposition_is_read_from_stored_drc_summary(self):
        passing = {"drc": {"selectedAcceptance": "pass"}}
        blocked = {"drc": {"selectedAcceptance": "blocker"}}
        self.assertTrue(cam.selected_drc_is_clean(passing))
        self.assertFalse(cam.selected_drc_is_clean(blocked))

    def test_source_status_binds_both_native_board_and_project(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory) / "board.kicad_pcb"
            project = Path(directory) / "board.kicad_pro"
            native.write_text("native")
            project.write_text("project")
            record = {"nativePath": str(native), "nativeSha256": cam.sha256_file(native),
                      "projectPath": str(project), "projectSha256": cam.sha256_file(project)}
            self.assertTrue(cam.current_source_status(record))
            project.write_text("edited project")
            self.assertFalse(cam.current_source_status(record))

    def test_compact_evidence_reports_clean_selection_and_command_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            thumbnails_dir = root / "thumbs"
            thumbnails_dir.mkdir()
            thumbnails = []
            boards = []
            for index in range(52):
                selected = index < 43
                board_id = f"board-{index:02d}"
                layer_number = 1 if selected and index < 5 else 2
                board = {
                    "id": board_id,
                    "category": "selected" if selected else "alternatives",
                    "nativeBoard": f"panels/{board_id}.kicad_pcb",
                    "nativeSha256": "a" * 64,
                    "projectSha256": "b" * 64,
                    "ruleContract": {},
                    "ruleSeverities": {},
                    "layerNumber": layer_number,
                    "drc": {
                        "nativeLoadReportCreated": True,
                        "selectedAcceptance": "pass" if selected else "reference-only",
                        "violationCount": 0,
                        "violationsByType": {},
                        "unclassifiedIgnoredChecks": [],
                    },
                    "sourceUnchanged": True,
                }
                if selected:
                    board["cam"] = {
                        "status": "pass", "finish": "ENIG", "maskColor": "black",
                        "checks": {}, "files": [], "packageZip": {"sha256": "c" * 64},
                    }
                boards.append(board)
                if layer_number == 1:
                    thumb_path = thumbnails_dir / f"{board_id}.png"
                    Image.new("RGB", (303, 368), (220, 220, 220)).save(thumb_path)
                    thumbnails.append((board, thumb_path))

            run = {
                "startedUtc": "2026-09-27T00:00:00+00:00",
                "finishedUtc": "2026-09-27T00:01:00+00:00",
                "kicadVersion": "KiCad 10",
                "kicadCli": "kicad-cli",
                "cliHelpSha256": "d" * 64,
                "inputs": {},
                "commands": {},
            }
            output = root / "raw"
            evidence = root / "evidence"
            report_path, _, _ = cam._make_compact_evidence(run, boards, output, evidence, thumbnails)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "pass_local_native_and_cam_checks")
            self.assertEqual(report["nativeLoads"]["selectedCleanDrcCount"], 43)

            boards[0]["commandFailure"] = True
            report_path, _, _ = cam._make_compact_evidence(run, boards, output, evidence, thumbnails)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "blocked_by_local_findings")
            self.assertEqual(report["nativeLoads"]["commandFailureIds"], ["board-00"])
            self.assertEqual(report["nativeLoads"]["selectedCommandFailureIds"], ["board-00"])

    def test_edge_loop_validation_rejects_self_intersection(self):
        points = [(0, 0), (1, 1), (0, 1), (1, 0)]
        segments = [(points[index], points[(index + 1) % len(points)])
                    for index in range(len(points))]
        with self.assertRaisesRegex(ValueError, "valid positive-area contour"):
            cam.loop_polygons(segments)

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
