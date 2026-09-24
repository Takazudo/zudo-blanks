#!/usr/bin/env python3
"""Index local mask retreats against the separate manufacturing geometry.

The result is a candidate until full width, copper, visual and native gates pass.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
module=importlib.util.spec_from_file_location('export_reference',ROOT/'tools/export_kicad.py')
export=importlib.util.module_from_spec(module)
module.loader.exec_module(export)
GRID=.000001


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rounded(geom):
    return shapely.set_precision(geom,GRID)


def pairs(geom):
    parts=export.ordered(geom)
    tree=STRtree(parts)
    for i,p in enumerate(parts):
        for j in tree.query(p.buffer(.25)):
            j=int(j)
            if j>i and p.distance(parts[j])<.249999:
                yield i,j,parts


def board_id(design,layer):
    variant=('-'+design['variantId']) if design.get('variantId') else ''
    return (f'{int(design["number"]):02d}-{design["id"]}{variant}-'
            f'L{layer["index"]+1:02d}-{layer["colorKey"]}-{layer["finish"]}')


def source_body(layer,spec):
    drills=export.drill_specs(layer,spec)
    cut=export.split_functional_holes(layer,drills)
    return Polygon(layer['outer']).difference(unary_union(cut)).difference(
        unary_union([export.drill_shape(d) for d in drills]))


def merge_spider_web_slivers(design,layer,body,mask,records):
    """Apply only the three measured guide-to-web channel joins.

    The channels have no original black paint. The selected closing patches
    touch both members of an indexed pair; every other closing patch is
    rejected, including unrelated narrow gaps elsewhere on the board.
    """
    if design['id']!='spider-nest' or layer['index']!=0:
        return mask
    if any(item.get('color') for key in ('fills','strokes') for item in layer['art'][key]):
        raise ValueError('Spider web merge would cover explicitly painted black art')
    parts=export.ordered(mask)
    measured={(0,1):.034614,(0,5):.044372,(0,2):.002574}
    source_strokes={(0,1):[41,111],(0,5):[33,97],(0,2):[38,112]}
    for (i,j),expected in measured.items():
        if abs(parts[i].distance(parts[j])-expected)>.001:
            raise ValueError(f'Spider indexed channel {i},{j} changed unexpectedly')
    closing=mask.buffer(.1255,quad_segs=64).buffer(-.1255,quad_segs=64)
    selected=[]
    for patch in export.ordered(closing.difference(mask)):
        matching=[list(pair) for pair in measured if patch.distance(parts[pair[0]])<.00001
                  and patch.distance(parts[pair[1]])<.00001]
        if matching:
            selected.append((patch,matching))
    if len(selected)!=4:
        raise ValueError(f'Spider requires exactly four indexed channel patches, found {len(selected)}')
    safe=body.buffer(-.35,quad_segs=64)
    additions=rounded(unary_union([p for p,_ in selected]).intersection(safe).difference(mask))
    if not 29.8<=additions.area<=30.0:
        raise ValueError(f'Spider web merge area changed: {additions.area}')
    for patch,matching in selected:
        records.append({
            'operation':'measured Spider guide-to-web mask merge; no original black paint',
            'originalFinishedUnionPairs0':matching,
            'sourceArtStrokePairs0':[source_strokes[tuple(pair)] for pair in matching],
            'closingRadiusMm':.1255,
            'sourceGapMm':[measured[tuple(pair)] for pair in matching],
            'patchBoundsMm':[round(v,6) for v in patch.bounds],
            'patchAreaMm2':round(patch.area,9),
            'patchWkbSha256':digest(patch.wkb),
            'patchWkbHex':patch.wkb_hex,
        })
    result=rounded(mask.union(additions))
    if list(pairs(result)):
        raise ValueError('Spider indexed channel merge left a narrow black web')
    if result.difference(safe).area>.00001:
        raise ValueError('Spider indexed channel merge exceeded mask safe region')
    return result


def corrected_mask(design,layer,spec,original_layer,actions):
    body=source_body(layer,spec)
    gold=export.paint_gold(layer,design,body)
    mask=gold.intersection(body.buffer(-.35,quad_segs=64))
    closed=[]
    if design['id']=='kumiko-void':
        for action in actions:
            if action['layerNumber']==layer['index']+1:
                closed.append(Polygon(original_layer['holes'][action['geometryHoleIndex0']]))
    if closed:
        mask=mask.difference(unary_union(closed))
    baseline=rounded(mask)
    rim_strokes=[s for s in layer['art']['strokes'] if s.get('purpose')=='top-gold-border']
    protected=unary_union([export.stroke_geometry(dict(s,w=.25),design.get('artStyle')=='angular')
                           for s in rim_strokes]) if rim_strokes else Polygon()
    records=[]
    mask=merge_spider_web_slivers(design,layer,body,baseline,records)
    for iteration in range(16):
        tiny=[]
        for i,part in enumerate(export.ordered(mask)):
            if part.buffer(-.125,quad_segs=64).is_empty:
                tiny.append(part)
                records.append({
                    'operation':'remove isolated gold component with no admissible 0.25 mm disk',
                    'iteration':iteration,
                    'originalFinishedUnionComponentIndex0':i,
                    'originalComponentWkbSha256':digest(part.wkb),
                    'removedComponentWkbHex':part.wkb_hex,
                    'boundsMm':[round(v,6) for v in part.bounds],
                    'areaMm2':round(part.area,9),
                })
        if tiny:
            mask=rounded(mask.difference(rounded(unary_union(tiny))))
            if protected.difference(mask).area>.00001:
                raise ValueError(f'{board_id(design,layer)}: necessary-width cleanup damaged a rim core')
        close=list(pairs(mask))
        print(f'{board_id(design,layer)}: mask pass {iteration}: {len(close)} close pairs',flush=True)
        if not close:
            break
        patches=[]
        for i,j,parts in close:
            p,q=parts[i],parts[j]
            a,b=nearest_points(p,q)
            mid=Point((a.x+b.x)/2,(a.y+b.y)/2)
            choices=[]
            for side,source,neighbor in (('A',p,q),('B',q,p)):
                near=rounded(neighbor.buffer(.251,quad_segs=64))
                patch=rounded(source.intersection(near))
                if patch.is_empty:
                    continue
                remainder=source.difference(patch)
                choices.append((patch.intersection(protected).area>.00001,
                                remainder.is_empty,len(export.polygons(remainder))>1,
                                patch.area,side,patch))
            if not choices:
                raise ValueError(f'{board_id(design,layer)}: no local retreat for pair {i},{j}')
            choices.sort(key=lambda choice:choice[:4])
            rim_hit,deleted,split,_,side,patch=choices[0]
            if rim_hit or deleted or split:
                raise ValueError(f'{board_id(design,layer)}: retreat changes protected topology at {i},{j}')
            patches.append(patch)
            records.append({
                'operation':'one-sided local mask retreat',
                'iteration':iteration,
                'finishedUnionPairIndices0':[i,j],
                'retreatSide':side,
                'beforeGapMm':round(p.distance(q),9),
                'beforeClosestPointsMm':[[round(a.x,9),round(a.y,9)],
                                         [round(b.x,9),round(b.y,9)]],
                'localCenterMm':[round(mid.x,9),round(mid.y,9)],
                'patchBoundsMm':[round(v,6) for v in patch.bounds],
                'patchAreaMm2':round(patch.area,9),
                'patchWkbSha256':digest(patch.wkb),
                'patchWkbHex':patch.wkb_hex,
            })
        next_mask=rounded(mask.difference(rounded(unary_union(patches))))
        if next_mask.equals(mask):
            raise ValueError(f'{board_id(design,layer)}: mask retreat stalled')
        mask=next_mask
        if protected.difference(mask).area>.00001:
            raise ValueError(f'{board_id(design,layer)}: mask retreat damaged a rim core')
    else:
        raise ValueError(f'{board_id(design,layer)}: mask retreat did not converge')
    if list(pairs(mask)):
        raise ValueError(f'{board_id(design,layer)}: unresolved mask pairs')
    if any(part.buffer(-.125,quad_segs=64).is_empty for part in export.polygons(mask)):
        raise ValueError(f'{board_id(design,layer)}: mask component lacks a 0.25 mm disk')
    return baseline,mask,records


def run():
    policy=json.loads((HERE/'policy.json').read_text())
    geometry_path=HERE/'manufacturing-geometry.json'
    data=json.loads(geometry_path.read_text())
    original=json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    review=json.loads((ROOT/'validation/export-art-review.json').read_text())
    boards=[]
    for family,source_family in zip(data['designs'],original['designs']):
        design=(family['variants'][0] if family['id']=='kumiko-void' else family)
        source=(source_family['variants'][0] if family['id']=='kumiko-void' else source_family)
        for layer,original_layer in zip(design['layers'],source['layers']):
            if layer['finish']=='mask-only':
                continue
            before,after,records=corrected_mask(design,layer,data['spec'],original_layer,
                                                 policy['selectedApertureActions'])
            old_review=next(b for b in review['boards'] if b['boardId']==board_id(design,layer))
            patch_shapes=[(index,shapely.from_wkb(bytes.fromhex(record['patchWkbHex'])))
                          for index,record in enumerate(records) if 'patchWkbHex' in record]
            removed_shapes=[(index,shapely.from_wkb(bytes.fromhex(record['removedComponentWkbHex'])))
                            for index,record in enumerate(records) if 'removedComponentWkbHex' in record]
            dispositions=[]
            for issue in old_review['blackMaskGapsBelow013Mm']:
                a,b=issue['closestPointsMm']
                mid=Point((a[0]+b[0])/2,(a[1]+b[1])/2)
                near_patches=[index for index,shape in patch_shapes if shape.distance(mid)<=.5]
                near_removed=[index for index,shape in removed_shapes if shape.distance(mid)<=.5]
                dispositions.append({
                    'key':f'art:{old_review["sourceSha256"]}:{board_id(design,layer)}:F.Mask black gap:{issue["polygonIndices0"][0]}:{issue["polygonIndices0"][1]}',
                    'sourceExportSha256':old_review['sourceSha256'],
                    'originalPolygonIndices0':issue['polygonIndices0'],
                    'originalClosestPointsMm':issue['closestPointsMm'],
                    'originalGapMm':issue['gapMm'],
                    'nearbyMaskPatchRecordIndices0':near_patches,
                    'nearbyRemovedComponentRecordIndices0':near_removed,
                    'finishedUnionPairScreen':'pass: no distinct mask component gap below 0.25 mm',
                })
            original_gold=export.paint_gold(original_layer,source,source_body(original_layer,data['spec']))
            loss=original_gold.difference(after).area/original_gold.area if original_gold.area else 0
            if loss>.30+1e-8:
                raise ValueError(f'{board_id(design,layer)}: gold-loss budget exceeded: {loss}')
            reconstructed=after.buffer(-.125,quad_segs=64).buffer(.125,quad_segs=64)
            width_residue=after.difference(reconstructed).area
            miter_reconstructed=after.buffer(-.125,join_style='mitre',quad_segs=64).buffer(
                .125,join_style='mitre',quad_segs=64)
            miter_residue=after.difference(miter_reconstructed).area
            boards.append({
                'boardId':board_id(design,layer),
                'originalGoldAreaMm2':round(original_gold.area,6),
                'beforeLocalRetreatAreaMm2':round(before.area,6),
                'afterLocalRetreatAreaMm2':round(after.area,6),
                'goldAddedFromApprovedMm2':round(after.difference(original_gold).area,6),
                'goldRemovedFromApprovedMm2':round(original_gold.difference(after).area,6),
                'goldLossFractionFromApproved':round(loss,9),
                'widthResidueAreaMm2':round(width_residue,6),
                'miterWidthResidueAreaMm2':round(miter_residue,6),
                'withinComponentGoldWidthProven':width_residue<=.00001,
                'retreatCount':sum(r['operation']=='one-sided local mask retreat' for r in records),
                'removedNoDiskComponents':sum(r['operation'].startswith('remove isolated') for r in records),
                'afterMaskWkbHex':after.wkb_hex,
                'records':records,
                'originalMaskFindingDispositions':dispositions,
            })
            print(f'{board_id(design,layer)}: {len(records)} indexed edits, {loss:.3%} original-gold loss',flush=True)
    result={
        'status':'candidate; copper joins, full width proof, visual review and native output pending',
        'sourceGeometrySha256':digest(geometry_path.read_bytes()),
        'policySha256':digest((HERE/'policy.json').read_bytes()),
        'gridMm':GRID,
        'boards':boards,
    }
    (HERE/'mask-repair-candidate.json').write_text(json.dumps(result,separators=(',', ':'))+'\n')


if __name__=='__main__':
    run()
