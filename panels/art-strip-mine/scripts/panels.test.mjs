// Validate exported panel outlines, screw positions, score lines and source pit geometry.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import "../preview/geometry.js";
import { parseGerber, parseDrill, contours, gerberPt, samePt } from "./fab-parse.mjs";
const G = globalThis.StripMineGeometry;
for (const colour of ["black", "red"]) {
  const dir = new URL("../panel-" + colour + "/", import.meta.url);
  const p = JSON.parse(readFileSync(new URL("layout.json", dir)));
  const read = (suffix) => readFileSync(new URL("gerber/" + p.name + suffix, dir), "utf8");
  const edge = contours(parseGerber(read("-Edge_Cuts.gm1")));
  assert.equal(edge.length, p.boards.length + 1);
  assert.ok(edge.every((c) => samePt(c[0], c.at(-1))));
  const drills = readdirSync(new URL("gerber/", dir)).filter((f) => f.endsWith(".drl"))
    .flatMap((f) => parseDrill(readFileSync(new URL("gerber/" + f, dir), "utf8")).holes);
  assert.equal(drills.length, 4 * p.boards.length);
  for (const { board, dx, dy } of p.placements) {
    for (const [x, y] of G.SCREWS)
      assert.ok(drills.some((h) => h.dia === 3.2 && samePt(gerberPt(h.at), [x + dx, y + dy])));
    const pit = G.openings[board - 1].map(([x, y]) => [x + dx, y + dy]);
    assert.ok(edge.some((c) => pit.every((pt) => c.some((q) => samePt(gerberPt(q), pt.map((v) => +v.toFixed(6)))))));
  }
  const scoreFile = readdirSync(new URL("gerber/", dir)).find((f) => f.includes("User_Drawings"));
  assert.ok(scoreFile, "V-score Gerber exported separately");
  const scores = parseGerber(readFileSync(new URL("gerber/" + scoreFile, dir), "utf8"));
  assert.equal(scores.draws.length, p.scores.length);
  for (const [a, b] of p.scores)
    assert.ok(scores.draws.some((d) => samePt(gerberPt(d.from), a) && samePt(gerberPt(d.to), b)),
      "V-score must match full-span seam");
  for (const suffix of ["-F_Silkscreen.gto", "-B_Silkscreen.gbo"]) {
    const silk = parseGerber(read(suffix));
    assert.equal(silk.draws.length + silk.flashes.length + silk.regions.length, 0);
  }
  console.log("PASS", colour, "panel: source pit geometry, mounting holes, closed contours, V-score export");
}
