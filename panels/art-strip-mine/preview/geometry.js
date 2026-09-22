// Strip Mine geometry and artwork, shared by the browser preview (index.html)
// and the Node KiCad generator. Classic script on purpose: relative ES-module
// imports are blocked over file://, a plain <script src> is not. Node loads it
// with `import "./geometry.js"` and reads globalThis.StripMineGeometry.
(() => {
"use strict";

// ---------------------------------------------------------------------------
// Spec. Panel coordinates follow KiCad: origin top-left, +y downward.
// ---------------------------------------------------------------------------
const W = 101.3, H = 128.5, T = 1.6, SPACER = 3;

// Rail slots copied from panels/art-ufo-v2/ufo-panel.kicad_pcb (must stay identical)
const SLOTS = [[10.17, 2.87], [91.13, 2.86], [10.16, 125.64], [91.14, 125.65]];
const SLOT_DRILL = [10.28, 3.2], SLOT_PAD = [11.08, 4];

// zudo-rail nuts-v2 profile: 12.59 mm tall, nut channel centred 6.37 mm from its outer face
const RAIL_TALL = 12.59, RAIL_DEEP = 20.13, RAIL_NUT_FROM_OUTER = 6.37;
const RAIL_REACH = SLOTS[0][1] + (RAIL_TALL - RAIL_NUT_FROM_OUTER); // rail's inner edge, from panel edge
const RAIL_SPACING = 8; // requested margin on top of the rail reach
// Rounded to 0.1 mm so board edges and screw centres land on clean numbers (17.1, 23.6)
const KEEP_OUT = +(RAIL_REACH + RAIL_SPACING).toFixed(1);

const SCREW_INSET_X = 6.5, SCREW_FROM_LOWER_EDGE = 6.5;
const SCREW_Y = KEEP_OUT + SCREW_FROM_LOWER_EDGE;
const SCREWS = [[SCREW_INSET_X, SCREW_Y], [W - SCREW_INSET_X, SCREW_Y],
                [SCREW_INSET_X, H - SCREW_Y], [W - SCREW_INSET_X, H - SCREW_Y]];
// M3 clearance hole through a plated annular pad; spacers are 6 mm OD
const M3_HOLE = 3.2, SCREW_PAD = 6.0, SPACER_OD = 6;

const LAYERS = [
  { name: "Black", mask: "#101113" },
  { name: "Red", mask: "#a3121b" },
  { name: "Black", mask: "#101113" },
  { name: "Red", mask: "#a3121b" },
  { name: "Black", mask: "#101113" },
  { name: "Red", mask: "#a3121b" },
  { name: "Black", mask: "#101113" },
  { name: "Red", mask: "#a3121b" },
  { name: "Blue (lake)", mask: "#1450c8" },
];
const PITCH = T + SPACER;
const STACK_DEPTH = LAYERS.length * T + (LAYERS.length - 1) * SPACER;

// ---------------------------------------------------------------------------
// Pit openings: faceted, shrinking terraces that drift slightly down-left
// ---------------------------------------------------------------------------
function rng(seed) {
  return () => {
    seed |= 0; seed = seed + 0x6d2b79f5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
const FACETS = 15, OPENINGS = LAYERS.length - 1;
const TOP_RX = 35, TOP_RY = 32, BOTTOM_SCALE = 0.3;
const CENTER0 = [W / 2 + 1, H / 2 - 1], DRIFT = [-0.4, 0.35];
const shared = (() => { const r = rng(7); return Array.from({ length: FACETS }, () => r() * 2 - 1); })();
const openings = Array.from({ length: OPENINGS }, (_, i) => {
  const r = rng(100 + i);
  const s = 1 - (1 - BOTTOM_SCALE) * i / (OPENINGS - 1);
  const cx = CENTER0[0] + DRIFT[0] * i, cy = CENTER0[1] + DRIFT[1] * i;
  return Array.from({ length: FACETS }, (_, k) => {
    const a = (k / FACETS) * Math.PI * 2 + 0.2;
    const j = 1 + shared[k] * 0.08 + (r() * 2 - 1) * 0.012;
    return [cx + Math.cos(a) * TOP_RX * s * j, cy + Math.sin(a) * TOP_RY * s * j];
  });
});

function pointInPoly([x, y], poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function distToPoly([x, y], poly) {
  let best = Infinity;
  for (let i = 0; i < poly.length; i++) {
    const [ax, ay] = poly[i], [bx, by] = poly[(i + 1) % poly.length];
    const dx = bx - ax, dy = by - ay;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
    best = Math.min(best, Math.hypot(x - ax - t * dx, y - ay - t * dy));
  }
  return best;
}
const bbox = (poly) => {
  const xs = poly.map((p) => p[0]), ys = poly.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
};

// Visible gold widths: top pit rim, lower terrace rims, top-board outer edge band
const TOP_RIM = 1.4, RIM = 1.0, EDGE_BAND = 0.9, PIT_R = 30, LINE_MIN = 0.28;
function noise2(seed) {
  const h = (i, j) => {
    let n = Math.imul(i, 374761393) + Math.imul(j, 668265263) + Math.imul(seed, 982451653);
    n = Math.imul(n ^ n >>> 13, 1274126177);
    return ((n ^ n >>> 16) >>> 0) / 4294967296 * 2 - 1;
  };
  const s = (t) => t * t * (3 - 2 * t);
  const v = (x, y) => {
    const i = Math.floor(x), j = Math.floor(y), fx = s(x - i), fy = s(y - j);
    const a = h(i, j), b = h(i + 1, j), c = h(i, j + 1), d = h(i + 1, j + 1);
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
  };
  return (x, y, scale, octaves = 3) => {
    let sum = 0, amp = 1, norm = 0, f = 1 / scale;
    for (let o = 0; o < octaves; o++) { sum += amp * v(x * f + o * 17.3, y * f - o * 9.1); norm += amp; amp *= 0.5; f *= 2; }
    return sum / norm;
  };
}

const G = 0.35, GX = Math.round(W / G) + 1, GY = Math.round(H / G) + 1;
// Signed distance to the top opening (negative inside), shared by every variant
const PIT_DIST = (() => {
  const out = new Float32Array(GX * GY);
  for (let j = 0; j < GY; j++) for (let i = 0; i < GX; i++) {
    const pt = [i * G, j * G];
    out[j * GX + i] = distToPoly(pt, openings[0]) * (pointInPoly(pt, openings[0]) ? -1 : 1);
  }
  return out;
})();
function pitDist(x, y) {
  const fx = Math.min(Math.max(x / G, 0), GX - 1.001), fy = Math.min(Math.max(y / G, 0), GY - 1.001);
  const i = Math.floor(fx), j = Math.floor(fy), tx = fx - i, ty = fy - j, k = j * GX + i;
  const a = PIT_DIST[k], b = PIT_DIST[k + 1], c = PIT_DIST[k + GX], d = PIT_DIST[k + GX + 1];
  return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty;
}

// Marching squares with endpoint joining → connected polylines per level
function isolines(field, levels, mask) {
  const F = new Float32Array(GX * GY), keep = new Uint8Array(GX * GY);
  for (let j = 0; j < GY; j++) for (let i = 0; i < GX; i++) {
    const k = j * GX + i, x = i * G, y = j * G;
    F[k] = field(x, y); keep[k] = PIT_DIST[k] > 0.5 && (!mask || mask(x, y)) ? 1 : 0;
  }
  let maxGrad = 0;
  for (let j = 0; j < GY - 1; j++) for (let i = 0; i < GX - 1; i++) {
    const k = j * GX + i;
    const gx = F[k + 1] - F[k], gy = F[k + GX] - F[k];
    if (keep[k] && keep[k + 1] && keep[k + GX] && Math.abs(gx) < 3 && Math.abs(gy) < 3) maxGrad = Math.max(maxGrad, Math.hypot(gx, gy) / G);
  }
  const lines = [];
  for (const level of levels) {
    const pts = new Map(), adj = new Map(), segs = [];
    const edge = (key, x1, y1, f1, x2, y2, f2) => {
      if (!pts.has(key)) { const t = (level - f1) / (f2 - f1); pts.set(key, [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]); }
      return key;
    };
    for (let j = 0; j < GY - 1; j++) for (let i = 0; i < GX - 1; i++) {
      const a = j * GX + i, b = a + 1, c = a + GX + 1, d = a + GX;
      if (!(keep[a] && keep[b] && keep[c] && keep[d])) continue;
      const fa = F[a], fb = F[b], fc = F[c], fd = F[d], x = i * G, y = j * G;
      const cross = [];
      if ((fa > level) !== (fb > level)) cross.push(edge(a * 2, x, y, fa, x + G, y, fb));
      if ((fb > level) !== (fc > level)) cross.push(edge(b * 2 + 1, x + G, y, fb, x + G, y + G, fc));
      if ((fc > level) !== (fd > level)) cross.push(edge(d * 2, x, y + G, fd, x + G, y + G, fc));
      if ((fd > level) !== (fa > level)) cross.push(edge(a * 2 + 1, x, y, fa, x, y + G, fd));
      for (let q = 0; q + 1 < cross.length; q += 2) {
        const s = segs.length; segs.push([cross[q], cross[q + 1]]);
        for (const k of [cross[q], cross[q + 1]]) { if (!adj.has(k)) adj.set(k, []); adj.get(k).push(s); }
      }
    }
    const used = new Uint8Array(segs.length);
    const walk = (start) => {
      const line = [pts.get(start)]; let key = start;
      for (;;) {
        const s = (adj.get(key) || []).find((i) => !used[i]);
        if (s === undefined) break;
        used[s] = 1; key = segs[s][0] === key ? segs[s][1] : segs[s][0]; line.push(pts.get(key));
      }
      return line;
    };
    for (const [key, list] of adj) if (list.length === 1 && !used[list[0]]) lines.push(walk(key));
    for (let s = 0; s < segs.length; s++) if (!used[s]) lines.push(walk(segs[s][0]));
  }
  return { lines: lines.filter((l) => l.length > 3), maxGrad };
}

const len = (line) => { let t = 0; for (let i = 1; i < line.length; i++) t += Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]); return t; };
// Resample to even spacing so dashes, dots and width changes are smooth
function resample(line, step) {
  const out = [line[0]]; let carry = 0;
  for (let i = 1; i < line.length; i++) {
    const [ax, ay] = line[i - 1], [bx, by] = line[i], L = Math.hypot(bx - ax, by - ay);
    let t = step - carry;
    while (t <= L) { out.push([ax + (bx - ax) * t / L, ay + (by - ay) * t / L]); t += step; }
    carry = L - (t - step);
  }
  return out;
}
// Cut a polyline into pieces with gaps; pieces shorter than minLen vanish
function fragment(line, r, { piece = [15, 60], gap = [2, 8], keep = 0.85 } = {}) {
  const out = []; let i = 0;
  while (i < line.length) {
    const n = Math.round((piece[0] + r() * (piece[1] - piece[0])) / 0.5);
    const part = line.slice(i, i + n);
    if (part.length > 4 && r() < keep) out.push(part);
    i += n + Math.round((gap[0] + r() * (gap[1] - gap[0])) / 0.5);
  }
  return out;
}

// Random walk that follows a noise field; optional 45° quantised turns
function wander(r, n, start, steps, { turn = 0.35, quant = false, step = 0.5, scale = 20, heading } = {}) {
  let [x, y] = start, a = heading ?? r() * Math.PI * 2, out = [[x, y]];
  let aa = quant ? Math.round(a / (Math.PI / 4)) * (Math.PI / 4) : a;
  for (let s = 0; s < steps; s++) {
    if (quant) { if (r() < turn) aa += (r() < 0.5 ? -1 : 1) * Math.PI / 4; }
    else { a += n(x, y, scale) * turn; aa = a; }
    x += Math.cos(aa) * step; y += Math.sin(aa) * step;
    if (x < 1 || x > W - 1 || y < 1 || y > H - 1 || pitDist(x, y) < 1.5) break;
    out.push([x, y]);
  }
  return out;
}

// Organic field: near the rim it is the (warped) distance to the pit; further
// out it hands over to an independent wave/blob field, and the warp grows with
// distance, so each successive line drifts further from the hole's own shape.
const smooth = (a, b, t) => { const u = Math.min(1, Math.max(0, (t - a) / (b - a))); return u * u * (3 - 2 * u); };
const WAVES = {
  h: (n, x, y) => 20 * n(x * 0.45, y, 40, 2) + 5 * n(x + 300, y, 16, 2) + 14 * n(x + 500, y * 0.6, 70, 1),
  v: (n, x, y) => 20 * n(x, y * 0.45, 40, 2) + 5 * n(x + 300, y, 16, 2) + 14 * n(x * 0.6, y + 500, 70, 1),
  diag: (n, x, y) => 20 * n((x + y) * 0.32, (y - x) * 0.7, 40, 2) + 5 * n(x + 300, y, 16, 2) + 14 * n(x + 500, y, 70, 1),
  blob: (n, x, y) => 24 * n(x, y, 44, 2) + 5 * n(x + 300, y, 16, 2) + 12 * n(x + 500, y, 70, 1),
};
function org(n, x, y, wave = "h", { D = 26, warp = 0.35, detail = 0.5, swell = 1 } = {}) {
  const d0 = Math.max(0, pitDist(x, y));
  const a = 1.5 + warp * d0;
  const d = pitDist(x + a * n(x, y, 30), y + a * n(x + 90, y, 30));
  return d + swell * smooth(0, D, d0) * WAVES[wave](n, x, y) + detail * n(x + 200, y, 9);
}

// Irregular level list: mostly base spacing, with tight pairs and wide gaps
function levels(r, from, to, base, { jitter = 0.6, pair = 0.18, skip = 0.12, grow = 0 } = {}) {
  const out = []; let v = from;
  while (v < to) {
    if (r() > skip) out.push(v);
    const u = r(), b = base * (1 + grow * (v - from));
    v += u < pair ? b * 0.7 : b * (1 - jitter / 2 + r() * jitter) * (u > 0.9 ? 2.2 : 1);
  }
  return out;
}

function buildingCluster(r, site, angle, count) {
  const out = [], dir = [Math.cos(angle), Math.sin(angle)];
  for (let i = 0; i < count; i++) {
    const t = (i - count / 2) * 5.5 + (r() - 0.5) * 2, side = (r() - 0.5) * 6;
    const w = 2 + r() * 3.5, h = 1.8 + r() * 3;
    const cols = Math.max(1, Math.floor((w - 0.8) / 1.4)), rows = Math.max(1, Math.floor((h - 0.8) / 1.4)), windows = [];
    for (let c = 0; c < cols; c++) for (let k = 0; k < rows; k++) if (r() > 0.4) windows.push([c, k]);
    out.push({ x: site[0] + dir[0] * t - dir[1] * side, y: site[1] + dir[1] * t + dir[0] * side, w, h, cols, rows, windows });
    if (r() < 0.6) out.push({ x: site[0] + dir[0] * t - dir[1] * (side + 4), y: site[1] + dir[1] * t + dir[0] * (side + 4), w: 0.7, h: 0.7, cols: 1, rows: 1, windows: [] });
  }
  return out;
}

// Sites for building clusters, chosen away from the pit, slots and screws
const SITES = [[22, 38, -0.5], [80, 24, -0.4], [78, 104, 0.3], [24, 96, 0.5], [50, 16, 0], [52, 113, 0.1]];

// Every variant is the "fine strata" recipe (dense thin rings that turn into
// waves, with occasional heavy lines) with a different seed, wave direction,
// swell amplitude, spacing and building sites.
function strata({ name, note, seed, wave = "h", D = 18, warp = 0.5, swell = 1, base = 1.7, heavy = 9, heavyW = [0.7, 1.0], grow = 0.01, frag = { piece: [50, 250], gap: [1.5, 5], keep: 0.92 }, sites, extras }) {
  const f = (n) => (x, y) => org(n, x, y, wave, { D, warp, swell }) + 0.8 * n(x, y, 7);
  return { name, note, seed, sites, layers: (n, r) => [
    { field: f(n), levels: levels(r, 1.4, 130, base, { jitter: 0.4, pair: 0, grow }), width: [0.25, 0.32], frag },
    ...(heavy ? [{ field: f(n), levels: levels(r, 4, 130, heavy, { jitter: 0.6 }), width: heavyW }] : []),
    ...(extras ? extras(n, r) : []),
  ] };
}
const TOP_VARIANTS = [
  strata({ name: "Fine strata", note: "The original: fine dense rings turning into horizontal waves, with heavy accent lines.", seed: 7, sites: [2] }),
  strata({ name: "Strata, wide swell", note: "Same recipe with bigger, slower swells and fewer accent lines.", seed: 11, swell: 1.5, D: 14, heavy: 14, sites: [1, 3] }),
  strata({ name: "Strata, vertical", note: "Lines flow vertically past the pit instead of horizontally.", seed: 12, wave: "v", sites: [0, 2] }),
  strata({ name: "Strata, diagonal", note: "Waves sweeping diagonally, with a tighter bundle at the rim.", seed: 13, wave: "diag", D: 22, warp: 0.6, sites: [4, 3] }),
  strata({ name: "Strata, blobs", note: "Far field breaks into free blobs and islands rather than waves.", seed: 14, wave: "blob", D: 16, sites: [1, 5] }),
  strata({ name: "Strata, calm", note: "Gentler swells, tighter and more regular lines, no accent lines.", seed: 15, swell: 0.6, warp: 0.3, heavy: 0, base: 1.6, sites: [2] }),
  strata({ name: "Strata, broken", note: "Same waves but lines break into shorter dashes toward the edges.", seed: 16, frag: { piece: [12, 60], gap: [2, 7], keep: 0.85 }, sites: [0, 2, 5] }),
  strata({ name: "Strata, heavy", note: "More and bolder accent lines between the fine ones.", seed: 17, heavy: 5.5, heavyW: [0.9, 1.3], base: 1.9, sites: [3] }),
  strata({ name: "Strata, turbulent", note: "Strongest warp: the rings twist and fold before becoming waves.", seed: 18, warp: 0.8, swell: 1.3, D: 12, sites: [1, 4] }),
  strata({ name: "Strata, dotted far field", note: "Fine strata near the pit, dotted trails further out.", seed: 19, sites: [2, 4],
    extras: (n, r) => [{ field: (x, y) => org(n, x, y, "h", { D: 18, warp: 0.5 }) + 2, levels: levels(r, 30, 130, 7), width: [0.4, 0.5], mode: "dot" }],
    frag: { piece: [50, 250], gap: [1.5, 5], keep: 0.92 } }),
];

// Turn a recipe into concrete strokes (polyline chunks with widths) and dots
const traced = new Map();
function tracePattern(index) {
  if (traced.has(index)) return traced.get(index);
  const variant = TOP_VARIANTS[index];
  const n = noise2(variant.seed), r = rng(variant.seed * 31);
  const strokes = [], dots = [];
  let minGap = Infinity, result_dbg, source = 0; // source: id of the isoline or walk a stroke was cut from
  const emit = (line, { width = [0.3, 0.5], mode = "solid", taper = false, mix = false } = {}) => {
    if (line.length < 4) return;
    const pts = resample(line, 0.5);
    if (pts.length < 3) return;
    const style = mix ? ["solid", "solid", "dash", "dot"][Math.floor(r() * 4)] : mode;
    const w0 = Array.isArray(width) ? width[0] + r() * (width[1] - width[0]) : width;
    const total = pts.length * 0.5;
    if (style === "dot") {
      const gap = 1.2 + r() * 1.2;
      for (let s = 0; s < total; s += gap) { const p = pts[Math.min(pts.length - 1, Math.round(s / 0.5))]; dots.push([p[0], p[1], w0 * 0.6]); }
      minGap = Math.min(minGap, gap - w0 * 1.2);
      return;
    }
    let on = true, run = 0, onLen = 2 + r() * 4, offLen = 1 + r() * 1.5;
    const chunkPts = [];
    const flush = () => { if (chunkPts.length > 1) strokes.push({ pts: chunkPts.slice(), w: chunkPts.w, source }); chunkPts.length = 0; };
    for (let i = 0; i < pts.length; i++) {
      const s = i * 0.5;
      let w = w0 * (0.8 + 0.4 * (n(pts[i][0] * 3, pts[i][1] * 3, 8) + 0.5));
      if (taper) { const e = Math.min(s, total - s); if (e < 4) w *= Math.max(0.35, e / 4); }
      if (style === "dash") {
        run += 0.5;
        if (on && run > onLen) { on = false; run = 0; flush(); } else if (!on && run > offLen) { on = true; run = 0; }
        if (!on) continue;
      }
      if (chunkPts.length && Math.abs(w - chunkPts.w) > 0.06) { const last = chunkPts[chunkPts.length - 1]; flush(); chunkPts.push(last); }
      if (!chunkPts.length) chunkPts.w = Math.max(LINE_MIN, w);
      chunkPts.push(pts[i]);
    }
    flush();
  };
  for (const layer of variant.layers(n, r)) {
    let { lines, maxGrad } = isolines(layer.field, layer.levels, layer.mask);
    const wmax = Array.isArray(layer.width) ? layer.width[1] : layer.width;
    const step0 = Math.min(...layer.levels.slice(1).map((v, i) => v - layer.levels[i]).filter((s) => s > 0), Infinity);
    if (isFinite(step0) && step0 / maxGrad - wmax < 0.4) {
      const k = (0.4 + wmax) * maxGrad / step0, from = layer.levels[0];
      layer.levels = layer.levels.map((v) => from + (v - from) * k);
      ({ lines, maxGrad } = isolines(layer.field, layer.levels, layer.mask));
    }
    // Spacing: smallest level step over the field's steepest gradient, minus the widest line
    const steps = layer.levels.slice(1).map((v, i) => v - layer.levels[i]).filter((s) => s > 0);
    if (steps.length) (result_dbg ??= []).push([Math.min(...steps).toFixed(2), maxGrad.toFixed(2)]);
    if (steps.length) minGap = Math.min(minGap, Math.min(...steps) / maxGrad - (Array.isArray(layer.width) ? layer.width[1] : layer.width));
    for (const line of lines) { source++; for (const part of layer.frag ? fragment(line, r, layer.frag) : [line]) emit(part, layer); }
  }
  for (const walk of variant.walks ? variant.walks(n, r) : []) {
    source++;
    emit(walk.line, { width: walk.width, mode: walk.mode || "solid", taper: walk.taper });
    if (walk.pad && walk.line.length > 10) { const p = walk.line[walk.line.length - 1]; dots.push([p[0], p[1], 0.9]); }
  }
  const buildings = variant.sites.flatMap((s) => buildingCluster(r, SITES[s], SITES[s][2], 3 + Math.floor(r() * 3)));
  const result = { strokes, dots, buildings, minGap, dbg: result_dbg };
  traced.set(index, result);
  return result;
}

// ---------------------------------------------------------------------------
// Finished artwork per board: strokes and dots already cleared around every
// other feature, buildings already cut into strips. The KiCad generator emits
// this list 1:1, so all compositing happens here and not in the renderer.
// ---------------------------------------------------------------------------
function segPointDist([ax, ay], [bx, by], [px, py]) {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}
const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
function segSegDist(a, b, c, d) {
  const d1 = cross(c, d, a), d2 = cross(c, d, b), d3 = cross(a, b, c), d4 = cross(a, b, d);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) return 0;
  return Math.min(segPointDist(c, d, a), segPointDist(c, d, b), segPointDist(a, b, c), segPointDist(a, b, d));
}

// Keep-out zones as capsules (segment core + radius) and filled polygons with
// an optional band; clearance() is the distance from a segment to the nearest one.
function halos({ buildings }) {
  const capsules = [], polys = [];
  const [sl, sw] = [SLOT_PAD[0] + 2, SLOT_PAD[1] + 2];
  for (const [x, y] of SLOTS) capsules.push({ a: [x - (sl - sw) / 2, y], b: [x + (sl - sw) / 2, y], r: sw / 2 });
  for (const s of SCREWS) capsules.push({ a: s, b: s, r: SPACER_OD / 2 + 1.1 });
  for (const b of buildings) {
    const x0 = b.x - 0.9, y0 = b.y - 0.9, x1 = b.x + b.w + 0.9, y1 = b.y + b.h + 0.9;
    polys.push({ poly: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], r: 0 });
  }
  polys.push({ poly: openings[0], r: TOP_RIM + 0.6 });
  const edge = 1.6;
  for (const h of [...capsules, ...polys]) {
    const pts = h.poly || [h.a, h.b];
    const [x0, y0, x1, y1] = bbox(pts);
    h.box = [x0 - h.r, y0 - h.r, x1 + h.r, y1 + h.r];
  }
  return (a, b) => {
    // Distance to the outer band is linear along a segment, so its minimum is at an end
    let best = Math.min(...[a, b].flatMap(([x, y]) => [x, W - x, y, H - y])) - edge;
    const lx = Math.min(a[0], b[0]), ly = Math.min(a[1], b[1]), hx = Math.max(a[0], b[0]), hy = Math.max(a[1], b[1]);
    for (const h of capsules) {
      const [x0, y0, x1, y1] = h.box;
      if (lx - x1 > best || x0 - hx > best || ly - y1 > best || y0 - hy > best) continue;
      best = Math.min(best, segSegDist(a, b, h.a, h.b) - h.r);
    }
    for (const h of polys) {
      const [x0, y0, x1, y1] = h.box;
      if (lx - x1 > best || x0 - hx > best || ly - y1 > best || y0 - hy > best) continue;
      if (pointInPoly(a, h.poly) || pointInPoly(b, h.poly)) return -h.r;
      for (let k = 0; k < h.poly.length; k++) best = Math.min(best, segSegDist(a, b, h.poly[k], h.poly[(k + 1) % h.poly.length]) - h.r);
    }
    return best;
  };
}

// Split a polyline wherever a vertex or segment comes within w/2 of a halo
function clearStroke(stroke, clearance, out) {
  const { pts, w } = stroke;
  let piece = [];
  const flush = () => { if (piece.length >= 2) out.push({ ...stroke, pts: piece }); piece = []; };
  for (let k = 0; k < pts.length; k++) {
    if (clearance(pts[k], pts[k]) < w / 2) { flush(); continue; }
    if (piece.length && clearance(piece[piece.length - 1], pts[k]) < w / 2) flush();
    piece.push(pts[k]);
  }
  flush();
}

// Strokes from different source lines (fine vs accent levels of the same field) can run
// nearly tangent, leaving a sub-0.1 mm gap or a copper sliver. Wider strokes win: each
// thinner stroke is split wherever it comes within STROKE_GAP of a wider one from another line.
const STROKE_GAP = 0.4, CELL = 2;
function separateStrokes(strokes) {
  const order = strokes.map((_, k) => k).sort((a, b) => strokes[b].w - strokes[a].w || a - b);
  const grid = new Map(), kept = strokes.map(() => []);
  const cells = (x0, y0, x1, y1, fn) => {
    for (let i = Math.floor(x0 / CELL); i <= Math.floor(x1 / CELL); i++) for (let j = Math.floor(y0 / CELL); j <= Math.floor(y1 / CELL); j++) fn(`${i},${j}`);
  };
  let reach = 0; // widest accepted stroke so far, bounds the grid query
  for (const k of order) {
    const s = strokes[k];
    const clearance = (a, b) => {
      const m = s.w / 2 + STROKE_GAP + reach / 2, seen = new Set();
      let best = Infinity;
      cells(Math.min(a[0], b[0]) - m, Math.min(a[1], b[1]) - m, Math.max(a[0], b[0]) + m, Math.max(a[1], b[1]) + m, (c) => {
        for (const seg of grid.get(c) || []) {
          if (seen.has(seg) || seg.source === s.source) continue;
          seen.add(seg);
          best = Math.min(best, segSegDist(a, b, seg.a, seg.b) - seg.w / 2 - STROKE_GAP);
        }
      });
      return best;
    };
    clearStroke(s, clearance, kept[k]);
    for (const { pts, w, source } of kept[k]) {
      reach = Math.max(reach, w);
      for (let p = 1; p < pts.length; p++) {
        const seg = { a: pts[p - 1], b: pts[p], w, source };
        cells(Math.min(seg.a[0], seg.b[0]), Math.min(seg.a[1], seg.b[1]), Math.max(seg.a[0], seg.b[0]), Math.max(seg.a[1], seg.b[1]), (c) => {
          if (!grid.has(c)) grid.set(c, []);
          grid.get(c).push(seg);
        });
      }
    }
  }
  return kept.flat();
}

// A split on one segment leaves the two round caps only a segment length (0.5 mm) apart, and
// separateStrokes() ignores pieces of the same source line. Walk each line's pieces in order and
// trim the head of any piece that starts within STROKE_GAP of where the previous one ended;
// pieces that meet exactly (a width change mid-line) stay joined.
function spaceStrokeEnds(strokes) {
  const prev = new Map(), out = [];
  for (const s of strokes) {
    const last = prev.get(s.source);
    let pts = s.pts;
    if (last) {
      const end = last.pts[last.pts.length - 1];
      const tooClose = (p) => Math.hypot(p[0] - end[0], p[1] - end[1]) - (s.w + last.w) / 2 < STROKE_GAP;
      if (!(pts[0][0] === end[0] && pts[0][1] === end[1])) {
        let k = 0;
        while (k < pts.length && tooClose(pts[k])) k++;
        pts = pts.slice(k);
      }
    }
    if (pts.length < 2) continue;
    const kept = pts === s.pts ? s : { ...s, pts };
    out.push(kept);
    prev.set(s.source, kept);
  }
  return out;
}

// Building rect minus its windows: solid row bands, and within each window row
// the strips between windows
function buildingRects(b) {
  const cw = (b.w - 0.8) / b.cols, ch = (b.h - 0.8) / b.rows, out = [], eps = 1e-9;
  const rows = [...new Set(b.windows.map(([, rr]) => rr))].sort((p, q) => p - q);
  const band = (y, h) => { if (h > eps) out.push({ x: b.x, y, w: b.w, h }); };
  let y = b.y;
  for (const rr of rows) {
    const wy = b.y + 0.4 + rr * ch + ch * 0.25, wh = ch * 0.5;
    band(y, wy - y);
    let x = b.x;
    for (const cc of b.windows.filter(([, k]) => k === rr).map(([c]) => c).sort((p, q) => p - q)) {
      const wx = b.x + 0.4 + cc * cw + cw * 0.25;
      if (wx - x > eps) out.push({ x, y: wy, w: wx - x, h: wh });
      x = wx + cw * 0.5;
    }
    if (b.x + b.w - x > eps) out.push({ x, y: wy, w: b.x + b.w - x, h: wh });
    y = wy + wh;
  }
  band(y, b.y + b.h - y);
  return out;
}

// Signed gap from a rect to the top pit edge (negative when a corner is inside)
function pitGap({ x, y, w, h }) {
  const c = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], pit = openings[0];
  if (c.some((p) => pointInPoly(p, pit))) return -1;
  let best = Infinity;
  for (let k = 0; k < 4; k++) for (let m = 0; m < pit.length; m++) {
    best = Math.min(best, segSegDist(c[k], c[(k + 1) % 4], pit[m], pit[(m + 1) % pit.length]));
  }
  return best;
}
// Buildings closer than this would fuse into the pit rim or be routed away with the cut
const BUILDING_PIT_GAP = 2;

