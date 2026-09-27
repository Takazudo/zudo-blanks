#!/usr/bin/env python3
"""Run KiCad 10 DRC and independently verify selected per-board CAM exports.

This is a local evidence generator, not a manufacturing release. Raw KiCad
reports and CAM files belong in an ignored/local output directory. The tracked
summary is intentionally compact and binds every result to exact inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
import zipfile

import PIL
import shapely
from PIL import Image, ImageChops, ImageDraw, ImageFont
from shapely import unary_union
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box


HERE = Path(__file__).resolve().parent
PCB_ART = HERE.parent
REPO = HERE.parents[2]
MANIFEST = PCB_ART / "pcb" / "manifest.json"
NATIVE_GENERATION = HERE / "native-generation.json"
POLICY = HERE / "policy.json"
GENERATOR = HERE / "generate_native.py"
CAM_LAYERS = ("F.Cu", "B.Cu", "F.Mask", "B.Mask", "Edge.Cuts")
FORBIDDEN_ART_LAYERS = (
    "B.Cu", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS",
    "F.Adhes", "B.Adhes",
)
GERBER_SUFFIXES = {
    "F.Cu": ("-f_cu.gtl", "-f_cu.gbr"),
    "B.Cu": ("-b_cu.gbl", "-b_cu.gbr"),
    "F.Mask": ("-f_mask.gts", "-f_mask.gbr"),
    "B.Mask": ("-b_mask.gbs", "-b_mask.gbr"),
    "Edge.Cuts": ("-edge_cuts.gm1", "-edge_cuts.gbr"),
}
EXPECTED_IGNORED_DRC_CHECKS = {
    "footprint_filters_mismatch": "The boards contain mechanical NPTH footprints and no schematic-linked components.",
    "footprint_type_mismatch": "The boards contain mechanical NPTH footprints and no electrical component types.",
    "lib_footprint_issues": "The custom NPTH footprint identifiers are descriptive board-only placeholders, not library parts.",
    "lib_footprint_mismatch": "The custom NPTH footprint identifiers are descriptive board-only placeholders, not library parts.",
    "missing_courtyard": "No component courtyards are used; the footprints only describe mechanical NPTH drills.",
    "npth_inside_courtyard": "No component courtyards are used; exact NPTH placement is checked against the fabrication contract.",
    "pth_inside_courtyard": "The boards contain no plated through holes or component courtyards.",
    "track_not_centered_on_via": "The boards contain no tracks or vias.",
    "tuning_profile_track_geometries": "The boards contain no tuned tracks.",
}
MASK_RGB = {
    "black": (37, 40, 43), "white": (235, 234, 226), "red": (174, 46, 52),
    "green": (42, 111, 74), "blue": (42, 75, 143), "purple": (102, 68, 137),
    "yellow": (220, 180, 57), "gold": (198, 157, 52),
}
GOLD_RGB = (218, 178, 70)
VOID_RGB = (243, 242, 235)
EDGE_RGB = (19, 21, 23)
DRILL_RGB = (227, 222, 201)
NUMERIC_DISTANCE_TOLERANCE_MM = 0.001
NUMERIC_AREA_TOLERANCE_MM2 = 0.00001


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_layer(value: str) -> str:
    return value.replace("_", ".").replace("-", ".").lower()


def load_inventory(boards_root: Path = REPO) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text())
    generation = json.loads(NATIVE_GENERATION.read_text())
    policy = json.loads(POLICY.read_text())
    selected = {b["nativeBoard"]: b for b in generation["boards"]}
    inventory: list[dict[str, Any]] = []
    if len(manifest["boards"]) != 52 or len(selected) != 43:
        raise ValueError("Expected the exact 52-board manifest and 43-board selected generation record")
    expected_selected = {b["nativeBoard"] for b in manifest["boards"] if b["category"] == "selected"}
    if set(selected) != expected_selected:
        raise ValueError("native-generation.json board membership differs from the selected manifest split")
    for board in manifest["boards"]:
        rel = board["nativeBoard"]
        path = (boards_root / rel).resolve()
        if not path.is_file():
            raise ValueError(f"Missing native board: {rel}")
        source_hash = sha256_file(path)
        gen = selected.get(rel)
        expected_hash = gen["sha256"] if gen else board["nativeBoardSha256"]
        if source_hash != expected_hash:
            raise ValueError(f"Native board hash changed since its source manifest: {rel}")
        project_rel = gen["project"] if gen else None
        project_path = (boards_root / project_rel).resolve() if project_rel else path.with_suffix(".kicad_pro")
        project_hash = sha256_file(project_path) if project_path.is_file() else None
        if gen and project_hash != gen["projectSha256"]:
            raise ValueError(f"Selected KiCad project hash differs from native-generation.json: {project_rel}")
        inventory.append({
            **board,
            "nativePath": str(path),
            "nativeSha256": source_hash,
            "expectedNativeSha256": expected_hash,
            "projectPath": str(project_path) if project_path.is_file() else None,
            "projectSha256": project_hash,
            "generation": gen,
        })
    selected_count = sum(b["category"] == "selected" for b in inventory)
    alternatives_count = sum(b["category"] == "alternatives" for b in inventory)
    if (selected_count, alternatives_count) != (43, 9):
        raise ValueError(f"Unexpected selection split: selected={selected_count}, alternatives={alternatives_count}")
    evidence = {
        "manifestSha256": sha256_file(MANIFEST),
        "nativeGenerationSha256": sha256_file(NATIVE_GENERATION),
        "policySha256": sha256_file(POLICY),
        "generatorSha256": sha256_file(GENERATOR),
        "verifierSha256": sha256_file(Path(__file__).resolve()),
        "requirementsSha256": sha256_file(PCB_ART / "preview-source" / "requirements.txt"),
        "pythonVersion": sys.version.split()[0],
        "shapelyVersion": shapely.__version__,
        "pillowVersion": PIL.__version__,
        "selectedCount": selected_count,
        "alternativeCount": alternatives_count,
        "policy": policy,
    }
    return inventory, evidence


def find_kicad_cli(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return shutil.which("kicad-cli") or (
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
        if Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli").is_file()
        else None
    )


def kicad_commands(cli: str, board: dict[str, Any], target: Path, export_cam: bool) -> list[tuple[str, list[str]]]:
    board_path = board["nativePath"]
    drc = [cli, "pcb", "drc", "--format", "json", "--units", "mm",
           "--severity-all", "--severity-exclusions", "--exit-code-violations",
           "--output", str(target / "drc.json"), board_path]
    commands = [("drc", drc)]
    if export_cam:
        cam_dir = target / "cam"
        commands += [
            ("gerbers", [cli, "pcb", "export", "gerbers", "--layers", ",".join(CAM_LAYERS),
                          "--precision", "6", "--output", str(cam_dir) + "/", board_path]),
            ("drill", [cli, "pcb", "export", "drill", "--format", "excellon",
                       "--drill-origin", "absolute", "--excellon-units", "mm",
                       "--excellon-zeros-format", "decimal", "--excellon-oval-format", "route",
                       "--excellon-separate-th", "--generate-map", "--map-format", "svg",
                       "--generate-report", "--report-path", str(cam_dir / "drill.rpt"),
                       "--output", str(cam_dir) + "/", board_path]),
        ]
    return commands


def run_command(argv: list[str], stdout_path: Path, stderr_path: Path) -> int:
    result = subprocess.run(argv, text=True, capture_output=True)
    stdout_path.write_text(result.stdout)
    stderr_path.write_text(result.stderr)
    return result.returncode


def parse_rule_contract(board: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    project_path = Path(board["projectPath"]) if board.get("projectPath") else None
    if not project_path or not project_path.is_file():
        if board["category"] == "selected":
            raise ValueError(f"Selected board has no recorded KiCad project: {board['id']}")
        return {"projectPresent": False, "projectSha256": None, "localRules": None,
                "ruleSeverities": None, "drcExclusions": []}
    project = json.loads(project_path.read_text())
    design = project["board"]["design_settings"]
    rules = design["rules"]
    severity = design.get("rule_severities", {})
    exclusions = design.get("drc_exclusions", [])
    required = {
        "min_clearance": policy["rulesMm"]["minimumSeparateCopperGap"],
        "min_copper_edge_clearance": policy["rulesMm"]["topCopperToRoutedEdgeOrDrill"],
        "min_hole_clearance": policy["rulesMm"]["topCopperToRoutedEdgeOrDrill"],
        "solder_mask_to_copper_clearance": 0.0,
    }
    if board["category"] == "selected":
        mismatches = {key: (rules.get(key), value) for key, value in required.items()
                      if not math.isclose(float(rules.get(key, float("nan"))), value, abs_tol=1e-9)}
        if mismatches:
            raise ValueError(f"{board['id']}: KiCad project rules differ from frozen local rules: {mismatches}")
        ignored_manufacturing = [key for key in ("copper_edge_clearance", "solder_mask_bridge", "shorting_items")
                                 if severity.get(key) == "ignore"]
        if ignored_manufacturing:
            raise ValueError(f"{board['id']}: manufacturing DRC checks remain ignored: {ignored_manufacturing}")
        if exclusions:
            raise ValueError(f"{board['id']}: project carries KiCad DRC exclusions: {len(exclusions)}")
    return {
        "projectPresent": True,
        "projectSha256": sha256_file(project_path),
        "localRules": {key: rules.get(key) for key in sorted(required)},
        "ruleSeverities": severity,
        "drcExclusions": exclusions,
    }


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
GR_LINE_RE = re.compile(
    rf'^\s*\(gr_line\s+\(start\s+({NUMBER})\s+({NUMBER})\)\s+'
    rf'\(end\s+({NUMBER})\s+({NUMBER})\).*?\(layer\s+"([^"]+)"\)', re.M)
GR_POLY_RE = re.compile(
    r'^\s*\(gr_poly\s+\(pts\s+(.*?)\)\s+\(stroke\b.*?\(layer\s+"([^"]+)"\)', re.M)
XY_RE = re.compile(rf'\(xy\s+({NUMBER})\s+({NUMBER})\)')
FOOTPRINT_BLOCK_RE = re.compile(r'(?m)^  \(footprint\b(?s:.*?)(?=^  \(|^\)\s*$)')
FOOTPRINT_AT_RE = re.compile(rf'\(at\s+({NUMBER})\s+({NUMBER})(?:\s+({NUMBER}))?\)')
NPTH_PAD_RE = re.compile(
    rf'\(pad\s+"[^"]*"\s+np_thru_hole\s+(circle|oval)\s+'
    rf'\(at\s+({NUMBER})\s+({NUMBER})(?:\s+({NUMBER}))?\)\s+'
    rf'\(size\s+({NUMBER})\s+({NUMBER})\)\s+'
    rf'\(drill\s+(?:oval\s+)?({NUMBER})(?:\s+({NUMBER}))?\)', re.S)


def parse_native_board(path: Path) -> dict[str, Any]:
    text = path.read_text()
    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    polygons: dict[str, list[Polygon]] = defaultdict(list)
    polygon_contours: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
    primitive_counts: Counter[str] = Counter()
    for match in GR_LINE_RE.finditer(text):
        x1, y1, x2, y2 = map(float, match.groups()[:4])
        layer = match.group(5)
        primitive_counts[layer] += 1
        if layer == "Edge.Cuts":
            edges.append(((x1, y1), (x2, y2)))
    for match in GR_POLY_RE.finditer(text):
        layer = match.group(2)
        points = [(float(x), float(y)) for x, y in XY_RE.findall(match.group(1))]
        if len(points) < 3:
            raise ValueError(f"{path.name}: malformed native {layer} polygon")
        poly = Polygon(points)
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f"{path.name}: invalid native {layer} polygon")
        primitive_counts[layer] += 1
        polygons[layer].append(poly)
        polygon_contours[layer].append(points)
    pads: list[dict[str, Any]] = []
    for block in FOOTPRINT_BLOCK_RE.finditer(text):
        body = block.group(0)
        footprint_at = FOOTPRINT_AT_RE.search(body)
        pad_match = NPTH_PAD_RE.search(body)
        if not pad_match:
            continue
        if not footprint_at:
            raise ValueError(f"{path.name}: NPTH footprint lacks absolute placement")
        fx, fy = float(footprint_at.group(1)), float(footprint_at.group(2))
        angle = float(footprint_at.group(3) or 0)
        shape, px, py, pad_angle, width, height, drill_width, drill_height = pad_match.groups()
        px, py = float(px), float(py)
        radians = math.radians(angle)
        x = fx + px * math.cos(radians) - py * math.sin(radians)
        y = fy + px * math.sin(radians) + py * math.cos(radians)
        pads.append({
            "shape": shape, "x": x, "y": y,
            "width": float(width), "height": float(height),
            "drillWidth": float(drill_width),
            "drillHeight": float(drill_height or drill_width),
        })
    for forbidden in FORBIDDEN_ART_LAYERS:
        if primitive_counts[forbidden]:
            raise ValueError(f"{path.name}: forbidden native artwork on {forbidden}")
    return {"edgeSegments": edges, "polygons": dict(polygons),
            "polygonContours": dict(polygon_contours), "primitiveCounts": dict(primitive_counts),
            "npthPads": pads, "text": text}


def expected_drills(native: dict[str, Any], board: dict[str, Any]) -> list[dict[str, Any]]:
    pads = native["npthPads"]
    if len(pads) != 4 + (4 if board["layerNumber"] == 1 else 0):
        raise ValueError(f"{board['id']}: native NPTH pad count is {len(pads)}")
    circles = [p for p in pads if p["shape"] == "circle"]
    slots = [p for p in pads if p["shape"] == "oval"]
    if len(circles) != 4 or len(slots) != (4 if board["layerNumber"] == 1 else 0):
        raise ValueError(f"{board['id']}: expected 4 round NPTH mounts and top-only NPTH slots")
    if any(abs(p["drillWidth"] - 3.2) > 1e-6 or abs(p["drillHeight"] - 3.2) > 1e-6 for p in circles):
        raise ValueError(f"{board['id']}: round mount drill is not Ø3.2 mm")
    if any(abs(p["drillWidth"] - 10.28) > 1e-6 or abs(p["drillHeight"] - 3.2) > 1e-6 for p in slots):
        raise ValueError(f"{board['id']}: top rail NPTH slot is not 10.28 × 3.2 mm")
    policy = json.loads(POLICY.read_text())
    centers = policy["mechanical"]["screwCentersMm"]
    if len(centers) != 4:
        raise ValueError("Frozen mechanical policy must list four screw centers")
    match_points([[(p["x"], p["y"]) for p in circles]], [centers], "native screw centers")
    slots_contract = policy["mechanical"].get("railSlotCentersMm", [])
    if board["layerNumber"] == 1:
        if len(slots_contract) != 4:
            raise ValueError("Frozen mechanical policy must list four top slot centers")
        match_points([[(p["x"], p["y"]) for p in slots]], [slots_contract], "native rail slot centers")
    return pads


def match_points(actual_groups: list[list[tuple[float, float]]],
                 expected_groups: list[list[tuple[float, float]]], label: str,
                 tolerance: float = NUMERIC_DISTANCE_TOLERANCE_MM) -> None:
    actual = sorted((round(x, 6), round(y, 6)) for group in actual_groups for x, y in group)
    expected = sorted((round(float(x), 6), round(float(y), 6)) for group in expected_groups for x, y in group)
    if len(actual) != len(expected) or any(math.dist(a, b) > tolerance for a, b in zip(actual, expected)):
        raise ValueError(f"{label} do not match: actual={actual}, expected={expected}")


def component_loops(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)
    for a, b in segments:
        if a == b:
            raise ValueError("Edge.Cuts contains a zero-length segment")
        adjacency[a].append(b)
        adjacency[b].append(a)
    if not segments:
        return []
    bad = [point for point, linked in adjacency.items() if len(linked) != 2]
    if bad:
        raise ValueError(f"Edge.Cuts linework is not a set of closed loops; {len(bad)} endpoint(s) have degree != 2")
    remaining = set(adjacency)
    loops: list[list[tuple[float, float]]] = []
    while remaining:
        start = min(remaining)
        line = [start]
        previous = None
        current = start
        while True:
            options = adjacency[current]
            nxt = options[0] if options[0] != previous else options[1]
            if nxt == start:
                break
            if nxt in line:
                raise ValueError("Edge.Cuts loop intersects or repeats a vertex")
            line.append(nxt)
            previous, current = current, nxt
        remaining.difference_update(line)
        loops.append(line)
    return loops


def loop_polygons(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[Polygon]:
    result = []
    for points in component_loops(segments):
        poly = Polygon(points)
        if not poly.is_valid or poly.area <= 0:
            raise ValueError("Edge.Cuts loop does not make a valid positive-area contour")
        result.append(poly)
    return result


def native_finish_and_mask(board: dict[str, Any], native_text: str) -> tuple[str, str]:
    finish_match = re.search(r'\(copper_finish\s+"([^"]+)"\)', native_text)
    mask_match = re.search(r'\(layer\s+"F\.Mask"\s+\(type\s+"Top Solder Mask"\)\s+\(color\s+"([^"]+)"\)\)', native_text)
    if not finish_match or not mask_match:
        raise ValueError(f"{board['id']}: native stackup lacks finish or top mask color metadata")
    finish = finish_match.group(1)
    mask_color = mask_match.group(1).lower()
    expected_finish = "ENIG" if board["finish"].startswith("enig-") else "Lead-free HASL"
    expected_color = board["maskColor"].lower()
    if finish.casefold() != expected_finish.casefold():
        raise ValueError(f"{board['id']}: finish metadata {finish!r}, expected {expected_finish!r}")
    if mask_color != expected_color:
        raise ValueError(f"{board['id']}: mask color metadata {mask_color!r}, expected {expected_color!r}")
    return finish, mask_color


@dataclass
class GerberCAM:
    path: Path
    function: str | None
    events: list[tuple[str, Any]]
    strokes: list[tuple[str, LineString, float]]
    flashes: list[tuple[str, Any]]
    regions: list[tuple[str, Polygon]]
    coordinateCount: int
    unsupported: list[str]

    def geometry(self):
        current = GeometryCollection()
        grouped: list[tuple[str, list[Any]]] = []
        for polarity, item in self.events:
            if grouped and grouped[-1][0] == polarity:
                grouped[-1][1].append(item)
            else:
                grouped.append((polarity, [item]))
        for polarity, items in grouped:
            merged = unary_union(items)
            current = current.union(merged) if polarity == "dark" else current.difference(merged)
        return current


GERBER_COORD_RE = re.compile(rf"(?P<axis>[XYIJ])(?P<value>{NUMBER})")
GERBER_APERTURE_RE = re.compile(r"ADD(\d+)([A-Z]),?([0-9.X]*)")


def _coordinate(value: str, decimals: int, units: str) -> float:
    mm = float(value) if "." in value else int(value) / (10 ** decimals)
    return mm if units == "mm" else mm * 25.4


def _aperture_geometry(aperture: tuple[str, list[float]] | None, center: tuple[float, float]):
    if aperture is None:
        raise ValueError("CAM file uses an aperture before defining it")
    shape, params = aperture
    x, y = center
    if shape == "C":
        return Point(x, y).buffer(params[0] / 2, quad_segs=32)
    if shape == "R":
        return box(x - params[0] / 2, y - params[1] / 2,
                   x + params[0] / 2, y + params[1] / 2)
    if shape == "O":
        width, height = params[:2]
        if width >= height:
            return LineString([(x - (width-height)/2, y), (x + (width-height)/2, y)]).buffer(height/2, quad_segs=32)
        return LineString([(x, y - (height-width)/2), (x, y + (height-width)/2)]).buffer(width/2, quad_segs=32)
    raise ValueError(f"Unsupported Gerber aperture shape: {shape}")


def _arc_points(start: tuple[float, float], end: tuple[float, float],
                i_offset: float, j_offset: float, clockwise: bool) -> list[tuple[float, float]]:
    cx, cy = start[0] + i_offset, start[1] + j_offset
    radius = math.dist(start, (cx, cy))
    if radius == 0 or abs(math.dist(end, (cx, cy)) - radius) > 0.002:
        raise ValueError("Gerber circular interpolation has inconsistent I/J radius")
    a0 = math.atan2(start[1] - cy, start[0] - cx)
    a1 = math.atan2(end[1] - cy, end[0] - cx)
    if clockwise:
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    sweep = a1 - a0
    n = max(8, math.ceil(abs(sweep) * 128 / (2 * math.pi)))
    return [(cx + radius * math.cos(a0 + sweep * k / n),
             cy + radius * math.sin(a0 + sweep * k / n)) for k in range(1, n)] + [end]


def parse_gerber(path: Path) -> GerberCAM:
    source = path.read_text(errors="replace").replace("\r", "").replace("\n", "")
    tokens = re.findall(r"%[^%]*%|[^*]*\*", source)
    apertures: dict[int, tuple[str, list[float]]] = {}
    function = None
    digits = 6
    units = "mm"
    current = (0.0, 0.0)
    selected_aperture: tuple[str, list[float]] | None = None
    polarity = "dark"
    operation = 2
    interpolation = "G01"
    region = False
    region_path: list[tuple[float, float]] = []
    region_paths: list[list[tuple[float, float]]] = []
    events: list[tuple[str, Any]] = []
    strokes: list[tuple[str, LineString, float]] = []
    flashes: list[tuple[str, Any]] = []
    regions: list[tuple[str, Polygon]] = []
    unsupported: list[str] = []
    coordinate_count = 0

    def close_region_path() -> None:
        nonlocal region_path
        points = region_path
        region_path = []
        if len(points) >= 3:
            if points[0] == points[-1]:
                points = points[:-1]
            if len(points) >= 3:
                region_paths.append(points)
        elif points:
            raise ValueError(f"{path.name}: Gerber region has fewer than three points")

    def finish_region() -> None:
        nonlocal region_paths
        close_region_path()
        for points in region_paths:
            polygon = Polygon(points)
            if not polygon.is_valid or polygon.area <= 0:
                raise ValueError(f"{path.name}: invalid Gerber region")
            regions.append((polarity, polygon))
            events.append((polarity, polygon))
        region_paths = []

    def add_stroke(start: tuple[float, float], end: tuple[float, float]) -> None:
        if start == end:
            return
        line = LineString([start, end])
        if selected_aperture is None:
            raise ValueError(f"{path.name}: Gerber stroke has no selected aperture")
        if selected_aperture[0] != "C":
            unsupported.append(f"stroke aperture {selected_aperture[0]}")
        width = selected_aperture[1][0]
        strokes.append((polarity, line, width))
        events.append((polarity, line.buffer(width/2, cap_style="round", join_style="round", quad_segs=16)))

    for raw_token in tokens:
        token = raw_token.strip()
        if not token:
            continue
        if token.startswith("%") and token.endswith("%"):
            commands = token[1:-1].split("*")
        else:
            commands = [token.rstrip("*")]
        for command in commands:
            command = command.strip()
            if not command or command.startswith("G04"):
                continue
            fs = re.search(r"FSLAX(\d)(\d)Y(\d)(\d)", command)
            if fs:
                digits = int(fs.group(2))
                continue
            if "MOMM" in command:
                units = "mm"
                continue
            if "MOIN" in command:
                units = "in"
                continue
            file_function = re.search(r"TF\.FileFunction,([^*]+)", command)
            if file_function:
                function = file_function.group(1).strip()
                continue
            aperture_match = GERBER_APERTURE_RE.search(command)
            if aperture_match:
                number = int(aperture_match.group(1))
                shape = aperture_match.group(2)
                raw_params = aperture_match.group(3)
                params = [float(x) for x in re.split(r"X", raw_params) if x]
                if units == "in":
                    params = [x * 25.4 for x in params]
                if shape in ("C", "R", "O") and params:
                    apertures[number] = (shape, params)
                else:
                    unsupported.append(f"aperture {number}:{shape}")
                continue
            if command.startswith("LPD"):
                polarity = "dark"
                continue
            if command.startswith("LPC"):
                polarity = "clear"
                continue
            if command == "G36":
                if region:
                    raise ValueError(f"{path.name}: nested Gerber region")
                region = True
                region_paths = []
                region_path = []
                continue
            if command == "G37":
                if not region:
                    raise ValueError(f"{path.name}: Gerber region closes without opening")
                finish_region()
                region = False
                continue
            if command in ("G01", "G1"):
                interpolation = "G01"
                continue
            if command in ("G02", "G2"):
                interpolation = "G02"
                continue
            if command in ("G03", "G3"):
                interpolation = "G03"
                continue
            if command.startswith("ADD") or command.startswith("AM"):
                continue
            if command.startswith("TF.") or command.startswith("TA.") or command.startswith("TO."):
                continue
            if command.startswith("M02") or command.startswith("M00"):
                break
            if command.startswith("G54D"):
                command = command[3:]
            if re.fullmatch(r"D\d+", command):
                dcode = int(command[1:])
                if dcode >= 10:
                    if dcode not in apertures:
                        raise ValueError(f"{path.name}: undefined aperture D{dcode}")
                    selected_aperture = apertures[dcode]
                elif dcode in (1, 2, 3):
                    operation = dcode
                continue
            coords = {m.group("axis"): m.group("value") for m in GERBER_COORD_RE.finditer(command)}
            if not coords:
                if command.startswith(("G", "D", "M")):
                    unsupported.append(command[:80])
                continue
            x = _coordinate(coords["X"], digits, units) if "X" in coords else current[0]
            # KiCad writes native Y-down board coordinates as negative CAM Y-up.
            y = -_coordinate(coords["Y"], digits, units) if "Y" in coords else current[1]
            target = (x, y)
            dmatch = re.search(r"D0?([123])\s*$", command)
            active_operation = int(dmatch.group(1)) if dmatch else operation
            if dmatch:
                operation = active_operation
            coordinate_count += 1
            if active_operation == 2:
                if region:
                    close_region_path()
                    region_path = [target]
                current = target
                continue
            if active_operation == 3:
                flash = _aperture_geometry(selected_aperture, target)
                flashes.append((polarity, flash))
                events.append((polarity, flash))
                current = target
                continue
            if interpolation != "G01":
                if interpolation not in ("G02", "G03"):
                    raise ValueError(f"{path.name}: unknown interpolation {interpolation}")
                i_offset = _coordinate(coords.get("I", "0"), digits, units)
                j_offset = -_coordinate(coords.get("J", "0"), digits, units)
                # Reflecting Y also reverses clockwise/counter-clockwise sense.
                arc = _arc_points(current, target, i_offset, j_offset, interpolation == "G03")
                if region:
                    region_path.extend(arc)
                else:
                    for a, b in zip([current] + arc[:-1], arc):
                        add_stroke(a, b)
            elif region:
                if not region_path:
                    region_path = [current]
                region_path.append(target)
            else:
                add_stroke(current, target)
            current = target
    if region:
        raise ValueError(f"{path.name}: Gerber file ends inside a region")
    if unsupported:
        raise ValueError(f"{path.name}: unsupported Gerber commands/apertures: {unsupported[:8]}")
    return GerberCAM(path, function, events, strokes, flashes, regions, coordinate_count, unsupported)


@dataclass
class ExcellonCAM:
    path: Path
    fileFunction: str | None
    tools: dict[int, float]
    hits: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    unsupported: list[str]

    @property
    def hitCount(self) -> int:
        return len(self.hits)

    def geometry(self):
        features = [Point(h["x"], h["y"]).buffer(h["diameter"]/2, quad_segs=32) for h in self.hits]
        features.extend(LineString(r["points"]).buffer(r["diameter"]/2, cap_style="round", quad_segs=32)
                        for r in self.routes)
        return unary_union(features) if features else GeometryCollection()


def parse_excellon(path: Path) -> ExcellonCAM:
    text = path.read_text(errors="replace").replace("\r", "")
    units = "mm"
    zero_mode = "decimal"
    coordinate_decimals = 6
    tools: dict[int, float] = {}
    hits: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    unsupported: list[str] = []
    file_function = None
    current_tool = None
    current = (0.0, 0.0)
    route_active = False
    route_points: list[tuple[float, float]] = []
    route_start: tuple[float, float] | None = None
    pattern_xy = re.compile(rf"([XY])({NUMBER})")

    def parse_axis(axis: str, value: str) -> float:
        result = float(value) if "." in value else int(value) / (10 ** coordinate_decimals)
        if units == "in":
            result *= 25.4
        return -result if axis == "Y" else result

    def move_from(command: str) -> tuple[float, float] | None:
        nonlocal current
        axes = {axis: value for axis, value in pattern_xy.findall(command)}
        if not axes:
            return None
        current = (parse_axis("X", axes["X"]) if "X" in axes else current[0],
                   parse_axis("Y", axes["Y"]) if "Y" in axes else current[1])
        return current

    for original in text.splitlines():
        line = original.strip()
        if not line:
            continue
        if line.startswith(";"):
            fmt = re.search(r"FORMAT\s*=\s*(\d+)\s*:\s*(\d+)", line, re.I)
            if fmt:
                coordinate_decimals = int(fmt.group(2))
            tf = re.search(r"TF\.FileFunction,([^*]+)", line, re.I)
            if tf:
                file_function = tf.group(1).strip()
            continue
        if line.upper().startswith("METRIC"):
            units = "mm"
            zero_mode = "leading" if "LZ" in line.upper() else "trailing" if "TZ" in line.upper() else "decimal"
            continue
        if line.upper().startswith("INCH"):
            units = "in"
            zero_mode = "leading" if "LZ" in line.upper() else "trailing" if "TZ" in line.upper() else "decimal"
            continue
        tool_match = re.match(r"T(\d+)C(" + NUMBER + r")", line, re.I)
        if tool_match:
            tools[int(tool_match.group(1))] = float(tool_match.group(2)) * (1 if units == "mm" else 25.4)
            continue
        selected = re.fullmatch(r"T(\d+)", line, re.I)
        if selected:
            current_tool = int(selected.group(1))
            if current_tool not in tools:
                raise ValueError(f"{path.name}: selected undefined drill tool T{current_tool}")
            continue
        upper = line.upper()
        if "M15" in upper:
            route_active = True
            route_points = [current]
            route_start = current
            continue
        if "M16" in upper:
            if route_active and route_start is not None and len(route_points) >= 2:
                if current_tool is None:
                    raise ValueError(f"{path.name}: route has no selected drill tool")
                routes.append({"points": route_points, "diameter": tools[current_tool]})
            route_active = False
            route_points = []
            route_start = None
            continue
        if "G85" in upper:
            pairs = pattern_xy.findall(upper)
            if len(pairs) >= 4:
                coords = [parse_axis(axis, value) for axis, value in pairs[-4:]]
                start, end = (coords[0], coords[1]), (coords[2], coords[3])
            else:
                start, end = current, move_from(upper)
            if current_tool is None or end is None:
                raise ValueError(f"{path.name}: malformed G85 slot command")
            routes.append({"points": [start, end], "diameter": tools[current_tool]})
            current = end
            continue
        if upper.startswith(("M48", "G90", "G05", "FMAT", "%")):
            continue
        if upper.startswith("M30") or upper.startswith("M00") or upper.startswith("M02"):
            break
        if "G91" in upper:
            raise ValueError(f"{path.name}: incremental Excellon moves are not expected")
        if any(code in upper for code in ("G00", "G01", "G02", "G03")):
            point = move_from(upper)
            if point is not None and route_active:
                route_points.append(point)
            continue
        if "X" in upper or "Y" in upper:
            point = move_from(upper)
            if point is None:
                continue
            if route_active:
                route_points.append(point)
            else:
                if current_tool is None:
                    raise ValueError(f"{path.name}: drill hit has no selected tool")
                hits.append({"x": point[0], "y": point[1], "diameter": tools[current_tool]})
            continue
        if upper not in ("M71", "M72", "%"):
            unsupported.append(line[:80])
    if route_active and route_start is not None and len(route_points) >= 2:
        if current_tool is None:
            raise ValueError(f"{path.name}: route has no selected drill tool")
        routes.append({"points": route_points, "diameter": tools[current_tool]})
    if unsupported:
        raise ValueError(f"{path.name}: unsupported Excellon commands: {unsupported[:8]}")
    return ExcellonCAM(path, file_function, tools, hits, routes, unsupported)


def _gerber_layer_from_file(path: Path, gerber: GerberCAM) -> str | None:
    return _gerber_layer_from_function(path, gerber.function)


def _gerber_layer_from_function(path: Path, file_function: str | None) -> str | None:
    function = (file_function or "").lower()
    if "copper,l1,top" in function:
        return "F.Cu"
    if "copper,l2,bot" in function:
        return "B.Cu"
    if "soldermask,top" in function:
        return "F.Mask"
    if "soldermask,bot" in function:
        return "B.Mask"
    if "profile" in function:
        return "Edge.Cuts"
    name = path.name.lower()
    for layer, suffixes in GERBER_SUFFIXES.items():
        if any(name.endswith(suffix) for suffix in suffixes):
            return layer
    return None


def _find_cam_files(cam_dir: Path, drill_dir: Path | None = None) -> tuple[dict[str, Path], list[Path], list[Path]]:
    gerbers = {}
    for path in sorted(cam_dir.iterdir()):
        if path.suffix.lower() not in (".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gm1", ".gko"):
            continue
        with path.open("r", errors="replace") as handle:
            header = handle.read(4096)
        function_match = re.search(r"TF\.FileFunction,([^*]+)\*", header)
        layer = _gerber_layer_from_function(path, function_match.group(1).strip() if function_match else None)
        if layer is None:
            raise ValueError(f"Unclassified Gerber file: {path.name} / {function_match.group(1) if function_match else None}")
        if layer in gerbers:
            raise ValueError(f"Multiple Gerbers were exported for {layer}")
        gerbers[layer] = path
    missing = set(CAM_LAYERS) - set(gerbers)
    if missing:
        raise ValueError(f"Missing expected Gerber layers: {sorted(missing)}")
    drills = sorted((drill_dir or cam_dir).glob("*.drl"))
    npth = [p for p in drills if "npth" in p.name.lower()]
    pth = [p for p in drills if "npth" not in p.name.lower()]
    if len(npth) != 1:
        raise ValueError(f"Expected one separate NPTH Excellon file, found {[p.name for p in npth]}")
    return gerbers, npth, pth


def compare_geometries(expected, actual, label: str,
                       distance_tolerance: float = NUMERIC_DISTANCE_TOLERANCE_MM,
                       area_tolerance: float = NUMERIC_AREA_TOLERANCE_MM2) -> dict[str, Any]:
    if expected.is_empty and actual.is_empty:
        return {"status": "pass", "expectedAreaMm2": 0.0, "actualAreaMm2": 0.0,
                "symmetricDifferenceMm2": 0.0, "boundaryHausdorffMm": 0.0}
    delta = expected.symmetric_difference(actual).area
    if expected.is_empty or actual.is_empty:
        hausdorff = None
    else:
        hausdorff = expected.boundary.hausdorff_distance(actual.boundary)
    passed = delta <= area_tolerance and (hausdorff is None or hausdorff <= distance_tolerance)
    if not passed:
        raise ValueError(f"{label}: output geometry differs: area={delta:.9g} mm², boundary={hausdorff} mm")
    return {"status": "pass", "expectedAreaMm2": round(expected.area, 8),
            "actualAreaMm2": round(actual.area, 8),
            "symmetricDifferenceMm2": round(delta, 9),
            "boundaryHausdorffMm": round(hausdorff or 0, 9)}


def contour_signature(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    normalized = [(round(float(x), 6), round(float(y), 6)) for x, y in points]
    compact = [point for i, point in enumerate(normalized)
               if i == 0 or point != normalized[i-1]]
    if len(compact) > 1 and compact[0] == compact[-1]:
        compact.pop()
    if len(compact) < 3:
        raise ValueError("CAM polygon contour has fewer than three distinct coordinates")
    def rotated_min(points_: list[tuple[float, float]]):
        minimum = min(points_)
        candidates = [i for i, point in enumerate(points_) if point == minimum]
        return min(tuple(points_[i:] + points_[:i]) for i in candidates)
    forward = rotated_min(compact)
    reverse = rotated_min(list(reversed(compact)))
    return min(forward, reverse)


def compare_region_contours(native: dict[str, Any], parsed: GerberCAM,
                            layer: str, board_id: str) -> dict[str, Any]:
    expected = Counter(contour_signature(points) for points in native["polygonContours"].get(layer, []))
    if any(polarity != "dark" for polarity, _ in parsed.regions):
        raise ValueError(f"{board_id} {layer}: CAM layer contains clear-polarity art regions")
    actual = Counter(contour_signature(list(poly.exterior.coords)) for _, poly in parsed.regions)
    missing_counts = expected - actual
    extra_counts = actual - expected
    missing = list(missing_counts.elements())
    extra = list(extra_counts.elements())
    native_by_signature: dict[tuple[tuple[float, float], ...], list[Polygon]] = defaultdict(list)
    for points, poly in zip(native["polygonContours"].get(layer, []), native["polygons"].get(layer, [])):
        native_by_signature[contour_signature(points)].append(poly)
    missing_polys = []
    for signature in missing:
        candidates = native_by_signature[signature]
        if candidates:
            missing_polys.append(candidates.pop())
    missing_area = sum(poly.area for poly in missing_polys)
    missing_extent = max((math.hypot(poly.bounds[2]-poly.bounds[0], poly.bounds[3]-poly.bounds[1])
                          for poly in missing_polys), default=0.0)
    extra_area = 0.0
    if extra:
        extra_sigs = Counter(extra)
        for polarity, poly in parsed.regions:
            signature = contour_signature(list(poly.exterior.coords))
            if polarity == "dark" and extra_sigs[signature]:
                extra_area += poly.area
                extra_sigs[signature] -= 1
    if (extra or missing_area > NUMERIC_AREA_TOLERANCE_MM2 or
            missing_extent > NUMERIC_DISTANCE_TOLERANCE_MM):
        raise ValueError(f"{board_id} {layer}: CAM region contours differ from native geometry "
                         f"(missing={len(missing)}, extra={len(extra)}, omittedArea={missing_area:.9g} mm², "
                         f"omittedExtent={missing_extent:.9g} mm)")
    return {
        "status": "pass" if not missing else "pass_with_subtolerance_native_sliver_omission",
        "nativePolygonCount": sum(expected.values()),
        "camRegionCount": sum(actual.values()),
        "matchedContourCount": sum((expected & actual).values()),
        "omittedNativeContourCount": len(missing),
        "omittedNativeContourAreaMm2": float(f"{missing_area:.12g}"),
        "maximumOmittedContourExtentMm": round(missing_extent, 9),
        "extraCamContourCount": len(extra),
        "extraCamContourAreaMm2": float(f"{extra_area:.12g}"),
        "comparison": "exact six-decimal canonical contour identity; area allowance is the frozen 0.00001 mm² serialization tolerance",
    }


def check_mask_copper_support(mask_polygons: list[Polygon], copper_polygons: list[Polygon],
                              label: str) -> dict[str, Any]:
    from shapely import STRtree
    if not mask_polygons:
        return {"status": "pass", "maskRegionCount": 0,
                "requiredCopperMarginMm": 0.05, "worstUncoveredAreaMm2": 0.0}
    if not copper_polygons:
        raise ValueError(f"{label}: solder-mask artwork exists without front copper")
    tree = STRtree(copper_polygons)
    worst_uncovered = 0.0
    minimum_boundary_distance = float("inf")
    failing = 0
    for mask_poly in mask_polygons:
        nearby_ids = tree.query(mask_poly.buffer(0.05, quad_segs=16))
        nearby = [copper_polygons[int(i)] for i in nearby_ids]
        if not nearby:
            uncovered_area = mask_poly.area
            boundary_distance = 0.0
        else:
            local_copper = unary_union(nearby)
            uncovered_area = mask_poly.difference(local_copper).area
            boundary_distance = mask_poly.distance(local_copper.boundary)
        worst_uncovered = max(worst_uncovered, uncovered_area)
        minimum_boundary_distance = min(minimum_boundary_distance, boundary_distance)
        if (uncovered_area > NUMERIC_AREA_TOLERANCE_MM2 or
                boundary_distance < 0.05 - NUMERIC_DISTANCE_TOLERANCE_MM):
            failing += 1
    if failing:
        raise ValueError(f"{label}: {failing} mask region(s) lack 0.05 mm copper support; "
                         f"max uncovered area {worst_uncovered:.9g} mm², "
                         f"minimum boundary distance {minimum_boundary_distance:.9g} mm")
    return {"status": "pass", "maskRegionCount": len(mask_polygons),
            "requiredCopperMarginMm": 0.05,
            "allowedNumericDistanceToleranceMm": NUMERIC_DISTANCE_TOLERANCE_MM,
            "worstUncoveredAreaMm2": round(worst_uncovered, 10),
            "minimumCopperBoundaryDistanceMm": round(minimum_boundary_distance, 9)}


def compare_drills(board: dict[str, Any], native: dict[str, Any],
                   npth_file: Path, pth_files: list[Path]) -> tuple[dict[str, Any], ExcellonCAM]:
    expected = expected_drills(native, board)
    parsed = parse_excellon(npth_file)
    if parsed.fileFunction:
        if "nonplated" not in parsed.fileFunction.lower() and "npth" not in parsed.fileFunction.lower():
            raise ValueError(f"{board['id']}: separate drill file metadata does not identify NPTH")
    elif "npth" not in npth_file.name.lower():
        raise ValueError(f"{board['id']}: separate drill file has no NPTH identity")
    actual_circles = sorted((round(h["x"], 6), round(h["y"], 6), round(h["diameter"], 6)) for h in parsed.hits)
    expected_circles = sorted((round(p["x"], 6), round(p["y"], 6), round(p["drillWidth"], 6))
                              for p in expected if p["shape"] == "circle")
    if actual_circles != expected_circles:
        raise ValueError(f"{board['id']}: NPTH round drill centers/sizes differ: {actual_circles} != {expected_circles}")
    actual_routes = []
    for route in parsed.routes:
        points = route["points"]
        if len(points) < 2:
            raise ValueError(f"{board['id']}: Excellon slot route lacks endpoints")
        actual_routes.append((points[0], points[-1], route["diameter"]))
    expected_routes = []
    for pad in expected:
        if pad["shape"] != "oval":
            continue
        radius_line = (pad["drillWidth"] - pad["drillHeight"]) / 2
        if radius_line < 0:
            endpoints = [(pad["x"], pad["y"] - abs(radius_line)), (pad["x"], pad["y"] + abs(radius_line))]
        else:
            endpoints = [(pad["x"] - radius_line, pad["y"]), (pad["x"] + radius_line, pad["y"])]
        expected_routes.append((endpoints[0], endpoints[1], min(pad["drillWidth"], pad["drillHeight"])))
    if len(actual_routes) != len(expected_routes):
        raise ValueError(f"{board['id']}: expected {len(expected_routes)} routed NPTH slots, found {len(actual_routes)}")
    unused = actual_routes[:]
    for expected_start, expected_end, expected_dia in expected_routes:
        match_index = None
        for i, (actual_start, actual_end, actual_dia) in enumerate(unused):
            direct = max(math.dist(expected_start, actual_start), math.dist(expected_end, actual_end))
            reverse = max(math.dist(expected_start, actual_end), math.dist(expected_end, actual_start))
            if min(direct, reverse) <= NUMERIC_DISTANCE_TOLERANCE_MM and abs(actual_dia-expected_dia) <= NUMERIC_DISTANCE_TOLERANCE_MM:
                match_index = i
                break
        if match_index is None:
            raise ValueError(f"{board['id']}: exported routed slot does not match native NPTH geometry")
        unused.pop(match_index)
    pth_nonempty = []
    for pth_path in pth_files:
        report = parse_excellon(pth_path)
        if report.hits or report.routes:
            pth_nonempty.append({"file": pth_path.name, "hits": len(report.hits), "routes": len(report.routes)})
    if pth_nonempty:
        raise ValueError(f"{board['id']}: a nominally unpopulated PTH file contains tools: {pth_nonempty}")
    return ({"status": "pass", "npthFile": npth_file.name,
             "roundHoleCount": len(actual_circles), "roundHoleDiameterMm": 3.2,
             "slotCount": len(actual_routes), "slotToolDiameterMm": 3.2,
             "pthFileCount": len(pth_files), "pthFilesEmpty": True,
             "toolDiametersMm": sorted(set(round(x, 6) for x in parsed.tools.values()))}, parsed)


def expected_geometry(native: dict[str, Any], layer: str):
    pieces = native["polygons"].get(layer, [])
    return unary_union(pieces) if pieces else GeometryCollection()


def expected_npth_mask_geometry(native: dict[str, Any]):
    features = []
    for pad in native["npthPads"]:
        if pad["shape"] == "circle":
            features.append(Point(pad["x"], pad["y"]).buffer(pad["width"]/2, quad_segs=32))
        else:
            width, height = pad["width"], pad["height"]
            if width >= height:
                centerline = LineString([(pad["x"]-(width-height)/2, pad["y"]),
                                         (pad["x"]+(width-height)/2, pad["y"])])
                features.append(centerline.buffer(height/2, quad_segs=32))
            else:
                centerline = LineString([(pad["x"], pad["y"]-(height-width)/2),
                                         (pad["x"], pad["y"]+(height-width)/2)])
                features.append(centerline.buffer(width/2, quad_segs=32))
    return unary_union(features) if features else GeometryCollection()


def gerber_art_geometry(parsed: GerberCAM):
    positives = [poly for polarity, poly in parsed.regions if polarity == "dark"]
    if any(polarity == "clear" for polarity, _ in parsed.regions) or parsed.strokes:
        raise ValueError(f"{parsed.path.name}: unexpected clear regions or non-outline strokes")
    return positives


def gerber_stroke_geometry(parsed: GerberCAM):
    lines = [line for polarity, line, _ in parsed.strokes if polarity == "dark"]
    return unary_union(lines) if lines else GeometryCollection()


def verify_cam_board(board: dict[str, Any], result_dir: Path,
                     cam_dir_override: Path | None = None,
                     drill_dir_override: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    native_path = Path(board["nativePath"])
    native = parse_native_board(native_path)
    pads = expected_drills(native, board)
    finish, mask_color = native_finish_and_mask(board, native["text"])
    cam_dir = cam_dir_override or result_dir / "cam"
    gerber_paths, npth_paths, pth_paths = _find_cam_files(cam_dir, drill_dir_override)
    parsed = {layer: parse_gerber(path) for layer, path in gerber_paths.items()}
    checks: dict[str, Any] = {}
    expected_edges = native["edgeSegments"]
    expected_loops = component_loops(expected_edges)
    actual_edge = parsed["Edge.Cuts"]
    if actual_edge.regions or actual_edge.flashes:
        raise ValueError(f"{board['id']}: Edge.Cuts contains fills/flashes that can duplicate drill contours")
    if not actual_edge.strokes or not expected_edges:
        raise ValueError(f"{board['id']}: Edge.Cuts output is empty")
    actual_edge_segments = [(tuple(line.coords[0]), tuple(line.coords[-1]))
                            for _, line, _ in actual_edge.strokes]
    actual_loops = component_loops(actual_edge_segments)
    actual_loop_polygons = loop_polygons(actual_edge_segments)
    expected_loop_count = board.get("generation", {}).get("edgeLoopCount")
    if len(actual_loops) != len(expected_loops) or (expected_loop_count and len(actual_loops) != expected_loop_count):
        raise ValueError(f"{board['id']}: CAM contour loop count differs: {len(actual_loops)} != {expected_loop_count or len(expected_loops)}")
    policy = json.loads(POLICY.read_text())
    mechanical = policy["mechanical"]
    contract_bounds = tuple(mechanical["topBoundsMm"] if board["layerNumber"] == 1
                            else mechanical["lowerBoundsMm"])
    if any(abs(a-b) > NUMERIC_DISTANCE_TOLERANCE_MM
           for a, b in zip(board["boardBoundsMm"], contract_bounds)):
        raise ValueError(f"{board['id']}: manifest bounds differ from the frozen panel bounds")
    outer_loop = max(actual_loop_polygons, key=lambda polygon: polygon.area)
    outer_check = compare_geometries(box(*contract_bounds), outer_loop,
                                     f"{board['id']} continuous outer routed perimeter")
    def segment_key(a, b):
        a = (round(a[0], 6), round(a[1], 6))
        b = (round(b[0], 6), round(b[1], 6))
        return tuple(sorted((a, b)))
    native_segments = Counter(segment_key(a, b) for a, b in expected_edges)
    cam_segments = Counter(segment_key(a, b) for a, b in actual_edge_segments)
    if native_segments != cam_segments:
        raise ValueError(f"{board['id']}: CAM Edge.Cuts segment set differs from native "
                         f"(missing={sum((native_segments-cam_segments).values())}, "
                         f"extra={sum((cam_segments-native_segments).values())})")
    if any(abs(width - 0.05) > NUMERIC_DISTANCE_TOLERANCE_MM for _, _, width in actual_edge.strokes):
        raise ValueError(f"{board['id']}: Edge.Cuts Gerber aperture is not 0.05 mm")
    edge_length_delta = abs(sum(line.length for _, line, _ in actual_edge.strokes) -
                            sum(math.dist(a, b) for a, b in expected_edges))
    cam_points = [point for a, b in actual_edge_segments for point in (a, b)]
    cam_bounds = (min(p[0] for p in cam_points), min(p[1] for p in cam_points),
                  max(p[0] for p in cam_points), max(p[1] for p in cam_points))
    if edge_length_delta > 1e-6:
        raise ValueError(f"{board['id']}: CAM Edge.Cuts length delta is {edge_length_delta} mm")
    expected_bounds = tuple(board["boardBoundsMm"])
    if any(abs(a-b) > NUMERIC_DISTANCE_TOLERANCE_MM for a, b in zip(cam_bounds, expected_bounds)):
        raise ValueError(f"{board['id']}: CAM Edge.Cuts bounds differ from manifest: {cam_bounds} != {expected_bounds}")
    checks["edgeCuts"] = {
        "status": "pass", "loopCount": len(actual_loops),
        "nativeSegmentCount": len(expected_edges), "camStrokeCount": len(actual_edge.strokes),
        "segmentIdentity": "exact six-decimal undirected segment identity",
        "centerlineLengthDeltaMm": round(edge_length_delta, 9),
        "boundsMm": [round(x, 6) for x in cam_bounds],
        "outerPerimeter": outer_check,
        "standaloneProfileWithoutBreakawayGeometry": True,
        "noFillsOrFlashes": True,
    }
    layer_results: dict[str, Any] = {}
    actual_geometries = {}
    npth_mask = expected_npth_mask_geometry(native)
    for layer in ("F.Cu", "B.Cu", "F.Mask", "B.Mask"):
        parsed_layer = parsed[layer]
        actual_art_polygons = gerber_art_geometry(parsed_layer)
        layer_results[layer] = compare_region_contours(native, parsed_layer, layer, board["id"])
        actual_geometries[layer] = actual_art_polygons
        layer_results[layer]["camRegionCount"] = len(parsed_layer.regions)
        layer_results[layer]["camStrokeCount"] = len(parsed_layer.strokes)
        layer_results[layer]["camFlashCount"] = len(parsed_layer.flashes)
        if layer in ("F.Cu", "B.Cu") and parsed_layer.flashes:
            raise ValueError(f"{board['id']}: {layer} contains unexpected CAM flashes")
        if layer in ("F.Mask", "B.Mask"):
            if len(parsed_layer.flashes) != len(native["npthPads"]):
                raise ValueError(f"{board['id']}: {layer} does not contain one mechanical mask aperture per NPTH pad")
            flash_geometry = unary_union([g for polarity, g in parsed_layer.flashes if polarity == "dark"])
            compare_geometries(npth_mask, flash_geometry, f"{board['id']} {layer} NPTH mask apertures")
            if len(parsed_layer.regions) != len(native["polygons"].get(layer, [])) or parsed_layer.strokes:
                raise ValueError(f"{board['id']}: {layer} includes unexpected non-polygon artwork or mask strokes")
    if actual_geometries["B.Cu"]:
        raise ValueError(f"{board['id']}: rear copper CAM must be empty")
    if expected_geometry(native, "B.Mask").area > NUMERIC_AREA_TOLERANCE_MM2:
        raise ValueError(f"{board['id']}: native board contains forbidden B.Mask artwork")
    copper_polygons = [poly for polarity, poly in parsed["F.Cu"].regions if polarity == "dark"]
    mask_polygons = [poly for polarity, poly in parsed["F.Mask"].regions if polarity == "dark"]
    support = check_mask_copper_support(mask_polygons, copper_polygons, f"{board['id']} F.Mask CAM")
    checks["frontCopperAndMask"] = {
        "status": "pass", "layers": layer_results,
        "maskOpeningBackedByCopperMarginMm": 0.05,
        "npthMaskAperturesOnBothSides": len(native["npthPads"]),
        "rearMaskContainsOnlyNpthApertures": True,
        "copperSupport": support,
        "copperFinish": finish, "maskColor": mask_color,
    }
    drill_check, drill_data = compare_drills(board, native, npth_paths[0], pth_paths)
    checks["drills"] = drill_check
    for required in ("F.Cu", "B.Cu", "F.Mask", "B.Mask", "Edge.Cuts"):
        if _gerber_layer_from_file(gerber_paths[required], parsed[required]) != required:
            raise ValueError(f"{board['id']}: Gerber output has wrong layer identity for {required}")
    return checks, {
        "native": native, "parsedGerbers": parsed, "parsedDrills": drill_data,
        "finish": finish, "maskColor": mask_color, "pads": pads,
        "gerberPaths": gerber_paths, "npthPath": npth_paths[0], "pthPaths": pth_paths,
    }


def _pixel(point: tuple[float, float], bounds: tuple[float, float, float, float],
           scale: float, origin: tuple[int, int]) -> tuple[int, int]:
    return (origin[0] + round((point[0]-bounds[0])*scale),
            origin[1] + round((point[1]-bounds[1])*scale))


def render_cam_thumbnail(board: dict[str, Any], details: dict[str, Any], output: Path) -> None:
    scale = 2.4
    pad = 15
    header = 30
    bounds = tuple(board["boardBoundsMm"])
    width = round((bounds[2]-bounds[0])*scale) + 2*pad
    height = round((bounds[3]-bounds[1])*scale) + 2*pad + header
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((pad, 8), board["id"], fill=(25, 28, 30), font=font)
    draw.text((pad, 18), f"{details['finish']} | {details['maskColor']} mask | parsed CAM",
              fill=(72, 76, 80), font=font)
    origin = (pad, header + pad)
    edge = details["parsedGerbers"]["Edge.Cuts"]
    segments = [(tuple(line.coords[0]), tuple(line.coords[-1])) for _, line, _ in edge.strokes]
    loops = component_loops(segments)
    loop_polygons = [(abs(Polygon(points).area), points) for points in loops]
    if not loop_polygons:
        raise ValueError(f"{board['id']}: no edge loops for representative rendering")
    outer = max(loop_polygons, key=lambda row: row[0])[1]
    outer_px = [_pixel(p, bounds, scale, origin) for p in outer]
    mask_color = MASK_RGB.get(details["maskColor"].lower())
    if mask_color is None:
        raise ValueError(f"{board['id']}: no raster color mapping for mask {details['maskColor']}")
    draw.polygon(outer_px, fill=mask_color)
    for _, loop in loop_polygons:
        if loop is outer:
            continue
        draw.polygon([_pixel(p, bounds, scale, origin) for p in loop], fill=VOID_RGB)

    copper_mask = Image.new("L", (width, height), 0)
    mask_art = Image.new("L", (width, height), 0)
    for polarity, polygon in details["parsedGerbers"]["F.Cu"].regions:
        target = 255 if polarity == "dark" else 0
        ImageDraw.Draw(copper_mask).polygon(
            [_pixel((x, y), bounds, scale, origin) for x, y in polygon.exterior.coords], fill=target)
    for polarity, polygon in details["parsedGerbers"]["F.Mask"].regions:
        target = 255 if polarity == "dark" else 0
        ImageDraw.Draw(mask_art).polygon(
            [_pixel((x, y), bounds, scale, origin) for x, y in polygon.exterior.coords], fill=target)
    gold_mask = ImageChops.darker(copper_mask, mask_art)
    body_clip = Image.new("L", (width, height), 0)
    ImageDraw.Draw(body_clip).polygon(outer_px, fill=255)
    for _, loop in loop_polygons:
        if loop is not outer:
            ImageDraw.Draw(body_clip).polygon([_pixel(p, bounds, scale, origin) for p in loop], fill=0)
    gold_mask = ImageChops.darker(gold_mask, body_clip)
    image.paste(GOLD_RGB, mask=gold_mask)

    drills = details["parsedDrills"]
    d = ImageDraw.Draw(image)
    for hit in drills.hits:
        x, y = _pixel((hit["x"], hit["y"]), bounds, scale, origin)
        radius = hit["diameter"] * scale / 2
        d.ellipse((round(x-radius), round(y-radius), round(x+radius), round(y+radius)),
                  fill=VOID_RGB, outline=EDGE_RGB, width=1)
    for route in drills.routes:
        points = [_pixel(p, bounds, scale, origin) for p in route["points"]]
        line_width = max(1, round(route["diameter"] * scale))
        d.line(points, fill=VOID_RGB, width=line_width)
        radius = line_width/2
        for x, y in (points[0], points[-1]):
            d.ellipse((round(x-radius), round(y-radius), round(x+radius), round(y+radius)),
                      fill=VOID_RGB)
    for _, loop in loop_polygons:
        points = [_pixel(p, bounds, scale, origin) for p in loop]
        d.line(points+[points[0]], fill=EDGE_RGB, width=1, joint="curve")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def compose_cam_overview(thumbnails: list[tuple[dict[str, Any], Path | None]], output: Path) -> None:
    if len(thumbnails) != 5:
        raise ValueError(f"Expected five top-board CAM slots, found {len(thumbnails)}")
    images = [Image.open(path).convert("RGB") for _, path in thumbnails if path is not None]
    cell_width = max((image.width for image in images), default=303)
    cell_height = max((image.height for image in images), default=368)
    gap = 14
    sheet = Image.new("RGB", (5*cell_width+6*gap, cell_height+2*gap), (244, 245, 246))
    for index, (board, path) in enumerate(thumbnails):
        x = gap + index*(cell_width+gap)
        if path is not None:
            image = Image.open(path).convert("RGB")
            sheet.paste(image, (x, gap))
        else:
            draw = ImageDraw.Draw(sheet)
            draw.rectangle((x, gap, x + cell_width - 1, gap + cell_height - 1),
                           fill=(250, 250, 250), outline=(150, 65, 65), width=2)
            draw.text((x + 12, gap + 14), board["id"], fill=(25, 28, 30), font=ImageFont.load_default())
            draw.text((x + 12, gap + 34), "CAM appearance unavailable", fill=(150, 45, 45),
                      font=ImageFont.load_default())
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, sheet.height-13),
              "Parsed CAM appearance; blank tiles mark boards without a verified top export. Factory finish pending.",
              fill=(58, 61, 64), font=ImageFont.load_default())
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def cam_file_records(cam_dir: Path, gerbers: dict[str, Path], npth_path: Path) -> list[dict[str, Any]]:
    records = []
    by_path = {p.resolve(): layer for layer, p in gerbers.items()}
    for path in sorted(p for p in cam_dir.iterdir() if p.is_file()):
        layer = by_path.get(path.resolve())
        if path == npth_path:
            layer = "NPTH drill"
        elif path.suffix.lower() == ".drl" and layer is None:
            layer = "PTH drill (empty)"
        elif path.suffix.lower() == ".gbrjob":
            layer = "Gerber X2 job metadata"
        elif path.suffix.lower() == ".svg":
            layer = "drill map"
        elif path.suffix.lower() == ".rpt":
            layer = "drill report"
        records.append({"name": path.name, "layer": layer,
                        "sizeBytes": path.stat().st_size, "sha256": sha256_file(path)})
    return records


def make_board_zip(board: dict[str, Any], output_root: Path, board_output: Path,
                   details: dict[str, Any], cam_files: list[dict[str, Any]]) -> dict[str, Any]:
    package_root = output_root / "packages"
    package_root.mkdir(parents=True, exist_ok=True)
    zip_path = package_root / f"{board['id']}.zip"
    package_paths = list(details["gerberPaths"].values()) + [details["npthPath"]]
    job_files = sorted((board_output / "cam").glob("*.gbrjob"))
    if len(job_files) > 1:
        raise ValueError(f"{board['id']}: multiple Gerber job files")
    package_paths.extend(job_files)
    package_hashes = [{"name": path.name, "sha256": sha256_file(path),
                       "sizeBytes": path.stat().st_size} for path in package_paths]
    package_manifest = {
        "boardId": board["id"], "category": board["category"],
        "sourceNativeBoardSha256": board["nativeSha256"],
        "finish": details["finish"], "maskColor": details["maskColor"],
        "camFiles": package_hashes,
        "pthDrillFile": "empty; not included in release package",
        "status": "local CAM review candidate; factory acceptance pending",
    }
    manifest_path = board_output / "package-manifest.json"
    write_json(manifest_path, package_manifest)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in package_paths:
            archive.write(path, arcname=path.name)
        archive.write(manifest_path, arcname="package-manifest.json")
    return {"name": zip_path.name, "sizeBytes": zip_path.stat().st_size,
            "sha256": sha256_file(zip_path), "fileCount": len(package_paths),
            "camFiles": package_hashes, "packageManifestSha256": sha256_file(manifest_path)}


def summarize_drc(drc_path: Path, command_exit_code: int) -> dict[str, Any]:
    report = json.loads(drc_path.read_text())
    violations = report.get("violations", [])
    severity_counts = Counter(str(v.get("severity", "unknown")) for v in violations)
    type_counts = Counter(str(v.get("type", "unknown")) for v in violations)
    ignored = [item.get("key", "unknown") for item in report.get("ignored_checks", [])]
    unclassified = [key for key in ignored if key not in EXPECTED_IGNORED_DRC_CHECKS]
    return {
        "status": "clean" if not violations else "violations_reported",
        "nativeLoadReportCreated": True,
        "commandExitCode": command_exit_code,
        "kicadVersionInReport": report.get("kicad_version"),
        "violationCount": len(violations),
        "violationsBySeverity": dict(sorted(severity_counts.items())),
        "violationsByType": dict(sorted(type_counts.items())),
        "unconnectedItemCount": len(report.get("unconnected_items", [])),
        "ignoredChecks": ignored,
        "unclassifiedIgnoredChecks": unclassified,
        "sampleViolations": [{"type": v.get("type"), "severity": v.get("severity"),
                              "description": v.get("description")}
                             for v in violations[:8]],
        "allViolationsRecordedInRawReport": True,
    }


def current_source_status(board: dict[str, Any]) -> bool:
    if sha256_file(Path(board["nativePath"])) != board["nativeSha256"]:
        return False
    project_path = board.get("projectPath")
    if project_path:
        project = Path(project_path)
        return project.is_file() and sha256_file(project) == board.get("projectSha256")
    return True


def _report_board(record: dict[str, Any]) -> dict[str, Any]:
    severity_map = record.get("ruleSeverities") or {}
    audited_rules = ("copper_edge_clearance", "solder_mask_bridge", "shorting_items",
                     *EXPECTED_IGNORED_DRC_CHECKS.keys())
    return {
        "id": record["id"], "category": record["category"],
        "nativeBoard": record["nativeBoard"], "nativeSha256": record["nativeSha256"],
        "projectSha256": record.get("projectSha256"),
        "ruleContract": record.get("ruleContract"),
        "auditedRuleSeverities": {key: severity_map[key] for key in audited_rules if key in severity_map},
        "nativeLoad": record.get("drc"),
        "selectedDrcDisposition": record.get("drc", {}).get("selectedAcceptance"),
        "cam": record.get("cam"),
        "sourceUnchanged": record.get("sourceUnchanged"),
    }


def _save_progress(output: Path, run_record: dict[str, Any], board_records: list[dict[str, Any]]) -> None:
    run_record["boards"] = [_report_board(board) for board in board_records]
    write_json(output / "native-cam-run.json", run_record)


def selected_drc_is_clean(record: dict[str, Any]) -> bool:
    return record.get("drc", {}).get("selectedAcceptance") == "pass"


def _cli_info(cli: str, export_cam: bool) -> tuple[str, dict[str, str]]:
    version = subprocess.run([cli, "version"], text=True, capture_output=True)
    if version.returncode:
        raise RuntimeError(f"Could not read KiCad version: {version.stderr.strip()}")
    help_commands = [["pcb", "drc"]]
    if export_cam:
        help_commands += [["pcb", "export", "gerbers"], ["pcb", "export", "drill"]]
    help_text = {}
    for command in help_commands:
        result = subprocess.run([cli, *command, "--help"], text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Installed KiCad does not support {' '.join(command)}: {result.stderr.strip()}")
        help_text[" ".join(command)] = result.stdout + result.stderr
    return version.stdout.strip(), help_text


def _drc_violation_summary(drc: dict[str, Any], selected: bool,
                           rule_error: str | None) -> dict[str, Any]:
    result = {**drc}
    if selected:
        unexplained = []
        if drc["violationCount"]:
            unexplained.append("DRC violations are not covered by a board-specific approved exception")
        if drc["unclassifiedIgnoredChecks"]:
            unexplained.append("KiCad ignored checks lack a documented board-only disposition")
        if rule_error:
            unexplained.append("The selected board's local KiCad project rules failed policy checks")
        result["selectedAcceptance"] = "pass" if not unexplained else "blocker"
        result["unexplainedFindings"] = unexplained
    else:
        result["selectedAcceptance"] = "reference-only; findings retained separately"
        result["unexplainedFindings"] = []
    return result


def _make_compact_evidence(run_record: dict[str, Any], board_records: list[dict[str, Any]],
                           output: Path, evidence_dir: Path,
                           thumbnails: list[tuple[dict[str, Any], Path | None]]) -> tuple[Path, Path, Path]:
    selected = [b for b in board_records if b["category"] == "selected"]
    alternatives = [b for b in board_records if b["category"] == "alternatives"]
    selected_clean = [b for b in selected if selected_drc_is_clean(b)]
    selected_cam_pass = [b for b in selected if b.get("cam", {}).get("status") == "pass"]
    native_command_failures = [b["id"] for b in board_records if b.get("commandFailure")]
    native_loads_ok = all(b.get("drc", {}).get("nativeLoadReportCreated") and not b.get("commandFailure")
                          for b in board_records)
    sources_unchanged = all(b.get("sourceUnchanged") for b in board_records)
    selected_command_failures = [b["id"] for b in selected if b.get("commandFailure")]
    cam_command_failures = [b["id"] for b in selected
                            if b.get("cam", {}).get("commandFailure")]
    local_pass = (len(selected_clean) == 43 and len(selected_cam_pass) == 43 and
                  native_loads_ok and sources_unchanged and not native_command_failures and
                  not selected_command_failures and not cam_command_failures)
    expected_top_boards = [b for b in selected if b["layerNumber"] == 1]
    if len(expected_top_boards) != 5:
        raise ValueError(f"Expected exactly five selected top boards, found {len(expected_top_boards)}")
    thumbnails_by_id = {board["id"]: path for board, path in thumbnails}
    appearance_slots = [(board, thumbnails_by_id.get(board["id"])) for board in expected_top_boards]
    missing_appearance_ids = [board["id"] for board, path in appearance_slots if path is None]
    report = {
        "schemaVersion": 1,
        "status": "pass_local_native_and_cam_checks" if local_pass else "blocked_by_local_findings",
        "releaseStatus": "candidate only; factory acceptance is not claimed",
        "startedUtc": run_record["startedUtc"], "finishedUtc": run_record["finishedUtc"],
        "kicadVersion": run_record["kicadVersion"],
        "kicadCli": run_record["kicadCli"],
        "cliHelpSha256": run_record["cliHelpSha256"],
        "inputs": run_record["inputs"],
        "commands": run_record["commands"],
        "nativeLoads": {
            "boardCount": len(board_records), "reportsCreated": sum(bool(b.get("drc", {}).get("nativeLoadReportCreated")) for b in board_records),
            "selectedBoardCount": len(selected), "selectedCleanDrcCount": len(selected_clean),
            "selectedCommandFailureIds": selected_command_failures,
            "commandFailureIds": native_command_failures,
            "referenceAlternativeCount": len(alternatives),
            "referenceFindingsByType": {
                b["id"]: b.get("drc", {}).get("violationsByType", {}) for b in alternatives
                if b.get("drc", {}).get("violationCount", 0)
            },
            "unclassifiedIgnoredCheckIds": {
                b["id"]: b.get("drc", {}).get("unclassifiedIgnoredChecks", []) for b in selected
                if b.get("drc", {}).get("unclassifiedIgnoredChecks")
            },
            "projectRuleErrors": {b["id"]: b.get("ruleContractError") for b in selected
                                  if b.get("ruleContractError")},
        },
        "cam": {
            "selectedBoardCount": len(selected), "verifiedBoardCount": len(selected_cam_pass),
            "commandFailureIds": cam_command_failures,
            "packageCount": sum(bool(b.get("cam", {}).get("packageZip")) for b in selected),
            "perBoardZipDirectory": "local/ignored run output only",
            "checks": ["native Edge.Cuts segment identity and closed loops",
                       "F.Cu/F.Mask positive-region contour identity",
                       "NPTH-only front/back mask flashes and empty back copper art",
                       "four Ø3.2 NPTH mounts and top-only 10.28 × 3.2 NPTH routes",
                       "finish/color metadata, file hashes, and representative CAM rendering"],
        },
        "representativeAppearance": {
            "status": "complete" if not missing_appearance_ids else "partial",
            "expectedTopBoardCount": len(expected_top_boards),
            "renderedTopBoardIds": [board["id"] for board, path in appearance_slots if path is not None],
            "missingTopBoardIds": missing_appearance_ids,
            "image": "native-cam-representative.png",
        },
        "sourceFilesUnchanged": sources_unchanged,
        "pendingExternalChecks": ["factory CAM acceptance", "quote/order", "physical fit"],
        "optInDiagnostics": ["exhaustive all-boundary width certificate", "broad full-union width reconstruction"],
        "rawOutput": "generated locally at the caller-specified output path; not committed",
    }
    manifest = {
        "schemaVersion": 1,
        "runStatus": report["status"],
        "kicadVersion": run_record["kicadVersion"],
        "kicadCli": run_record["kicadCli"],
        "inputHashes": run_record["inputs"],
        "boards": [],
    }
    for board in board_records:
        board_manifest = {
            "id": board["id"], "category": board["category"],
            "nativeBoard": board["nativeBoard"], "nativeBoardSha256": board["nativeSha256"],
            "projectSha256": board.get("projectSha256"),
            "drcReport": board.get("drc"),
            "sourceUnchanged": board.get("sourceUnchanged"),
        }
        if board.get("cam"):
            board_manifest["cam"] = {
                "status": board["cam"].get("status"),
                "finish": board["cam"].get("finish"),
                "maskColor": board["cam"].get("maskColor"),
                "checks": board["cam"].get("checks"),
                "files": board["cam"].get("files", []),
                "packageZip": board["cam"].get("packageZip"),
            }
        manifest["boards"].append(board_manifest)

    overview_local = output / "representative-cam-appearance.png"
    compose_cam_overview(appearance_slots, overview_local)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_path = evidence_dir / "native-kicad-cam-report.json"
    manifest_path = evidence_dir / "native-kicad-cam-manifest.json"
    image_path = evidence_dir / "native-cam-representative.png"
    write_json(report_path, report)
    write_json(manifest_path, manifest)
    shutil.copy2(overview_local, image_path)
    write_json(output / "native-cam-summary.json", report)
    write_json(output / "native-cam-file-manifest.json", manifest)
    return report_path, manifest_path, image_path


def run_pipeline(args: argparse.Namespace) -> int:
    boards_root = args.boards_root.resolve()
    inventory, evidence = load_inventory(boards_root)
    cli = find_kicad_cli(args.kicad_cli)
    if not cli:
        raise RuntimeError("KiCad CLI was not found; no native checks were run")
    version, help_text = _cli_info(cli, args.export_selected)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Output directory is not empty; use a new local output path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "installed-cli-help.json", help_text)
    cli_help_sha256 = sha256_file(output / "installed-cli-help.json")
    run_record = {
        "schemaVersion": 1,
        "status": "running",
        "startedUtc": utc_now(),
        "finishedUtc": None,
        "kicadVersion": version,
        "kicadCli": cli,
        "cliHelpSha256": cli_help_sha256,
        "nativeKiCadActuallyRun": True,
        "camIsReviewOnly": True,
        "manufacturingRelease": False,
        "rawOutputRoot": str(output),
        "inputs": {key: value for key, value in evidence.items() if key != "policy"},
        "commands": {
            "drc": ["pcb", "drc", "--format", "json", "--units", "mm",
                    "--severity-all", "--severity-exclusions", "--exit-code-violations",
                    "--output", "<board-output>/drc.json", "<board.kicad_pcb>"],
            "gerbers": ["pcb", "export", "gerbers", "--layers", ",".join(CAM_LAYERS),
                        "--precision", "6", "--output", "<board-cam-directory>/", "<board.kicad_pcb>"],
            "drills": ["pcb", "export", "drill", "--format", "excellon", "--drill-origin", "absolute",
                       "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
                       "--excellon-oval-format", "route", "--excellon-separate-th", "--generate-map",
                       "--map-format", "svg", "--generate-report", "--report-path",
                       "<board-cam-directory>/drill.rpt", "--output", "<board-cam-directory>/",
                       "<board.kicad_pcb>"],
            "localRuleContract": {
                "minimumCopperGapMm": evidence["policy"]["rulesMm"]["minimumSeparateCopperGap"],
                "copperToEdgeOrDrillMm": evidence["policy"]["rulesMm"]["topCopperToRoutedEdgeOrDrill"],
                "minimumCopperUnderMaskMm": evidence["policy"]["rulesMm"]["copperUnderMaskMargin"],
                "numericDistanceToleranceMm": evidence["policy"]["rulesMm"]["numericDistanceTolerance"],
                "numericAreaToleranceMm2": evidence["policy"]["rulesMm"]["numericAreaTolerance"],
            },
        },
        "boards": [],
    }
    board_records = []
    _save_progress(output, run_record, board_records)
    for index, board in enumerate(inventory, start=1):
        target = output / "native" / board["id"]
        target.mkdir(parents=True, exist_ok=True)
        record = {
            "id": board["id"], "category": board["category"],
            "nativeBoard": board["nativeBoard"], "nativeSha256": board["nativeSha256"],
            "expectedNativeSha256": board["expectedNativeSha256"],
            "projectPath": board.get("projectPath"), "projectSha256": board.get("projectSha256"),
            "drcReportPath": str((target / "drc.json").relative_to(output)),
        }
        try:
            contract = parse_rule_contract(board, evidence["policy"])
            record["ruleContract"] = {k: v for k, v in contract.items() if k != "ruleSeverities"}
            record["ruleSeverities"] = contract.get("ruleSeverities")
        except Exception as exc:
            record["ruleContract"] = None
            record["ruleContractError"] = str(exc)
        argv = kicad_commands(cli, board, target, export_cam=False)[0][1]
        record["drcCommand"] = argv
        command_exit = run_command(argv, target / "drc.stdout.txt", target / "drc.stderr.txt")
        record["drcCommandExitCode"] = command_exit
        drc_path = target / "drc.json"
        if drc_path.is_file() and command_exit in (0, 5):
            summary = summarize_drc(drc_path, command_exit)
            summary["reportSha256"] = sha256_file(drc_path)
            summary["reportSizeBytes"] = drc_path.stat().st_size
            record["drc"] = _drc_violation_summary(
                summary, board["category"] == "selected", record.get("ruleContractError"))
            record["commandFailure"] = False
        else:
            record["drc"] = {"status": "command_failure", "nativeLoadReportCreated": drc_path.is_file(),
                              "commandExitCode": command_exit, "violationCount": None}
            record["commandFailure"] = True
        record["sourceUnchanged"] = current_source_status(board)
        board_records.append(record)
        _save_progress(output, run_record, board_records)
        disposition = record.get("drc", {}).get("selectedAcceptance")
        print(f"DRC {index:02d}/52 {board['id']}: {record['drc']['status']}"
              + (f" ({record['drc'].get('violationCount')} findings)" if record['drc'].get("violationCount") else ""),
              flush=True)

    thumbnails: list[tuple[dict[str, Any], Path]] = []
    if args.export_selected:
        selected = [b for b in inventory if b["category"] == "selected"]
        for index, board in enumerate(selected, start=1):
            target = output / "cam" / board["id"]
            target.mkdir(parents=True, exist_ok=True)
            cam_dir = target / "cam"
            cam_dir.mkdir(parents=True, exist_ok=True)
            commands = kicad_commands(cli, board, target, export_cam=True)[1:]
            command_results = []
            for name, argv in commands:
                stdout_path, stderr_path = target / f"{name}.stdout.txt", target / f"{name}.stderr.txt"
                command_exit = run_command(argv, stdout_path, stderr_path)
                command_results.append({"purpose": name, "argv": argv, "exitCode": command_exit})
            record = next(b for b in board_records if b["id"] == board["id"])
            record["camCommands"] = command_results
            if any(command["exitCode"] != 0 for command in command_results):
                record["cam"] = {"status": "command_failure", "commandFailure": True,
                                  "commands": command_results}
            else:
                try:
                    checks, details = verify_cam_board(board, target)
                    files = cam_file_records(cam_dir, details["gerberPaths"], details["npthPath"])
                    package = make_board_zip(board, output, target, details, files)
                    record["cam"] = {
                        "status": "pass", "commandFailure": False,
                        "finish": details["finish"], "maskColor": details["maskColor"],
                        "checks": checks, "files": files, "packageZip": package,
                        "commands": command_results,
                    }
                    if board["layerNumber"] == 1:
                        thumb = output / "cam-review" / f"{board['id']}.png"
                        render_cam_thumbnail(board, details, thumb)
                        thumbnails.append((board, thumb))
                except Exception as exc:
                    record["cam"] = {"status": "verification_failure", "commandFailure": False,
                                      "error": str(exc), "commands": command_results}
            record["sourceUnchanged"] = current_source_status(board)
            _save_progress(output, run_record, board_records)
            print(f"CAM {index:02d}/43 {board['id']}: {record['cam']['status']}", flush=True)

    run_record["finishedUtc"] = utc_now()
    selected_records = [b for b in board_records if b["category"] == "selected"]
    native_ok = all(b.get("drc", {}).get("nativeLoadReportCreated") and not b.get("commandFailure")
                    for b in board_records)
    selected_ok = all(selected_drc_is_clean(b) for b in selected_records)
    cam_ok = all(b.get("cam", {}).get("status") == "pass" for b in selected_records) if args.export_selected else False
    sources_ok = all(b.get("sourceUnchanged") for b in board_records)
    run_record["status"] = "pass_local_native_and_cam_checks" if (native_ok and selected_ok and cam_ok and sources_ok) else "blocked_by_local_findings"
    _save_progress(output, run_record, board_records)
    report_path, manifest_path, image_path = _make_compact_evidence(
        run_record, board_records, output, args.evidence_dir.resolve(), thumbnails)
    print(json.dumps({
        "status": run_record["status"], "kicadVersion": version,
        "nativeReports": sum(bool(b.get("drc", {}).get("nativeLoadReportCreated")) for b in board_records),
        "selectedCleanDrc": sum(b.get("drc", {}).get("selectedAcceptance") == "pass" for b in selected_records),
        "camVerified": sum(b.get("cam", {}).get("status") == "pass" for b in selected_records),
        "report": str(report_path), "manifest": str(manifest_path), "appearance": str(image_path),
        "rawOutput": str(output),
    }, indent=2))
    return 0 if run_record["status"] == "pass_local_native_and_cam_checks" else 1


def verify_existing(args: argparse.Namespace) -> int:
    inventory, _ = load_inventory(args.boards_root.resolve())
    boards = [board for board in inventory if board["id"] == args.board_id]
    if len(boards) != 1:
        raise RuntimeError(f"Unknown or ambiguous manifest board id: {args.board_id}")
    checks, details = verify_cam_board(boards[0], args.cam_dir.resolve().parent,
                                       args.cam_dir.resolve(),
                                       args.drill_dir.resolve() if args.drill_dir else None)
    print(json.dumps({"boardId": args.board_id, "nativeSha256": boards[0]["nativeSha256"],
                      "status": "pass", "checks": checks,
                      "gerberFiles": {layer: path.name for layer, path in details["gerberPaths"].items()},
                      "npthFile": details["npthPath"].name,
                      "pthFiles": [path.name for path in details["pthPaths"]]}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run KiCad DRC on all 52 boards")
    parser.add_argument("--export-selected", action="store_true", help="Also export and verify CAM for the 43 selected boards")
    parser.add_argument("--verify-existing", action="store_true", help="Read-only CAM smoke against an existing one-board output folder")
    parser.add_argument("--board-id", help="Manifest board id used with --verify-existing")
    parser.add_argument("--cam-dir", type=Path, help="Existing Gerber directory used with --verify-existing")
    parser.add_argument("--drill-dir", type=Path, help="Optional existing Excellon directory if split from Gerbers")
    parser.add_argument("--boards-root", type=Path, default=REPO,
                        help="Repository root containing the 52 native boards")
    parser.add_argument("--output", type=Path, help="New local output directory for a full KiCad run")
    parser.add_argument("--evidence-dir", type=Path, default=HERE,
                        help="Directory for compact tracked report, manifest and preview PNG")
    parser.add_argument("--kicad-cli", help="KiCad CLI executable path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.verify_existing:
        if args.execute or args.export_selected or args.output:
            parser.error("--verify-existing is read-only; do not combine it with run/output flags")
        if not args.board_id or not args.cam_dir:
            parser.error("--verify-existing requires --board-id and --cam-dir")
        return verify_existing(args)
    if not args.execute:
        parser.error("Choose --execute for the full native run or --verify-existing for a read-only CAM smoke")
    if not args.output:
        parser.error("--execute requires --output")
    if not args.export_selected:
        parser.error("Issue #16 requires selected CAM output; pass --export-selected")
    return run_pipeline(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"native CAM verification failed before completion: {exc}", file=sys.stderr)
        sys.exit(1)
