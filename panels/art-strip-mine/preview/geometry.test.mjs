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
assert.deepEqual(top.rims.map((r) => [r.w, r.closed]), [[2 * G.TOP_RIM, true], [2 * G.EDGE_BAND, true]]);

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
