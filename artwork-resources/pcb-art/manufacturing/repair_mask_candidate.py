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
from shapely.geometry import LineString, Point, Polygon, box
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


def safe_region(layer,body,art_layer):
    setback=.35 if art_layer=='mask' else .30
    safe=body.buffer(-setback,quad_segs=64)
    if layer['index']>0:
        outer_setback=.55 if art_layer=='mask' else .50
        safe=safe.intersection(Polygon(layer['outer']).buffer(-outer_setback,
            join_style='mitre'))
    return safe


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
    policy=json.loads((HERE/'policy.json').read_text())
    rule=next(item for item in policy['errata'] if item['id']==
              'spider-l01-channel-merge-2026-09-25')
    evidence=json.loads((HERE/rule['evidence']).read_text())
    normalized_hash=digest(shapely.normalize(mask).wkb)
    example=evidence['implementationExample']
    rib_local=False
    network_local=False
    if normalized_hash!=example['preMergeMaskNormalizedWkbSha256']:
        network_rule=next(item for item in policy['errata'] if item['id']==
                          'spider-l01-unfiltered-network-2026-09-25')
        if digest((HERE/network_rule['evidence']).read_bytes())!=network_rule['evidenceSha256']:
            raise ValueError('Spider network decision evidence hash changed')
        network_decision=json.loads((HERE/network_rule['evidence']).read_text())
        stage=json.loads((HERE/'spider-prior-stage.json').read_text())
        if stage['priorChannelEvidenceSha256']!=digest((HERE/rule['evidence']).read_bytes()):
            raise ValueError('Captured pre-rib implementation evidence changed')
        prior=shapely.from_wkb(bytes.fromhex(stage['preRibMaskWkbHex']))
        if digest(shapely.normalize(prior).wkb)!=example[
                'preMergeMaskNormalizedWkbSha256']:
            raise ValueError('Captured pre-rib Spider mask hash changed')
        ribbon=unary_union([LineString(path['pointsMm']).buffer(
            network_rule['ribbonWidthMm']/2,cap_style='flat',join_style='mitre')
            for path in network_decision['paths']])
        captured_body=shapely.from_wkb(bytes.fromhex(evidence['candidateBodyWkbHex']))
        if (captured_body.difference(body).area>.00001 or
                body.difference(captured_body).area>network_rule['maximumCombinedAdditionAreaMm2']):
            raise ValueError('Spider body differs beyond bounded network addition')
        if shapely.set_precision(mask,.000001).symmetric_difference(
                shapely.set_precision(prior,.000001)).difference(
                    ribbon.buffer(.500001)).area>.00001:
            raise ValueError('Spider pre-merge mask changed outside network/guide envelope')
        rib_local=True
        network_local=True
    parts=export.ordered(mask)
    measured={(0,1):.034614,(0,5):.044372,(0,2):.002574}
    source_strokes={(0,1):[41,111],(0,5):[33,97],(0,2):[38,112]}
    for (i,j),expected in measured.items():
        if abs(parts[i].distance(parts[j])-expected)>.001:
            raise ValueError(f'Spider indexed channel {i},{j} changed unexpectedly')
    selected=[]
    if rib_local:
        selected=[(shapely.from_wkb(bytes.fromhex(item['wkbHex'])),
                   [item['componentIndices0']])
                  for item in example['patches']]
    else:
        closing=mask.buffer(.1255,quad_segs=64).buffer(-.1255,quad_segs=64)
        for patch in export.ordered(closing.difference(mask)):
            matching=[list(pair) for pair in measured if patch.distance(parts[pair[0]])<.00001
                      and patch.distance(parts[pair[1]])<.00001]
            if matching:
                selected.append((patch,matching))
    if len(selected)!=4:
        raise ValueError(f'Spider requires exactly four indexed channel patches, found {len(selected)}')
    example_hashes={item['normalizedWkbSha256'] for item in example['patches']}
    selected_hashes={digest(shapely.normalize(patch).wkb) for patch,_ in selected}
    if selected_hashes!=example_hashes:
        raise ValueError('Spider channel patches differ from bounded erratum envelope')
    safe=safe_region(layer,body,'mask')
    additions=rounded(unary_union([p for p,_ in selected]).intersection(safe).difference(mask))
    if not 29.8<=additions.area<=rule['maximumTotalAddedGoldAreaMm2']:
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
    if rib_local and not network_local:
        # Two enclosed black channels terminate as sub-width pointed pockets
        # inside the newly widened rib. Round only those source-indexed ends;
        # an open third channel continues beyond the authorized rib envelope.
        indexed_ink=[
            ([7,101],4.99588643,[56.373370,44.149271,73.585645,54.659973]),
            ([8,103],2.896711386,[55.864859,48.388865,65.869368,54.832917]),
        ]
        ink_parts=export.polygons(body.difference(result))
        terminal_patches=[]
        for strokes,expected_area,bounds in indexed_ink:
            found=[part for part in ink_parts if abs(part.area-expected_area)<.00001
                   and max(abs(a-b) for a,b in zip(part.bounds,bounds))<.001]
            if len(found)!=1:
                raise ValueError(f'Spider indexed terminal channel {strokes} changed')
            channel=found[0]
            rounded_ink=channel.buffer(-.125,quad_segs=64).buffer(.125,quad_segs=64)
            patch=channel.difference(rounded_ink)
            if patch.difference(ribbon.buffer(.5)).area>.00001:
                raise ValueError('Spider terminal cap exceeded rib/guide envelope')
            terminal_patches.append(patch)
            records.append({
                'operation':'round bounded Spider enclosed channel terminal',
                'sourceArtStrokeIndices0':strokes,
                'beforeInkAreaMm2':round(channel.area,9),
                'beforeInkBoundsMm':[round(v,6) for v in channel.bounds],
                'terminalCapAreaMm2':round(patch.area,9),
                'terminalCapWkbSha256':digest(patch.wkb),
            })
        terminal_additions=unary_union(terminal_patches).difference(result)
        if abs(terminal_additions.area-.215574956)>.0001:
            raise ValueError('Spider indexed terminal cap area changed')
        result=rounded(result.union(terminal_additions))
    if rib_local:
        prior_final=shapely.from_wkb(bytes.fromhex(stage['preRibFinalMaskWkbHex']))
        if digest(prior_final.wkb)!=stage['preRibFinalMaskWkbSha256']:
            raise ValueError('Captured pre-rib final Spider mask hash changed')
        if shapely.set_precision(result,.000001).symmetric_difference(
                shapely.set_precision(prior_final,.000001)).difference(
                    ribbon.buffer(.500001)).area>.00001:
            raise ValueError('Spider final mask changed outside rib/guide envelope')
    if list(pairs(result)):
        raise ValueError('Spider indexed channel merge left a narrow black web')
    if result.difference(safe).area>.00001:
        raise ValueError('Spider indexed channel merge exceeded mask safe region')
    return result


