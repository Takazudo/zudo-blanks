"""Millimetre geometry shared by the five PCB art preview generators.

Design modules return dicts with a `layers` list produced by make_layer().
Bodies are Shapely geometry BEFORE common mounting holes are subtracted.
Coordinates follow KiCad: x right, y down, origin at the front's upper left.
"""
from math import cos, sin, pi
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union

W, H, T, GAP, KEEP_OUT = 101.3, 128.5, 1.6, 3.0, 17.1
SCREWS = [(6.5, 23.6), (94.8, 23.6), (6.5, 104.9), (94.8, 104.9)]
SLOTS = [(10.17, 2.87), (91.13, 2.86), (10.16, 125.64), (91.14, 125.65)]
SLOT_DRILL = (10.28, 3.2)
PALETTE = {
    'black': {'name': 'Black', 'nameJa': '黒', 'mask': '#15161a'},
    'white': {'name': 'White', 'nameJa': '白', 'mask': '#eeeae0'},
    'gold': {'name': 'ENIG gold on black', 'nameJa': '全面ENIG金／黒基板', 'mask': '#15161a', 'surface': 'gold'},
    'red': {'name': 'Red', 'nameJa': '赤', 'mask': '#a4162d'},
    'green': {'name': 'Green', 'nameJa': '緑', 'mask': '#126243'},
    'purple': {'name': 'Purple', 'nameJa': '紫', 'mask': '#692c92'},
    'yellow': {'name': 'Yellow', 'nameJa': '黄', 'mask': '#e4be21'},
    'blue': {'name': 'Blue', 'nameJa': '青', 'mask': '#164dba'},
}

def plate(index):
    return box(0, 0 if index == 0 else KEEP_OUT, W, H if index == 0 else H-KEEP_OUT)

def rounded_rect(x0, y0, x1, y1, radius=3.0):
    return box(x0+radius, y0+radius, x1-radius, y1-radius).buffer(radius, quad_segs=10)

def art_window():
    return rounded_rect(10.5, 27.0, W-10.5, H-27.0, 5.0)

def frame(index, window=None):
    return plate(index).difference(art_window() if window is None else window)

def ribbon(points, width, rounded=True):
    return LineString(points).buffer(width/2, cap_style=1 if rounded else 2, join_style=1 if rounded else 2, quad_segs=6)

def make_layer(index, color, body, strokes=None, fills=None, solid=False, note=''):
    return {'index': index, 'colorKey': color, **PALETTE[color], 'body': body,
            'art': {'strokes': strokes or [], 'fills': fills or []},
            'solid': solid, 'note': note}

def stroke(points, width=0.35, color=None, closed=False):
    item = {'pts': [[float(x),float(y)] for x,y in points], 'w': width}
    if color: item['color'] = color
    if closed: item['closed'] = True
    return item

def fill(points, color=None):
    item = {'pts': [[float(x),float(y)] for x,y in points]}
    if color: item['color'] = color
    return item

def polyline_art(geometry, width=0.30, color=None):
    """Convert line geometry into clipped drawing strokes."""
    if geometry.is_empty: return []
    if geometry.geom_type in ('LineString','LinearRing'):
        return [stroke(list(geometry.coords), width, color)]
    if hasattr(geometry, 'geoms'):
        return [s for g in geometry.geoms for s in polyline_art(g, width, color)]
    return []

def ensure_polygon(body, label):
    if not body.is_valid:
        body = body.buffer(0)
    if body.geom_type != 'Polygon':
        sizes = [round(g.area,5) for g in getattr(body,'geoms',[])]
        raise ValueError(f'{label}: expected one connected Polygon, got {body.geom_type}: {sizes}')
    return body
