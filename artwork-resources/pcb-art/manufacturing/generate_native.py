#!/usr/bin/env python3
"""Regenerate the 43 selected home boards from indexed manufacturing candidates.

Existing native edits are protected by the approved handoff manifest on the
first run, and by this generator's output manifest on subsequent runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LinearRing, Polygon

from repair_mask_candidate import HERE, ROOT, board_id, digest, export

REPO=ROOT.parents[1]
OUTPUT=HERE/'native-generation.json'
TEMPLATE=REPO/'panels/art-strip-mine/pcb-01-black/strip-mine-01.kicad_pro'
SERIALIZED_ART_MAX_DELTA_MM2=.02  # Existing export_kicad.py output-level limit.
EDGE_MIN_SEGMENT_MM=.001  # Preserve previously clean contours' segmentation.
EDGE_DRC_CONTOUR_REPAIR_MM=.003001
EDGE_COLLINEAR_SEGMENT_MM=.0044
EDGE_DRC_CONTOUR_REPAIR_BOARDS={
    '01-spider-nest-L03-gold-enig-fill',
    '13-fault-line-L02-red-mask-only',
    '13-fault-line-L07-black-mask-only',
    '13-fault-line-L08-red-mask-only',
    '18-woven-maze-L07-black-mask-only',
}
EDGE_MAX_DEVIATION_MM=.001
EDGE_MAX_AREA_DELTA_MM2=.02


def home_path(design, layer):
    family=REPO/'panels'/f'art-{design["id"]}'
    return family/(board_id(design,layer)+'.kicad_pcb')


def project_content(stem):
    data=copy.deepcopy(json.loads(TEMPLATE.read_text()))
    rules=data['board']['design_settings']['rules']
    rules['min_clearance']=.25
    rules['min_copper_edge_clearance']=.30
    rules['min_hole_clearance']=.30
    rules['solder_mask_to_copper_clearance']=0.0
    severities=data['board']['design_settings']['rule_severities']
    # The Strip Mine template ignores these fabrication checks. Native art
    # boards must run them; board-only NPTH/library checks remain documented
    # separately in the independent DRC report.
    for name in ('copper_edge_clearance','solder_mask_bridge','shorting_items'):
        severities[name]='error'
    data['meta']['filename']=stem+'.kicad_pro'
    data['schematic']['top_level_sheets']=[]
    return json.dumps(data,indent=2)+'\n'


def _collinear_between(a,b,c):
    """Exact test on KiCad's serialized 1 nm coordinate grid."""
    ax,ay=(round(v*1_000_000) for v in a)
    bx,by=(round(v*1_000_000) for v in b)
    cx,cy=(round(v*1_000_000) for v in c)
    return ((bx-ax)*(cy-ay)==(by-ay)*(cx-ax)
            and min(ax,cx)<=bx<=max(ax,cx)
            and min(ay,cy)<=by<=max(ay,cy))


def native_edge_rings(rings, min_segment_mm=EDGE_MIN_SEGMENT_MM,
                      ring_thresholds=None, collinear_rings=None):
    """Remove short serialized Edge.Cuts segments rejected by KiCad DRC.

    Copper/mask artwork and the source geometry are unchanged. Both contour
    displacement and area change are bounded against the 1 nm input rings.
    """
    result=[]
    removed=0
    max_deviation=0.0
    area_delta=0.0
    for ring_index,ring in enumerate(rings):
        before=export.ring_points(ring)
        points=before.copy()
        if len(points)<3 or not Polygon(points).is_valid:
            raise ValueError('Source Edge.Cuts ring is invalid at 1 nm precision')
        # A few apertures split straight runs into micrometre stubs.
        # Removing only redundant points preserves the exact path.
        # Other rings keep their original segmentation: KiCad's polygonizer
        # can be sensitive to a changed starting vertex even with no
        # geometric displacement.
        if ring_index in (collinear_rings or ()):
            while True:
                redundant=next((i for i in range(len(points))
                                if math.dist(points[i],points[(i+1)%len(points)])
                                <EDGE_COLLINEAR_SEGMENT_MM
                                and _collinear_between(points[i-1],points[i],
                                                       points[(i+1)%len(points)])),None)
                if redundant is None:
                    redundant=next((i for i in range(len(points))
                                    if math.dist(points[i],points[(i+1)%len(points)])
                                    <EDGE_COLLINEAR_SEGMENT_MM
                                    and _collinear_between(points[i],
                                                           points[(i+1)%len(points)],
                                                           points[(i+2)%len(points)])),None)
                    if redundant is not None:
                        redundant=(redundant+1)%len(points)
                if redundant is None:
                    break
                del points[redundant]
                removed+=1
                if len(points)<3:
                    raise ValueError('Edge.Cuts collinear repair collapsed a loop')
        threshold=(ring_thresholds or {}).get(ring_index,min_segment_mm)
        while True:
            short=next((i for i in range(len(points))
                        if math.dist(points[i-1],points[i])<threshold),None)
            if short is None:
                break
            del points[short]
            removed+=1
            if len(points)<3:
                raise ValueError('Edge.Cuts short-segment repair collapsed a loop')
        after=Polygon(points)
        if not after.is_valid:
            raise ValueError('Edge.Cuts short-segment repair invalidated a loop')
        original=LinearRing(before)
        repaired=LinearRing(points)
        max_deviation=max(max_deviation,original.hausdorff_distance(repaired))
        area_delta+=Polygon(before).symmetric_difference(after).area
        result.append(repaired)
    if max_deviation>EDGE_MAX_DEVIATION_MM+1e-9 or area_delta>EDGE_MAX_AREA_DELTA_MM2:
        raise ValueError('Edge.Cuts short-segment repair exceeds native tolerance')
    return result,{'removedShortSegments':removed,
                   'maxDeviationMm':round(max_deviation,9),
                   'areaDeltaMm2':round(area_delta,9)}


