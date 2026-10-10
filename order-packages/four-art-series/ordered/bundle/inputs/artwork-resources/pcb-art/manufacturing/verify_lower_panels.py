#!/usr/bin/env python3
"""Native DRC, output CAM and exact 25-stack accounting for grouped lower boards."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import zipfile

from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from verify_native_cam import (
    REPO, HERE, parse_native_board, parse_gerber, parse_excellon,
    component_loops, contour_signature, compare_region_contours,
    _gerber_layer_from_file, CAM_LAYERS, expected_npth_mask_geometry, compare_geometries,
)

NATIVE_RECORD = HERE / "lower-panels-native.json"
POLICY = HERE / "policy.json"
PCB_MANIFEST = HERE.parent / "pcb" / "manifest.json"
INDIVIDUAL_CAM = HERE / "native-kicad-cam-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jwrite(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def segkey(a, b):
    return tuple(sorted((tuple(round(v, 6) for v in a), tuple(round(v, 6) for v in b))))


def validate_scores(native, record):
    # Fixed 5 mm rails and cell pitch are the issue 23/frozen policy contract.
    from verify_native_cam import GR_LINE_RE
    w, h = record["widthMm"], record["heightMm"]
    columns, rows = round((w-10)/101.3), round((h-10)/94.3)
    if not (70 <= w <= 475 and 70 <= h <= 475 and columns > 0 and rows > 0
            and abs(w-(10+columns*101.3)) < 1e-6 and abs(h-(10+rows*94.3)) < 1e-6):
        raise ValueError("Invalid scored panel dimensions")
    xs=[5+i*101.3 for i in range(columns+1)]
    ys=[5+i*94.3 for i in range(rows+1)]
    if (record["scoreXMm"] != xs or record["scoreYMm"] != ys
            or max(len(xs),len(ys)) > 25):
        raise ValueError("Invalid score coordinate record")
    expected=Counter(segkey((x,0),(x,h)) for x in xs)
    expected.update(segkey((0,y),(w,y)) for y in ys)
    actual=Counter()
    for match in GR_LINE_RE.finditer(native["text"]):
        if match.group(5)=="Dwgs.User":
            a,b,c,d=map(float,match.groups()[:4])
            actual[segkey((a,b),(c,d))]+=1
    if actual != expected or native["polygonContours"].get("Dwgs.User"):
        raise ValueError("Native scores differ from full-span grid")


def native_partition(panel, record, boards, source_root=REPO):
    """Compare every member's apertures, art polygons and NPTH after translation."""
    actual = parse_native_board(panel)
    validate_scores(actual, record)
    expected_edges = Counter()
    expected_polys = {"F.Cu": Counter(), "F.Mask": Counter()}
    expected_pads = Counter()
    outer = [(0, 0), (record["widthMm"], 0),
             (record["widthMm"], record["heightMm"]), (0, record["heightMm"])]
    expected_edges.update(segkey(outer[k], outer[(k+1)%4]) for k in range(4))
    cells=[]
    columns=round((record["widthMm"]-10)/101.3)
    for index, placement in enumerate(record["placements"]):
        expected_translation=[round(5+(index%columns)*101.3,6), round(5+(index//columns)*94.3-17.1,6)]
        if (placement["translationMm"]!=expected_translation or placement["column"]!=index%columns
                or placement["row"]!=index//columns):
            raise ValueError("Placement differs from the fixed rail and row-major grid")
        board=boards[placement["id"]]
        source=source_root / board["nativeBoard"]
        if sha(source)!=placement["sourceSha256"]:
            raise ValueError(f"Source hash changed: {placement['id']}")
        native=parse_native_board(source)
        dx,dy=placement["translationMm"]
        area=box(dx,17.1+dy,101.3+dx,111.4+dy)
        if any(area.intersection(old).area > 1e-8 for old in cells):
            raise ValueError("Panel cells overlap")
        cells.append(area)
        for a,b in native["edgeSegments"]:
            if ((abs(a[0]-b[0])<1e-8 and a[0] in (0,101.3)) or
                (abs(a[1]-b[1])<1e-8 and a[1] in (17.1,111.4))):
                continue
            expected_edges[segkey((a[0]+dx,a[1]+dy),(b[0]+dx,b[1]+dy))]+=1
        for layer in expected_polys:
            for contour in native["polygonContours"].get(layer,[]):
                expected_polys[layer][contour_signature([(x+dx,y+dy) for x,y in contour])]+=1
        for pad in native["npthPads"]:
            expected_pads[(round(pad["x"]+dx,6),round(pad["y"]+dy,6),
                           pad["shape"],pad["drillWidth"],pad["drillHeight"])]+=1
    got_edges=Counter(segkey(a,b) for a,b in actual["edgeSegments"])
    if got_edges!=expected_edges:
        raise ValueError(f"{record['id']}: native routed contours changed: missing={sum((expected_edges-got_edges).values())}, extra={sum((got_edges-expected_edges).values())}")
    for layer in expected_polys:
        got=Counter(contour_signature(points) for points in actual["polygonContours"].get(layer,[]))
        if got!=expected_polys[layer]:
            raise ValueError(f"{record['id']}: translated {layer} contours changed")
    pads=Counter((round(p["x"],6),round(p["y"],6),p["shape"],p["drillWidth"],p["drillHeight"])
                 for p in actual["npthPads"])
    if pads!=expected_pads:
        raise ValueError(f"{record['id']}: translated NPTH pads changed")
    loops=[Polygon(points) for points in component_loops(actual["edgeSegments"])]
    largest=max(loops,key=lambda p:p.area)
    if not largest.equals(box(0,0,record["widthMm"],record["heightMm"])):
        raise ValueError(f"{record['id']}: panel outer outline changed")
    apertures=[p for p in loops if p is not largest]
    if any(not largest.contains(p) for p in apertures):
        raise ValueError(f"{record['id']}: routed aperture escapes the sheet")
    material=largest.difference(unary_union(apertures))
    if not material.is_valid or material.geom_type!="Polygon":
        raise ValueError(f"{record['id']}: routed sheet is disconnected or invalid")
    return actual,{"edgeSegments":len(actual["edgeSegments"]),
                   "apertureLoops":len(loops)-1,"sheetMaterialConnected":True,
                   "frontCopperPolygons":sum(expected_polys["F.Cu"].values()),
                   "frontMaskPolygons":sum(expected_polys["F.Mask"].values()),
                   "npthMounts":sum(expected_pads.values())}


def run_cli(cli, argv, log):
    proc=subprocess.run([cli,*argv],capture_output=True,text=True)
    log.write_text("COMMAND " + " ".join([cli,*argv]) + "\nEXIT " + str(proc.returncode) +
                   "\nSTDOUT\n" + proc.stdout + "\nSTDERR\n" + proc.stderr)
    if proc.returncode:
        raise RuntimeError(f"KiCad command failed ({proc.returncode}): {log}")


def checked_reused_drc(record, panel, entry):
    if not entry or set(entry)!={"nativeBoardSha256","reportPath","reportSha256"}:
        raise ValueError(f"{record['id']}: missing or malformed reused DRC binding")
    if entry["nativeBoardSha256"]!=record["nativeBoardSha256"] or sha(panel)!=entry["nativeBoardSha256"]:
        raise ValueError(f"{record['id']}: reused DRC board hash mismatch")
    path=Path(entry["reportPath"])
    if not path.is_file() or sha(path)!=entry["reportSha256"]:
        raise ValueError(f"{record['id']}: reused DRC report missing or hash mismatch")
    report=json.loads(path.read_text())
    if report.get("source")!=panel.name or report.get("coordinate_units")!="mm":
        raise ValueError(f"{record['id']}: reused DRC report source/units mismatch")
    if not {"error","warning","exclusion"}.issubset(set(report.get("included_severities",[]))):
        raise ValueError(f"{record['id']}: reused DRC did not include all severities")
    if report.get("violations") or report.get("unconnected_items"):
        raise ValueError(f"{record['id']}: reused DRC has violations/unconnected items")
    if not report.get("kicad_version"," ").startswith("10."):
        raise ValueError(f"{record['id']}: reused DRC is not from KiCad 10")
    return path,report


def export_and_verify(record, boards, cli, output, reused_drc=None, *, native_root=REPO, source_root=REPO):
    panel=native_root/record["nativeBoard"]
    if sha(panel)!=record["nativeBoardSha256"]:
        raise ValueError(f"Native panel hash changed: {record['id']}")
    if sha(panel.with_suffix(".kicad_pro"))!=record["projectSha256"]:
        raise ValueError(f"Native project hash changed: {record['id']}")
    native,partition=native_partition(panel,record,boards,source_root)
    directory=output/record["id"]
    cam=directory/"cam"
    cam.mkdir(parents=True,exist_ok=True)
    drc=directory/"drc.json"
    if reused_drc is None:
        run_cli(cli,["pcb","drc","--format","json","--units","mm","--severity-all",
                     "--severity-exclusions","--exit-code-violations","--output",str(drc),str(panel)],
                directory/"drc.log")
        report=json.loads(drc.read_text())
        drc_source=drc
    else:
        drc_source,report=checked_reused_drc(record,panel,reused_drc)
        if drc_source.resolve()!=drc.resolve():
            shutil.copyfile(drc_source,drc)
    if report.get("violations") or report.get("unconnected_items"):
        raise ValueError(f"{record['id']}: nonclean DRC: {drc}")
    checked_reused_drc(record, panel, {"nativeBoardSha256":sha(panel),
                       "reportPath":str(drc), "reportSha256":sha(drc)})
    layers=','.join((*CAM_LAYERS,"Dwgs.User"))
    run_cli(cli,["pcb","export","gerbers","--layers",layers,"--precision","6",
                 "--output",str(cam)+"/",str(panel)],directory/"gerbers.log")
    run_cli(cli,["pcb","export","drill","--format","excellon","--drill-origin","absolute",
                 "--excellon-units","mm","--excellon-zeros-format","decimal",
                 "--excellon-oval-format","route","--excellon-separate-th",
                 "--output",str(cam)+"/",str(panel)],directory/"drill.log")
    gerbers={}
    for path in cam.iterdir():
        if path.suffix.lower() not in (".gbr",".gm1",".gtl",".gbl",".gts",".gbs"):
            continue
        if "user" in path.name.lower():
            continue
        parsed_header=parse_gerber(path)
        layer=_gerber_layer_from_file(path,parsed_header)
        if layer not in CAM_LAYERS or layer in gerbers:
            raise ValueError(f"{record['id']}: unexpected or duplicate CAM layer: {path.name}")
        gerbers[layer]=path
    if set(gerbers)!=set(CAM_LAYERS):
        raise ValueError(f"{record['id']}: missing CAM layer: {set(CAM_LAYERS)-set(gerbers)}")
    drills=sorted(cam.glob("*.drl"))
    npth=[p for p in drills if "npth" in p.name.lower()]
    pth=[p for p in drills if "npth" not in p.name.lower()]
    if len(npth)!=1:raise ValueError(f"{record['id']}: expected one NPTH drill file")
    score_files=[p for p in cam.iterdir() if "user" in p.name.lower() and p.suffix.lower() in (".gbr",".gm1")]
    if len(score_files)!=1:
        raise ValueError(f"{record['id']}: expected one separate Dwgs.User score Gerber")
    parsed={layer:parse_gerber(path) for layer,path in gerbers.items()}
    native_edges=Counter(segkey(a,b) for a,b in native["edgeSegments"])
    edge=parsed["Edge.Cuts"]
    cam_edges=Counter(segkey(line.coords[0],line.coords[-1]) for _,line,_ in edge.strokes)
    if cam_edges!=native_edges or edge.regions or edge.flashes:
        raise ValueError(f"{record['id']}: CAM Edge.Cuts differ from native")
    for layer in ("F.Cu","B.Cu","F.Mask","B.Mask"):
        compare_region_contours(native,parsed[layer],layer,record["id"])
        if _gerber_layer_from_file(gerbers[layer],parsed[layer])!=layer:
            raise ValueError(f"{record['id']}: wrong Gerber layer identity")
        if layer in ("F.Cu","B.Cu") and parsed[layer].flashes:
            raise ValueError(f"{record['id']}: unexpected copper flash")
    if parsed["B.Cu"].regions or parsed["B.Cu"].strokes:
        raise ValueError(f"{record['id']}: back copper is nonempty")
    if any(len(parsed[layer].flashes)!=len(native["npthPads"]) for layer in ("F.Mask","B.Mask")):
        raise ValueError(f"{record['id']}: NPTH mask flash count differs")
    for layer in ("F.Mask", "B.Mask"):
        flashes=unary_union([shape for polarity,shape in parsed[layer].flashes if polarity=="dark"])
        compare_geometries(expected_npth_mask_geometry(native), flashes,
                           f"{record['id']} {layer} NPTH mask apertures")
    drill=parse_excellon(npth[0])
    expected_holes=Counter((round(p["x"],6),round(p["y"],6),round(p["drillWidth"],6))
                           for p in native["npthPads"])
    actual_holes=Counter((round(h["x"],6),round(h["y"],6),round(h["diameter"],6)) for h in drill.hits)
    if drill.routes or actual_holes!=expected_holes:
        raise ValueError(f"{record['id']}: Excellon NPTH differs")
    if any(parse_excellon(p).hits or parse_excellon(p).routes for p in pth):
        raise ValueError(f"{record['id']}: PTH drill file nonempty")
    score=parse_gerber(score_files[0])
    expected_scores=Counter(segkey((x,0),(x,record["heightMm"])) for x in record["scoreXMm"])
    expected_scores.update(segkey((0,y),(record["widthMm"],y)) for y in record["scoreYMm"])
    actual_scores=Counter(segkey(line.coords[0],line.coords[-1]) for _,line,_ in score.strokes)
    if actual_scores!=expected_scores or score.regions or score.flashes:
        raise ValueError(f"{record['id']}: exported score drawing differs")
    if native["primitiveCounts"].get("F.SilkS",0) or native["primitiveCounts"].get("B.SilkS",0):
        raise ValueError(f"{record['id']}: score contaminated silkscreen")
    instruction=panel.parent/"FABRICATION.txt"
    package=output/(record["id"]+".zip")
    files=sorted([*cam.glob("*.gtl"),*cam.glob("*.gbl"),*cam.glob("*.gts"),*cam.glob("*.gbs"),
                  *cam.glob("*.gm1"),*cam.glob("*.gbr"),*cam.glob("*.drl"),instruction])
    with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED) as archive:
        for file in files: archive.write(file,file.name)
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None or set(archive.namelist())!={p.name for p in files}:
            raise ValueError(f"{record['id']}: ZIP verification failed")
    return {"id":record["id"],"status":"pass_local_native_drc_cam",
            "nativePartition":partition,"drcReportSha256":sha(drc),
            "nativeBoardSha256":sha(panel),"drcReused":reused_drc is not None,
            "drcOriginalPath":str(drc_source),
            "camFiles":[{"name":p.name,"sha256":sha(p)} for p in files if p!=instruction],
            "zip":{"path":str(package),"sha256":sha(package),"sizeBytes":package.stat().st_size},
            "scoreGerber":score_files[0].name,"scoreCount":sum(expected_scores.values())}


def order_manifest(panel_records, policy, selected, individual, panel_results, prior_output):
    verified={b["id"]:b for b in individual["boards"] if b["category"]=="selected"}
    def checked_individual(board_id):
        board=verified[board_id]
        if (board.get("drcReport",{}).get("selectedAcceptance")!="pass" or
            board.get("cam",{}).get("status")!="pass"):
            raise ValueError(f"Individual package lacks successful DRC/CAM evidence: {board_id}")
        source=REPO/selected[board_id]["nativeBoard"]
        if sha(source)!=board["nativeBoardSha256"]:
            raise ValueError(f"Individual source hash changed: {board_id}")
        return board
    packages=[]
    useful=Counter()
    waste=0
    group_by={g["id"]:g for g in policy["panelGroups"]}
    panel_by={p["groupId"]:p for p in panel_records}
    result_by={p["id"]:p for p in panel_results}
    for group in policy["panelGroups"]:
        ids=group["memberIds"]
        if len(ids)>1:
            p=panel_by[group["id"]]
            result=result_by[p["id"]]
            zip_info=result["zip"]
            package_id=p["id"]
            kind="scored_lower_grid"
        else:
            board=checked_individual(ids[0])
            zip_info=board["cam"]["packageZip"]
            path=prior_output/"packages"/zip_info["name"]
            if sha(path)!=zip_info["sha256"]:
                raise ValueError(f"Prior verified singleton package missing/changed: {path}")
            zip_info={"path":str(path),"sha256":sha(path),"sizeBytes":path.stat().st_size}
            package_id=ids[0]
            kind="routed_lower_singleton"
        for board_id in ids: useful[board_id]+=25
        waste+=group["unusedCells"]*25
        packages.append({"id":package_id,"kind":kind,"memberIds":ids,"quantity":25,
                         "usefulYieldPerUnit":{x:1 for x in ids},"unusedCellsPerUnit":group["unusedCells"],
                         "color":group["color"],"finish":group["finish"],
                         "material":"FR-4","thicknessMm":1.6,"copperLayers":2,"copperOz":1,
                         "widthMm":group["widthMm"],"heightMm":group["heightMm"],"zip":zip_info})
    tops=sorted((b for b in selected.values() if b["layerNumber"]==1),key=lambda b:b["id"])
    if len(tops)!=5:raise ValueError("Expected exactly five tops")
    for top in tops:
        board=checked_individual(top["id"])
        zip_info=board["cam"]["packageZip"]
        path=prior_output/"packages"/zip_info["name"]
        if sha(path)!=zip_info["sha256"]:raise ValueError(f"Prior verified top package changed: {path}")
        useful[top["id"]]+=25
        packages.append({"id":top["id"],"kind":"routed_standalone_top","memberIds":[top["id"]],
                         "quantity":25,"usefulYieldPerUnit":{top["id"]:1},"unusedCellsPerUnit":0,
                         "color":"black","finish":"ENIG","material":"FR-4","thicknessMm":1.6,
                         "copperLayers":2,"copperOz":1,"widthMm":101.3,"heightMm":128.5,
                         "zip":{"path":str(path),"sha256":sha(path),"sizeBytes":path.stat().st_size}})
    if set(useful)!=set(selected) or any(q!=25 for q in useful.values()):
        raise ValueError("Order yield is not exactly 25 of each selected ID")
    if len(packages)!=13 or sum(p["quantity"] for p in packages)!=325 or sum(useful.values())!=1075 or waste!=75:
        raise ValueError("Package, quantity, useful yield or waste count differs from policy")
    designs=Counter(b["designId"] for b in selected.values())
    return {"schemaVersion":1,"status":"local_native_and_cam_pass; factory_CAM_quote_and_fit_pending",
            "policyDecisionId":policy["decisionId"],"packageCount":len(packages),
            "orderedSheetsAndStandaloneUnits":325,"usefulBoardCount":1075,"usefulYieldByBoardId":dict(sorted(useful.items())),
            "wasteCells":75,"unavoidableSurplusFinishedBoards":0,"selectedBoardCount":43,
            "designs":{d:{"boardIds":count,"completeStacks":25,
                           "boardsPerStack":count,"nominalDepthMm":33.8 if count==8 else 38.4}
                       for d,count in sorted(designs.items())},
            "hardware":{"screws":500,"spacers":3800,"nuts":500,
                        "washerCount":"pending hardware selection","screwUsableLength":"pending physical fit",
                        "nutAndWasherTolerances":"pending physical fit"},
            "packages":packages,
            "fabricationInstructions":["Use the separate Dwgs.User Gerber for full-length V-scores; never route it as Edge.Cuts.",
                                        "Route decorative apertures and outer sheet boundary from Edge.Cuts.",
                                        "Drill only the separate NPTH Excellon hits. Keep colors and ENIG/HASL packages separate.",
                                        "Scored individual outer edges have published +/-0.4 mm tolerance, not precision route tolerance."],
            "pendingExternal":["manufacturer CAM and score web-depth/handling signoff","quote, material/finish/color availability and charges",
                               "physical stack/fastener fit, washer and nut tolerances"]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("/tmp/zudo-blanks-issue17-panel-cam"))
    parser.add_argument("--prior-output",type=Path,default=Path("/tmp/zudo-blanks-issue16-native-cam-release"))
    parser.add_argument("--kicad-cli",default=shutil.which("kicad-cli"))
    parser.add_argument("--reuse-drc-reports",type=Path,
                        help="JSON mapping panel IDs to source/report SHA256 bindings for completed clean KiCad DRC")
    args=parser.parse_args()
    if not args.kicad_cli:raise ValueError("KiCad CLI required")
    policy=json.loads(POLICY.read_text())
    record=json.loads(NATIVE_RECORD.read_text())
    inventory=json.loads(PCB_MANIFEST.read_text())
    individual=json.loads(INDIVIDUAL_CAM.read_text())
    selected={b["id"]:b for b in inventory["boards"] if b["category"]=="selected"}
    if record["policySha256"]!=sha(POLICY) or record["sourceManifestSha256"]!=sha(PCB_MANIFEST):
        raise ValueError("Native panel record input hash changed")
    reused=json.loads(args.reuse_drc_reports.read_text()) if args.reuse_drc_reports else None
    if reused is not None and set(reused)!={p["id"] for p in record["panels"]}:
        raise ValueError("Reused DRC mapping must cover exactly the five final native panels")
    args.output.mkdir(parents=True,exist_ok=True)
    results=[export_and_verify(p,selected,args.kicad_cli,args.output,
                               reused[p["id"]] if reused is not None else None)
             for p in record["panels"]]
    order=order_manifest(record["panels"],policy,selected,individual,results,args.prior_output)
    jwrite(HERE/"lower-panels-cam-report.json",{"schemaVersion":1,"status":"pass_local",
           "kicadVersion":subprocess.check_output([args.kicad_cli,"version"],text=True).strip(),
           "nativeRecordSha256":sha(NATIVE_RECORD),"policySha256":sha(POLICY),
           "panels":results})
    jwrite(HERE/"lower-panels-order-manifest.json",order)
    print(json.dumps({"panels":len(results),"packages":len(order["packages"]),
                      "useful":order["usefulBoardCount"],"waste":order["wasteCells"]}))


if __name__=="__main__":main()
