#!/usr/bin/env python3
"""Build indexed hidden copper joins beneath the corrected visible artwork."""
from __future__ import annotations

import json

import shapely
from shapely.geometry import LineString
from shapely.ops import nearest_points, unary_union

from repair_mask_candidate import (HERE, board_id, digest, pairs, rounded,
                                   safe_region, source_body)


def run():
    geometry_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    data=json.loads(geometry_path.read_text())
    mask_report=json.loads(mask_path.read_text())
    if mask_report['sourceGeometrySha256']!=digest(geometry_path.read_bytes()):
        raise ValueError('Mask candidate does not match manufacturing geometry')
    masks={board['boardId']:board for board in mask_report['boards']}
    boards=[]
    for family in data['designs']:
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        for layer in design['layers']:
            if layer['finish']=='mask-only':
                continue
            name=board_id(design,layer)
            mask=shapely.from_wkb(bytes.fromhex(masks[name]['afterMaskWkbHex']))
            body=source_body(layer,data['spec'])
            safe=safe_region(layer,body,'copper')
            copper=rounded(mask.buffer(.05,quad_segs=64).intersection(safe))
            before=copper
            center_safe=safe.buffer(-.126,quad_segs=64)
            patches=[]
            records=[]
            for i,j,parts in pairs(before):
                a,b=nearest_points(parts[i],parts[j])
                direct_gap=a.distance(b)
                route='direct'
                bridge=LineString([a,b]).buffer(.1255,quad_segs=64)
                if bridge.difference(safe).area>.00001:
                    # The shortest straight chord can graze a Coral route.
                    # Move both anchors onto the admissible bridge-center
                    # region and keep the same pair-specific local join.
                    lhs=parts[i].intersection(center_safe)
                    rhs=parts[j].intersection(center_safe)
                    if lhs.is_empty or rhs.is_empty:
                        raise ValueError(f'{name}: no safe copper anchor at {i},{j}')
                    a,b=nearest_points(lhs,rhs)
                    bridge=LineString([a,b]).buffer(.1255,quad_segs=64)
                    route='inset anchors'
                if a.distance(b)>.60 or bridge.difference(safe).area>.00001:
                    raise ValueError(f'{name}: copper join exceeds reach or safe region at {i},{j}')
                if not bridge.intersects(parts[i]) or not bridge.intersects(parts[j]):
                    raise ValueError(f'{name}: copper join does not reach both components at {i},{j}')
                patches.append(bridge)
                records.append({
                    'operation':'hidden 0.251 mm copper join beneath retained mask',
                    'beforeFinishedUnionPairIndices0':[i,j],
                    'beforeComponentWkbSha256':[digest(parts[i].wkb),digest(parts[j].wkb)],
                    'beforeGapMm':round(direct_gap,9),
                    'route':route,
                    'centerlineMm':[[round(a.x,9),round(a.y,9)],
                                    [round(b.x,9),round(b.y,9)]],
                    'centerlineLengthMm':round(a.distance(b),9),
                    'nominalWidthMm':.251,
                    'patchBoundsMm':[round(v,6) for v in bridge.bounds],
                    'patchWkbSha256':digest(bridge.wkb),
                })
            if patches:
                copper=rounded(before.union(unary_union(patches)))
            if list(pairs(copper)):
                raise ValueError(f'{name}: copper still has a distinct-component gap')
            if copper.difference(safe).area>.00001:
                raise ValueError(f'{name}: copper exceeds its safe region')
            if mask.difference(copper).area>.00001:
                raise ValueError(f'{name}: mask opening lacks underlying copper')
            boards.append({
                'boardId':name,
                'beforeCopperWkbSha256':digest(before.wkb),
                'afterCopperWkbSha256':digest(copper.wkb),
                'beforeCopperAreaMm2':round(before.area,6),
                'afterCopperAreaMm2':round(copper.area,6),
                'joinCount':len(records),
                'insetAnchorJoinCount':sum(r['route']=='inset anchors' for r in records),
                'records':records,
                'afterCopperWkbHex':copper.wkb_hex,
            })
            print(f'{name}: {len(records)} hidden joins, '
                  f'{sum(r["route"]=="inset anchors" for r in records)} inset',flush=True)
    result={
        'status':'candidate; full copper/gold width and output proof pending',
        'sourceGeometrySha256':digest(geometry_path.read_bytes()),
        'maskCandidateSha256':digest(mask_path.read_bytes()),
        'policySha256':digest((HERE/'policy.json').read_bytes()),
        'gridMm':.000001,
        'boards':boards,
    }
    # The full positive copper polygons are a reproducible local intermediate.
    # Keep the much smaller indexed ledger and hashes in Git.
    (HERE/'copper-repair-candidate.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    compact={**result,
             'boards':[{k:v for k,v in board.items() if k!='afterCopperWkbHex'}
                       for board in boards]}
    (HERE/'copper-repair-ledger.json').write_text(json.dumps(compact,indent=2)+'\n')


if __name__=='__main__':
    run()
