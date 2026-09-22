// Plain-node test for kicad-emit.mjs: node panels/art-strip-mine/scripts/emit.test.mjs
// Regenerates the fixture board, then checks what KiCad actually manufactures from it.
// KICAD_CLI overrides the kicad-cli path.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { contours, gerberPt, near, parseDrill, parseGerber, samePt } from "./fab-parse.mjs";
import { assertUniqueUuids, slotFootprint } from "./kicad-emit.mjs";
import { writeFixture } from "./fixture/make-fixture.mjs";

const KICAD_CLI = process.env.KICAD_CLI ?? "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli";
const FIXTURE_DIR = fileURLToPath(new URL("./fixture/", import.meta.url));
const UFO_PCB = fileURLToPath(new URL("../../art-ufo-v2/ufo-panel.kicad_pcb", import.meta.url));

const tmp = mkdtempSync(join(tmpdir(), "strip-mine-emit-"));
const results = [];
function test(name, fn) {
  fn();
  results.push(name);
  console.log(`ok - ${name}`);
}
const read = (dir, name) => readFileSync(join(dir, name));

function kicad(args) {
  const r = spawnSync(KICAD_CLI, args, { encoding: "utf8" });
  if (r.error) throw new Error(`cannot run ${KICAD_CLI}: ${r.error.message}`);
  return r;
}

