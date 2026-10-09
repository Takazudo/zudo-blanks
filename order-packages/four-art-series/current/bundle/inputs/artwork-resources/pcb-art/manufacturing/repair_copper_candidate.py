#!/usr/bin/env python3
"""Build indexed hidden copper joins beneath the corrected visible artwork."""
from __future__ import annotations

import json

import shapely
from shapely.geometry import LineString
from shapely.ops import nearest_points, unary_union

from repair_mask_candidate import (HERE, export, board_id, digest, pairs, rounded,
                                   safe_region, source_body)


def _board(job):
    name,mask_hex,layer,spec=job
    mask=shapely.from_wkb(bytes.fromhex(mask_hex))
    body=source_body(layer,spec)
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
        # Point-touching components have a zero-length chord.
        bridge=(a.buffer(.1255,quad_segs=64) if direct_gap<1e-9 else
                LineString([a,b]).buffer(.1255,quad_segs=64))
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
        if a.distance(b)>.60:
            raise ValueError(f'{name}: copper join exceeds reach or safe region at {i},{j}')
        outside=bridge.difference(safe).area
        if outside>.00001:
            # A buffered centerline can graze a routed edge even with both
            # inset anchors legal. Clip only a small fringe, and retain a
            # single connected, pair-specific patch. Final copper width is
            # checked again on the complete serialized union.
            if outside>.002 or outside/bridge.area>.02:
                raise ValueError(f'{name}: copper join exceeds reach or safe region at {i},{j}')
            bridge=rounded(bridge.intersection(safe))
            if len(export.polygons(bridge))!=1:
                raise ValueError(f'{name}: clipped copper join is disconnected at {i},{j}')
            route='safe-clipped inset anchors'
        if not bridge.intersects(parts[i]) or not bridge.intersects(parts[j]):
            raise ValueError(f'{name}: copper join does not reach both components at {i},{j}')
        patches.append(bridge)
        records.append({
            'operation':'hidden 0.251 mm copper join beneath retained mask',
            'beforeFinishedUnionPairIndices0':[i,j],
            'beforeComponentWkbSha256':[digest(parts[i].wkb),digest(parts[j].wkb)],
            'beforeGapMm':round(direct_gap,9),
            'route':route,
            'safetyClipAreaMm2':round(outside,9),
            'centerlineMm':[[round(a.x,9),round(a.y,9)],
                            [round(b.x,9),round(b.y,9)]],
            'centerlineLengthMm':round(a.distance(b),9),
            'nominalWidthMm':.251,
            'patchBoundsMm':[round(v,6) for v in bridge.bounds],
            'patchWkbSha256':digest(bridge.wkb),
        })
    if patches:
        copper=rounded(before.union(unary_union(patches)))
    # Copper must extend 0.05 mm past every gold opening, so a legal
    # black web leaves a copper-free gap 0.10 mm narrower. Fill such
    # gaps with hidden copper beneath the retained mask (a closing at
    # the 0.25 mm special-class gap), confined to the copper safe region.
    closed=copper.buffer(.1255,quad_segs=64).buffer(-.1255,quad_segs=64)
    fill=rounded(closed.difference(copper).intersection(safe))
    # Sub-micron fill specks are optional hidden additions; skipping
    # them avoids detached numerical fragments after grid rounding.
    fills=[part for part in shapely.get_parts(fill)
           if part.geom_type=='Polygon' and part.area>1e-6]
    fill=unary_union(fills) if fills else shapely.Polygon()
    if fill.intersection(mask).area>.00001:
        raise ValueError(f'{name}: hidden channel fill touches a gold opening')
    if fills:
        merged=export.polygons(rounded(copper.union(fill)))
        # A piece with no gold opening over it can only be a detached
        # fill fragment (e.g. touching at a single point); drop it.
        copper=rounded(unary_union([part for part in merged
                                    if part.intersects(mask)]))
    channel_fill={'pieceCount':len(fills),'areaMm2':round(fill.area,9),
                  'largestPieces':[{'areaMm2':round(part.area,9),
                                    'boundsMm':[round(v,6) for v in part.bounds]}
                                   for part in sorted(fills,key=lambda q:-q.area)[:20]],
                  'fillWkbSha256':digest(fill.wkb)}
    # Close sub-micron notches left by grid rounding (1 um, inside the
    # 0.001 mm distance tolerance); copper is hidden beneath the mask.
    copper=rounded(copper.buffer(.001,quad_segs=8).buffer(-.001,quad_segs=8)
                   .intersection(safe).union(copper))
    from width_geometry import enforce_copper
    required=rounded(mask.buffer(.05,quad_segs=64).intersection(safe))
    copper,width_records,copper_unresolved=enforce_copper(copper,required,safe,body,name)
    leftover=list(pairs(copper))
    if leftover:
        for i,j,parts in leftover:
            a,b=nearest_points(parts[i],parts[j])
            print('LEFTOVER',name,round(a.distance(b),6),a.wkt,parts[i].area,parts[j].area,flush=True)
        raise ValueError(f'{name}: copper still has a distinct-component gap')
    if copper.difference(safe.buffer(.000001)).area>.00001:
        raise ValueError(f'{name}: copper exceeds its safe region')
    if mask.difference(copper).area>.00001:
        raise ValueError(f'{name}: mask opening lacks underlying copper')
    board={
        'boardId':name,
        'beforeCopperWkbSha256':digest(before.wkb),
        'afterCopperWkbSha256':digest(copper.wkb),
        'beforeCopperAreaMm2':round(before.area,6),
        'afterCopperAreaMm2':round(copper.area,6),
        'joinCount':len(records),
        'hiddenChannelFill':channel_fill,
        'copperWidthEdits':width_records,
        'unresolvedCopperWidthFailures':copper_unresolved,
        'insetAnchorJoinCount':sum(r['route']!='direct' for r in records),
        'records':records,
        'afterCopperWkbHex':copper.wkb_hex,
    }
    print(f'{name}: {len(records)} hidden joins, '
          f'{sum(r["route"]!="direct" for r in records)} inset',flush=True)
    return board


def run():
    geometry_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    data=json.loads(geometry_path.read_text())
    mask_report=json.loads(mask_path.read_text())
    if mask_report['sourceGeometrySha256']!=digest(geometry_path.read_bytes()):
        raise ValueError('Mask candidate does not match manufacturing geometry')
    masks={board['boardId']:board for board in mask_report['boards']}
    jobs=[]
    for family in data['designs']:
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        for layer in design['layers']:
            if layer['finish']=='mask-only':
                continue
            jobs.append((board_id(design,layer),masks[board_id(design,layer)]['afterMaskWkbHex'],
                         layer,data['spec']))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=3) as pool:
        boards=list(pool.map(_board,jobs))
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
