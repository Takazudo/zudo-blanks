"""Finished-union width tests and the local repair that enforces them.

Width follows policy: opposing nonadjacent boundary points closer than the
class width, joined by an interior chord, fail. Adjacent-edge corners whose
boundary path is at most MITRE_RATIO times the chord (interior angle >= ~23
degrees, the same limit as a mitre opening) are ordinary corners. Candidates
come from the mitred opening residue, so the chord search stays local.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from repair_mask_candidate import export, rounded

TOLERANCE=.001
MITRE_RATIO=5.0
SAMPLE_STEP=.002


def _overlay(op,a,b):
    """Overlay that retries on validated inputs with 1 nm snap-rounding.

    Long enforcement runs on dense art occasionally hit GEOS topology errors
    (non-noded intersections, free holes) on near-coincident edges.
    """
    try:
        return op(a,b)
    except shapely.errors.GEOSException:
        return op(shapely.make_valid(a),shapely.make_valid(b),grid_size=1e-6)


def sub(a,b):
    return _overlay(shapely.difference,a,b)


def add(a,b):
    return _overlay(shapely.union,a,b)


def inter(a,b):
    return _overlay(shapely.intersection,a,b)


def clean(geom):
    """Valid polygonal part on the 1 nm grid.

    Geometry carrying a precision grid makes later overlays snap-rounded,
    which avoids GEOS non-noded intersection failures on near-coincident edges.
    """
    return rounded(unary_union(export.polygons(shapely.make_valid(geom))))


def opening_residue(region,width):
    radius=width/2-.000001
    core=region.buffer(-radius,join_style='mitre',quad_segs=64)
    return sub(region,core.buffer(radius,join_style='mitre',quad_segs=64))


def thick(residue):
    return [p for p in export.polygons(residue) if not p.buffer(-TOLERANCE/2).is_empty]


def plane_complement(body,region):
    # Mask beside a routed edge is governed by edge clearance, not web width.
    return sub(box(*body.bounds).buffer(1,join_style='mitre'),region)


class RingIndex:
    """Boundary rings of a region with a spatial index, built once per check."""

    def __init__(self,region):
        from shapely.strtree import STRtree
        self.rings=[r for poly in export.polygons(region) for r in [poly.exterior,*poly.interiors]]
        self.tree=STRtree(self.rings)

    def near(self,zone):
        return [self.rings[int(i)] for i in self.tree.query(zone,predicate='intersects')]


def violating_chords(region,piece,width,index=None):
    """Failing chords near a residue piece, worst first, one per half-width cell."""
    zone=clean(piece.buffer(width,quad_segs=16))
    index=index or RingIndex(region)
    points,ring_ids,along,lengths=[],[],[],[]
    for ring in index.near(zone):
        line=LineString(ring.coords)
        try:
            part=line.intersection(zone)
        except shapely.errors.GEOSException:
            part=shapely.intersection(line,zone,grid_size=1e-6)
        for seg in getattr(part,'geoms',[part]):
            if seg.is_empty or seg.geom_type not in ('LineString','LinearRing'):
                continue
            ts=np.linspace(0,seg.length,max(2,int(seg.length/SAMPLE_STEP)+1))
            sampled=shapely.line_interpolate_point(seg,ts)
            points.append(shapely.get_coordinates(sampled))
            # A clipped piece is a contiguous stretch of its ring: locate its
            # start once and add the offset instead of locating every sample.
            # Clipped pieces may come back reversed; take direction from the end.
            start=line.project(Point(seg.coords[0]))
            end=line.project(Point(seg.coords[-1]))
            forward=abs(np.mod(end-start,line.length)-seg.length)<=abs(np.mod(start-end,line.length)-seg.length)
            along.append(np.mod(start+ts if forward else start-ts,line.length))
            ring_ids.append(np.full(len(ts),len(lengths)))
        lengths.append(line.length)
    if not points:
        return []
    P=np.concatenate(points)
    R=np.concatenate(ring_ids)
    S=np.concatenate(along)
    L=np.array(lengths)[R][:,None]
    D=np.sqrt(((P[:,None,:]-P[None,:,:])**2).sum(-1))
    gap=np.abs(S[:,None]-S[None,:])
    path=np.where(R[:,None]==R[None,:],np.minimum(gap,L-gap),np.inf)
    pairs=np.argwhere(np.triu((D<width-TOLERANCE)&(D>1e-9)&(path>MITRE_RATIO*D)))
    if not len(pairs):
        return []
    pairs=pairs[np.argsort(D[pairs[:,0],pairs[:,1]],kind='stable')]
    mids=(P[pairs[:,0]]+P[pairs[:,1]])/2
    cells=np.floor(mids/(width/2)).astype(np.int64)
    chosen=[]
    for cell in np.unique(cells,axis=0):
        for k in np.flatnonzero((cells==cell).all(1))[:64]:
            i,j=pairs[k]
            step=P[j]-P[i]
            # Endpoints lie on the boundary; the middle 80% avoids losing a
            # sub-micron chord to 1 nm grid snapping.
            if region.contains(LineString([P[i]+.1*step,P[j]-.1*step])):
                chosen.append({'lengthMm':float(D[i,j]),'a':P[i],'b':P[j],'mid':mids[k]})
                break
    return sorted(chosen,key=lambda c:c['lengthMm'])


def gap_zones(region,width,within=None):
    """Candidate zones where two nonadjacent boundary segments come within width.

    Covers gaps between distinct rings and between far-apart parts of one ring
    (e.g. facing tips of one U-shaped piece), which an opening can miss when
    the region beside a short gap is reconstructed from both sides.
    """
    from shapely.strtree import STRtree
    starts,ends,ring_of,poly_of,along,ring_len=[],[],[],[],[],[]
    rings=[(p,r) for p,poly in enumerate(export.polygons(region))
           for r in [poly.exterior,*poly.interiors]]
    for k,(p,ring) in enumerate(rings):
        xy=np.asarray(ring.coords)
        seg=np.hypot(*(xy[1:]-xy[:-1]).T)
        starts.append(xy[:-1]);ends.append(xy[1:])
        ring_of.append(np.full(len(seg),k));poly_of.append(np.full(len(seg),p))
        along.append(np.concatenate([[0],np.cumsum(seg)[:-1]]))
        ring_len.append(np.full(len(seg),seg.sum()))
    if not starts:
        return []
    A=np.concatenate(starts);B=np.concatenate(ends);K=np.concatenate(ring_of);Q=np.concatenate(poly_of)
    S=np.concatenate(along);L=np.concatenate(ring_len)
    segments=shapely.linestrings(np.stack([A,B],axis=1))
    if within is not None:
        mask=shapely.dwithin(segments,within,width)
        index=np.flatnonzero(mask)
    else:
        index=np.arange(len(segments))
    if not len(index):
        return []
    tree=STRtree(segments)
    left,right=tree.query(segments[index],predicate='dwithin',distance=width-TOLERANCE)
    left=index[left]
    # A chord inside the region joins rings of one polygon; pairs across
    # separate polygons are the other phase's gap and are tested there.
    keep=(left<right)&(Q[left]==Q[right])
    left,right=left[keep],right[keep]
    lines=shapely.shortest_line(segments[left],segments[right])
    ends_xy=shapely.get_coordinates(lines).reshape(-1,2,2)
    distance=shapely.length(lines)
    # Ring path between the two closest points (segment start plus offset).
    at_l=S[left]+np.hypot(*(ends_xy[:,0]-A[left]).T)
    at_r=S[right]+np.hypot(*(ends_xy[:,1]-A[right]).T)
    gap=np.abs(at_l-at_r)
    around=np.minimum(gap,L[left]-gap)
    far=(K[left]!=K[right])|(around>MITRE_RATIO*np.maximum(distance,1e-9))
    left,right=left[far],right[far]
    if not len(left):
        return []
    lines=lines[far]
    mids=shapely.get_coordinates(shapely.line_interpolate_point(lines,.5,normalized=True))
    cells=np.unique(np.floor(mids/(width/2)).astype(np.int64),axis=0,return_index=True)[1]
    return [Point(mids[i]).buffer(width/2,quad_segs=16) for i in cells]


def violations(region,width,within=None):
    """Width failures of region; with within, only chords whose midpoint lies in it."""
    region=clean(region)
    shapely.prepare(region)
    found=[]
    index=RingIndex(region)
    keep=(lambda chords:[c for c in chords if within is None or within.contains(Point(c['mid']))])
    for piece in thick(opening_residue(region,width)):
        if within is not None and not piece.intersects(within):
            continue
        chords=keep(violating_chords(region,piece,width,index))
        if chords:
            found.append((piece,chords))
    for zone in gap_zones(region,width,within):
        chords=[c for c in keep(violating_chords(region,zone,width,index))
                if not any(np.hypot(*(c['mid']-d['mid']))<width/2 for _,known in found for d in known)]
        if chords:
            found.append((inter(disks(chords,width/2),region),chords))
    return found


def chord_row(phase,width,piece,chords):
    worst=chords[0]
    return {'phase':phase,'widthMm':width,'minimumChordMm':round(worst['lengthMm'],6),
            'chordMm':[[round(v,6) for v in worst['a']],[round(v,6) for v in worst['b']]],
            'chordCount':len(chords),'residueAreaMm2':round(piece.area,9),
            'residueBoundsMm':[round(v,6) for v in piece.bounds]}


def disks(chords,radius):
    """Disks at chord midpoints, joined by capsules to neighbours.

    Bare disks spaced about a radius apart leave cusps narrower than the
    diameter; capsules between neighbouring midpoints keep the full width.
    """
    mids=[c['mid'] for c in chords]
    shapes=[Point(m).buffer(radius,quad_segs=32) for m in mids]
    for i,a in enumerate(mids):
        for b in mids[i+1:]:
            if np.hypot(*(np.asarray(a)-np.asarray(b)))<=2*radius:
                shapes.append(LineString([a,b]).buffer(radius,quad_segs=32))
    return shapely.union_all(shapes)


def capsules(chords,radius):
    """Disks joined along each chord, so every point left is radius from it.

    A disk at the midpoint alone lets two sharp corners reappear on its rim
    a little closer than the diameter, so the gap creeps up without closing.
    """
    return shapely.union_all([disks(chords,radius)]+[
        LineString([c['a'],c['b']]).buffer(radius,quad_segs=32) for c in chords])


def enforce_widths(mask,body,safe,protected,black_width,label,max_iterations=24):
    """Retreat gold at failing black webs; widen or cap failing gold. Records every edit."""
    records=[]
    mask,body,safe,protected=clean(mask),clean(body),clean(safe),clean(protected)
    dirty=None
    for iteration in range(max_iterations):
        ink=violations(plane_complement(body,mask),black_width,dirty)
        gold=violations(mask,.25,dirty)
        if not ink and not gold:
            break
        before=mask
        for piece,chords in ink:
            cut=sub(inter(capsules(chords,black_width/2+TOLERANCE),mask),protected)
            if cut.area>0:
                records.append({'operation':'retreat gold to open indexed sub-width black web',
                                'iteration':iteration,**chord_row('black-ink',black_width,piece,chords),
                                'goldRemovedAreaMm2':round(cut.area,9),'goldRemovedWkbSha256':_sha(cut),
                                'editWkbHex':cut.wkb_hex})
                mask=clean(sub(mask,cut))
        for piece,chords in gold:
            grow=sub(inter(disks(chords,.125+TOLERANCE),safe),mask)
            widened=add(clean(mask),grow)
            zone=piece.buffer(.5)
            new_ink=[v for v in violations(inter(plane_complement(body,widened),zone.buffer(.3)),black_width)
                     if v[0].intersects(zone)]
            local=[v for v in violations(inter(widened,zone.buffer(.3)),.25) if v[0].intersects(piece)]
            if grow.area>0 and not new_ink and not local:
                records.append({'operation':'widen indexed sub-width gold inside mask-safe region',
                                'iteration':iteration,**chord_row('visible-gold',.25,piece,chords),
                                'goldAddedAreaMm2':round(grow.area,9),'goldAddedWkbSha256':_sha(grow),
                                'editWkbHex':grow.wkb_hex})
                mask=clean(widened)
            else:
                # Cap at the failing chords; they can lie beside the residue piece.
                cut=sub(inter(disks(chords,.125+TOLERANCE),mask),protected)
                records.append({'operation':'cap indexed sub-width gold where widening would narrow black',
                                'iteration':iteration,**chord_row('visible-gold',.25,piece,chords),
                                'goldRemovedAreaMm2':round(cut.area,9),'goldRemovedWkbSha256':_sha(cut),
                                'editWkbHex':cut.wkb_hex})
                mask=clean(sub(mask,cut))
        mask=clean(shapely.from_wkb(rounded(mask).wkb))
        changed=clean(mask.symmetric_difference(before))
        if changed.is_empty:
            break
        dirty=changed.buffer(.5,quad_segs=8)
    # Judge what downstream stages read: the WKB-serialized geometry.
    mask=shapely.from_wkb(mask.wkb)
    remaining=[chord_row('black-ink',black_width,p,c) for p,c in violations(plane_complement(body,mask),black_width)]
    remaining+=[chord_row('visible-gold',.25,p,c) for p,c in violations(mask,.25)]
    print(f'{label}: width enforcement stopped with {len(remaining)} unresolved',flush=True)
    return mask,records,remaining


def _sha(geom):
    import hashlib
    return hashlib.sha256(shapely.normalize(geom).wkb).hexdigest()


def enforce_copper(copper,required,safe,body,label,max_iterations=12):
    """Hidden copper: fill sub-0.25 copper-free gaps, widen or trim thin copper.

    required (gold plus its 0.05 mm margin) is never removed; nothing leaves safe.
    """
    records=[]
    copper,required,safe,body=clean(copper),clean(required),clean(safe),clean(body)
    dirty=None
    for iteration in range(max_iterations):
        free=violations(plane_complement(body,copper),.25,dirty)
        thin=violations(copper,.25,dirty)
        if not free and not thin:
            break
        before=copper
        for piece,chords in free:
            grow=sub(inter(capsules(chords,.125+TOLERANCE),safe),copper)
            if grow.area>0:
                records.append({'operation':'fill sub-0.25 mm copper-free gap beneath retained mask',
                                'iteration':iteration,**chord_row('copper-free',.25,piece,chords),
                                'copperAddedAreaMm2':round(grow.area,9)})
                copper=clean(add(copper,grow))
        for piece,chords in thin:
            # Full-width disks: the safe-region clip can remove half of each.
            grow=sub(inter(disks(chords,.25+TOLERANCE),safe),copper)
            widened=add(copper,grow)
            if grow.area>0 and not [v for v in violations(inter(widened,piece.buffer(.6)),.25)
                                   if v[0].intersects(piece)]:
                records.append({'operation':'widen thin hidden copper inside safe region',
                                'iteration':iteration,**chord_row('copper',.25,piece,chords),
                                'copperAddedAreaMm2':round(grow.area,9)})
                copper=clean(widened)
                continue
            cut=sub(inter(disks(chords,.125+TOLERANCE),copper),required)
            if cut.area>0:
                records.append({'operation':'trim thin hidden copper not backing a gold opening',
                                'iteration':iteration,**chord_row('copper',.25,piece,chords),
                                'copperRemovedAreaMm2':round(cut.area,9)})
                copper=clean(sub(copper,cut))
        copper=shapely.from_wkb(rounded(unary_union(
            [p for p in export.polygons(copper) if p.intersects(required)])).wkb)
        changed=clean(copper.symmetric_difference(before))
        if changed.is_empty:
            break
        dirty=changed.buffer(.5,quad_segs=8)
    copper=shapely.from_wkb(copper.wkb)
    remaining=[chord_row('copper-free',.25,p,c) for p,c in violations(plane_complement(body,copper),.25)]
    remaining+=[chord_row('copper',.25,p,c) for p,c in violations(copper,.25)]
    print(f'{label}: copper enforcement stopped with {len(remaining)} unresolved',flush=True)
    return copper,records,remaining
