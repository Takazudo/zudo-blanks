"""Validate the bounded Spider permission, not final production printability."""
import hashlib
import json
from pathlib import Path
import unittest

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE=Path(__file__).resolve().parents[1]


def normsha(geometry):
    return hashlib.sha256(shapely.normalize(geometry).wkb).hexdigest()


def geometry(record):
    return shapely.from_wkb(bytes.fromhex(record['wkbHex']))


class SpiderErratumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((HERE/'policy.json').read_text())
        cls.rule=cls.policy['errata'][0]
        cls.raw=(HERE/cls.rule['evidence']).read_bytes()
        cls.evidence=json.loads(cls.raw)
        cls.mask=shapely.from_wkb(bytes.fromhex(cls.evidence['preMergeMaskWkbHex']))
        cls.body=shapely.from_wkb(bytes.fromhex(cls.evidence['candidateBodyWkbHex']))
        cls.parts=sorted(cls.mask.geoms,key=lambda p:(tuple(round(v,6) for v in p.bounds),round(p.area,9)))
        cls.safe=cls.body.buffer(-.35,quad_segs=64)

    def test_source_and_candidate_bindings(self):
        self.assertEqual({r['id'] for r in self.policy['errata']},
                         {'spider-l01-channel-merge-2026-09-25','spider-l01-rib-width-2026-09-25',
                          'spider-l01-complete-network-2026-09-25','spider-l01-unfiltered-network-2026-09-25'})
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),self.rule['evidenceSha256'])
        self.assertEqual(self.rule['id'],'spider-l01-channel-merge-2026-09-25')
        self.assertEqual(self.rule['boardId'],'01-spider-nest-L01-black-enig-art')
        self.assertEqual(self.rule['sourceStrokePairs0'],[[41,111],[33,97],[38,112]])
        self.assertEqual(normsha(self.mask),self.rule['preMergeMaskNormalizedWkbSha256'])
        self.assertEqual(self.evidence['originalReviewedCandidateSha256'],self.rule['reviewedCandidateSha256'])
        self.assertEqual(self.evidence['evidenceCandidateSha256'],self.rule['evidenceCandidateSha256'])
        raw=(HERE.parent/'preview-source/assets/geometry.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.rule['approvedSourceSha256'])
        source=next(d for d in json.loads(raw)['designs'] if d['id']=='spider-nest')['layers'][0]
        self.assertFalse(any(a.get('color') for a in source['art']['fills']+source['art']['strokes']))
        for index,expected in self.evidence['sourceStrokeSha256'].items():
            encoded=json.dumps(source['art']['strokes'][int(index)],sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(hashlib.sha256(encoded).hexdigest(),expected)

    def test_four_reference_patches_are_pair_specific(self):
        patches=[]
        close=lambda g:g.buffer(.1255,quad_segs=32).buffer(-.1255,quad_segs=32)
        for pair in self.evidence['pairs']:
            a,b=[self.parts[i] for i in pair['componentIndices0']]
            reconstructed=close(a.union(b)).difference(close(a).union(close(b))).difference(a.union(b))
            recorded=unary_union([geometry(p) for p in pair['patches']])
            self.assertLess(reconstructed.symmetric_difference(recorded).area,.00001)
            self.assertAlmostEqual(a.distance(b),pair['beforeGapMm'],8)
            patches.extend(geometry(p) for p in pair['patches'])
        self.assertEqual(len(patches),4)
        self.assertLessEqual(unary_union(patches).area,30.0)
        self.assertLess(unary_union(patches).difference(self.safe).area,.00001)

    def test_implementation_example_stays_in_each_channel(self):
        references={p['id']:p for pair in self.evidence['pairs'] for p in pair['patches']}
        example=self.evidence['implementationExample']
        rounded=shapely.set_precision(self.mask,example['gridMm'])
        self.assertEqual(normsha(rounded),example['preMergeMaskNormalizedWkbSha256'])
        self.assertEqual(len(example['patches']),4)
        closed=rounded.buffer(.1255,quad_segs=64).buffer(-.1255,quad_segs=64)
        candidates=list(closed.difference(rounded).geoms)
        candidate_hashes={normsha(p) for p in candidates}
        for patch in example['patches']:
            self.assertIn(patch['normalizedWkbSha256'],candidate_hashes)
        self.assertEqual({p['id'] for p in example['patches']},set(references))
        patches=[]
        for record in example['patches']:
            patch=geometry(record)
            self.assertTrue(patch.is_valid)
            self.assertEqual(normsha(patch),record['normalizedWkbSha256'])
            reference=geometry(references[record['id']])
            self.assertGreater(patch.intersection(reference).area/min(patch.area,reference.area),.99)
            self.assertLess(patch.difference(self.mask.buffer(.1265)).area,.00001)
            self.assertLess(patch.difference(self.safe).area,.00001)
            for index in record['componentIndices0']:
                self.assertLessEqual(patch.distance(self.parts[index]),.001)
            patches.append(patch)
        additions=unary_union(patches)
        self.assertLessEqual(additions.area,self.rule['maximumTotalAddedGoldAreaMm2'])
        # Addition alone preserves pre-merge gold, including any rim core it contains.
        self.assertLess(self.mask.difference(self.mask.union(additions)).area,.00001)
        self.assertFalse(self.rule['referencePatchAreasAreEqualityRequirements'])

    def test_permission_is_not_a_width_or_cam_pass(self):
        self.assertEqual(self.rule['maximumTotalAddedGoldAreaMm2'],30.0)
        self.assertEqual(self.rule['minimumMaskSafeClearanceMm'],.35)
        self.assertFalse(self.rule['explicitBlackPaintAllowed'])
        self.assertFalse(self.rule['newTrappedMaskPocketsAllowed'])
        self.assertFalse(self.rule['productionApproval'])
        self.assertIn('positive gold width including connected branches',self.rule['requiredGates'])
        self.assertIn('negative mask width including channels inside one gold component',self.rule['requiredGates'])
        self.assertIn('full-board and enlarged before/after visual comparison',self.rule['requiredGates'])


if __name__=='__main__':
    unittest.main()
