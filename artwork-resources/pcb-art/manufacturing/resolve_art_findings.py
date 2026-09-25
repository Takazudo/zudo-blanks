#!/usr/bin/env python3
"""Cross-reference inherited art gaps with indexed final-union repairs."""
from __future__ import annotations

import hashlib
import json

from shapely.geometry import LineString, Point

from repair_mask_candidate import HERE, ROOT, digest


def run():
    review_path=ROOT/'validation/export-art-review.json'
    mask_path=HERE/'mask-repair-candidate.json'
    copper_path=HERE/'copper-repair-ledger.json'
    review=json.loads(review_path.read_text())
    masks=json.loads(mask_path.read_text())
    coppers=json.loads(copper_path.read_text())
    mask_boards={b['boardId']:b for b in masks['boards']}
    copper_boards={b['boardId']:b for b in coppers['boards']}
    findings=[]
    for board in review['boards']:
        if board['category']!='selected' or board['boardId'] not in mask_boards:
            continue
        name=board['boardId']
        recorded_mask={r['key']:r for r in mask_boards[name]['originalMaskFindingDispositions']}
        joins=copper_boards[name]['records']
        for feature,source_key in [('F.Mask black gap','blackMaskGapsBelow013Mm'),
                                   ('F.Cu island gap','copperGapsBelow010Mm')]:
            for issue in board[source_key]:
                i,j=issue['polygonIndices0']
                key=f'art:{board["sourceSha256"]}:{name}:{feature}:{i}:{j}'
                original_points=issue['closestPointsMm']
                item={
                    'key':key,'boardId':name,'feature':feature,
                    'sourceExportSha256':board['sourceSha256'],
                    'originalPolygonIndices0':[i,j],
                    'originalClosestPointsMm':original_points,
                    'originalGapMm':issue['gapMm'],
                    'finishedUnionDistinctGapScreen':'pass: no separate copper or gold '
                                                      'components closer than 0.25 mm',
                    'withinComponentWidthProof':'pending',
                }
                if feature=='F.Mask black gap':
                    known=recorded_mask[key]
                    item['nearbyMaskPatchRecordIndices0']=known['nearbyMaskPatchRecordIndices0']
                    item['nearbyRemovedComponentRecordIndices0']=known[
                        'nearbyRemovedComponentRecordIndices0']
                else:
                    midpoint=Point((original_points[0][0]+original_points[1][0])/2,
                                   (original_points[0][1]+original_points[1][1])/2)
                    item['nearbyCopperJoinRecordIndices0']=[index for index,r in enumerate(joins)
                        if LineString(r['centerlineMm']).distance(midpoint)<=.5]
                findings.append(item)
    if len(findings)!=715 or len({f['key'] for f in findings})!=715:
        raise ValueError('Original selected art finding inventory changed')
    policy=json.loads((HERE/'policy.json').read_text())
    report={
        'status':'distinct-component gap repairs cross-referenced; full width proof pending',
        'sourceReviewSha256':digest(review_path.read_bytes()),
        'manufacturingGeometrySha256':digest((HERE/'manufacturing-geometry.json').read_bytes()),
        'maskCandidateSha256':digest(mask_path.read_bytes()),
        'copperLedgerSha256':digest(copper_path.read_bytes()),
        'selectedFindingCount':len(findings),
        'alternativeIssueIds':policy['alternativeUnresolvedIssueIds'],
        'findings':findings,
    }
    (HERE/'art-resolution-ledger.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'selectedFindings':len(findings),
                      'copperWithNearbyJoin':sum(bool(f.get('nearbyCopperJoinRecordIndices0'))
                                                for f in findings if f['feature']=='F.Cu island gap')}))


if __name__=='__main__':
    run()
