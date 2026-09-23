// Run with: node panels/art-strip-mine/preview/geometry.test.mjs
import assert from "node:assert/strict";
import "./geometry.js";

const G = globalThis.StripMineGeometry;
const EPS = 1e-9;

assert.equal(G.openings.length, 8);
assert.equal(G.KEEP_OUT, 17.1);
const round = (v) => Math.round(v * 1000) / 1000;
assert.deepEqual(G.SCREWS.map((p) => p.map(round)), [[6.5, 23.6], [94.8, 23.6], [6.5, 104.9], [94.8, 104.9]]);
assert.equal(G.M3_HOLE, 3.2);
assert.equal(G.SCREW_PAD, 6);

const top = G.composeBoard(0, { pattern: 4 });
assert.ok(top.strokes.length > 0, "board 0 has strokes");
assert.ok(top.rects.length > 0, "board 0 has building strips");
assert.deepEqual([top.rims[0].w, top.rims[0].closed], [2 * G.TOP_RIM, true]);
// The outer frame is closed and overlaps every rail slot pad.
assert.deepEqual(top.rims.slice(1), [{ pts: G.TOP_OUTLINE, w: 2 * G.EDGE_BAND, closed: true }]);
for (const [x, y] of G.SLOTS) {
  const edgeY = y < G.H / 2 ? G.TOP_OUTLINE[2][1] : G.TOP_OUTLINE[0][1];
  assert.ok(Math.abs(y - edgeY) - G.SLOT_PAD[1] / 2 < G.EDGE_BAND,
    `frame must overlap slot pad at ${x},${y}`);
}

// Stroke points keep w/2 clear of the screw discs and slot stadium halos
const segDist = ([ax, ay], [bx, by], [px, py]) => {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
};
const screwR = G.SPACER_OD / 2 + 1.1;
const slotL = G.SLOT_PAD[0] + 2, slotW = G.SLOT_PAD[1] + 2, slotHalf = (slotL - slotW) / 2;
for (const { pts, w } of top.strokes) {
  assert.ok(pts.length >= 2);
  for (const p of pts) {
    for (const s of G.SCREWS) assert.ok(Math.hypot(p[0] - s[0], p[1] - s[1]) - screwR >= w / 2 - EPS, `stroke point ${p} touches screw halo ${s}`);
    for (const [x, y] of G.SLOTS) {
      assert.ok(segDist([x - slotHalf, y], [x + slotHalf, y], p) - slotW / 2 >= w / 2 - EPS, `stroke point ${p} touches slot halo ${[x, y]}`);
    }
  }
}

assert.ok(top.rects.every((r) => G.pitGap(r) >= G.BUILDING_PIT_GAP), "building strips clear of the pit");

// Strokes from different source lines keep STROKE_GAP between their copper edges (brute force)
const segs = top.strokes.flatMap(({ pts, w, source }) => pts.slice(1).map((b, k) => {
  const a = pts[k];
  return { a, b, w, source, box: [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])] };
}));
const segSeg = (p, q, r, s) => Math.min(segDist(r, s, p), segDist(r, s, q), segDist(p, q, r), segDist(p, q, s));
for (let x = 0; x < segs.length; x++) for (let y = x + 1; y < segs.length; y++) {
  const s = segs[x], t = segs[y], m = (s.w + t.w) / 2 + G.STROKE_GAP;
  if (s.source === t.source || t.box[0] - s.box[2] > m || s.box[0] - t.box[2] > m || t.box[1] - s.box[3] > m || s.box[1] - t.box[3] > m) continue;
  assert.ok(segSeg(s.a, s.b, t.a, t.b) >= m - 1e-6, `strokes ${s.a} and ${t.a} closer than STROKE_GAP`);
}

