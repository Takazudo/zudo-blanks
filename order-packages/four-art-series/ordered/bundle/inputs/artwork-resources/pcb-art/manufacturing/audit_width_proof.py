#!/usr/bin/env python3
"""Class-aware positive/negative width gate on the serialized final unions.

Uses the opposing-boundary width test in width_geometry. Classes come from
policy erratum process-classes-2026-09-25. A pass is a local geometric proof,
not factory acceptance.
"""
from __future__ import annotations

import json

import shapely
from shapely.geometry import Point
from shapely.strtree import STRtree

from audit_final_width import source_features
from repair_mask_candidate import HERE, ROOT, board_id, digest, export, source_body
from width_geometry import (TOLERANCE, chord_row, plane_complement, violations)

POURS={'01-spider-nest-L03-gold-enig-fill','01-spider-nest-L05-gold-enig-fill',
       '01-spider-nest-L07-gold-enig-fill','03-coral-vault-L04-gold-enig-fill'}


def is_general(bid,part,area_tolerance):
    return bid in POURS or (not part.interiors and
                            part.convex_hull.difference(part).area<=area_tolerance)


def locate(found,phase,width,tree,names,shapes):
    rows=[]
    for piece,chords in found:
        row=chord_row(phase,width,piece,chords)
        mid=Point(chords[0]['mid'])
        index=tree.nearest(mid) if shapes else None
        row['nearestSourceFeature']=None if index is None else names[int(index)]
        row['nearestSourceDistanceMm']=None if index is None else round(shapes[int(index)].distance(mid),6)
        rows.append(row)
    return rows


def audit_board(bid,body,gold,copper,shapes,names,area_tolerance):
    tree=STRtree(shapes) if shapes else None
    black=.25 if bid.startswith('01-spider-nest-') else .13
    failures=locate(violations(gold,.25),'visible-gold',.25,tree,names,shapes)
    failures+=locate(violations(plane_complement(body,gold),black),'black-ink',black,tree,names,shapes)
    parts=export.polygons(copper)
    general=[p for p in parts if is_general(bid,p,area_tolerance)]
    special=[p for p in parts if not is_general(bid,p,area_tolerance)]
    for group,width in ((general,.10),(special,.25)):
        for part in group:
            failures+=locate(violations(part,width),'copper',width,tree,names,shapes)
    free=plane_complement(body,copper)
    narrow=violations(free,.10)
    failures+=locate(narrow,'copper-free',.10,tree,names,shapes)
    if special:
        near=shapely.union_all([p.buffer(TOLERANCE*2) for p in special])
        wide=[]
        for piece,chords in violations(free,.25):
            kept=[c for c in chords if c['lengthMm']>=.10-TOLERANCE and
                  (near.contains(Point(c['a'])) or near.contains(Point(c['b'])))]
            if kept:
                wide.append((piece,kept))
        failures+=locate(wide,'copper-free',.25,tree,names,shapes)
    counts={}
    for row in failures:
        key=f"{row['phase']}@{row['widthMm']}"
        counts[key]=counts.get(key,0)+1
    return {'boardId':bid,'blackInkWidthMm':black,'generalCopperComponents':len(general),
            'specialCopperComponents':len(special),'failureCounts':counts,
            'passed':not failures,'failures':failures}


def run():
    geom_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    copper_path=HERE/'copper-repair-candidate.json'
    data=json.loads(geom_path.read_text())
    policy=json.loads((HERE/'policy.json').read_text())
    area_tolerance=policy['rulesMm']['numericAreaTolerance']
    originals=json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    mask_by={b['boardId']:b for b in json.loads(mask_path.read_text())['boards']}
    copper_by={b['boardId']:b for b in json.loads(copper_path.read_text())['boards']}
    boards=[]
    for family,original_family in zip(data['designs'],originals['designs']):
        pick=lambda f:(next(d for d in f['variants'] if d.get('variantId')=='wide')
                       if f['id']=='kumiko-void' else f)
        design,original=pick(family),pick(original_family)
        for layer,original_layer in zip(design['layers'],original['layers']):
            if layer['finish']=='mask-only':
                continue
            bid=board_id(design,layer)
            body=source_body(layer,data['spec'])
            gold=shapely.from_wkb(bytes.fromhex(mask_by[bid]['afterMaskWkbHex']))
            copper=shapely.from_wkb(bytes.fromhex(copper_by[bid]['afterCopperWkbHex']))
            shapes,names=source_features(original_layer,original)
            boards.append(audit_board(bid,body,gold,copper,shapes,names,area_tolerance))
            print(bid,boards[-1]['failureCounts'] or 'PASS',flush=True)
    report={'status':'class-aware opening gate; a pass is a local geometric proof, not factory acceptance',
            'toleranceMm':TOLERANCE,'policyErratum':'process-classes-2026-09-25',
            'manufacturingGeometrySha256':digest(geom_path.read_bytes()),
            'maskCandidateSha256':digest(mask_path.read_bytes()),
            'copperCandidateSha256':digest(copper_path.read_bytes()),
            'passed':all(b['passed'] for b in boards),'boards':boards}
    (HERE/'width-proof.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    run()
