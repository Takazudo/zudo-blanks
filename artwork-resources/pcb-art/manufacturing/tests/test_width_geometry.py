"""Synthetic cases for the opposing-boundary width test."""
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from shapely.geometry import Polygon, box

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import width_geometry  # noqa: E402
from width_geometry import enforce_copper, enforce_widths, violations  # noqa: E402


def wedge(degrees):
    half=math.radians(degrees/2)
    return Polygon([(0,0),(5*math.cos(half),5*math.sin(half)),(5*math.cos(half),-5*math.sin(half))])


class WidthGeometryTests(unittest.TestCase):
    def assertFails(self,region,width,chord):
        found=violations(region,width)
        self.assertTrue(found)
        self.assertAlmostEqual(found[0][1][0]['lengthMm'],chord,delta=.003)

    def test_thin_bar_neck_and_needle_fail(self):
        self.assertFails(box(0,0,5,.2),.25,.2)
        self.assertFails(box(0,0,2,2).union(box(2,.9,2.5,1.1)).union(box(2.5,0,4.5,2)),.25,.2)
        self.assertTrue(violations(wedge(15),.25))

    def test_short_gap_between_separate_pieces_fails(self):
        # Facing ends: an opening reconstructs the region beside the gap.
        gold=box(1,4,4,4.3).union(box(4.2,4,8,4.3))
        self.assertFails(box(-1,-1,11,11).difference(gold),.25,.2)

    def test_facing_tips_of_one_piece_fail(self):
        # One U-shaped gold piece whose tips face each other 0.2 mm apart.
        gold=box(1,1,2,5).union(box(1,1,6,2)).union(box(5,1,6,5)).union(
            box(2,4.4,3.4,4.7)).union(box(3.6,4.4,5,4.7))
        self.assertFails(box(-1,-1,11,11).difference(gold),.25,.2)

    def test_gap_search_batched_and_single_query_agree(self):
        gold=box(1,1,2,5).union(box(1,1,6,2)).union(box(5,1,6,5)).union(
            box(2,4.4,3.4,4.7)).union(box(3.6,4.4,5,4.7))
        region=box(-1,-1,11,11).difference(gold)
        with patch.object(width_geometry,'SEGMENT_QUERY_BATCH',1), \
             patch.object(width_geometry,'SEGMENT_PAIR_BATCH',1):
            tiny=width_geometry.gap_zones(region,.25)
        with patch.object(width_geometry,'SEGMENT_QUERY_BATCH',10000), \
             patch.object(width_geometry,'SEGMENT_PAIR_BATCH',10000):
            broad=width_geometry.gap_zones(region,.25)
        self.assertTrue(tiny)
        self.assertEqual([zone.wkb for zone in tiny],[zone.wkb for zone in broad])

    def test_full_width_and_ordinary_corners_pass(self):
        for region in [box(0,0,5,.26),wedge(60),wedge(30),box(0,0,2,2).difference(box(.9,.9,1.1,1.1))]:
            self.assertEqual(violations(region,.25),[])

    def test_curved_edge_meeting_line_is_a_corner(self):
        corner=box(0,0,3,3).intersection(Polygon([(1.5,3.5),(3.5,3.5),(3.5,1.5)]).buffer(1,quad_segs=64))
        self.assertEqual(violations(corner,.25),[])

    def test_enforcement_opens_black_channel_by_retreat_only(self):
        body=box(0,0,10,10)
        gold=box(1,1,4,9).union(box(4.08,1,8,9))
        repaired,records,remaining=enforce_widths(gold,body,body.buffer(-.35),Polygon(),.13,'synthetic')
        self.assertEqual(remaining,[])
        self.assertTrue(records)
        self.assertLess(repaired.difference(gold).area,1e-9)
        self.assertEqual(violations(body.difference(repaired),.13),[])

    def test_enforcement_separates_facing_sharp_corners(self):
        # Two gold squares meeting corner to corner 0.1 mm apart diagonally.
        body=box(0,0,10,10)
        gold=box(2,2,4.9,4.9).union(box(4.9707,4.9707,8,8))
        repaired,records,remaining=enforce_widths(gold,body,body.buffer(-.35),Polygon(),.13,'corners')
        self.assertEqual(remaining,[])
        self.assertLess(repaired.difference(gold).area,1e-9)
        self.assertEqual(violations(body.difference(repaired),.13),[])

    def test_copper_fill_batches_preserve_union_and_indexed_area(self):
        body=box(0,0,8,8)
        copper=box(1,1,2,7).union(box(2.2,1,3.2,7)).union(
            box(3.4,1,4.4,7)).union(box(4.6,1,5.6,7))
        single,single_records,single_remaining=enforce_copper(
            copper,copper,body,body,'single',free_batch_size=1,thin_batch_size=1)
        batched,batch_records,batch_remaining=enforce_copper(
            copper,copper,body,body,'batched',free_batch_size=32,thin_batch_size=32)
        self.assertEqual(single_remaining,[])
        self.assertEqual(batch_remaining,[])
        self.assertLess(single.symmetric_difference(batched).area,1e-6)
        self.assertEqual(sum(r.get('copperAddedAreaMm2',0) for r in batch_records),
                         sum(r.get('copperAddedAreaMm2',0) for r in single_records))
        self.assertTrue(any(r['operation'].startswith('fill sub-0.25')
                            for r in batch_records))

    def test_copper_thin_batches_preserve_local_acceptance_and_union(self):
        body=box(0,0,8,8)
        copper=box(1,1,1.2,7).union(box(3,1,3.2,7))
        single,single_records,single_remaining=enforce_copper(
            copper,copper,body,body,'thin single',thin_batch_size=1)
        batched,batch_records,batch_remaining=enforce_copper(
            copper,copper,body,body,'thin batched',thin_batch_size=32)
        self.assertEqual(single_remaining,batch_remaining)
        self.assertLess(single.symmetric_difference(batched).area,1e-6)
        self.assertEqual(sum(r.get('copperAddedAreaMm2',0) for r in batch_records),
                         sum(r.get('copperAddedAreaMm2',0) for r in single_records))
        self.assertTrue(any(r['operation'].startswith('widen thin') for r in batch_records))


if __name__=='__main__':
    unittest.main()