// Signed gap between two axis-aligned rects: [dx, dy] per axis, negative on both when they overlap
function rectGap(a, b) {
  return [Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w)), Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h))];
}
// A cluster's annex square sits a fixed 4 mm off its building whatever the building's size, so it
// can land a hair away from another building and etch as a sub-0.35 mm slit. Nudge each building
// directly away from an earlier near miss until STROKE_GAP separates them; one that still conflicts
// afterwards, or now reaches the pit, is dropped. Overlapping buildings stay merged as before.
function spaceBuildings(bldgs) {
  const kept = [];
  const nearMiss = (b) => kept.find((k) => {
    const [dx, dy] = rectGap(k, b);
    return !(dx < 0 && dy < 0) && Math.hypot(Math.max(dx, 0), Math.max(dy, 0)) < STROKE_GAP - 1e-9;
  });
  for (const b of bldgs) {
    const k = nearMiss(b);
    if (!k) { kept.push(b); continue; }
    // Move along the separating axis, or diagonally when they only face corner to corner
    const [rx, ry] = rectGap(k, b), dx = Math.max(rx, 0), dy = Math.max(ry, 0), len = Math.hypot(dx, dy);
    const [ax, ay] = len > 0 ? [dx, dy] : [+(rx >= 0), +(ry >= 0)], norm = Math.hypot(ax, ay);
    const [ux, uy] = [ax / norm, ay / norm];
    const sx = Math.sign(b.x + b.w / 2 - k.x - k.w / 2) || 1, sy = Math.sign(b.y + b.h / 2 - k.y - k.h / 2) || 1;
    const moved = { ...b, x: b.x + sx * ux * (STROKE_GAP - len), y: b.y + sy * uy * (STROKE_GAP - len) };
    if (!nearMiss(moved) && pitGap(moved) >= BUILDING_PIT_GAP) kept.push(moved);
  }
  return kept;
}

