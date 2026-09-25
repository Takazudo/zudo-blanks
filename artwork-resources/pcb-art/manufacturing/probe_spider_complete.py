#!/usr/bin/env python3
"""Unfiltered Spider decision and bounded terminal proof; no production export."""
import copy
import importlib.util
import json
import math
from pathlib import Path

import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('spider_network_history', HERE/'probe_spider_network.py')
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
spec = importlib.util.spec_from_file_location('spider_complete_export', ROOT/'tools/export_kicad.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)
digest, normsha, coordsha = history.digest, history.normsha, history.coordsha
polygons, frame, intervals = history.polygons, history.frame, history.intervals
MISSED = {0: (-1,109), 1: (-1,106), 11: (1,96), 12: (1,100),
          13: (-1,99), 14: (-1,102), 19: (1,108), 20: (1,107),
          21: (-1,113), 22: (-1,110), 23: (1,113), 24: (1,110),
          33: (1,103), 38: (1,103), 41: (1,103)}
SIDES = {i: list(zip((-1,1), guides)) for i,guides in history.GUIDES.items()}
SIDES.update({i:[side] for i,side in MISSED.items()})
RADIUS = .124999
ENDPOINT = (62.3351,62.7319)
CURVE = [(62.181101247,62.580686103),
         (62.17314271088659,62.60961120806345),
         (62.197407280681276,62.73523629369559),
         (62.204648978,62.764349140)]
MITER = (63.223765344788745,62.58198555873749)


def survey(top, snapshot):
    """Every source 0–94, including a central gold interval widened by a merge."""
    body = shapely.from_wkb(bytes.fromhex(snapshot['bodyWkbHex']))
    gold = shapely.from_wkb(bytes.fromhex(snapshot['goldWkbHex']))
    inks = sorted(polygons(body.difference(gold)), key=lambda p:-p.area)
    ink_tree = STRtree(inks)
    guide_tree = STRtree([LineString(s['pts']) for s in snapshot['guideCenterlines']])
    runs = []
    for index,stroke in enumerate(top['art']['strokes'][:95]):
        for segment,(a,b) in enumerate(zip(stroke['pts'],stroke['pts'][1:])):
            length,u,n = frame(a,b)
            if length < 1:
                continue
            count = max(2,math.ceil(length/.2))
            step = length/count
            samples = []
            for j in range(count):
                t = (j+.5)*step
                m = (a[0]+t*u[0],a[1]+t*u[1])
                section = LineString([(m[0]-2*n[0],m[1]-2*n[1]),(m[0]+2*n[0],m[1]+2*n[1])])
                spans = intervals(gold,section,m,n)
                central = next((k for k,(lo,hi) in enumerate(spans) if lo < 0 < hi),None)
                row = {}
                # Deliberately no central-gold-width filter: opposite-side
                # merges do not excuse a remaining narrow black channel.
                if central is not None:
                    material = next((lo,hi) for lo,hi in intervals(body,section,m,n) if lo < 0 < hi)
                    for side in (-1,1):
                        other = central+side
                        if not 0 <= other < len(spans):
                            continue
                        lo,hi = ((spans[central][1],spans[other][0]) if side == 1
                                 else (spans[other][1],spans[central][0]))
                        if not 1e-6 < hi-lo < .25:
                            continue
                        offset = (lo+hi)/2
                        hits = ink_tree.query(Point(m[0]+offset*n[0],m[1]+offset*n[1]),predicate='intersects')
                        if len(hits) != 1:
                            continue
                        outer = sum(spans[other])/2
                        gi = int(guide_tree.nearest(Point(m[0]+outer*n[0],m[1]+outer*n[1])))
                        available = material[1] if side == 1 else -material[0]
                        row[side] = {'width':hi-lo,'availableSide':available,
                                     'guide':snapshot['guideCenterlines'][gi]['sourceStrokeIndex0'],
                                     'ink':int(hits[0]),'centralGoldWidth':spans[central][1]-spans[central][0]}
                samples.append(row)
            for threshold in (.13,.25):
                for side in (-1,1):
                    start = None
                    last = None
                    for j in range(count+1):
                        value = samples[j].get(side) if j < count else None
                        key = (value['guide'],value['ink']) if value and value['width'] < threshold else None
                        if start is not None and key != last:
                            if (j-start)*step >= 1:
                                values = [samples[k][side] for k in range(start,j)]
                                runs.append({'sourceStrokeIndex0':index,'sourceSegmentIndex0':segment,
                                             'side':side,'thresholdMm':threshold,'guideStrokeIndex0':last[0],
                                             'inkComponentNormalizedWkbSha256':normsha(inks[last[1]]),
                                             'distanceAlongSegmentMm':[start*step,j*step],
                                             'sampleSpacingMm':step,'lengthMm':(j-start)*step,
                                             'widthRangeMm':[min(v['width'] for v in values),max(v['width'] for v in values)],
                                             'centralGoldWidthRangeMm':[min(v['centralGoldWidth'] for v in values),max(v['centralGoldWidth'] for v in values)],
                                             'minimumAvailableChannelSideMm':min(v['availableSide'] for v in values),
                                             'requiredChannelSideAt025Mm':.14+.25+.25+.35,
                                             'maximumSideDeficitMm':max(0,.99-min(v['availableSide'] for v in values))})
                            start = None
                        if key is not None and start is None:
                            start,last = j,key
    return {'method':'all source strokes 0–94; both adjacent guide sides; <=0.20 mm sample step and >=1 mm runs; no central-gold-width exclusion; not an exhaustive terminal-width certificate',
            'interiorRuns':[r for r in runs if r['sourceStrokeIndex0'] < 43],
            'rimTransitionFlags':[r for r in runs if r['sourceStrokeIndex0'] >= 43]}


def guide_portions(top):
    result = []
    for central,sides in sorted(SIDES.items()):
        points = top['art']['strokes'][central]['pts']
        for segment,(a,b) in enumerate(zip(points,points[1:])):
            length,u,n = frame(a,b)
            for side,guide in sides:
                hits = []
                gps = top['art']['strokes'][guide]['pts']
                for edge,(c,d) in enumerate(zip(gps,gps[1:])):
                    gl,gu,_ = frame(c,d)
                    if gl < 1 or abs(gu[0]*u[0]+gu[1]*u[1]) < .9999:
                        continue
                    offsets = [(v[0]-a[0])*n[0]+(v[1]-a[1])*n[1] for v in (c,d)]
                    ts = [(v[0]-a[0])*u[0]+(v[1]-a[1])*u[1] for v in (c,d)]
                    lo,hi = max(min(ts),0),min(max(ts),length)
                    if hi-lo < 1 or max(abs(v) for v in offsets) > .8:
                        continue
                    original = [[c[k]+(d[k]-c[k])*(t-ts[0])/(ts[1]-ts[0]) for k in (0,1)] for t in (lo,hi)]
                    proposed = [[a[k]+t*u[k]+side*.5165*n[k] for k in (0,1)] for t in (lo,hi)]
                    reach = max(math.dist(v,w) for v,w in zip(original,proposed))
                    assert reach <= .5
                    hits.append({'centralStrokeIndex0':central,'centralSegmentIndex0':segment,
                                 'guideStrokeIndex0':guide,'originalGuideEdgeIndex0':edge,
                                 'originalGuideContourSha256':coordsha(gps),'originalEdgeMm':[c,d],
                                 'originalPortionMm':original,'distanceAlongCentralSegmentMm':[lo,hi],
                                 'side':side,'nominalCenterOffsetMm':side*.5165,
                                 'nominalRelocatedPortionMm':proposed,'maximumNominalDisplacementMm':reach})
                assert len(hits) == 1,(central,segment,guide)
                result.extend(hits)
    return result


def line_intersection(a,b,c,d):
    def cross(v,w):
        return v[0]*w[1]-v[1]*w[0]
    u,v = [b[k]-a[k] for k in (0,1)],[d[k]-c[k] for k in (0,1)]
    denominator = cross(u,v)
    if abs(denominator) < 1e-9:
        return [(b[k]+c[k])/2 for k in (0,1)]
    t = cross([c[k]-a[k] for k in (0,1)],v)/denominator
    return [a[k]+t*u[k] for k in (0,1)]


def indexed_miters(top, portions):
    """Use source edge order and shared vertices, never global length ratios."""
    by_guide = {}
    for p in portions:
        edge = p['originalEdgeMm']
        dx,dy = edge[1][0]-edge[0][0],edge[1][1]-edge[0][1]
        pairs = sorted(zip(p['originalPortionMm'],p['nominalRelocatedPortionMm']),
                       key=lambda pair:(pair[0][0]-edge[0][0])*dx+(pair[0][1]-edge[0][1])*dy)
        by_guide.setdefault(p['guideStrokeIndex0'],[]).append((p,pairs))
    result = []
    for guide,records in sorted(by_guide.items()):
        line = LineString(top['art']['strokes'][guide]['pts'])
        records.sort(key=lambda row:(row[0]['originalGuideEdgeIndex0'],line.project(Point(row[1][0][0]))))
        for (a,ap),(b,bp) in zip(records,records[1:]+records[:1]):
            if math.dist(ap[-1][0],bp[0][0]) > 1e-5:
                continue
            point = line_intersection(ap[0][1],ap[1][1],bp[0][1],bp[1][1])
            reach = math.dist(point,ap[-1][0])
            assert reach <= .5,(guide,point,reach)
            result.append({'guideStrokeIndex0':guide,
                           'centralStrokeIndices0':[a['centralStrokeIndex0'],b['centralStrokeIndex0']],
                           'originalGuideEdgeIndices0':[a['originalGuideEdgeIndex0'],b['originalGuideEdgeIndex0']],
                           'originalSharedPointMm':ap[-1][0],'intersectionMm':point,'displacementMm':reach})
    return result


def width_residue(g):
    return g.difference(g.buffer(-RADIUS,join_style='mitre',quad_segs=64).buffer(RADIUS,join_style='mitre',quad_segs=64))


def terminal_probe(body, original_top, network_envelope):
    raw = (HERE/'spider-complete-input.json').read_bytes()
    capture = json.loads(raw)
    assert capture['approvedSourceSha256'] == history.SOURCE_SHA
    oldbody = shapely.from_wkb(bytes.fromhex(capture['bodyWkbHex']))
    oldgold = shapely.from_wkb(bytes.fromhex(capture['goldWkbHex']))
    layer = capture['layer']
    design = {'id':'spider-nest','artStyle':capture['artStyle']}
    oldpaint = export.paint_gold(layer,design,oldbody).intersection(oldbody.buffer(-.35,quad_segs=64))
    remove,add = oldpaint.difference(oldgold),oldgold.difference(oldpaint)
    safe = body.buffer(-.35,quad_segs=64)
    revised = copy.deepcopy(layer)
    def index(points,target):
        i = min(range(len(points)),key=lambda i:math.dist(points[i],target))
        assert math.dist(points[i],target) < 1e-6
        return i
    points = revised['art']['strokes'][100]['pts']
    i,j = index(points,(63.217890084,62.558366018)),index(points,(63.117009075,62.64269289))
    assert j == i+1
    revised['art']['strokes'][100]['pts'] = points[:i]+[list(MITER)]+points[j+1:]
    def mask(l):
        return shapely.from_wkb(shapely.set_precision(
            export.paint_gold(l,design,body).intersection(safe).difference(remove).union(add),1e-6).wkb)
    before = mask(revised)
    points = revised['art']['strokes'][103]['pts']
    a,c1,c2,b = CURVE
    i,j = index(points,a),index(points,b)
    assert j == i+3
    curve = []
    for k in range(65):
        t = k/64
        curve.append([(1-t)**3*a[z]+3*(1-t)**2*t*c1[z]+3*(1-t)*t*t*c2[z]+t**3*b[z] for z in (0,1)])
    revised['art']['strokes'][103]['pts'] = points[:i]+curve+points[j+1:]
    curved = mask(revised)
    endpoint = Point(ENDPOINT)
    envelope = endpoint.buffer(.5,quad_segs=64)
    cap_envelope = endpoint.buffer(.55,quad_segs=64)
    ink = body.difference(curved)
    disk_union = ink.buffer(-.125,quad_segs=64).buffer(.125,quad_segs=64)
    caps = [q for q in polygons(ink.difference(disk_union)) if q.area > 1e-8 and q.intersects(envelope)]
    assert len(caps) == 3
    patch = unary_union(caps)
    assert abs(patch.area-.04765467720707662) < 1e-8
    after = shapely.from_wkb(shapely.set_precision(curved.union(patch),1e-6).wkb)
    final_ink = body.difference(after)
    core = unary_union([export.stroke_geometry(s,design['artStyle']=='angular') for s in layer['art']['strokes'][:95]])
    rims = unary_union([export.stroke_geometry(dict(s,w=.25),design['artStyle']=='angular') for s in layer['art']['strokes'] if s.get('purpose')=='top-gold-border'])
    reach = LineString(original_top['art']['strokes'][103]['pts']).hausdorff_distance(LineString(revised['art']['strokes'][103]['pts']))
    reference_difference = final_ink.intersection(envelope).symmetric_difference(disk_union.intersection(envelope))
    # Cover the entire changed terminal and its .50 mm approach, including
    # both cap tails outside .50. The whole .55 camera circle also catches an
    # unrelated guide100 corner; opening that corner is not authorized here.
    proof_envelope = envelope.union(patch.buffer(.001,quad_segs=64))
    full_reference_difference = final_ink.intersection(proof_envelope).symmetric_difference(disk_union.intersection(proof_envelope))
    full_reference_distance = final_ink.intersection(proof_envelope).hausdorff_distance(disk_union.intersection(proof_envelope))
    prior = json.loads((HERE/'spider-channel-erratum.json').read_text())
    prior_patches = unary_union([shapely.from_wkb(bytes.fromhex(p['wkbHex']))
                                 for p in prior['implementationExample']['patches']])
    checks = {
        'allTerminalChangesInsideNetworkEnvelope':after.symmetric_difference(before).difference(network_envelope).area < 1e-5,
        'curvePaintInside050':curved.symmetric_difference(before).difference(envelope).area < 1e-5,
        'priorFourPatchesUnchanged':after.symmetric_difference(before).intersection(prior_patches).area < 1e-5,
        'sourceHasNoExplicitBlackPaint':not any(a.get('color') for a in original_top['art']['fills']+original_top['art']['strokes']),
        'curveCenterlineInsideOriginalEndpointEnvelope':LineString(curve).difference(envelope).length < 1e-8,
        'guideDisplacementWithin050':reach <= .5,
        'onlyBoundCapsInside055':patch.difference(cap_envelope).area < 1e-8,
        'goldInside035SafeRegion':after.difference(before).difference(safe).area < 1e-5,
        'radialGoldPreserved':core.intersection(before).difference(after).area < 1e-5,
        'nineRimCoresPreserved':rims.difference(after).area < 1e-5,
        'goldComponentsUnchanged':len(polygons(before)) == len(polygons(after)) == 5,
        'oneErodedCorePerGoldComponent':sum(len(polygons(q.buffer(-RADIUS,quad_segs=64))) for q in polygons(after)) == 5,
        'capsPreserveExistingInkComponents':len(polygons(ink)) == len(polygons(final_ink)),
        'localGoldWidthScreen':width_residue(after).intersection(cap_envelope).area < 1e-5,
        'localInkWidthScreen':width_residue(final_ink).intersection(cap_envelope).area < 1e-5,
        'serializedInkMatches025DiskUnion':reference_difference.area < 1e-5 and final_ink.intersection(envelope).hausdorff_distance(disk_union.intersection(envelope)) < .001,
        'completeChangedTerminalAndApproachMatches025DiskUnion':full_reference_difference.area < 1e-5 and full_reference_distance < .001,
        'noLocalUndersizedInkPocket':not any(q.area > 1e-5 and q.intersects(envelope) and q.buffer(-RADIUS,quad_segs=64).is_empty for q in polygons(final_ink)),
    }
    assert all(checks.values()),checks
    report = {'input':'spider-complete-input.json','inputSha256':digest(raw),
              'inputMaskCandidateSha256':capture['maskCandidateSha256'],
              'baselineRole':'captured current guide artwork on 34-path material, with adjacent guide100 miter corrected; not complete final 68-portion artwork',
              'baselineGoldNormalizedWkbSha256':normsha(before),'curvedGoldNormalizedWkbSha256':normsha(curved),
              'finalGoldNormalizedWkbSha256':normsha(after),
              'guide100MiterMm':MITER,'guide100OriginalVertexMm':[63.0875,62.5908],
              'guide100DisplacementMm':math.dist(MITER,(63.0875,62.5908)),
              'guide103OriginalEdgeIndex0':27,'guide103OriginalEndpointMm':ENDPOINT,
              'cubicControlPointsMm':CURVE,'cubicSegments':64,'maximumGuide103DisplacementMm':reach,
              'curveGoldAddedAreaMm2':curved.difference(before).area,'curveGoldRemovedAreaMm2':before.difference(curved).area,
              'curveGoldChangeOutside050AreaMm2':curved.symmetric_difference(before).difference(envelope).area,
              'terminalOpeningRadiusMm':.125,'quadrantSegments':64,'serializationGridMm':1e-6,
              'caps':[{'id':i,'areaMm2':q.area,'boundsMm':q.bounds,'normalizedWkbSha256':normsha(q),'wkbHex':q.wkb_hex,
                       'maximumDistanceFromEndpointMm':max(math.dist(v,ENDPOINT) for v in q.exterior.coords)} for i,q in enumerate(caps)],
              'diskUnionProofEnvelope':'union of original endpoint radius-0.50 disk and all three exact caps buffered by 0.001 mm; includes every changed terminal boundary and the complete local approach',
              'combinedCapAreaMm2':patch.area,'capAreaOutside050Mm2':patch.difference(envelope).area,
              'capAreaOutside055Mm2':patch.difference(cap_envelope).area,
              'goldComponents':len(polygons(after)),'inkComponentsBeforeCurve':len(polygons(body.difference(before))),
              'inkComponentsAfterCurve':len(polygons(ink)),'inkComponentsAfterCaps':len(polygons(final_ink)),
              'localGoldMiterResidueAreaMm2':width_residue(after).intersection(cap_envelope).area,
              'localInkMiterResidueAreaMm2':width_residue(final_ink).intersection(cap_envelope).area,
              'serializedInkDiskUnionDifferenceAreaMm2':reference_difference.area,
              'completeTerminalDiskUnionDifferenceAreaMm2':full_reference_difference.area,
              'completeTerminalDiskUnionHausdorffMm':full_reference_distance,
              'serializedInkDiskUnionHausdorffMm':final_ink.intersection(envelope).hausdorff_distance(disk_union.intersection(envelope)),
              'checks':checks}
    return report,before,after


def measure():
    # Each import owns a private historical module instance. The historical
    # files and their independently reproducible probes remain unchanged.
    history.NEW_STROKES = sorted(set(history.NEW_STROKES)|set(MISSED))
    history.GUIDES = SIDES
    history.guide_portions = guide_portions
    report,before,initial,final = history.measure(include_survey=False)
    source = json.loads((ROOT/'preview-source/assets/geometry.json').read_text())
    top = next(d for d in source['designs'] if d['id']=='spider-nest')['layers'][0]
    snapshot = json.loads((HERE/'spider-network-input.json').read_text())
    report['id'] = 'spider-l01-unfiltered-network-2026-09-25'
    report['status'] = 'complete sustained-run survey and bounded material/terminal feasibility; final artwork and native/CAM gates pending'
    report['correctsDecisionId'] = 'spider-l01-complete-network-2026-09-25'
    report['surveyCorrection'] = 'remove central-gold-width<=0.31 exclusion; merged opposite-side gold never exempts the remaining ink channel'
    report['additionalPathSides'] = [{'centralStrokeIndex0':i,'side':s,'guideStrokeIndex0':g} for i,(s,g) in MISSED.items()]
    report['centralStrokeIndices0'] = sorted(SIDES)
    report['survey'] = survey(top,snapshot)
    report['sourceEdgeLocalMiters'] = indexed_miters(top,report['guidePortions'])
    # Preserve the 13 previously measured nominal joins as an auditable subset.
    previous_portions = json.loads((HERE/'spider-network-decision.json').read_text())['guidePortions']
    report['previouslyMeasuredThirteenMiters'] = indexed_miters(top,previous_portions)
    assert len(report['previouslyMeasuredThirteenMiters']) == 13
    assert len(report['guidePortions']) == 68
    assert len(report['centralStrokeIndices0']) == 34
    network_envelope = unary_union([LineString(p['pointsMm']).buffer(1,cap_style=2,join_style=2) for p in report['paths']]).buffer(.5)
    report['terminal'],term_before,term_after = terminal_probe(final,top,network_envelope)
    report['exporterSha256'] = digest((ROOT/'tools/export_kicad.py').read_bytes())
    report['sourceEdgeMapping'] = 'original edge index and endpoint correspondence; actual line intersections; never whole-contour normalized arclength'
    report['baseProbeSha256'] = digest((HERE/'probe_spider_network.py').read_bytes())
    report['probeScriptSha256'] = digest(Path(__file__).read_bytes())
    return report,before,initial,final,term_before,term_after


def render(report,before,initial,final,term_before,term_after):
    from PIL import Image,ImageDraw,ImageFont
    image = Image.new('RGB',(1400,1700),'#eef1ee')
    draw = ImageDraw.Draw(image)
    def font(size):
        for name in ['/System/Library/Fonts/Supplemental/Arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
            if Path(name).exists():
                return ImageFont.truetype(name,size)
        return ImageFont.load_default(size=size)
    def paint(g,bounds,x,y,w,h,color,hole_color='#eef1ee'):
        x0,y0,x1,y1 = bounds
        scale = min(w/(x1-x0),h/(y1-y0))
        def points(ring):
            return [(x+(xx-x0)*scale,y+(yy-y0)*scale) for xx,yy in ring.coords]
        for q in polygons(g.intersection(box(*bounds))):
            draw.polygon(points(q.exterior),fill=color)
            for ring in q.interiors:
                draw.polygon(points(ring),fill=hole_color)
    draw.text((25,20),'Spider L01: unfiltered 34-path decision correction',font=font(28),fill='#14212a')
    draw.text((25,66),'Left: pre-rib material. Right: all 34 paths; blue material ribbons, orange exact cutter cleanup.',font=font(18),fill='#14212a')
    draw.text((25,103),'Material and one indexed terminal proof only. Complete final artwork and CAM still require verification.',font=font(18),fill='#704527')
    bounds=(0,0,101.3,128.5)
    for x,g in [(60,before),(760,final)]:
        paint(g,bounds,x,155,530,675,'#293b47')
    paint(initial.difference(before),bounds,760,155,530,675,'#128dc2')
    paint(final.difference(initial),bounds,760,155,530,675,'#d16a22')
    draw.text((25,870),f"Cumulative aperture loss {100*report['cumulativeApertureLossFraction']:.6f}%; all 19 apertures retained.",font=font(22),fill='#14212a')
    draw.text((25,925),'Guide103/source31 terminal: before curved splice / after splice and exact round caps',font=font(20),fill='#14212a')
    crop=(61.85,61.95,63.5,63.6)
    for x,g in [(40,term_before),(740,term_after)]:
        paint(final,crop,x,975,620,600,'#222222')
        paint(g,crop,x,975,620,600,'#d1aa46',hole_color='#222222')
    caps=unary_union([shapely.from_wkb(bytes.fromhex(q['wkbHex'])) for q in report['terminal']['caps']])
    paint(caps,crop,740,975,620,600,'#d16a22',hole_color='#222222')
    draw.text((25,1610),'Caps: 0.047655 mm2, bounded at this endpoint only by 0.55 mm; guide displacement stays <=0.50 mm.',font=font(18),fill='#14212a')
    draw.text((25,1650),'The tiny candidate-created ink pocket rejoins its channel; the rounded caps preserve that channel.',font=font(18),fill='#14212a')
    image.save(HERE/'spider-complete-comparison.png')


if __name__=='__main__':
    result=measure()
    (HERE/'spider-complete-decision.json').write_text(json.dumps(result[0],indent=2)+'\n')
    render(*result)
    print(json.dumps({k:result[0][k] for k in ['initialAdditionAreaMm2','routingCleanupAreaMm2','combinedAdditionAreaMm2','cumulativeApertureLossFraction']}))
