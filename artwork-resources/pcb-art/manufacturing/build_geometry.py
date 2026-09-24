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

from shapely.geometry import Point, Polygon

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