// Top board Edge.Cuts outline, verbatim from panels/art-ufo-v2/ufo-panel.kicad_pcb (within 2 um of W x H)
const TOP_OUTLINE = [[101.298286, 128.498474], [0, 128.498474], [0, 0.001518], [101.298286, 0.001518]];

// The rail slot pads reach 0.87 mm in from the edge, inside the edge band, so the band
// breaks around each pad with the same copper clearance as between strokes.
const SLOT_PAD_CLEAR = STROKE_GAP;
function slotPadDist(p) {
  const hl = (SLOT_PAD[0] - SLOT_PAD[1]) / 2;
  return Math.min(...SLOTS.map(([x, y]) => segPointDist([x - hl, y], [x + hl, y], p))) - SLOT_PAD[1] / 2;
}
// Open polylines along `outline` where a stroke of width w keeps SLOT_PAD_CLEAR off every slot pad
function bandPieces(outline, w) {
  const ok = (p) => slotPadDist(p) >= w / 2 + SLOT_PAD_CLEAR;
  const at = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  // Boundary between a kept and a dropped parameter, bisected to 1 um on a 100 mm edge
  const edgeT = (a, b, lo, hi) => {
    for (let k = 0; k < 20; k++) { const m = (lo + hi) / 2; if (ok(at(a, b, m)) === ok(at(a, b, lo))) lo = m; else hi = m; }
    return ok(at(a, b, lo)) ? lo : hi;
  };
  if (!ok(outline[0])) throw new Error("bandPieces: outline must start at a kept vertex");
  const pieces = [];
  let cur = [outline[0]];
  for (let k = 0; k < outline.length; k++) {
    const a = outline[k], b = outline[(k + 1) % outline.length];
    const n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1);
    for (let s = 1; s <= n; s++) {
      const t0 = (s - 1) / n, t1 = s / n, k0 = ok(at(a, b, t0)), k1 = ok(at(a, b, t1));
      if (k0 && !k1) { cur.push(at(a, b, edgeT(a, b, t0, t1))); pieces.push(cur); cur = null; }
      else if (!k0 && k1) cur = [at(a, b, edgeT(a, b, t1, t0))];
    }
    if (cur) cur.push(b);
  }
  // The walk ends back at outline[0]; join that tail onto the first piece
  if (cur && pieces.length) pieces[0] = [...cur.slice(0, -1), ...pieces[0]];
  else if (cur) return [{ pts: outline, w, closed: true }];
  return pieces.map((pts) => ({ pts, w, closed: false }));
}