def rim_cores(design,layer):
    rim_strokes=[s for s in layer['art']['strokes'] if s.get('purpose')=='top-gold-border']
    return unary_union([export.stroke_geometry(dict(s,w=.25),design.get('artStyle')=='angular')
                        for s in rim_strokes]) if rim_strokes else Polygon()


def corrected_mask(design,layer,spec,original_layer,actions):
    body=source_body(layer,spec)
    gold=export.paint_gold(layer,design,body)
    mask=gold.intersection(safe_region(layer,body,'mask'))
    closed=[]
    if design['id']=='kumiko-void':
        for action in actions:
            if action['layerNumber']==layer['index']+1:
                closed.append(Polygon(original_layer['holes'][action['geometryHoleIndex0']]))
    if closed:
        mask=mask.difference(unary_union(closed))
    baseline=rounded(mask)
    protected=rim_cores(design,layer)
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
    if design['id']=='coral-vault' and layer['index']==0:
        if any(item.get('color') for key in ('fills','strokes')
               for item in original_layer['art'][key]):
            raise ValueError('Coral rim island merge would cover explicit black paint')
        mask=shapely.from_wkb(mask.wkb)
        safe=safe_region(layer,body,'mask')
        rim=unary_union([export.stroke_geometry(stroke,False)
                         for stroke in layer['art']['strokes']
                         if stroke.get('purpose')=='top-gold-border'
                         and stroke.get('feature')=='perimeter'])
        negative=body.difference(mask)
        islands=[part for part in export.polygons(negative)
                 if part.area>1e-8 and part.buffer(-.125,quad_segs=64).is_empty]
        if len(islands)!=19 or abs(sum(p.area for p in islands)-1.039835068)>.00001:
            raise ValueError('Coral indexed rim-ink island inventory changed')
        if any(p.distance(rim)>.00001 or p.difference(safe).area>.00001 for p in islands):
            raise ValueError('Coral rim-ink island exceeds bounded merge envelope')
        source_strokes=[export.stroke_geometry(stroke,False)
                        for stroke in original_layer['art']['strokes']]
        source_tree=STRtree(source_strokes)
        before_parts=len(export.polygons(mask))
        for island in islands:
            index=int(source_tree.nearest(island.representative_point()))
            records.append({
                'operation':'merge isolated unpainted Coral rim-to-motif ink island',
                'originalArtStrokeIndex0':index,
                'originalStrokeWkbSha256':digest(source_strokes[index].wkb),
                'islandBoundsMm':[round(v,6) for v in island.bounds],
                'islandAreaMm2':round(island.area,9),
                'patchWkbSha256':digest(island.wkb),
                'patchWkbHex':island.wkb_hex,
            })
        mask=shapely.from_wkb(rounded(mask.union(unary_union(islands))).wkb)
        if len(export.polygons(mask))!=before_parts or list(pairs(mask)):
            raise ValueError('Coral bounded rim merge changed gold connectivity or mask webs')
        if mask.difference(safe.buffer(.001,quad_segs=64)).area>.00001:
            raise ValueError('Coral bounded rim merge exceeded mask safe region')
        # The remaining connecting neck is a clipped junction between source
        # strokes 527 and 524. Add a local full-width corridor instead of
        # erasing its .0297 mm² terminal wedge and splitting the motif.
        neck_source_indices=[527,524]
        neck_centerline=[
            [25.3511,47.2707],[25.187917048,47.709979042],
            [25.363853787,47.814617010],[25.474788655,47.880595266],
            [25.499200911,47.895114399],[25.920567358,48.143364159],
            [25.9875,48.1612],[26.5305,48.2218],
        ]
        center_safe=body.buffer(-.4765,quad_segs=64)
        projected=[]
        for x,y in neck_centerline:
            point=Point(x,y)
            if center_safe.covers(point):
                projected.append([x,y])
            else:
                _,nearest=nearest_points(point,center_safe)
                projected.append([round(nearest.x,9),round(nearest.y,9)])
        corridor=LineString(projected).buffer(.1255,quad_segs=64)
        patch=rounded(corridor.intersection(safe).difference(mask))
        sources=unary_union([source_strokes[i] for i in neck_source_indices])
        if (patch.difference(sources.buffer(.5,quad_segs=64)).area>.00001 or
                abs(patch.area-.058779889)>.0001):
            raise ValueError(f'Coral neck corridor exceeded indexed envelope: {patch.area}')
        before_parts=len(export.polygons(mask))
        mask=shapely.from_wkb(rounded(mask.union(patch)).wkb)
        if len(export.polygons(mask))!=before_parts or list(pairs(mask)):
            raise ValueError('Coral neck corridor changed gold connectivity or mask webs')
        if protected.difference(mask).area>.00001:
            raise ValueError('Coral neck corridor damaged top-rim core')
        records.append({
            'operation':'add indexed Coral 527/524 full-width gold neck corridor',
            'originalArtStrokeIndices0':neck_source_indices,
            'originalStrokeWkbSha256':[digest(source_strokes[i].wkb)
                                       for i in neck_source_indices],
            'centerlineMm':projected,
            'nominalWidthMm':.251,
            'patchBoundsMm':[round(v,6) for v in patch.bounds],
            'patchAreaMm2':round(patch.area,9),
            'patchWkbSha256':digest(patch.wkb),
            'patchWkbHex':patch.wkb_hex,
        })
    if design['id']=='fault-line' and layer['index']==0:
        mask=shapely.from_wkb(mask.wkb)
        source_strokes=[export.stroke_geometry(stroke,design.get('artStyle')=='angular')
                        for stroke in original_layer['art']['strokes']]
        source_tree=STRtree(source_strokes)
        original_parts=len(export.polygons(mask))
        original_pockets=sum(len(p.interiors) for p in export.polygons(mask))
        for iteration in range(3):
            # A 1 nm inset avoids declaring the twelve exact-0.25 mm source
            # strokes vanished solely because of GEOS threshold rounding.
            radius=.124999
            reconstructed=mask.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
                radius,join_style='mitre',quad_segs=64)
            residue=mask.difference(reconstructed)
            if residue.area<=.00001:
                break
            tips=[part for part in export.polygons(residue) if part.area>1e-8]
            if not tips:
                raise ValueError('Fault sub-width terminal residue has no indexable patches')
            for tip in tips:
                index=int(source_tree.nearest(tip.representative_point()))
                records.append({
                    'operation':'cap indexed Fault terminal gold wedge',
                    'iteration':iteration,
                    'originalArtStrokeIndex0':index,
                    'originalStrokeWkbSha256':digest(source_strokes[index].wkb),
                    'patchBoundsMm':[round(v,6) for v in tip.bounds],
                    'patchAreaMm2':round(tip.area,9),
                    'patchWkbSha256':digest(tip.wkb),
                    'patchWkbHex':tip.wkb_hex,
                })
            mask=rounded(mask.difference(unary_union(tips)))
            mask=shapely.from_wkb(mask.wkb)
            now_parts=len(export.polygons(mask))
            now_pockets=sum(len(p.interiors) for p in export.polygons(mask))
            if now_parts!=original_parts or now_pockets!=original_pockets:
                raise ValueError(f'Fault tip cap changed topology at {iteration}: '
                                 f'{original_parts}/{original_pockets} -> '
                                 f'{now_parts}/{now_pockets}')
            if protected.difference(mask).area>.00001:
                raise ValueError('Fault tip cap damaged a top-rim core')
        else:
            raise ValueError('Fault tip cap did not converge')
        # The three remaining isolated ink pockets are bounded by the named
        # source stroke pairs. Widen their ink locally, restore neighboring
        # gold to full width, then cap only local terminal wedges.
        expected_pockets=[
            ([16,52],.006035327,[18.496780,58.552294,18.643675,58.640432]),
            ([20,52],.000172576,[7.951416,60.835954,7.991034,60.851636]),
            ([16,57],.175149401,[76.913557,110.931111,77.816905,112.305962]),
        ]
        ink=body.difference(mask)
        pocket_parts=export.polygons(ink)
        indexed=[]
        for stroke_pair,area,bounds in expected_pockets:
            matches=[part for part in pocket_parts
                     if abs(part.area-area)<.000001 and
                     max(abs(a-b) for a,b in zip(part.bounds,bounds))<.001]
            if len(matches)!=1:
                raise ValueError(f'Fault indexed ink pocket {stroke_pair} changed')
            pocket=matches[0]
            indexed.append(pocket)
            records.append({
                'operation':'repair source-indexed Fault black pocket',
                'originalArtStrokePairIndices0':stroke_pair,
                'originalStrokeWkbSha256':[digest(source_strokes[i].wkb)
                                           for i in stroke_pair],
                'pocketBoundsMm':[round(v,6) for v in pocket.bounds],
                'pocketAreaMm2':round(pocket.area,9),
                'pocketWkbSha256':digest(pocket.wkb),
            })
        retreat=unary_union([part.buffer(.126,quad_segs=64) for part in indexed])
        envelope=unary_union([part.buffer(.49,quad_segs=64) for part in indexed])
        repaired=mask.difference(retreat).union(retreat.buffer(.251,quad_segs=64).difference(retreat))
        closing=repaired.buffer(.126,quad_segs=64).buffer(-.126,quad_segs=64)
        local_joins=closing.difference(repaired).intersection(envelope).difference(retreat)
        repaired=repaired.union(local_joins)
        radius=.124999
        reconstructed=repaired.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
            radius,join_style='mitre',quad_segs=64)
        terminal_caps=repaired.difference(reconstructed).intersection(envelope)
        repaired=shapely.from_wkb(rounded(repaired.difference(terminal_caps)).wkb)
        added=repaired.difference(mask)
        removed=mask.difference(repaired)
        if (added.difference(envelope).area>.00001 or
                removed.difference(envelope).area>.00001 or
                added.difference(safe_region(layer,body,'mask')).area>.00001):
            raise ValueError('Fault local black-pocket repair exceeded indexed envelope')
        if protected.difference(repaired).area>.00001:
            raise ValueError('Fault local black-pocket repair damaged a top-rim core')
        final_ink=body.difference(repaired)
        if (len(export.polygons(repaired))!=original_parts or
                sum(len(p.interiors) for p in export.polygons(repaired))!=original_pockets or
                list(pairs(repaired))):
            raise ValueError('Fault local black-pocket repair changed topology or mask webs')
        if any(part.area>1e-8 and part.buffer(-.125,quad_segs=64).is_empty
               for part in export.polygons(final_ink)):
            raise ValueError('Fault local black-pocket repair left a no-disk ink island')
        records.append({
            'operation':'bounded Fault ink-widening/gold-restoration/cap composite',
            'sourceArtStrokePairs0':[p[0] for p in expected_pockets],
            'inkRetreatRadiusMm':.126,
            'goldRestorationRadiusMm':.251,
            'localEnvelopeRadiusMm':.49,
            'goldAddedAreaMm2':round(added.area,9),
            'goldRemovedAreaMm2':round(removed.area,9),
            'localJoinAreaMm2':round(local_joins.area,9),
            'terminalCapAreaMm2':round(terminal_caps.area,9),
            'addedWkbSha256':digest(added.wkb),
            'removedWkbSha256':digest(removed.wkb),
        })
        # Two short nominally 0.251 mm angular source joins disappear under
        # erosion even though the positive miter residue is nearly zero.
        # Restore only their indexed butt/round junctions.
        junctions=[
            ([24,29],LineString([(1.4173,28.6187),(1.4538,28.5248)])),
            ([19,23],Point(4.2741,31.5871)),
        ]
        neck_patches=[]
        for indices,center in junctions:
            patch=center.buffer(.1255,quad_segs=64)
            if patch.difference(unary_union([source_strokes[i] for i in indices]).buffer(
                    .5,quad_segs=64)).area>.00001:
                raise ValueError('Fault indexed eroded-core neck exceeds source reach')
            neck_patches.append(patch)
            records.append({
                'operation':'restore indexed Fault gold butt/round neck',
                'originalArtStrokePairIndices0':indices,
                'originalStrokeWkbSha256':[digest(source_strokes[i].wkb)
                                           for i in indices],
                'centerMm':[[round(x,9),round(y,9)] for x,y in center.coords]
                           if center.geom_type=='LineString' else
                           [[round(center.x,9),round(center.y,9)]],
                'nominalWidthMm':.251,
                'patchWkbSha256':digest(patch.wkb),
            })
        neck_union=unary_union(neck_patches)
        with_necks=rounded(repaired.union(neck_union))
        neck_added=with_necks.difference(repaired)
        if (abs(neck_added.area-.014198473)>.00001 or
                neck_added.difference(safe_region(layer,body,'mask')).area>.00001 or
                len(export.polygons(with_necks))!=original_parts or
                sum(len(p.interiors) for p in export.polygons(with_necks))!=original_pockets or
                protected.difference(with_necks).area>.00001):
            raise ValueError('Fault indexed eroded-core neck geometry/topology changed')
        records.append({
            'operation':'bounded Fault eroded-core neck additions',
            'sourceArtStrokePairs0':[item[0] for item in junctions],
            'goldAddedAreaMm2':round(neck_added.area,9),
            'goldAddedWkbSha256':digest(neck_added.wkb),
        })
        repaired=with_necks
        before_vendor_caps=shapely.from_wkb(repaired.wkb)
        if digest(before_vendor_caps.wkb)!=(
                'ae5f8d0a37d1c2e344869fce12bf87a96cf0f98b40d898480cdd7accd79a576c'):
            raise ValueError('Fault pre-cap serialized gold changed')
        # At the published 0.13 mm black-mask class, 48 source-attributed
        # pointed ink tips can be rounded without touching a gold core. Two
        # remaining tips at stroke 54 / bottom rim require paired geometry;
        # retain them rather than create a new sub-width gold wedge.
        radius=.064999
        ink=body.difference(before_vendor_caps)
        reconstructed=ink.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
            radius,join_style='mitre',quad_segs=64)
        tips=[part for part in export.polygons(ink.difference(reconstructed))
              if part.area>1e-8]
        reserved=[
            (.003133116,[13.021111,68.850091,13.124701,68.914013]),
            (.00000946,[77.445,128.11,86.0504,128.1101]),
        ]
        selected=[]
        excluded=[]
        for tip in tips:
            match=any(abs(tip.area-area)<.000001 and
                      max(abs(a-b) for a,b in zip(tip.bounds,bounds))<.001
                      for area,bounds in reserved)
            (excluded if match else selected).append(tip)
        if (len(selected)!=48 or len(excluded)!=2 or
                abs(sum(p.area for p in selected)-.107720255)>.00001):
            raise ValueError('Fault published-mask tip inventory changed')
        if any(item.get('color') for item in original_layer['art']['strokes']):
            raise ValueError('Fault vendor-class ink caps would cover explicit black paint')
        for tip in selected:
            index=int(source_tree.nearest(tip.representative_point()))
            if tip.difference(source_strokes[index].buffer(.5,quad_segs=64)).area>.00001:
                raise ValueError('Fault vendor-class ink tip exceeded source reach')
            records.append({
                'operation':'cap indexed Fault sub-0.13 mm unpainted ink tip',
                'originalArtStrokeIndex0':index,
                'originalStrokeWkbSha256':digest(source_strokes[index].wkb),
                'patchBoundsMm':[round(v,6) for v in tip.bounds],
                'patchAreaMm2':round(tip.area,9),
                'patchWkbSha256':digest(tip.wkb),
                'patchWkbHex':tip.wkb_hex,
            })
        cap_union=unary_union(selected).intersection(safe_region(layer,body,'mask'))
        mask=shapely.from_wkb(rounded(before_vendor_caps.union(cap_union)).wkb)
        after_ink=body.difference(mask)
        gold_core=mask.buffer(-.124999,join_style='mitre',quad_segs=64)
        gold_residue=mask.difference(gold_core.buffer(.124999,join_style='mitre',
                                                    quad_segs=64)).area
        black_core=after_ink.buffer(-radius,join_style='mitre',quad_segs=64)
        black_residue=after_ink.difference(black_core.buffer(radius,join_style='mitre',
                                                              quad_segs=64)).area
        if (len(export.polygons(mask))!=original_parts or
                sum(len(p.interiors) for p in export.polygons(mask))!=original_pockets or
                len(export.polygons(after_ink))!=103 or
                protected.difference(mask).area>.00001 or list(pairs(mask)) or
                gold_residue>.00001 or black_residue>.00315):
            raise ValueError('Fault vendor-class ink caps changed topology or gold width')
        records.append({
            'operation':'bounded Fault published-mask class screen repair; project 0.25 mm still open',
            'sourceArtStrokeIndices0':sorted({r['originalArtStrokeIndex0'] for r in records
                if r['operation']=='cap indexed Fault sub-0.13 mm unpainted ink tip'}),
            'capCount':len(selected),
            'goldAddedAreaMm2':round(mask.difference(before_vendor_caps).area,9),
            'black013ResidueAreaMm2':round(black_residue,9),
            'gold025ResidueAreaMm2':round(gold_residue,9),
        })
    if design['id']=='kumiko-void' and layer['index'] in (0,3,6):
        mask=shapely.from_wkb(mask.wkb)
        fill_indices=[i for i,fill in enumerate(original_layer['art']['fills'])
                      if fill.get('color') is None]
        source_fills=[Polygon(original_layer['art']['fills'][i]['pts']) for i in fill_indices]
        source_tree=STRtree(source_fills)
        original_parts=len(export.polygons(mask))
        original_pockets=sum(len(p.interiors) for p in export.polygons(mask))
        radius=.124999
        reconstructed=mask.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
            radius,join_style='mitre',quad_segs=64)
        residue=mask.difference(reconstructed)
        tips=[part for part in export.polygons(residue) if part.area>1e-8]
        for tip in tips:
            position=int(source_tree.nearest(tip.representative_point()))
            source=source_fills[position]
            if tip.difference(source.buffer(.5,join_style='mitre')).area>.00001:
                raise ValueError('Kumiko tip cap exceeds indexed local-art reach')
            records.append({
                'operation':'cap indexed Kumiko terminal gold taper',
                'originalArtFillIndex0':fill_indices[position],
                'originalFillWkbSha256':digest(source.wkb),
                'patchBoundsMm':[round(v,6) for v in tip.bounds],
                'patchAreaMm2':round(tip.area,9),
                'patchWkbSha256':digest(tip.wkb),
                'patchWkbHex':tip.wkb_hex,
            })
        if tips:
            mask=shapely.from_wkb(rounded(mask.difference(unary_union(tips))).wkb)
        if (len(export.polygons(mask))!=original_parts or
                sum(len(p.interiors) for p in export.polygons(mask))!=original_pockets):
            raise ValueError('Kumiko tip caps changed gold component or black facet topology')
        if protected.difference(mask).area>.00001:
            raise ValueError('Kumiko tip caps damaged a top-rim core')
        reconstructed=mask.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
            radius,join_style='mitre',quad_segs=64)
        if mask.difference(reconstructed).area>.00001:
            raise ValueError('Kumiko tip caps left a positive-width residue')
        if layer['index']==0:
            # Open only the upper, explicitly black fill-137 facet beside the
            # protected left rail rim. The lower 116/117 facet is separate.
            upper=original_layer['art']['fills'][137]
            if upper.get('color')!='#15161a':
                raise ValueError('Kumiko upper black facet paint changed')
            local=box(15.85,123.2,17.1,124.85)
            rect=box(15.925,123.3,16.175,124.7).difference(protected)
            guide=LineString([(16.175,124.036575),(16.389,123.9131),
                              (16.610596,123.967345)])
            band=guide.offset_curve(-.1255).buffer(.1255,quad_segs=64)
            before=mask
            mask=rounded(mask.difference(rect.union(band)))
            cap_areas=[]
            for _ in range(2):
                reconstructed=mask.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
                    radius,join_style='mitre',quad_segs=64)
                cap=mask.difference(reconstructed).intersection(local)
                cap_areas.append(round(cap.area,9))
                mask=rounded(mask.difference(cap))
            changed=before.difference(mask)
            if (abs(changed.area-.299322758)>.00001 or
                    mask.difference(before).area>.00001 or
                    changed.difference(local).area>.00001 or
                    protected.difference(mask).area>.00001 or
                    len(export.polygons(mask))!=original_parts or
                    len(export.polygons(body.difference(mask)))!=64):
                raise ValueError('Kumiko upper black facet retreat changed envelope/topology')
            records.append({
                'operation':'retreat gold beside indexed Kumiko upper black facet',
                'originalBlackArtFillIndex0':137,
                'originalBlackFillWkbSha256':digest(Polygon(upper['pts']).wkb),
                'protectedRailSlotArtStrokeIndex0':7,
                'guideCenterlineMm':list(map(list,guide.coords)),
                'guideOffsetMm':-.1255,
                'bandRadiusMm':.1255,
                'localCapAreaMm2':cap_areas,
                'goldRemovedAreaMm2':round(changed.area,9),
                'goldRemovedWkbSha256':digest(changed.wkb),
            })
    if design['id']=='woven-maze' and layer['index']==0:
        if any(item.get('color') for key in ('fills','strokes')
               for item in original_layer['art'][key]):
            raise ValueError('Woven ink cap would cover explicitly painted black art')
        radius=.124999
        ink=body.difference(mask)
        opened=ink.buffer(-radius,join_style='mitre',quad_segs=64).buffer(
            radius,join_style='mitre',quad_segs=64)
        source_strokes=[export.stroke_geometry(stroke,False)
                        for stroke in original_layer['art']['strokes']]
        source_tree=STRtree(source_strokes)
        tips=[part for part in export.polygons(ink.difference(opened))
              if part.area>1e-8]
        if len(tips)!=8 or abs(sum(tip.area for tip in tips)-.040917377)>.00001:
            raise ValueError('Woven indexed terminal ink-tip inventory changed')
        safe=safe_region(layer,body,'mask')
        for tip in tips:
            index=int(source_tree.nearest(tip.representative_point()))
            if index not in (8,9,10,11) or tip.difference(
                    source_strokes[index].buffer(.5,quad_segs=64)).area>.00001:
                raise ValueError('Woven ink tip exceeds indexed source stroke reach')
            records.append({
                'operation':'cap indexed unpainted Woven terminal ink tip',
                'originalArtStrokeIndex0':index,
                'originalStrokeWkbSha256':digest(source_strokes[index].wkb),
                'patchBoundsMm':[round(v,6) for v in tip.bounds],
                'patchAreaMm2':round(tip.area,9),
                'patchWkbSha256':digest(tip.wkb),
                'patchWkbHex':tip.wkb_hex,
            })
        before_gold=export.polygons(mask)
        before_ink=export.polygons(ink)
        repaired=rounded(mask.union(unary_union(tips).intersection(safe)))
        after_gold=export.polygons(repaired)
        after_ink=export.polygons(body.difference(repaired))
        if (len(after_gold)!=len(before_gold) or
                sum(len(p.interiors) for p in after_gold)!=
                sum(len(p.interiors) for p in before_gold) or
                len(after_ink)!=len(before_ink) or
                sum(len(p.interiors) for p in after_ink)!=
                sum(len(p.interiors) for p in before_ink) or
                protected.difference(repaired).area>.00001 or
                repaired.difference(safe).area>.00001 or list(pairs(repaired))):
            raise ValueError('Woven indexed ink caps changed topology, rim or safe region')
        mask=shapely.from_wkb(repaired.wkb)
    return baseline,mask,records


