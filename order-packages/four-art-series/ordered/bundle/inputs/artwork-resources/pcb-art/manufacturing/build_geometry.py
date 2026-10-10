#!/usr/bin/env python3
"""Build a separate, indexed routing candidate from the frozen Rev5 source.

The artifact remains a candidate until all manufacturing gates pass. The
approved preview inputs are never modified by this program.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, substring, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'preview-source/assets/geometry.json'
OUTPUT = HERE / 'manufacturing-geometry.json'
LEDGER = HERE / 'indexed-deltas.json'

module = importlib.util.spec_from_file_location('export_reference', ROOT / 'tools/export_kicad.py')
export = importlib.util.module_from_spec(module)
module.loader.exec_module(export)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ring_hash(points) -> str:
    return digest(json.dumps(points, separators=(',', ':')).encode())


def manufacturing_ring(ring,digits=9):
    points = [[round(x, digits), round(y, digits)] for x, y in ring.coords]
    return points[:-1] if points[-1] == points[0] else points


def relocate_spider_network_guides(layer,original_layer,decision,network,source_hash):
    """Insert only the evidence-indexed straight guide portions and short joins."""
    by_stroke={}
    for portion in decision['guidePortions']:
        by_stroke.setdefault(portion['guideStrokeIndex0'],[]).append(portion)
    changes=[]
    miter_changes=[]
    curve_changes=[]
    for stroke_index,portions in sorted(by_stroke.items()):
        stroke=layer['art']['strokes'][stroke_index]
        source=original_layer['art']['strokes'][stroke_index]
        before=copy.deepcopy(stroke['pts'])
        original=source['pts']
        if stroke['w']!=.251:
            raise ValueError(f'Spider guide {stroke_index} width changed')
        source_line=LineString(original)
        generic_line=LineString(before)
        source_edge_starts=[0.0]
        for a,b in zip(original,original[1:]):
            source_edge_starts.append(source_edge_starts[-1]+math.dist(a,b))
        edge_distances={}
        def generic_edge_distance(vertex_index):
            guess=(source_edge_starts[vertex_index]/source_line.length*
                   generic_line.length)
            low=max(0.0,guess-2.0)
            high=min(generic_line.length,guess+2.0)
            local=substring(generic_line,low,high)
            distance=low+local.project(Point(original[vertex_index]))
            if generic_line.interpolate(distance).distance(
                    Point(original[vertex_index]))>.15:
                raise ValueError(f'Spider guide {stroke_index} edge-local mapping drift')
            return distance
        intervals=[]
        for p in portions:
            if p['originalGuideContourSha256']!=ring_hash(original):
                raise ValueError(f'Spider guide {stroke_index} source hash changed')
            j=p['originalGuideEdgeIndex0']
            a,b=original[j:j+2]
            if p['originalEdgeMm']!=[a,b]:
                raise ValueError(f'Spider guide {stroke_index} edge {j} changed')
            dx,dy=b[0]-a[0],b[1]-a[1]
            length2=dx*dx+dy*dy
            original_ends=p['originalPortionMm']
            nominal_ends=p['nominalRelocatedPortionMm']
            t=[((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/length2
               for pt in original_ends]
            if t[0]>t[1]:
                t.reverse()
                original_ends=list(reversed(original_ends))
                nominal_ends=list(reversed(nominal_ends))
            if t[0]<-.000001 or t[1]>1.000001:
                raise ValueError('Spider guide portion leaves its original edge')
            for old,new in zip(original_ends,nominal_ends):
                if math.dist(old,new)>.5:
                    raise ValueError('Spider guide nominal displacement exceeded .5 mm')
            if j not in edge_distances:
                edge_distances[j]=(generic_edge_distance(j),generic_edge_distance(j+1))
            edge_start,edge_end=edge_distances[j]
            d0=edge_start+max(0,t[0])*(edge_end-edge_start)
            d1=edge_start+min(1,t[1])*(edge_end-edge_start)
            for at,original_point in ((d0,original_ends[0]),(d1,original_ends[1])):
                if generic_line.interpolate(at).distance(Point(original_point))>.15:
                    raise ValueError('Spider guide portion leaves source-edge-local mapping')
            intervals.append((d0,d1,nominal_ends,p,j))
        revised=[before[0]]
        previous=0.0
        for d0,d1,(start,end),p,j in sorted(intervals,key=lambda row:row[0]):
            if d0<previous-.000001:
                raise ValueError(f'Spider guide {stroke_index} portions overlap')
            if d0>previous+.000001:
                retained=substring(generic_line,previous,d0)
                revised.extend([list(coord) for coord in retained.coords])
            revised.extend([[round(v,9) for v in start],
                            [round(v,9) for v in end]])
            previous=d1
            changes.append({
                    'board':'spider-nest-L01',
                    'artStrokeIndex0':stroke_index,
                    'originalGuideEdgeIndex0':j,
                    'centralStrokeIndex0':p['centralStrokeIndex0'],
                    'sourceGeometrySha256':source_hash,
                    'sourceContourSha256':ring_hash(original),
                    'originalPortionMm':p['originalPortionMm'],
                    'nominalRelocatedPortionMm':p['nominalRelocatedPortionMm'],
                    'maximumNominalDisplacementMm':p['maximumNominalDisplacementMm'],
                    'operation':'relocate exact Spider network guide portion with bounded endpoint join',
            })
        if previous<generic_line.length-.000001:
            retained=substring(generic_line,previous,generic_line.length)
            revised.extend([list(coord) for coord in retained.coords])
        compact=[]
        for point in revised:
            if not compact or math.dist(point,compact[-1])>1e-7:
                compact.append(point)
        if math.dist(compact[0],compact[-1])<1e-7:
            compact[-1]=compact[0]
        for miter in (m for m in decision['sourceEdgeLocalMiters']
                      if m['guideStrokeIndex0']==stroke_index):
            shared=Point(miter['originalSharedPointMm'])
            target=[]
            for edge in miter['originalGuideEdgeIndices0']:
                candidates=[p for p in portions if p['originalGuideEdgeIndex0']==edge]
                if not candidates:
                    raise ValueError('Spider miter has no indexed source edge')
                p=min(candidates,key=lambda p:min(Point(v).distance(shared)
                    for v in p['originalPortionMm']))
                k=min(range(2),key=lambda k:Point(p['originalPortionMm'][k]).distance(shared))
                nominal=p['nominalRelocatedPortionMm'][k]
                matched=min(range(len(compact)),key=lambda i:math.dist(compact[i],nominal))
                if math.dist(compact[matched],nominal)>.00001:
                    raise ValueError('Spider miter nominal endpoint not emitted')
                target.append(matched)
            point=[round(v,9) for v in miter['intersectionMm']]
            low,high=sorted(target)
            if low==high:
                compact[low]=point
            elif (miter['originalGuideEdgeIndices0'][1]==0 and
                  miter['originalGuideEdgeIndices0'][0]>0):
                compact=[point]+compact[low+1:high]+[point]
            else:
                compact=compact[:low]+[point]+compact[high+1:]
            miter_changes.append({
                'board':'spider-nest-L01',
                'artStrokeIndex0':stroke_index,
                'originalGuideEdgeIndices0':miter['originalGuideEdgeIndices0'],
                'centralStrokeIndices0':miter['centralStrokeIndices0'],
                'originalSharedPointMm':miter['originalSharedPointMm'],
                'intersectionMm':miter['intersectionMm'],
                'displacementMm':miter['displacementMm'],
                'sourceGeometrySha256':source_hash,
                'operation':'exact source-edge-local Spider guide miter',
            })
        if stroke_index==103:
            terminal=decision['terminal']
            controls=terminal['cubicControlPointsMm']
            start=min(range(len(compact)),key=lambda i:math.dist(compact[i],controls[0]))
            end=min(range(len(compact)),key=lambda i:math.dist(compact[i],controls[3]))
            if (start>=end or math.dist(compact[start],controls[0])>.000001 or
                    math.dist(compact[end],controls[3])>.000001 or
                    terminal['guide103OriginalEdgeIndex0']!=27 or
                    terminal['cubicSegments']!=64):
                raise ValueError('Spider guide103 cubic source jog changed')
            cubic=[]
            for step in range(terminal['cubicSegments']+1):
                t=step/terminal['cubicSegments']
                point=[(1-t)**3*controls[0][k]+3*(1-t)**2*t*controls[1][k]+
                       3*(1-t)*t*t*controls[2][k]+t**3*controls[3][k]
                       for k in (0,1)]
                cubic.append([round(v,9) for v in point])
            cubic[0]=controls[0]
            cubic[-1]=controls[3]
            if any(Point(p).distance(Point(terminal['guide103OriginalEndpointMm']))>.5
                   for p in cubic):
                raise ValueError('Spider guide103 cubic exceeded endpoint reach')
            compact=compact[:start]+cubic+compact[end+1:]
            curve_changes.append({
                'board':'spider-nest-L01',
                'artStrokeIndex0':103,
                'originalGuideEdgeIndex0':27,
                'controlPointsMm':controls,
                'segmentCount':64,
                'sourceGeometrySha256':source_hash,
                'operation':'replace indexed reverse jog with bounded Spider cubic',
            })
        line=LineString(compact)
        if LineString(original).hausdorff_distance(line)>.5:
            raise ValueError(f'Spider guide {stroke_index} exceeds .5 mm source reach')
        if line.difference(network.buffer(.5)).difference(
                LineString(before).buffer(.5)).length>.00001:
            raise ValueError(f'Spider guide {stroke_index} leaves network/end envelope')
        stroke['pts']=compact
        for change in changes:
            if change['artStrokeIndex0']==stroke_index:
                change['afterContourSha256']=ring_hash(compact)
    if len(changes)!=len(decision['guidePortions']):
        raise ValueError(f'Spider network guide portion count changed: {len(changes)}')
    if len(miter_changes)!=len(decision['sourceEdgeLocalMiters']):
        raise ValueError('Spider network miter count changed')
    if len(curve_changes)!=1:
        raise ValueError('Spider network guide103 cubic was not indexed once')
    return changes,miter_changes,curve_changes


def run() -> None:
    policy = json.loads((HERE / 'policy.json').read_text())
    original_bytes = SOURCE.read_bytes()
    assert digest(original_bytes) == policy['sourceHashes']['preview-source/assets/geometry.json']
    data = json.loads(original_bytes)
    actions = {(a['layerNumber'], a['geometryHoleIndex0']): a for a in policy['selectedApertureActions']}
    changes = []
    border_changes = []
    stroke_width_changes = []
    art_guide_changes = []
    art_neck_changes = []
    spider_network_changes = []
    spider_network_guide_changes = []
    spider_network_miter_changes = []
    spider_network_curve_changes = []
    art_fill_changes = []
    closed = set()
    network_rule=next(rule for rule in policy['errata']
                      if rule['id']=='spider-l01-unfiltered-network-2026-09-25')
    if digest((HERE/network_rule['evidence']).read_bytes())!=network_rule['evidenceSha256']:
        raise ValueError('Spider network decision evidence hash changed')
    network_decision=json.loads((HERE/network_rule['evidence']).read_text())
    if digest((HERE/network_rule['surveyInput']).read_bytes())!=network_rule[
            'surveyInputSha256']:
        raise ValueError('Spider network survey input changed')
    network=unary_union([LineString(path['pointsMm']).buffer(
        network_rule['ribbonWidthMm']/2,cap_style='flat',join_style='mitre')
        for path in network_decision['paths']])
    captured_body=shapely.from_wkb(bytes.fromhex(json.loads(
        (HERE/'spider-channel-erratum.json').read_text())['candidateBodyWkbHex']))
    if digest(shapely.normalize(captured_body).wkb)!=network_rule[
            'baseBodyNormalizedWkbSha256']:
        raise ValueError('Spider pre-rib body changed')
    network_initial=captured_body.union(network)
    network_initial_delta=network_initial.difference(captured_body)
    if digest(shapely.normalize(network_initial_delta).wkb)!=network_rule[
            'initialAdditionNormalizedWkbSha256']:
        raise ValueError('Spider exact initial network addition changed')
    source_spider=next(d for d in data['designs'] if d['id']=='spider-nest')
    original_decorative={i:Polygon(points) for i,points in enumerate(
        source_spider['layers'][0]['holes']) if i in network_rule[
        'affectedOriginalGeometryHoleIndices0']}
    network_apertures={}
    for interior in network_initial.interiors:
        aperture=Polygon(interior)
        matches=[i for i,original in original_decorative.items()
                 if aperture.intersection(original).area>.01]
        if matches:
            index=max(matches,key=lambda i:aperture.intersection(original_decorative[i]).area)
            if index in network_apertures:
                raise ValueError(f'Spider network aperture {index} split')
            network_apertures[index]=aperture
    if set(network_apertures)!=set(original_decorative):
        raise ValueError('Spider network aperture inventory changed')
    network_tool={row['originalGeometryHoleIndex0']:row for row in network_decision['toolAccess']}
    for family in data['designs']:
        if family['id'] == 'kumiko-void':
            designs = [next(d for d in family['variants'] if d.get('variantId') == 'wide')]
        else:
            designs = [family]
        for design in designs:
            for layer in design['layers']:
                board = f'{design["id"]}-L{layer["index"]+1:02d}'
                original_layer = copy.deepcopy(layer)
                drills = export.drill_specs(layer, data['spec'])
                corrected = []
                for index, points in enumerate(original_layer['holes']):
                    hole = Polygon(points)
                    if any(hole.covers(Point(d['x'], d['y'])) for d in drills):
                        corrected.append(points)
                        continue
                    action = actions.get((layer['index']+1, index)) if design['id'] == 'kumiko-void' else None
                    center = hole.buffer(-.5, quad_segs=64)
                    if action:
                        assert center.is_empty, action['issueId']
                        closed.add(action['issueId'])
                        after = Polygon()
                    else:
                        if center.is_empty:
                            raise ValueError(f'{board}: unindexed aperture closure at {index}')
                        after = center.buffer(.5, quad_segs=64).intersection(hole)
                        if board=='spider-nest-L01' and index in network_apertures:
                            initial=network_apertures[index]
                            proof=network_tool[index]
                            if digest(shapely.normalize(initial).wkb)!=proof[
                                    'initialApertureNormalizedWkbSha256']:
                                raise ValueError(f'{board}: network aperture {index} hash changed')
                            routed_center=initial.buffer(-.5,quad_segs=64)
                            if routed_center.is_empty:
                                raise ValueError(f'{board}: network closed aperture {index}')
                            swept=routed_center.buffer(.5,quad_segs=64).intersection(initial)
                            cleanup=initial.difference(swept)
                            routed=initial.difference(cleanup)
                            if (digest(shapely.normalize(cleanup).wkb)!=proof[
                                    'cleanupNormalizedWkbSha256'] or
                                    digest(shapely.normalize(routed).wkb)!=proof[
                                    'finalApertureNormalizedWkbSha256']):
                                raise ValueError(f'{board}: network aperture {index} cleanup changed')
                            emitted=shapely.set_precision(routed,1e-9)
                            if (not emitted.is_valid or
                                    routed.symmetric_difference(emitted).area>.00001 or
                                    len([p for p in export.ordered(emitted) if p.area>1e-8])!=
                                    len([p for p in export.ordered(routed) if p.area>1e-8])):
                                raise ValueError(f'{board}: network aperture {index} grid changed topology')
                            spider_network_changes.append({
                                'board':board,'sourceGeometrySha256':digest(original_bytes),
                                'originalGeometryHoleIndex0':index,
                                'operation':'exact once 2.0 mm network then all-center cutter sweep',
                                'beforeNetworkAreaMm2':round(after.area,9),
                                'initialRibbonMaterialAdditionMm2':round(after.difference(initial).area,9),
                                'routingCleanupMaterialAdditionMm2':round(cleanup.area,9),
                                'afterAreaMm2':round(emitted.area,9),
                                'deltaBoundsMm':[round(v,6) for v in after.difference(emitted).bounds],
                                'beforeContourSha256':digest(shapely.normalize(after).wkb),
                                'initialContourSha256':digest(shapely.normalize(initial).wkb),
                                'cleanupContourSha256':digest(shapely.normalize(cleanup).wkb),
                                'decisionFinalContourSha256':digest(shapely.normalize(routed).wkb),
                                'afterContourSha256':digest(shapely.normalize(emitted).wkb),
                                'gridAdjustmentAreaMm2':round(
                                    routed.symmetric_difference(emitted).area,12),
                            })
                            after=emitted
                        for part in export.ordered(after):
                            corrected.append(manufacturing_ring(part.exterior,
                                12 if board=='spider-nest-L01' and index in network_apertures
                                else 9))
                    delta = hole.symmetric_difference(after)
                    if delta.area > .00001:
                        changes.append({
                            'board': board,
                            'sourceGeometrySha256': digest(original_bytes),
                            'geometryHoleIndex0': index,
                            'issueId': action['issueId'] if action else None,
                            'operation': 'indexed closure' if action else 'all-component 1 mm tool sweep',
                            'originalBoundsMm': [round(v, 6) for v in hole.bounds],
                            'deltaBoundsMm': [round(v, 6) for v in delta.bounds],
                            'beforeAreaMm2': round(hole.area, 8),
                            'afterAreaMm2': round(after.area, 8),
                            'beforeContourSha256': ring_hash(points),
                            'afterContourSha256': digest(json.dumps(
                                [manufacturing_ring(p.exterior,
                                    12 if board=='spider-nest-L01' and index in network_apertures
                                    else 9) for p in export.ordered(after)],
                                separators=(',', ':')).encode()),
                            'toolCenterComponents': len(export.polygons(center)),
                        })
                layer['holes'] = corrected
                for stroke_index, stroke in enumerate(layer['art']['strokes']):
                    if (stroke.get('color') is None and stroke.get('purpose')!='top-gold-border'
                            and 0 < stroke.get('w',0) < .25):
                        old_width=stroke['w']
                        stroke['w']=.251
                        stroke_width_changes.append({
                            'board':board,
                            'sourceGeometrySha256':digest(original_bytes),
                            'artStrokeIndex0':stroke_index,
                            'originalContourSha256':ring_hash(stroke['pts']),
                            'originalWidthMm':old_width,
                            'manufacturingWidthMm':stroke['w'],
                            'operation':'widen source gold stroke to exceed 0.25 mm nominal width',
                        })
                if layer['index']==0 and design['id'] in ('spider-nest','woven-maze'):
                    target_indices=(range(95,114) if design['id']=='spider-nest' else range(0,3))
                    offset=.105 if design['id']=='spider-nest' else .145
                    for stroke_index in target_indices:
                        stroke=layer['art']['strokes'][stroke_index]
                        original_pts=copy.deepcopy(stroke['pts'])
                        if design['id']=='woven-maze':
                            guide=Polygon(original_pts).buffer(offset,join_style='mitre',
                                mitre_limit=10).exterior
                        else:
                            guide=LineString(original_pts).offset_curve(-offset,
                                join_style='bevel',mitre_limit=10)
                        if guide.geom_type not in ('LineString','LinearRing') or guide.is_empty:
                            raise ValueError(f'{board}: guide offset changed path topology at {stroke_index}')
                        translated=[[round(x,9),round(y,9)] for x,y in guide.coords]
                        if LineString(original_pts).hausdorff_distance(guide)>.5:
                            raise ValueError(f'{board}: guide offset exceeded local reach at {stroke_index}')
                        stroke['pts']=translated
                        art_guide_changes.append({
                            'board':board,'artStrokeIndex0':stroke_index,
                            'sourceGeometrySha256':digest(original_bytes),
                            'operation':'move guide centerline into retained substrate while retaining stroke width',
                            'offsetMm':offset,
                            'originalContourSha256':ring_hash(original_pts),
                            'manufacturingContourSha256':ring_hash(translated),
                        })
                    if design['id']=='woven-maze':
                        for fill_index in range(2,18):
                            fill=layer['art']['fills'][fill_index]
                            original_pts=copy.deepcopy(fill['pts'])
                            xs=[p[0] for p in original_pts];ys=[p[1] for p in original_pts]
                            minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
                            if abs(maxy-miny-.22)<.000001:
                                fill['pts']=[[x,round(y+(.0155 if y>miny else -.0155),9)]
                                             for x,y in original_pts]
                            elif abs(maxx-minx-.22)<.000001:
                                fill['pts']=[[round(x+(.0155 if x>minx else -.0155),9),y]
                                             for x,y in original_pts]
                            else:
                                raise ValueError(f'{board}: woven guide fill {fill_index} is not 0.22 mm')
                            art_fill_changes.append({
                                'board':board,'artFillIndex0':fill_index,
                                'sourceGeometrySha256':digest(original_bytes),
                                'operation':'widen 0.22 mm rectangular bar to 0.251 mm across short axis',
                                'originalContourSha256':ring_hash(original_pts),
                                'manufacturingContourSha256':ring_hash(fill['pts']),
                            })
                if design['id']=='spider-nest' and layer['index']==0:
                    guide_changes,miter_changes,curve_changes=relocate_spider_network_guides(
                        layer,original_layer,network_decision,network,digest(original_bytes))
                    spider_network_guide_changes.extend(guide_changes)
                    spider_network_miter_changes.extend(miter_changes)
                    spider_network_curve_changes.extend(curve_changes)
                if design['id']=='kumiko-void' and layer['index']==6:
                    # Two pointed L07 fill edges taper below the nominal gold
                    # width. Extend only their adjacent gold faces into retained
                    # material; the later black facets retain their paint order.
                    for fill_index, bounds in (
                        (120,(90.625,21.7257,90.876,25.4743)),
                        (134,(90.625,103.0257,90.876,106.7743)),
                    ):
                        fill=layer['art']['fills'][fill_index]
                        assert fill.get('color') is None
                        original_pts=copy.deepcopy(fill['pts'])
                        source_shape=Polygon(original_pts)
                        revised=source_shape.union(box(*bounds))
                        if revised.geom_type!='Polygon' or len(revised.interiors):
                            raise ValueError(f'{board}: L07 fill {fill_index} changed topology')
                        added=revised.difference(source_shape)
                        if not 0 < added.area < .7:
                            raise ValueError(f'{board}: L07 fill {fill_index} changed area unexpectedly')
                        fill['pts']=manufacturing_ring(revised.exterior)
                        art_fill_changes.append({
                            'board':board,'artFillIndex0':fill_index,
                            'sourceGeometrySha256':digest(original_bytes),
                            'operation':'locally widen tapered L07 gold fill within 0.50 mm reach',
                            'additionBoundsMm':[round(v,6) for v in added.bounds],
                            'addedAreaMm2':round(added.area,9),
                            'originalContourSha256':ring_hash(original_pts),
                            'manufacturingContourSha256':ring_hash(fill['pts']),
                        })
                if design['id']=='coral-vault' and layer['index']==0:
                    # Preserve these connected strokes while giving their
                    # locally clipped necks a full-width centerline corridor.
                    body=Polygon(layer['outer']).difference(unary_union(
                        export.split_functional_holes(layer,drills))).difference(
                        unary_union([export.drill_shape(d) for d in drills]))
                    for stroke_index in (637,645,852,853,857):
                        stroke=layer['art']['strokes'][stroke_index]
                        original_pts=copy.deepcopy(stroke['pts'])
                        if stroke_index in (852,853,857):
                            minimum_x=.71+.251+stroke['w']/2
                            revised=[[round(max(x,minimum_x),9),y] for x,y in original_pts]
                            operation='move outer-frame neck centerline inward'
                        else:
                            center_safe=body.buffer(-(.35+stroke['w']/2+.001),quad_segs=64)
                            revised=[]
                            for x,y in original_pts:
                                point=Point(x,y)
                                if center_safe.covers(point):
                                    revised.append([x,y])
                                else:
                                    _,nearest=nearest_points(point,center_safe)
                                    revised.append([round(nearest.x,9),round(nearest.y,9)])
                            operation='project clipped neck centerline into mask-safe core'
                        displacement=max(Point(a).distance(Point(b))
                                         for a,b in zip(original_pts,revised))
                        if not 0<displacement<=.5:
                            raise ValueError(f'{board}: Coral neck {stroke_index} reach {displacement}')
                        stroke['pts']=revised
                        art_neck_changes.append({
                            'board':board,'artStrokeIndex0':stroke_index,
                            'sourceGeometrySha256':digest(original_bytes),
                            'operation':operation,
                            'maximumCenterlineDisplacementMm':round(displacement,9),
                            'originalContourSha256':ring_hash(original_pts),
                            'manufacturingContourSha256':ring_hash(revised),
                        })
                if layer['index'] == 0:
                    for stroke in layer['art']['strokes']:
                        if stroke.get('purpose') != 'top-gold-border':
                            continue
                        if stroke.get('feature') == 'rail-slot':
                            border_changes.append({
                                'board':board, 'feature':'rail-slot',
                                'featureIndex':stroke['featureIndex'],
                                'operation':'retreat inner visible edge 0.05 mm at 0.35 mm safe-edge clip; retain source centerline',
                                'sourceContourSha256':ring_hash(stroke['pts']),
                            })
                        if (design['id']=='coral-vault' and stroke.get('feature')=='stack-hole'
                                and stroke['featureIndex'] in (1,2,3)):
                            original_pts = copy.deepcopy(stroke['pts'])
                            cx,cy=data['spec']['screws'][stroke['featureIndex']]
                            stroke['pts']=[[round(cx+(x-cx)*2.55/2.70,9),
                                            round(cy+(y-cy)*2.55/2.70,9)] for x,y in original_pts]
                            border_changes.append({
                                'board':board, 'feature':'stack-hole',
                                'featureIndex':stroke['featureIndex'],
                                'operation':'move circle radius 2.70 to 2.55 mm; retain 0.40 mm stroke and hole center',
                                'sourceContourSha256':ring_hash(original_pts),
                                'afterContourSha256':ring_hash(stroke['pts']),
                            })
    assert len(closed) == 56
    if [c['originalGeometryHoleIndex0'] for c in spider_network_changes]!=network_rule[
            'affectedOriginalGeometryHoleIndices0']:
        raise ValueError('Spider network indexed aperture set changed')
    initial_area=sum(c['initialRibbonMaterialAdditionMm2'] for c in spider_network_changes)
    cleanup_area=sum(c['routingCleanupMaterialAdditionMm2'] for c in spider_network_changes)
    if (abs(initial_area-network_decision['initialAdditionAreaMm2'])>.00001 or
            abs(cleanup_area-network_decision['routingCleanupAreaMm2'])>.00001 or
            initial_area>network_rule['maximumInitialAdditionAreaMm2'] or
            cleanup_area>network_rule['maximumAdditionalRoutingCleanupAreaMm2'] or
            initial_area+cleanup_area>network_rule['maximumCombinedAdditionAreaMm2']):
        raise ValueError('Spider network initial/cleanup area changed')
    result = {
        'schemaVersion': 1,
        'role': 'manufacturing geometry candidate; approved Rev5 source remains immutable',
        'decisionId': policy['decisionId'],
        'sourceGeometrySha256': digest(original_bytes),
        'policySha256': digest((HERE / 'policy.json').read_bytes()),
        'changes': changes,
        'borderChanges': border_changes,
        'strokeWidthChanges': stroke_width_changes,
        'artGuideChanges':art_guide_changes,
        'artNeckChanges':art_neck_changes,
        'spiderNetworkChanges':spider_network_changes,
        'spiderNetworkGuideChanges':spider_network_guide_changes,
        'spiderNetworkMiterChanges':spider_network_miter_changes,
        'spiderNetworkCurveChanges':spider_network_curve_changes,
        'artFillChanges':art_fill_changes,
        'closedIssueIds': sorted(closed),
        'unresolvedAlternativeIssueIds': policy['alternativeUnresolvedIssueIds'],
    }
    data['manufacturingProvenance'] = {k: result[k] for k in ('decisionId', 'sourceGeometrySha256', 'policySha256')}
    OUTPUT.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    result['manufacturingGeometrySha256'] = digest(OUTPUT.read_bytes())
    LEDGER.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'selectedApertureDeltas': len(changes), 'closures': len(closed),
                      'manufacturingGeometrySha256': result['manufacturingGeometrySha256']}))


if __name__ == '__main__':
    run()
