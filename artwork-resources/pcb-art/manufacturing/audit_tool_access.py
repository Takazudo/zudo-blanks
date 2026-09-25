#!/usr/bin/env python3
"""Index admissible cutter-center components and independent plunge points."""
from __future__ import annotations

import json

import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from repair_mask_candidate import HERE, ROOT, board_id, digest, export


def run():
    source_path=ROOT/'preview-source/assets/geometry.json'
    candidate_path=HERE/'manufacturing-geometry.json'
    ledger_path=HERE/'indexed-deltas.json'
    source=json.loads(source_path.read_text())
    candidate=json.loads(candidate_path.read_text())
    ledger=json.loads(ledger_path.read_text())
    indexed={(c['board'],c['geometryHoleIndex0']):c for c in ledger['changes']}
    records=[]
    for family,new_family in zip(source['designs'],candidate['designs']):
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        revised=(next(d for d in new_family['variants'] if d.get('variantId')=='wide')
                 if new_family['id']=='kumiko-void' else new_family)
        for old_layer,new_layer in zip(design['layers'],revised['layers']):
            board=f'{design["id"]}-L{old_layer["index"]+1:02d}'
            drills=export.drill_specs(old_layer,source['spec'])
            corrected_cutouts=unary_union(export.split_functional_holes(new_layer,drills))
            for index,points in enumerate(old_layer['holes']):
                original=Polygon(points)
                if any(original.covers(Point(d['x'],d['y'])) for d in drills):
                    continue
                center=original.buffer(-.5,quad_segs=64)
                change=indexed.get((board,index))
                if center.is_empty:
                    if not change or not change['issueId']:
                        raise ValueError(f'{board} H{index}: unindexed inaccessible closure')
                    records.append({'board':board,'originalHoleIndex0':index,
                                    'status':'indexed complete closure',
                                    'issueId':change['issueId'],'components':[]})
                    continue
                components=[]
                swept=[]
                for component_index,part in enumerate(export.ordered(center)):
                    plunge=part.representative_point()
                    disk=plunge.buffer(.5,quad_segs=64)
                    if disk.difference(original).area>.00001:
                        raise ValueError(f'{board} H{index}: plunge disk escapes aperture')
                    swept.append(part.buffer(.5,quad_segs=64).intersection(original))
                    components.append({
                        'componentIndex0':component_index,
                        'admissibleCenterAreaMm2':round(part.area,9),
                        'centerDomainNormalizedWkbSha256':digest(shapely.normalize(part).wkb),
                        'plungeCenterMm':[round(plunge.x,9),round(plunge.y,9)],
                        'plungeDiskContainedInOriginalHole':True,
                        'pathDomain':'the connected admissible center polygon; '
                                     'continuous in-domain raster traversal is possible',
                    })
                if unary_union(swept).difference(corrected_cutouts).area>.00001:
                    raise ValueError(f'{board} H{index}: swept domain missing from output')
                if change and change['toolCenterComponents']!=len(components):
                    raise ValueError(f'{board} H{index}: indexed center count changed')
                records.append({'board':board,'originalHoleIndex0':index,
                                'status':'admissible component plunge domains',
                                'components':components})
    split=[r for r in records if len(r['components'])>1]
    if {(r['board'],r['originalHoleIndex0']) for r in split}!={
            ('kumiko-void-L05',14),('woven-maze-L04',0)}:
        raise ValueError('Split center-region inventory changed')
    result={'status':'connected center-domain and plunge proof; actual CNC path pending',
            'sourceGeometrySha256':digest(source_path.read_bytes()),
            'manufacturingGeometrySha256':digest(candidate_path.read_bytes()),
            'indexedDeltasSha256':digest(ledger_path.read_bytes()),
            'toolDiameterMm':1.0,
            'recordCount':len(records),
            'splitCenterRegionCount':len(split),
            'records':records}
    (HERE/'tool-access-ledger.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'records':len(records),'closed':sum(not r['components'] for r in records),
                      'splitCenterRegions':len(split)}))


if __name__=='__main__':
    run()