def _enforce_job(job):
    """Width-enforce one board; optionally cached so an interrupted run resumes.

    WIDTH_CACHE_DIR (unset by default) keys results by the inputs and the
    width_geometry.py source, so any code or geometry change recomputes.
    """
    import os
    import pickle
    from width_geometry import enforce_widths
    mask,body,safe,protected,black,name=job
    cache=os.environ.get('WIDTH_CACHE_DIR')
    path=None
    if cache:
        key=hashlib.sha256(pickle.dumps(job)+(HERE/'width_geometry.py').read_bytes()).hexdigest()
        path=Path(cache)/f'mask-{name}-{key}.pickle'
        if path.exists():
            print(f'{name}: width enforcement reused from cache',flush=True)
            return pickle.loads(path.read_bytes())
    after,records,unresolved=enforce_widths(*(shapely.from_wkb(g) for g in (mask,body,safe,protected)),
                                            black,name)
    result=(after.wkb,records,unresolved)
    if path:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(pickle.dumps(result))
    return result


def run():
    policy=json.loads((HERE/'policy.json').read_text())
    geometry_path=HERE/'manufacturing-geometry.json'
    data=json.loads(geometry_path.read_text())
    original=json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    review=json.loads((ROOT/'validation/export-art-review.json').read_text())
    staged=[]
    for family,source_family in zip(data['designs'],original['designs']):
        design=(family['variants'][0] if family['id']=='kumiko-void' else family)
        source=(source_family['variants'][0] if family['id']=='kumiko-void' else source_family)
        for layer,original_layer in zip(design['layers'],source['layers']):
            if layer['finish']=='mask-only':
                continue
            before,after,records=corrected_mask(design,layer,data['spec'],original_layer,
                                                 policy['selectedApertureActions'])
            staged.append((design,source,layer,original_layer,before,after,records))
    # Width enforcement is independent per board and dominates run time.
    jobs=[]
    for design,_,layer,_,_,after,_ in staged:
        body=source_body(layer,data['spec'])
        jobs.append((after.wkb,body.wkb,safe_region(layer,body,'mask').wkb,
                     rim_cores(design,layer).wkb,
                     .25 if design['id']=='spider-nest' else .13,board_id(design,layer)))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=3) as pool:
        enforced=list(pool.map(_enforce_job,jobs))
    boards=[]
    for (design,source,layer,original_layer,before,_,records),(after_wkb,width_records,unresolved) in zip(staged,enforced):
        after=shapely.from_wkb(after_wkb)
        black=.25 if design['id']=='spider-nest' else .13
        records.extend(width_records)
        # Measure the serialized geometry that downstream consumers read.
        # GEOS overlay objects can carry a different vertex traversal until
        # round-tripped, which affects acute-tip buffer diagnostics.
        after=shapely.from_wkb(after.wkb)
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
        tolerance_radius=.124999
        tolerance_reconstructed=after.buffer(-tolerance_radius,join_style='mitre',
            quad_segs=64).buffer(tolerance_radius,join_style='mitre',quad_segs=64)
        tolerance_residue=after.difference(tolerance_reconstructed).area
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
            'toleranceAwareMiterWidthResidueAreaMm2':round(tolerance_residue,9),
            'withinComponentGoldWidthProven':width_residue<=.00001,
            'retreatCount':sum(r['operation']=='one-sided local mask retreat' for r in records),
            'removedNoDiskComponents':sum(r['operation'].startswith('remove isolated') for r in records),
            'indexedTerminalCaps':sum(r['operation'].startswith('cap indexed') for r in records),
            'blackWebWidthMm':black,
            'widthEnforcementEdits':len(width_records),
            'unresolvedWidthFailures':unresolved,
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