try {
  const genA = join(tmp, "a");
  const genB = join(tmp, "b");
  writeFixture(genA);
  writeFixture(genB);

  test("fixture generation is byte-identical across runs and matches the committed fixture", () => {
    for (const f of ["fixture.kicad_pcb", "fixture.kicad_pro"]) {
      assert.ok(read(genA, f).equals(read(genB, f)), `${f} differs between runs`);
      assert.ok(read(genA, f).equals(read(FIXTURE_DIR, f)), `committed ${f} is stale; run fixture/make-fixture.mjs`);
    }
  });

  const pcbPath = join(genA, "fixture.kicad_pcb");
  const pcb = read(genA, "fixture.kicad_pcb").toString();

  test("uuids are unique", () => {
    assert.ok(assertUniqueUuids(pcb) > 10);
    assert.throws(() => assertUniqueUuids('(uuid "x") (uuid "x")'));
  });

  test("project severities ignore only the artwork-inherent rules", () => {
    const pro = JSON.parse(read(genA, "fixture.kicad_pro"));
    const tpl = JSON.parse(readFileSync(UFO_PCB.replace(/\.kicad_pcb$/, ".kicad_pro")));
    assert.equal(pro.meta.filename, "fixture.kicad_pro");
    const sev = pro.board.design_settings.rule_severities;
    const changed = Object.keys(sev).filter((k) => sev[k] !== tpl.board.design_settings.rule_severities[k]);
    assert.deepEqual(changed.sort(), ["copper_edge_clearance", "lib_footprint_issues", "lib_footprint_mismatch", "shorting_items", "solder_mask_bridge"]);
  });

  test("slotFootprint reproduces the four UFO slot blocks (uuids aside)", () => {
    const ufo = readFileSync(UFO_PCB, "utf8");
    const blocks = [...ufo.matchAll(/^\t\(footprint [\s\S]*?^\t\)$/gm)].map((m) => m[0]);
    const strip = (s) => s.replace(/^\s*\(uuid "[^"]+"\)\n/gm, "");
    const mine = [
      slotFootprint(91.14, 125.65, "t0", { anonymous: true }),
      slotFootprint(10.17, 2.87, "t1"),
      slotFootprint(10.19, 125.66, "t2", { anonymous: true, padOffset: [-0.03, -0.02] }),
      slotFootprint(91.13, 2.86, "t3"),
    ].map((s) => s.replace(/^/gm, "\t"));
    assert.equal(blocks.length, 4);
    blocks.forEach((b, i) => assert.equal(strip(mine[i]), strip(b), `UFO block ${i}`));
  });

  const out = join(tmp, "gerber");
  const gerb = kicad(["pcb", "export", "gerbers", "-o", `${out}/`, pcbPath]);
  assert.equal(gerb.status, 0, gerb.stderr);
  const drill = kicad(["pcb", "export", "drill", "--format", "excellon", "-o", `${out}/`, pcbPath]);
  assert.equal(drill.status, 0, drill.stderr);
  const files = readdirSync(out);
  const layer = (suffix) => parseGerber(read(out, files.find((f) => f.includes(`-${suffix}.`))).toString());

  test("drill output has a 3.2 mm round hole and a 3.2 x 10.28 slot", () => {
    const d = parseDrill(read(out, files.find((f) => f.endsWith(".drl"))).toString());
    assert.ok(Object.values(d.tools).includes(3.2), "3.2 mm tool");
    assert.ok(d.holes.some((h) => h.dia === 3.2 && samePt(gerberPt(h.at), [5, 25])), "screw hole at (5,25)");
    const slot = d.slots.find((s) => s.dia === 3.2);
    assert.ok(slot, "3.2 mm routed slot");
    const len = Math.hypot(slot.to[0] - slot.from[0], slot.to[1] - slot.from[1]) + slot.dia;
    assert.ok(near(len, 10.28), `slot length ${len}`);
    assert.ok(samePt(gerberPt([(slot.from[0] + slot.to[0]) / 2, (slot.from[1] + slot.to[1]) / 2]), [15, 4]), "slot centred at (15,4)");
  });

  function checkArtwork(g, name) {
    const lineDraw = g.draws.find((d) => !d.arc && samePt(gerberPt(d.from), [22, 22]) && samePt(gerberPt(d.to), [27, 27]));
    assert.ok(lineDraw, `${name}: line draw`);
    assert.deepEqual(g.apertures[lineDraw.ap], { shape: "C", params: [0.3] }, `${name}: 0.3 mm line`);
    // A filled circle is plotted either as a flash or as a full ring stroked around its centre.
    const ring = g.draws.filter((d) => d.arc && samePt(gerberPt(d.center), [5, 15]));
    const disc = g.flashes.some((f) => samePt(gerberPt(f.at), [5, 15]));
    assert.ok(disc || ring.length > 0, `${name}: filled circle`);
    if (!disc) {
      const width = g.apertures[ring[0].ap].params[0];
      const radius = Math.hypot(ring[0].from[0] - ring[0].center[0], ring[0].from[1] - ring[0].center[1]);
      assert.ok(near(radius + width / 2, 1.5) && near(radius - width / 2, 0), `${name}: ring covers r=1.5 disc`);
    }
    const corners = [[23, 9], [27, 9], [27, 13], [23, 13]];
    assert.ok(
      g.regions.some((r) => corners.every((c) => r.some((p) => samePt(gerberPt(p), c)))),
      `${name}: filled rect region`,
    );
    assert.ok(g.flashes.some((f) => samePt(gerberPt(f.at), [15, 4])), `${name}: slot pad`);
    assert.ok(g.flashes.some((f) => samePt(gerberPt(f.at), [5, 25]) && g.apertures[f.ap].params[0] === 6), `${name}: 6 mm screw pad`);
  }

  test("F_Cu carries the line, circle, rect and both pads", () => checkArtwork(layer("F_Cu"), "F_Cu"));
  test("F_Mask mirrors F_Cu", () => {
    checkArtwork(layer("F_Mask"), "F_Mask");
    const strip = (t) => t.toString().split("\n").filter((l) => !/^(G04|%TF|%TA|%TO|%TD)/.test(l)).join("\n");
    const fcu = files.find((f) => f.includes("-F_Cu."));
    const fmask = files.find((f) => f.includes("-F_Mask."));
    assert.equal(strip(read(out, fmask)), strip(read(out, fcu)), "F_Mask body differs from F_Cu");
  });

  test("Edge_Cuts has two closed contours (outline + cutout)", () => {
    const cs = contours(layer("Edge_Cuts"));
    assert.equal(cs.length, 2);
    for (const c of cs) assert.ok(samePt(c[0], c.at(-1)), "contour closed");
  });

  test("silkscreens are empty", () => {
    for (const s of ["F_Silkscreen", "B_Silkscreen"]) {
      const g = layer(s);
      assert.equal(g.draws.length + g.flashes.length + g.regions.length, 0, s);
    }
  });

  test("DRC reports no violations", () => {
    const rpt = join(tmp, "drc.rpt");
    const r = kicad(["pcb", "drc", "--severity-all", "--exit-code-violations", "-o", rpt, pcbPath]);
    assert.equal(r.status, 0, readFileSync(rpt, "utf8"));
  });

  test("SVG export succeeds with nothing on stderr", () => {
    const r = kicad(["pcb", "export", "svg", "--layers", "F.Cu,F.Mask,Edge.Cuts", "-o", join(tmp, "fixture.svg"), pcbPath]);
    assert.equal(r.status, 0);
    assert.equal(r.stderr.trim(), "");
  });

  console.log(`\n${results.length} passed`);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
