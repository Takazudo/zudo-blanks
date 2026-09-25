"""Independent checks for the separate routing candidate and its indexed deltas."""
import hashlib
import importlib.util
import itertools
import json
import copy
from pathlib import Path
import unittest

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
module = importlib.util.spec_from_file_location('export_reference', ROOT/'tools/export_kicad.py')
export = importlib.util.module_from_spec(module)
module.loader.exec_module(export)
mask_module = importlib.util.spec_from_file_location('repair_mask_candidate',
                                                     HERE/'repair_mask_candidate.py')
mask_repair = importlib.util.module_from_spec(mask_module)
mask_module.loader.exec_module(mask_repair)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(data):
    for family in data['designs']:
        yield (next(d for d in family['variants'] if d.get('variantId') == 'wide')
               if family['id'] == 'kumiko-void' else family)


class ManufacturingGeometryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((HERE/'policy.json').read_text())
        cls.original = json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
        cls.candidate = json.loads((HERE/'manufacturing-geometry.json').read_text())
        cls.ledger = json.loads((HERE/'indexed-deltas.json').read_text())

    def test_source_and_candidate_hashes(self):
        self.assertEqual(digest(ROOT/'preview-source/assets/geometry.json'),
                         self.policy['sourceHashes']['preview-source/assets/geometry.json'])
        self.assertEqual(digest(HERE/'manufacturing-geometry.json'),
                         self.ledger['manufacturingGeometrySha256'])
        self.assertEqual(self.ledger['policySha256'], digest(HERE/'policy.json'))

    def test_art_findings_are_explicitly_unresolved(self):
        report=json.loads((HERE/'art-candidate-audit.json').read_text())
        source=json.loads((ROOT/'validation/export-art-review.json').read_text())
        expected=sum(len(b['copperGapsBelow010Mm'])+len(b['blackMaskGapsBelow013Mm'])
                     for b in source['boards'] if b['category']=='selected')
        self.assertEqual(len(report['findings']),expected)
        self.assertEqual(len(report['findings']),715)
        self.assertEqual(report['geometrySha256'],digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(len({f['key'] for f in report['findings']}),715)
        self.assertTrue(all(f['disposition'].startswith('unresolved') for f in report['findings']))
        self.assertEqual(len(report['finishedUnionPairs']),980)
        self.assertEqual(len({f['key'] for f in report['finishedUnionPairs']}),980)
        self.assertTrue(all(f['gapMm']<.25 for f in report['finishedUnionPairs']))
        self.assertEqual(len(report['necessaryWidthFailures']),289)
        copper_pairs=[f for f in report['finishedUnionPairs'] if f['feature']=='F.Cu island gap']
        self.assertEqual(len(copper_pairs),176)
        self.assertEqual(sum(not f['straight025MmJoinFitsCopperSafeRegion'] for f in copper_pairs),8)
        self.assertEqual(len(self.ledger['strokeWidthChanges']),680)
        source_strokes=sum(1 for design in selected(self.original) for layer in design['layers']
                           for stroke in layer['art']['strokes'] if stroke.get('color') is None
                           and stroke.get('purpose')!='top-gold-border'
                           and 0<stroke.get('w',0)<.25)
        self.assertEqual(source_strokes,680)

    def test_inherited_findings_have_final_union_cross_references(self):
        report=json.loads((HERE/'art-resolution-ledger.json').read_text())
        self.assertEqual(report['selectedFindingCount'],715)
        self.assertEqual(len({f['key'] for f in report['findings']}),715)
        self.assertEqual(report['maskCandidateSha256'],digest(HERE/'mask-repair-candidate.json'))
        self.assertEqual(report['copperLedgerSha256'],digest(HERE/'copper-repair-ledger.json'))
        self.assertTrue(all(f['finishedUnionDistinctGapScreen'].startswith('pass:')
                            for f in report['findings']))
        self.assertTrue(all(f['withinComponentWidthProof']=='pending'
                            for f in report['findings']))
        self.assertEqual(report['alternativeIssueIds'],
                         self.policy['alternativeUnresolvedIssueIds'])

    def test_actual_union_comparison_images_track_sources(self):
        report=json.loads((HERE/'candidate-comparisons.json').read_text())
        self.assertEqual(report['approvedGeometrySha256'],
                         digest(ROOT/'preview-source/assets/geometry.json'))
        self.assertEqual(report['manufacturingGeometrySha256'],
                         digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(report['maskCandidateSha256'],
                         digest(HERE/'mask-repair-candidate.json'))
        self.assertEqual(len(report['designs']),5)
        self.assertEqual(sum(d['selectedEnigLayers'] for d in report['designs']),11)
        for design in report['designs']:
            self.assertEqual(design['imageSha256'],digest(HERE/design['image']))
        self.assertEqual(sum(d['selectedLayers']
                             for d in report['allSelectedLayerComparisons']),43)
        for design in report['allSelectedLayerComparisons']+report['details']:
            self.assertEqual(design['imageSha256'],digest(HERE/design['image']))

    def test_inventory_closures_and_explicit_indices(self):
        self.assertEqual(sum(len(d['layers']) for d in selected(self.candidate)), 43)
        standard = next(d for d in self.candidate['designs'] if d['id']=='kumiko-void')
        original = next(d for d in self.original['designs'] if d['id']=='kumiko-void')
        self.assertEqual(standard['layers'], original['layers'])
        self.assertEqual(len(standard['layers']), 9)
        self.assertEqual(len(self.ledger['closedIssueIds']), 56)
        self.assertEqual(set(self.ledger['closedIssueIds']),
                         {a['issueId'] for a in self.policy['selectedApertureActions']})
        pairs = [(d['board'], d['geometryHoleIndex0']) for d in self.ledger['changes']]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_aperture_loss_registration_and_support(self):
        original = list(selected(self.original))
        candidate = list(selected(self.candidate))
        spec = self.original['spec']
        self.assertEqual(self.candidate['spec'], spec)
        for before_design, after_design in zip(original, candidate):
            self.assertEqual(before_design['id'], after_design['id'])
            for before, after in zip(before_design['layers'], after_design['layers']):
                key = (before_design['id'], before['index']+1)
                with self.subTest(board=key):
                    self.assertEqual(before['outer'], after['outer'])
                    expected_art=copy.deepcopy(before['art'])
                    expected_widths={c['artStrokeIndex0']:c for c in self.ledger['strokeWidthChanges']
                                     if c['board']==f'{key[0]}-L{key[1]:02d}'}
                    for i,change in expected_widths.items():
                        self.assertEqual(expected_art['strokes'][i]['w'],change['originalWidthMm'])
                        expected_art['strokes'][i]['w']=change['manufacturingWidthMm']
                    for change in self.ledger['artGuideChanges']:
                        if change['board']==f'{key[0]}-L{key[1]:02d}':
                            i=change['artStrokeIndex0']
                            expected_art['strokes'][i]['pts']=after['art']['strokes'][i]['pts']
                    for change in self.ledger['artNeckChanges']:
                        if change['board']==f'{key[0]}-L{key[1]:02d}':
                            i=change['artStrokeIndex0']
                            expected_art['strokes'][i]['pts']=after['art']['strokes'][i]['pts']
                    for change in self.ledger['artFillChanges']:
                        if change['board']==f'{key[0]}-L{key[1]:02d}':
                            i=change['artFillIndex0']
                            expected_art['fills'][i]['pts']=after['art']['fills'][i]['pts']
                    if key==('coral-vault',1):
                        for i,(a,b) in enumerate(zip(expected_art['strokes'],after['art']['strokes'])):
                            if (a.get('purpose')=='top-gold-border' and a.get('feature')=='stack-hole'
                                    and a.get('featureIndex') in (1,2,3)):
                                a['pts']=b['pts']
                    self.assertEqual(expected_art,after['art'])
                    old = unary_union([Polygon(h) for h in before['holes']])
                    new = unary_union([Polygon(h) for h in after['holes']])
                    self.assertLess(new.difference(old).area, .00001)
                    self.assertTrue(all(Polygon(h).is_valid for h in after['holes']))
                    decorative_old = [Polygon(h) for h in before['holes'] if not any(
                        Polygon(h).covers(Point(x,y)) for x,y in spec['screws'])]
                    if before['index']==0:
                        decorative_old = [p for p in decorative_old if not any(
                            p.covers(Point(x,y)) for x,y in spec['slots'])]
                    old_area = sum(p.area for p in decorative_old)
                    loss = old.area-new.area
                    limit = (.035 if key==('kumiko-void',1) else .02)
                    if old_area:
                        self.assertLessEqual(loss/old_area, limit+.000001)
                    functional = [Polygon(h) for h in after['holes'] if any(
                        Polygon(h).covers(Point(x,y)) for x,y in spec['screws']+(
                            spec['slots'] if before['index']==0 else []))]
                    decorative = new.difference(unary_union(functional))
                    material = Polygon(after['outer']).difference(decorative)
                    for x,y in spec['screws']:
                        self.assertLess(Point(x,y).buffer(3.05,quad_segs=128).difference(material).area,
                                        .00001)
                    rect = box(*(self.policy['mechanical']['topBoundsMm'] if before['index']==0
                                 else self.policy['mechanical']['lowerBoundsMm']))
                    self.assertLess(material.symmetric_difference(rect.difference(decorative)).area,.00001)
                    if before['index']==0:
                        self.assertLess(decorative.difference(box(0,17.1,101.3,111.4)).area,.00001)

    def test_tool_sweeps_and_structural_registration(self):
        indexed = {(c['board'],c['geometryHoleIndex0']):c for c in self.ledger['changes']}
        corrected = {d['id']:d for d in selected(self.candidate)}
        for original in selected(self.original):
            after_design = corrected[original['id']]
            previous = None
            paths = []
            for before, after in zip(original['layers'],after_design['layers']):
                board = f'{original["id"]}-L{before["index"]+1:02d}'
                drills = export.drill_specs(after, self.original['spec'])
                output_decorative = export.split_functional_holes(after,drills)
                cutouts = unary_union(output_decorative)
                substrate = Polygon(after['outer']).difference(cutouts)
                drilled = substrate.difference(unary_union([export.drill_shape(d) for d in drills]))
                with self.subTest(board=board):
                    self.assertEqual(drilled.geom_type,'Polygon')
                    self.assertGreaterEqual(len(export.polygons(drilled.buffer(-.5))),1)
                    cut_boundaries=[Polygon(r) for r in drilled.interiors]
                    widths=[p.distance(drilled.exterior) for p in cut_boundaries]
                    widths.extend(a.distance(b) for a,b in itertools.combinations(cut_boundaries,2))
                    self.assertGreaterEqual(min(widths,default=1),.999)
                    upper,lower = ((0,127.5) if before['index']==0 else (17.1,110.4))
                    for y in (upper,lower):
                        self.assertLess(box(0,y,101.3,y+1).difference(substrate).area,.00001)
                    if after.get('solid'):
                        self.assertEqual(len(output_decorative),0)
                    for i,hole in enumerate(before['holes']):
                        p=Polygon(hole)
                        if any(p.covers(Point(d['x'],d['y'])) for d in drills):
                            continue
                        action=indexed.get((board,i))
                        center=p.buffer(-.5,quad_segs=64)
                        if center.is_empty:
                            self.assertIsNotNone(action)
                            self.assertIsNotNone(action['issueId'])
                            continue
                        swept=center.buffer(.5,quad_segs=64).intersection(p)
                        # Output holes may split where the admissible cutter
                        # center has multiple components. Compare the union.
                        self.assertLess(swept.difference(cutouts).area,.00001)
                        self.assertEqual(action['toolCenterComponents'] if action else 1,
                                         len(export.polygons(center)))
                    if previous is not None and original['id'] in ('coral-vault','fault-line'):
                        self.assertLess(cutouts.difference(previous.buffer(.001)).area,.00001)
                    previous=cutouts
                    if original['id']=='woven-maze' and before['index']>0 and not after.get('solid'):
                        paths.append(hashlib.sha256(cutouts.wkb).hexdigest())
            if original['id']=='woven-maze':
                self.assertEqual(len(paths),len(set(paths)))

    def test_tool_center_plunge_domains_are_indexed(self):
        report=json.loads((HERE/'tool-access-ledger.json').read_text())
        self.assertEqual(report['sourceGeometrySha256'],
                         digest(ROOT/'preview-source/assets/geometry.json'))
        self.assertEqual(report['manufacturingGeometrySha256'],
                         digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(report['recordCount'],754)
        self.assertEqual(sum(not r['components'] for r in report['records']),56)
        split=[r for r in report['records'] if len(r['components'])>1]
        self.assertEqual({(r['board'],r['originalHoleIndex0']) for r in split},
                         {('kumiko-void-L05',14),('woven-maze-L04',0)})
        self.assertTrue(all(component['plungeDiskContainedInOriginalHole']
                            for r in report['records'] for component in r['components']))

    def test_indexed_guide_relocation(self):
        self.assertEqual(len(self.ledger['artGuideChanges']),22)
        self.assertEqual({c['artStrokeIndex0'] for c in self.ledger['artNeckChanges']},
                         {637,645,852,853,857})
        self.assertEqual(len(self.ledger['artFillChanges']),18)
        original={d['id']:d for d in selected(self.original)}
        corrected={d['id']:d for d in selected(self.candidate)}
        for change in self.ledger['artGuideChanges']:
            design_id=change['board'].split('-L')[0]
            before=original[design_id]['layers'][0]
            after=corrected[design_id]['layers'][0]
            index=change['artStrokeIndex0']
            old=before['art']['strokes'][index]['pts']
            new=after['art']['strokes'][index]['pts']
            distance=LineString(old).hausdorff_distance(LineString(new))
            self.assertLessEqual(distance,.5)
            self.assertGreater(distance,.10)
        for change in self.ledger['artFillChanges']:
            if change['board']=='kumiko-void-L07':
                self.assertIn(change['artFillIndex0'],(120,134))
                self.assertLess(change['addedAreaMm2'],.7)
                continue
            self.assertEqual(change['board'],'woven-maze-L01')
            index=change['artFillIndex0']
            old=original['woven-maze']['layers'][0]['art']['fills'][index]['pts']
            new=corrected['woven-maze']['layers'][0]['art']['fills'][index]['pts']
            self.assertEqual(len(old),len(new))
            self.assertAlmostEqual(max(Point(a).distance(Point(b)) for a,b in zip(old,new)),.0155,7)
        wide_before=original['kumiko-void']
        wide_after=corrected['kumiko-void']
        old_layer=wide_before['layers'][6]
        new_layer=wide_after['layers'][6]
        old_gold=export.paint_gold(old_layer,wide_before,
                                   mask_repair.source_body(old_layer,self.original['spec']))
        new_body=mask_repair.source_body(new_layer,self.candidate['spec'])
        new_gold=export.paint_gold(new_layer,wide_after,new_body)
        added=new_gold.difference(old_gold)
        self.assertAlmostEqual(added.area,1.2575552,6)
        self.assertLess(added.difference(mask_repair.safe_region(new_layer,new_body,'mask')).area,
                        .00001)

    def test_top_border_cores_in_candidate(self):
        for design in selected(self.candidate):
            layer=design['layers'][0]
            drills=export.drill_specs(layer,self.candidate['spec'])
            decorative=export.split_functional_holes(layer,drills)
            body=Polygon(layer['outer']).difference(unary_union(decorative)).difference(
                unary_union([export.drill_shape(d) for d in drills]))
            gold=export.paint_gold(layer,design,body)
            mask=gold.intersection(body.buffer(-.35,quad_segs=64))
            rims=[s for s in layer['art']['strokes'] if s.get('purpose')=='top-gold-border']
            self.assertEqual(len(rims),9,design['id'])
            for stroke in rims:
                with self.subTest(design=design['id'],feature=stroke.get('feature'),
                                  index=stroke.get('featureIndex')):
                    core=export.stroke_geometry(dict(stroke,w=.25),design.get('artStyle')=='angular')
                    self.assertLess(core.difference(mask).area,.00001)

    def test_mask_repair_candidate_scope(self):
        report=json.loads((HERE/'mask-repair-candidate.json').read_text())
        self.assertEqual(report['sourceGeometrySha256'],digest(HERE/'manufacturing-geometry.json'))
        self.assertEqual(len(report['boards']),11)
        self.assertTrue(report['status'].startswith('candidate;'))
        self.assertEqual(sum(len(b['originalMaskFindingDispositions']) for b in report['boards']),650)
        design_by_id={d['id']:d for d in selected(self.candidate)}
        for entry in report['boards']:
            design=design_by_id[next(d for d in design_by_id if f'-{d}-' in entry['boardId'])]
            layer=design['layers'][int(entry['boardId'].split('-L')[1][:2])-1]
            mask=shapely.from_wkb(bytes.fromhex(entry['afterMaskWkbHex']))
            with self.subTest(board=entry['boardId']):
                self.assertTrue(mask.is_valid)
                self.assertEqual(len(list(mask_repair.pairs(mask))),0)
                if layer['index']>0:
                    self.assertGreaterEqual(mask.distance(Polygon(layer['outer']).exterior),.549)
                self.assertLessEqual(entry['goldLossFractionFromApproved'],.30)
                if entry['boardId'].startswith(('13-fault-line-L01','17-kumiko-void-wide-L01',
                                        '17-kumiko-void-wide-L04','17-kumiko-void-wide-L07')):
                    self.assertLessEqual(entry['toleranceAwareMiterWidthResidueAreaMm2'],
                                         .00001)
                    self.assertGreater(entry['indexedTerminalCaps'],0)
                self.assertEqual(entry['retreatCount'],sum(r['operation']=='one-sided local mask retreat'
                    for r in entry['records']))
                self.assertTrue(all(d['finishedUnionPairScreen'].startswith('pass:')
                                    for d in entry['originalMaskFindingDispositions']))
                if layer['index']==0:
                    for stroke in (s for s in layer['art']['strokes']
                                   if s.get('purpose')=='top-gold-border'):
                        core=export.stroke_geometry(dict(stroke,w=.25),
                                                    design.get('artStyle')=='angular')
                        self.assertLess(core.difference(mask).area,.00001)
                if design['id']=='kumiko-void':
                    original_wide=next(d for d in self.original['designs']
                                       if d['id']=='kumiko-void')['variants'][0]
                    for action in self.policy['selectedApertureActions']:
                        if action['layerNumber']!=layer['index']+1:
                            continue
                        closed=Polygon(original_wide['layers'][layer['index']]['holes'][
                            action['geometryHoleIndex0']])
                        self.assertLess(mask.intersection(closed).area,.00001)
                if design['id']=='spider-nest' and layer['index']==0:
                    merges=[r for r in entry['records'] if r['operation'].startswith(
                        'measured Spider guide-to-web')]
                    self.assertEqual(len(merges),4)
                    self.assertLessEqual(sum(r['patchAreaMm2'] for r in merges),30)
                    self.assertEqual({tuple(pair) for r in merges
                                      for pair in r['originalFinishedUnionPairs0']},
                                     {(0,1),(0,5),(0,2)})
                    self.assertEqual({tuple(pair) for r in merges
                                      for pair in r['sourceArtStrokePairs0']},
                                     {(41,111),(33,97),(38,112)})
                    self.assertLess(entry['widthResidueAreaMm2'],.5)
                if design['id']=='coral-vault' and layer['index']==0:
                    merges=[r for r in entry['records'] if r['operation'].startswith(
                        'merge isolated unpainted Coral')]
                    self.assertEqual(len(merges),19)
                    self.assertAlmostEqual(sum(r['islandAreaMm2'] for r in merges),
                                           1.039835068,6)
                    neck=[r for r in entry['records'] if r['operation'].startswith(
                        'add indexed Coral 527/524')]
                    self.assertEqual(len(neck),1)
                    self.assertEqual(neck[0]['originalArtStrokeIndices0'],[527,524])
                    self.assertAlmostEqual(neck[0]['patchAreaMm2'],.058779889,5)
                    self.assertEqual(len(export.polygons(mask)),190)
                if design['id']=='woven-maze' and layer['index']==0:
                    self.assertLess(entry['widthResidueAreaMm2'],.4)


if __name__ == '__main__':
    unittest.main()
