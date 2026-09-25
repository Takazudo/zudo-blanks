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
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

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


def manufacturing_ring(ring):
    points = [[round(x, 9), round(y, 9)] for x, y in ring.coords]
    return points[:-1] if points[-1] == points[0] else points


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
    art_fill_changes = []
    closed = set()
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
                        for part in export.ordered(after):
                            corrected.append(manufacturing_ring(part.exterior))
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
                                [manufacturing_ring(p.exterior) for p in export.ordered(after)],
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