const composed = new Map();
function composeBoard(i, { pattern = 4, buildings = true } = {}) {
  const key = `${i}:${pattern}:${buildings}`;
  if (composed.has(key)) return composed.get(key);
  const out = { strokes: [], dots: [], rects: [], rims: [] };
  if (i === 0) {
    const art = tracePattern(pattern);
    const bldgs = buildings ? spaceBuildings(art.buildings.filter((b) => pitGap(b) >= BUILDING_PIT_GAP)) : [];
    const clearance = halos({ buildings: bldgs });
    const cleared = [];
    for (const s of art.strokes) clearStroke(s, clearance, cleared);
    out.strokes.push(...spaceStrokeEnds(separateStrokes(cleared)));
    for (const [x, y, r] of art.dots) if (clearance([x, y], [x, y]) >= r) out.dots.push({ x, y, r });
    for (const b of bldgs) out.rects.push(...buildingRects(b));
    // Rims straddle the cut: half of the stroke width is routed away
    out.rims.push({ pts: openings[0], w: 2 * TOP_RIM, closed: true });
    out.rims.push(...bandPieces(TOP_OUTLINE, 2 * EDGE_BAND));
  } else if (i < OPENINGS) {
    out.rims.push({ pts: openings[i], w: 2 * RIM, closed: true });
  }
  composed.set(key, out);
  return out;
}

globalThis.StripMineGeometry = {
  W, H, T, SPACER, SLOTS, SLOT_DRILL, SLOT_PAD,
  RAIL_TALL, RAIL_DEEP, RAIL_NUT_FROM_OUTER, RAIL_REACH, RAIL_SPACING, KEEP_OUT,
  SCREW_INSET_X, SCREW_FROM_LOWER_EDGE, SCREW_Y, SCREWS, M3_HOLE, SCREW_PAD, SPACER_OD,
  LAYERS, PITCH, STACK_DEPTH, FACETS, OPENINGS, CENTER0, openings,
  rng, pointInPoly, distToPoly, bbox, noise2, pitDist, isolines, resample, fragment, wander,
  WAVES, org, levels, SITES, buildingCluster, strata, TOP_VARIANTS, tracePattern,
  TOP_RIM, RIM, EDGE_BAND, LINE_MIN, BUILDING_PIT_GAP, pitGap, composeBoard,
  TOP_OUTLINE, SLOT_PAD_CLEAR, slotPadDist, STROKE_GAP,
};
})();
