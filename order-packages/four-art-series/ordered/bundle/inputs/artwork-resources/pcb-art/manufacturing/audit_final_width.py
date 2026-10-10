#!/usr/bin/env python3
"""Audit serialized positive/negative final-art width without granting passes."""
from __future__ import annotations

import json

import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from repair_mask_candidate import HERE, ROOT, board_id, digest, export, source_body

RADIUS=.124999  # 1 nm below the exact threshold avoids GEOS equality artifacts.


def source_features(layer,design):
    shapes=[]
    names=[]
    for index,stroke in enumerate(layer['art']['strokes']):
        shapes.append(export.stroke_geometry(stroke,design.get('artStyle')=='angular'))
        names.append({'type':'stroke','originalIndex0':index,'color':stroke.get('color')})
    for index,fill in enumerate(layer['art']['fills']):
        shapes.append(Polygon(fill['pts']))
        names.append({'type':'fill','originalIndex0':index,'color':fill.get('color')})
    return shapes,names


def width_screen(region,shapes,names,radius=RADIUS):
    eroded=region.buffer(-radius,join_style='mitre',quad_segs=64)
    reconstructed=eroded.buffer(radius,join_style='mitre',quad_segs=64)
    residue=region.difference(reconstructed)
    parts=export.polygons(region)
    cores=export.polygons(eroded)
    no_disk=[part for part in parts if part.area>1e-8 and
             part.buffer(-radius,quad_segs=64).is_empty]
    tree=STRtree(shapes) if shapes else None
    candidates=[]
    for part in sorted(export.polygons(residue),key=lambda p:p.area,reverse=True)[:20]:
        index=int(tree.nearest(part.representative_point())) if tree else None
        candidates.append({
            'areaMm2':round(part.area,9),
            'boundsMm':[round(v,6) for v in part.bounds],
            'nearestOriginalArtFeature':names[index] if index is not None else None,
        })
    return {
        'requestedWidthMm':round(radius*2+.000002,6),
        'componentCount':len(parts),
        'erodedCoreComponentCount':len(cores),
        'erodedCoreSplitExcessCount':max(0,len(cores)-len(parts)),
        'componentsWithoutRequestedWidthDisk':len(no_disk),
        'noDiskAreaMm2':round(sum(p.area for p in no_disk),9),
        'toleranceAwareMiterResidueAreaMm2':round(residue.area,9),
        'largestResidues':candidates,
    }


def run():
    geom_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    copper_path=HERE/'copper-repair-ledger.json'
    cache_path=HERE/'copper-repair-candidate.json'
    data=json.loads(geom_path.read_text())
    originals=json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    masks=json.loads(mask_path.read_text())
    copper_cache=json.loads(cache_path.read_text())
    mask_by={b['boardId']:b for b in masks['boards']}
    copper_by={b['boardId']:b for b in copper_cache['boards']}
    boards=[]
    for family,original_family in zip(data['designs'],originals['designs']):
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        original=(next(d for d in original_family['variants'] if d.get('variantId')=='wide')
                  if family['id']=='kumiko-void' else original_family)
        for layer,original_layer in zip(design['layers'],original['layers']):
            if layer['finish']=='mask-only':
                continue
            name=board_id(design,layer)
            body=source_body(layer,data['spec'])
            gold=shapely.from_wkb(bytes.fromhex(mask_by[name]['afterMaskWkbHex']))
            copper=shapely.from_wkb(bytes.fromhex(copper_by[name]['afterCopperWkbHex']))
            ink=body.difference(gold)
            copper_free=body.difference(copper)
            shapes,names=source_features(original_layer,original)
            boards.append({
                'boardId':name,
                'gold':width_screen(gold,shapes,names),
                'ink':width_screen(ink,shapes,names),
                'copper':width_screen(copper,shapes,names),
                'copperFreeAt010Mm':width_screen(copper_free,shapes,names,.049999),
                'copperFreeAt025Mm':width_screen(copper_free,shapes,names),
            })
            print(name,boards[-1]['gold']['toleranceAwareMiterResidueAreaMm2'],
                  boards[-1]['ink']['toleranceAwareMiterResidueAreaMm2'],flush=True)
    report={
        'status':'diagnostic; positive and negative connected-core screens; opposing-boundary width proof still required',
        'radiusMm':RADIUS,
        'copperFreeGeneralRadiusMm':.049999,
        'manufacturingGeometrySha256':digest(geom_path.read_bytes()),
        'maskCandidateSha256':digest(mask_path.read_bytes()),
        'copperLedgerSha256':digest(copper_path.read_bytes()),
        'boards':boards,
    }
    (HERE/'final-width-audit.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    run()