// Free end caps of one source line overlap or keep STROKE_GAP apart; ends where two pieces meet
// (a width change mid-line) are continuous copper and skipped
const ends = top.strokes.flatMap(({ pts, w, source }, id) => [pts[0], pts[pts.length - 1]].map((p) => ({ p, w, source, id })));
const joined = (e) => ends.filter((f) => f.source === e.source && f.p[0] === e.p[0] && f.p[1] === e.p[1]).length > 1;
const free = ends.filter((e) => !joined(e));
for (let x = 0; x < free.length; x++) for (let y = x + 1; y < free.length; y++) {
  const a = free[x], b = free[y];
  if (a.source !== b.source || a.id === b.id) continue;
  const gap = Math.hypot(a.p[0] - b.p[0], a.p[1] - b.p[1]) - (a.w + b.w) / 2;
  assert.ok(gap <= 0 || gap >= G.STROKE_GAP - 1e-6, `stroke ends at ${a.p} and ${b.p} ${gap.toFixed(3)} mm apart`);
}

// No stroke chain (pieces of one source joined end to end) is shorter than MIN_CHAIN_W x its width
{
  const parent = top.strokes.map((_, k) => k), find = (k) => (parent[k] === k ? k : (parent[k] = find(parent[k])));
  const endsOf = (u) => [u.pts[0], u.pts[u.pts.length - 1]];
  top.strokes.forEach((s, k) => top.strokes.forEach((t, m) => {
    if (m <= k || s.source !== t.source) return;
    if (endsOf(s).some((p) => endsOf(t).some((q) => p[0] === q[0] && p[1] === q[1]))) parent[find(k)] = find(m);
  }));
  const chains = new Map();
  top.strokes.forEach(({ pts, w }, k) => {
    const c = chains.get(find(k)) || { len: 0, w: 0, at: pts[0] };
    for (let i = 1; i < pts.length; i++) c.len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    c.w = Math.max(c.w, w);
    chains.set(find(k), c);
  });
  for (const c of chains.values()) assert.ok(c.len >= G.MIN_CHAIN_W * c.w, `stub chain at ${c.at}: ${c.len.toFixed(2)} mm`);
}

// Strips either touch (same or merged building) or keep BUILDING_GAP apart: no etched slits
for (let x = 0; x < top.rects.length; x++) for (let y = x + 1; y < top.rects.length; y++) {
  const a = top.rects[x], b = top.rects[y];
  const dx = Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w)), dy = Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h));
  const gap = Math.hypot(Math.max(dx, 0), Math.max(dy, 0));
  assert.ok(gap < 1e-6 || gap >= G.BUILDING_GAP - 1e-6, `building strips at ${[a.x, a.y]} and ${[b.x, b.y]} ${gap.toFixed(3)} mm apart`);
}

// Building strips never cover a window
const art = G.tracePattern(4);
for (const b of art.buildings) {
  const cw = (b.w - 0.8) / b.cols, ch = (b.h - 0.8) / b.rows;
  for (const [cc, rr] of b.windows) {
    const cx = b.x + 0.4 + cc * cw + cw / 2, cy = b.y + 0.4 + rr * ch + ch / 2;
    assert.ok(!top.rects.some((r) => cx > r.x && cx < r.x + r.w && cy > r.y && cy < r.y + r.h), "window is open");
  }
}

for (let i = 1; i <= 7; i++) {
  const b = G.composeBoard(i, { pattern: 4 });
  assert.equal(b.rims.length, 1, `board ${i} has one rim`);
  assert.equal(b.rims[0].w, 2);
  assert.equal(b.rims[0].pts, G.openings[i]);
  assert.deepEqual([b.strokes.length, b.dots.length, b.rects.length], [0, 0, 0]);
}
assert.deepEqual(G.composeBoard(8, { pattern: 4 }), { strokes: [], dots: [], rects: [], rims: [] });

assert.equal(G.composeBoard(0, { pattern: 4, buildings: false }).rects.length, 0);

console.log(`geometry ok: board 0 → ${top.strokes.length} strokes, ${top.dots.length} dots, ${top.rects.length} rects`);