def native_parts_with_precision_repair(geom):
    """Repair only partition contours made invalid by 1 nm serialization.

    The source union is never altered. A hole-splitting cut can introduce
    off-grid vertices; snap and repartition only the affected split piece,
    then check the complete serialized union against the existing exporter
    area limit. Unknown failures still stop generation.
    """
    try:
        parts,fragments=export.native_parts(geom)
        return parts,fragments,{'repairedSplitPieceCount':0,
                                'serializedSymmetricDifferenceMm2':None}
    except ValueError as exc:
        if str(exc)!='Artwork polygon became invalid at 1 nm precision':
            raise
    parts=[]
    collapsed=0
    collapsed_area=0.0
    repaired=0
    for piece in export.without_holes(geom):
        points=export.ring_points(piece.exterior)
        if len(points)<3 or Polygon(points).area==0:
            collapsed+=1
            collapsed_area+=piece.area
            continue
        ring=Polygon(points)
        if ring.is_valid:
            parts.append(ring)
            continue
        repaired+=1
        snapped=shapely.set_precision(piece,.000001)
        for subpiece in export.without_holes(snapped):
            points=export.ring_points(subpiece.exterior)
            ring=Polygon(points)
            if len(points)<3 or ring.area==0 or not ring.is_valid:
                raise ValueError('Precision repair did not yield a valid native contour')
            parts.append(ring)
    if collapsed_area>.000001:
        raise ValueError('Quantization would discard a meaningful artwork area')
    delta=shapely.union_all(parts).symmetric_difference(geom).area
    if delta>SERIALIZED_ART_MAX_DELTA_MM2:
        raise ValueError(f'Precision repair changed artwork by {delta} mm²')
    return parts,{'count':collapsed,'areaMm2':collapsed_area},{
        'repairedSplitPieceCount':repaired,
        'serializedSymmetricDifferenceMm2':round(delta,9),
    }


