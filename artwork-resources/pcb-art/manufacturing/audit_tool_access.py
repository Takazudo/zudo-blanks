#!/usr/bin/env python3
"""Index admissible cutter-center components and independent plunge points."""
from __future__ import annotations

import hashlib
import json

import shapely
from shapely.geometry import LineString, Point, Polygon
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
                rib_affected=board=='spider-nest-L01' and index in (1,6,16)
                aperture=corrected_cutouts.intersection(original) if rib_affected else original
                center=aperture.buffer(-.5,quad_segs=64)
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
                    if disk.difference(aperture).area>.00001:
                        raise ValueError(f'{board} H{index}: plunge disk escapes aperture')
                    swept.append(part.buffer(.5,quad_segs=64).intersection(aperture))
                    minx,miny,maxx,maxy=part.bounds
                    path=[LineString(part.exterior.coords)]
                    path.extend(LineString(ring.coords) for ring in part.interiors)
                    y=miny+.25
                    while y<maxy:
                        cut=part.intersection(LineString([(minx-1,y),(maxx+1,y)]))
                        path.extend(segment for segment in shapely.get_parts(cut)
                                    if segment.geom_type=='LineString' and segment.length>0)
                        y+=.5
                    if any(segment.difference(part).length>.000001 for segment in path):
                        raise ValueError(f'{board} H{index}: toolpath escapes center domain')
                    swept_path=unary_union([segment.buffer(.5,quad_segs=64)
                                            for segment in path]).intersection(aperture)
                    target=part.buffer(.5,quad_segs=64).intersection(aperture)
                    if (target.difference(swept_path).area>.00001 or
                            swept_path.difference(target).area>.00001):
                        raise ValueError(f'{board} H{index}: finite toolpath misses swept area')
                    path_digest=hashlib.sha256()
                    for segment in path:
                        path_digest.update(segment.wkb)
                    components.append({
                        'componentIndex0':component_index,
                        'admissibleCenterAreaMm2':round(part.area,9),
                        'centerDomainNormalizedWkbSha256':digest(shapely.normalize(part).wkb),
                        'plungeCenterMm':[round(plunge.x,9),round(plunge.y,9)],
                        'plungeDiskContainedInOriginalHole':True,
                        'pathStrategy':'admissible center-boundary loops and 0.50 mm '
                                       'horizontal scanline segments; each segment can '
                                       'plunge from above within this aperture',
                        'pathElementCount':len(path),
                        'pathLengthMm':round(sum(segment.length for segment in path),6),
                        'orderedPathWkbSha256':path_digest.hexdigest(),
                        'pathSweepUncoveredAreaMm2':round(target.difference(swept_path).area,9),
                    })
                if unary_union(swept).difference(corrected_cutouts).area>.00001:
                    raise ValueError(f'{board} H{index}: swept domain missing from output')
                if change and change['toolCenterComponents']!=len(components):
                    raise ValueError(f'{board} H{index}: indexed center count changed')
                records.append({'board':board,'originalHoleIndex0':index,
                                'status':'admissible component plunge domains',
                                'ribCorrectedAperture':rib_affected,
                                'components':components})
    split=[r for r in records if len(r['components'])>1]
    if {(r['board'],r['originalHoleIndex0']) for r in split}!={
            ('kumiko-void-L05',14),('woven-maze-L04',0)}:
        raise ValueError('Split center-region inventory changed')
    result={'status':'finite centerline path and plunge proof; machine CAM pending',
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
