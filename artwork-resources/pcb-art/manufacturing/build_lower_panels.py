#!/usr/bin/env python3
"""Build the frozen lower-board grids from verified native KiCad boards.

Only translations are applied to member artwork and drills. Individual outer
rectangles become score boundaries; all decorative Edge.Cuts loops remain routed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import uuid

from shapely.geometry import LineString, Point, Polygon, box

from verify_native_cam import component_loops, parse_native_board

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
POLICY = HERE / "policy.json"
GENERATION = HERE / "native-generation.json"
PCB_MANIFEST = HERE.parent / "pcb" / "manifest.json"
OUT = ROOT / "panels" / "art-grouped-lowers"
ITEM = re.compile(r"^  \((?:gr_line|gr_poly|footprint)\b", re.M)
XY = re.compile(r"\((start|end|xy) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)\)")
AT = re.compile(r"\(at (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)([^)]*)\)")
UUID = re.compile(r'\(uuid "([^"]+)"\)')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(value):
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def chunks(source):
    starts = [m.start() for m in ITEM.finditer(source)]
    if not starts:
        raise ValueError("Native board has no graphics")
    return source[:starts[0]], [source[a:b] for a, b in zip(starts, starts[1:] + [source.rfind("\n)")])]


def outer_line(item):
    if not item.lstrip().startswith("(gr_line") or '(layer "Edge.Cuts")' not in item:
        return False
    coords = [(float(x), float(y)) for _, x, y in XY.findall(item)]
    if len(coords) != 2:
        raise ValueError("Unrecognized Edge.Cuts line")
    a, b = coords
    return (abs(a[0] - b[0]) < 1e-8 and a[0] in (0, 101.3)
            or abs(a[1] - b[1]) < 1e-8 and a[1] in (17.1, 111.4))


def move(item, dx, dy, key):
    def xy(match):
        tag, x, y = match.groups()
        return f"({tag} {fmt(float(x)+dx)} {fmt(float(y)+dy)})"
    item = XY.sub(xy, item)
    if item.lstrip().startswith("(footprint"):
        item = AT.sub(lambda m: f"(at {fmt(float(m[1])+dx)} {fmt(float(m[2])+dy)}{m[3]})", item, count=1)
    return UUID.sub(lambda m: f'(uuid "{uuid.uuid5(uuid.NAMESPACE_URL, key+":"+m[1])}")', item)


def line(a, b, layer, key):
    uid = uuid.uuid5(uuid.NAMESPACE_URL, key)
    return (f'  (gr_line (start {fmt(a[0])} {fmt(a[1])}) '
            f'(end {fmt(b[0])} {fmt(b[1])}) '
            f'(stroke (width 0.05) (type default)) (layer "{layer}") '
            f'(uuid "{uid}"))\n')


PANEL_DRC_ORDER_WITNESSES = {
    "01-spider-nest-L04-white-mask-only": [(39.885386, 40.215874)],
    "03-coral-vault-L05-red-mask-only": [(26.671118, 24.423119)],
    "17-kumiko-void-wide-L08-red-mask-only": [(7.827669, 101.702169)],
}


def rotate_drc_witness_loops(items, native, board_id, extra_witnesses=()):
    """Change KiCad's seed edge for origin-sensitive aperture loops.

    At their translated panel coordinates KiCad 10 reports invalid outlines
    despite exact segment identity and clean individual DRC. Rotating each
    serialized primitive run retains every edge and all routed geometry.
    """
    loops=component_loops(native["edgeSegments"])
    for witness in [*PANEL_DRC_ORDER_WITNESSES.get(board_id, []), *extra_witnesses]:
        loop=next((points for points in loops if witness in points),None)
        if loop is None:
            raise ValueError(f"{board_id}: DRC witness loop changed")
        vertices=set(loop)
        indices=[]
        for i,item in enumerate(items):
            if not item.lstrip().startswith("(gr_line") or '(layer "Edge.Cuts")' not in item:
                continue
            coords=[(float(x),float(y)) for _,x,y in XY.findall(item)]
            if len(coords)==2 and coords[0] in vertices and coords[1] in vertices:
                indices.append(i)
        if len(indices)!=len(loop) or indices!=list(range(indices[0],indices[-1]+1)):
            raise ValueError(f"{board_id}: DRC witness loop is not contiguous")
        start,end=indices[0],indices[-1]+1
        pivot=len(loop)//2
        items[start:end]=items[start+pivot:end]+items[start:start+pivot]
    return items


def build(output=OUT, *, profile=None, variant="grouped", evidence_path=None):
    policy = json.loads(POLICY.read_text())
    manifest = json.loads(PCB_MANIFEST.read_text())
    generation = json.loads(GENERATION.read_text())
    selected = {b["id"]: b for b in manifest["boards"] if b["category"] == "selected"}
    native_hashes = {Path(b["nativeBoard"]).stem: b["sha256"] for b in generation["boards"]}
    if profile is not None:
        from order_profiles import load_profile, groups_for
        order_profile, selected = load_profile(profile)
        groups = groups_for(order_profile, variant, selected)
        if evidence_path is None:
            raise ValueError("Profile builds require an explicit evidence path")
    else:
        groups = policy["panelGroups"]
    rows = []
    for group in groups:
        members = group["memberIds"]
        assert members == sorted(members), group["id"]
        if group["columns"] * group["rows"] == 1:
            continue  # Existing verified native routed singleton is the package source.
        stem = "lower-panel-" + group["id"]
        target_dir = output / stem
        target_dir.mkdir(parents=True, exist_ok=True)
        source0 = ROOT / selected[members[0]]["nativeBoard"]
        header, _ = chunks(source0.read_text())
        header = re.sub(r'\(title "[^"]+"\)', f'(title "{stem}")', header, count=1)
        header = re.sub(r'\(comment 1 "[^"]+"\)', '(comment 1 "V-scores: separate Dwgs.User fabrication drawing; CAM signoff pending")', header, count=1)
        items = []
        placements = []
        nearest = {"apertureMm": float("inf"), "supportDiskMm": float("inf"),
                   "copperMm": float("inf"), "visibleGoldMm": float("inf")}
        for n, board_id in enumerate(members):
            board = selected[board_id]
            assert board["maskColor"] == group["color"]
            assert ("ENIG" if board["finish"].startswith("enig") else "lead-free HASL") == group["finish"]
            source = ROOT / board["nativeBoard"]
            if digest(source) != native_hashes[board_id]:
                raise ValueError(f"Verified native source changed: {board_id}")
            col, row = n % group["columns"], n // group["columns"]
            dx = group["railMm"] + col * 101.3
            dy = group["railMm"] + row * 94.3 - 17.1
            placements.append({"id": board_id, "column": col, "row": row,
                               "translationMm": [round(dx, 6), round(dy, 6)],
                               "sourceSha256": digest(source)})
            native = parse_native_board(source)
            loops = [Polygon(loop) for loop in component_loops(native["edgeSegments"])]
            inner = [p for p in loops if p.area < 101.3*94.3-1]
            seams = [LineString([(0, 17.1), (0, 111.4)]),
                     LineString([(101.3, 17.1), (101.3, 111.4)]),
                     LineString([(0, 17.1), (101.3, 17.1)]),
                     LineString([(0, 111.4), (101.3, 111.4)])]
            for seam in seams:
                for p in inner:
                    nearest["apertureMm"] = min(nearest["apertureMm"], seam.distance(p))
                for pad in native["npthPads"]:
                    support = Point(pad["x"], pad["y"]).buffer(3.05, quad_segs=64)
                    nearest["supportDiskMm"] = min(nearest["supportDiskMm"], seam.distance(support))
                for p in native["polygons"].get("F.Cu", []):
                    nearest["copperMm"] = min(nearest["copperMm"], seam.distance(p))
                for p in native["polygons"].get("F.Mask", []):
                    nearest["visibleGoldMm"] = min(nearest["visibleGoldMm"], seam.distance(p))
            _, source_items = chunks(source.read_text())
            # Linux KiCad's compact Fault red grid needs a different contour seed.
            # Scope this exact-segment reorder to the new split; legacy bytes stay unchanged.
            extra=((37.393315,46.330334),) if (profile is not None and variant=="split-red"
                and board_id=="13-fault-line-L08-red-mask-only") else ()
            source_items=rotate_drc_witness_loops(source_items,native,board_id,extra)
            items.extend(move(item, dx, dy, f"{stem}:{board_id}").rstrip()+"\n"
                         for item in source_items if not outer_line(item))
        if nearest["apertureMm"] < .999 or nearest["supportDiskMm"] < .999:
            raise ValueError(f"{stem}: score crosses aperture/support: {nearest}")
        if nearest["copperMm"] < .499 or nearest["visibleGoldMm"] < .549:
            raise ValueError(f"{stem}: score crosses art: {nearest}")
        w, h = group["widthMm"], group["heightMm"]
        if not (70 <= w <= 475 and 70 <= h <= 475):
            raise ValueError(f"{stem}: out of panel bounds")
        outer = [(0,0),(w,0),(w,h),(0,h)]
        items.extend(line(outer[k], outer[(k+1)%4], "Edge.Cuts", f"{stem}:outer:{k}") for k in range(4))
        x_scores = [group["railMm"]+i*101.3 for i in range(group["columns"]+1)]
        y_scores = [group["railMm"]+i*94.3 for i in range(group["rows"]+1)]
        for axis, values in (("x", x_scores), ("y", y_scores)):
            if len(values) > 25 or min(b-a for a,b in zip(values,values[1:])) < 3:
                raise ValueError(f"{stem}: score count/spacing")
            for k, value in enumerate(values):
                a,b = ((value,0),(value,h)) if axis == "x" else ((0,value),(w,value))
                items.append(line(a,b,"Dwgs.User",f"{stem}:score:{axis}:{k}"))
        pcb = target_dir / (stem + ".kicad_pcb")
        pcb.write_text(header + "".join(items) + ")\n")
        pro = json.loads(source0.with_suffix(".kicad_pro").read_text())
        pro["meta"]["filename"] = stem + ".kicad_pro"
        project = target_dir / (stem + ".kicad_pro")
        project.write_text(json.dumps(pro, indent=2) + "\n")
        fab = target_dir / "FABRICATION.txt"
        fab.write_text(f"{stem}: {fmt(w)} x {fmt(h)} mm. 2 layer FR-4, 1.6 mm, 1 oz, {group['color']} mask, {group['finish']}.\n"
                       f"Customer panel, {len(members)} distinct lower-board designs; order {group['quantity']} sheets.\n"
                       "V-score every full-length line from the separate Dwgs.User drawing. Scores are not Edge.Cuts or silk.\n"
                       "Route the outside and decorative apertures from Edge.Cuts; drill all NPTH mounts from Excellon.\n"
                       "Blank cells are waste. Preserve sorted row-major placement and finished 101.3 x 94.3 mm lower cells.\n"
                       "Scored outline tolerance is +/-0.4 mm. Web depth, handling, mask/finish and physical fit await factory CAM/quote review.\n")
        rows.append({"id": stem, "groupId":group["id"], "nativeBoard":str(pcb.relative_to(output)) if profile is not None else str(pcb.relative_to(ROOT)),
                     "nativeBoardSha256":digest(pcb), "projectSha256":digest(project),
                     "fabricationInstructionsSha256":digest(fab), "placements":placements,
                     "scoreXMm":x_scores,"scoreYMm":y_scores,"minimumScoreClearanceMm":{k:(round(v,6) if v!=float("inf") else None) for k,v in nearest.items()},
                     "widthMm":w,"heightMm":h,"unusedCells":group["unusedCells"]})
    result = {"schemaVersion":1,"policySha256":digest(POLICY),"nativeGenerationSha256":digest(GENERATION),
              "sourceManifestSha256":digest(PCB_MANIFEST),"panels":rows}
    if profile is not None:
        result.update(profileSha256=digest(Path(profile)), variant=variant)
    path=Path(evidence_path) if evidence_path is not None else HERE/"lower-panels-native.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--profile",type=Path)
    parser.add_argument("--variant",choices=("individual","grouped","split-red"),default="grouped")
    parser.add_argument("--evidence-path",type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.output, profile=args.profile, variant=args.variant, evidence_path=args.evidence_path),indent=2))