def run():
    geom_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    copper_path=HERE/'copper-repair-candidate.json'
    ledger_path=HERE/'copper-repair-ledger.json'
    data=json.loads(geom_path.read_text())
    masks=json.loads(mask_path.read_text())
    coppers=json.loads(copper_path.read_text())
    ledger=json.loads(ledger_path.read_text())
    compact={**coppers,'boards':[{k:v for k,v in b.items() if k!='afterCopperWkbHex'}
                                  for b in coppers['boards']]}
    if compact!=ledger:
        raise ValueError('Local copper geometry differs from indexed ledger')
    if masks['sourceGeometrySha256']!=digest(geom_path.read_bytes()):
        raise ValueError('Native input mask provenance mismatch')
    if coppers['sourceGeometrySha256']!=digest(geom_path.read_bytes()):
        raise ValueError('Native input copper provenance mismatch')
    if coppers['maskCandidateSha256']!=digest(mask_path.read_bytes()):
        raise ValueError('Native input copper/mask provenance mismatch')
    by_mask={b['boardId']:b for b in masks['boards']}
    by_copper={b['boardId']:b for b in coppers['boards']}
    approved=json.loads((ROOT/'pcb/manifest.json').read_text())
    approved_hashes={b['nativeBoard']:b['nativeBoardSha256'] for b in approved['boards']}
    previous=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else None
    previous_hashes={b['nativeBoard']:b['sha256'] for b in previous['boards']} if previous else {}
    previous_project_hashes={b['project']:b['projectSha256']
                             for b in previous['boards']} if previous else {}
    planned=[]
    for family in data['designs']:
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        for layer in design['layers']:
            target=home_path(design,layer)
            relative=str(target.relative_to(REPO))
            if not target.exists():
                raise ValueError(f'Missing selected home board: {relative}')
            actual=digest(target.read_bytes())
            allowed={approved_hashes.get(relative),previous_hashes.get(relative)}
            if actual not in allowed:
                raise ValueError(f'Native board has untracked manual edits: {relative}')
            project=target.with_suffix('.kicad_pro')
            if project.exists():
                current=digest(project.read_bytes())
                if current!=previous_project_hashes.get(str(project.relative_to(REPO))):
                    raise ValueError(f'Native project has untracked manual edits: {project}')
            planned.append((design,layer,target,project))
    assert len(planned)==43
    records=[]
    emitted=[]
    for design,layer,target,project in planned:
        name=board_id(design,layer)
        drills=export.drill_specs(layer,data['spec'])
        decorative=export.split_functional_holes(layer,drills)
        outline=Polygon(layer['outer'])
        edge_rings,edge_precision=native_edge_rings(
            [outline.exterior]+[p.exterior for p in decorative],
            (EDGE_DRC_CONTOUR_REPAIR_MM if name in EDGE_DRC_CONTOUR_REPAIR_BOARDS
             else EDGE_MIN_SEGMENT_MM),
            ({3:.0031} if name=='01-spider-nest-L03-gold-enig-fill' else None),
            ({1} if name in ('13-fault-line-L08-red-mask-only',
                             '18-woven-maze-L07-black-mask-only') else None))
        edge_precision['rotatedStartVertexRingIndices']=[]
        if name=='18-woven-maze-L08-white-mask-only':
            # KiCad 10's outline polygonizer reports a false intersection at
            # this aperture's original near-tangent starting vertex. Rotate
            # the closed contour seam to a smooth point. Every segment and
            # the routed geometry remain identical.
            points=export.ring_points(edge_rings[4])
            edge_rings[4]=LinearRing(points[50:]+points[:50])
            edge_precision['rotatedStartVertexRingIndices']=[4]
        if layer['finish']=='mask-only':
            copper=Polygon();mask=Polygon()
        else:
            mask=shapely.from_wkb(bytes.fromhex(by_mask[name]['afterMaskWkbHex']))
            copper=shapely.from_wkb(bytes.fromhex(by_copper[name]['afterCopperWkbHex']))
        cu_parts,cu_fragments,cu_precision=native_parts_with_precision_repair(copper)
        mask_parts,mask_fragments,mask_precision=native_parts_with_precision_repair(mask)
        if cu_fragments['areaMm2']>.00001 or mask_fragments['areaMm2']>.00001:
            raise ValueError(f'{name}: native polygon partition dropped non-grid art')
        native=export.native_board(name,layer,data['spec'],edge_rings,drills,cu_parts,mask_parts)
        native=native.replace('No exposed copper; quote non-ENIG finish separately',
                              'Lead-free HASL')
        export.check_sexpr(native)
        project_text=project_content(name)
        emitted.append((target,native,project,project_text))
        records.append({
            'boardId':name,
            'nativeBoard':str(target.relative_to(REPO)),
            'sha256':digest(native.encode()),
            'project':str(project.relative_to(REPO)),
            'projectSha256':digest(project_text.encode()),
            'edgeLoopCount':len(edge_rings),
            'edgePrecisionRepair':edge_precision,
            'npthRoundCount':sum(d['shape']=='circle' for d in drills),
            'npthSlotCount':sum(d['shape']=='oval' for d in drills),
            'nativeCopperPolygons':len(cu_parts),
            'nativeMaskPolygons':len(mask_parts),
            'copperPrecisionRepair':cu_precision,
            'maskPrecisionRepair':mask_precision,
            'copperSourceWkbSha256':digest(copper.wkb),
            'maskSourceWkbSha256':digest(mask.wkb),
        })
        print(name,records[-1]['nativeCopperPolygons'],
              records[-1]['nativeMaskPolygons'],flush=True)
    report={
        'status':'candidate; independent KiCad DRC/CAM and factory acceptance pending; exhaustive width certificate opt-in',
        'manufacturingGeometrySha256':digest(geom_path.read_bytes()),
        'maskCandidateSha256':digest(mask_path.read_bytes()),
        'copperCandidateSha256':digest(copper_path.read_bytes()),
        'copperLedgerSha256':digest(ledger_path.read_bytes()),
        'generatorSha256':digest(Path(__file__).read_bytes()),
        'selectedBoardCount':len(records),
        'boards':records,
    }
    for target,native,project,project_text in emitted:
        target.write_text(native)
        project.write_text(project_text)
    OUTPUT.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    run()
