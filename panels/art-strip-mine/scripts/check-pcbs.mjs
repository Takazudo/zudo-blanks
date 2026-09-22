// Fabrication checks for the nine generated Strip Mine boards. Prints PASS/FAIL per check and
// exits 1 on any FAIL. Usage: node panels/art-strip-mine/scripts/check-pcbs.mjs
// Writes gerbers + Excellon drills into each pcb-NN-*/gerber/ (gitignored).
// KICAD_CLI overrides the kicad-cli path; STRIP_MINE_PYTHON names a Python 3 with Pillow, numpy
// and scipy for the copper raster check (default: python3).

import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import "../preview/geometry.js";
import { contours, gerberPt, near, parseDrill, parseGerber, samePt } from "./fab-parse.mjs";

const G = globalThis.StripMineGeometry;
const KICAD_CLI = process.env.KICAD_CLI ?? "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli";
const PYTHON = process.env.STRIP_MINE_PYTHON ?? "python3";
const PANEL_DIR = fileURLToPath(new URL("../", import.meta.url));
const COPPER_CHECK = fileURLToPath(new URL("./copper-check.py", import.meta.url));
const UFO_PCB = fileURLToPath(new URL("../../art-ufo-v2/ufo-panel.kicad_pcb", import.meta.url));

const GERBER_LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts";
// Rules the artwork breaks on purpose (see kicad-emit.mjs project()); every other ignore is a
// KiCad default inherited unchanged from the art-ufo-v2 template.
const INTENTIONAL_IGNORES = ["copper_edge_clearance", "lib_footprint_issues", "lib_footprint_mismatch", "shorting_items", "solder_mask_bridge"];
const MIN_GAP = 0.35, MIN_WIDTH = 0.25, MIN_NEST_STEP = 2;
const [SLOT_LEN, SLOT_WIDTH] = G.SLOT_DRILL, HOLE = G.M3_HOLE;

let failures = 0;
function check(name, fn) {
  try {
    const detail = fn();
    console.log(`PASS  ${name}${detail ? `  (${detail})` : ""}`);
  } catch (e) {
    failures++;
    console.log(`FAIL  ${name}  ${e.message}`);
  }
}
function expect(ok, message) {
  if (!ok) throw new Error(message);
}

function run(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: "utf8", maxBuffer: 64 << 20 });
  if (r.error) throw new Error(`cannot run ${cmd}: ${r.error.message}`);
  return r;
}
const kicad = (args) => run(KICAD_CLI, args);

// --- Geometry helpers -------------------------------------------------------------------------
function segPointDist([ax, ay], [bx, by], [px, py]) {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  const t = l2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) : 0;
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}
const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
function segSegDist(a, b, c, d) {
  if (Math.sign(cross(c, d, a)) * Math.sign(cross(c, d, b)) < 0 && Math.sign(cross(a, b, c)) * Math.sign(cross(a, b, d)) < 0) return 0;
  return Math.min(segPointDist(c, d, a), segPointDist(c, d, b), segPointDist(a, b, c), segPointDist(a, b, d));
}
const edges = (poly) => poly.map((p, k) => [p, poly[(k + 1) % poly.length]]);
const polyDist = (p, q) => Math.min(...edges(p).flatMap(([a, b]) => edges(q).map(([c, d]) => segSegDist(a, b, c, d))));
const area = (pts) => Math.abs(edges(pts).reduce((s, [[x, y], [nx, ny]]) => s + x * ny - nx * y, 0)) / 2;

// --- .kicad_pcb text readers ------------------------------------------------------------------
const footprints = (pcb) => [...pcb.matchAll(/^\t\(footprint [\s\S]*?^\t\)$/gm)].map((m) => m[0]);
const stripUuids = (s) => s.replace(/^\s*\(uuid "[^"]+"\)\n/gm, "");
const footprintAt = (fp) => fp.match(/^\t\t\(at (\S+) (\S+)\)$/m).slice(1).map(Number);
function edgePolys(pcb) {
  return [...pcb.matchAll(/\(gr_poly\s*\(pts\s*((?:\(xy [^)]*\)\s*)+)\)[\s\S]*?\(layer "([^"]+)"\)/g)]
    .filter((m) => m[2] === "Edge.Cuts")
    .map((m) => [...m[1].matchAll(/\(xy (\S+) (\S+)\)/g)].map((x) => [Number(x[1]), Number(x[2])]));
}

// --- Boards -----------------------------------------------------------------------------------
const boards = readdirSync(PANEL_DIR)
  .filter((d) => /^pcb-\d\d-/.test(d))
  .sort()
  .map((dir) => {
    const name = `strip-mine-${dir.slice(4, 6)}`;
    const pcbPath = join(PANEL_DIR, dir, `${name}.kicad_pcb`);
    return { dir, name, pcbPath, pcb: readFileSync(pcbPath, "utf8"), pro: JSON.parse(readFileSync(pcbPath.replace(/pcb$/, "pro"), "utf8")) };
  });
const tmp = mkdtempSync(join(tmpdir(), "strip-mine-check-"));

try {
  console.log(`# Strip Mine fabrication checks: ${boards.length} boards, ${KICAD_CLI}\n`);

  // --- 1. DRC -----------------------------------------------------------------------------------
  console.log("## 1. DRC");
  const ignored = (b) => Object.entries(b.pro.board.design_settings.rule_severities).filter(([, v]) => v === "ignore").map(([k]) => k).sort();
  const tplSev = JSON.parse(readFileSync(UFO_PCB.replace(/pcb$/, "pro"), "utf8")).board.design_settings.rule_severities;
  const allIgnored = ignored(boards[0]);
  console.log(`  ignored in .kicad_pro, artwork-intentional: ${allIgnored.filter((k) => tplSev[k] !== "ignore").join(", ")}`);
  console.log(`  ignored in .kicad_pro, KiCad/template default: ${allIgnored.filter((k) => tplSev[k] === "ignore").join(", ")}`);
  check("every board ignores the same rules, and only the five intentional ones differ from the UFO template", () => {
    for (const b of boards) expect(ignored(b).join() === allIgnored.join(), `${b.name}: ${ignored(b)}`);
    const changed = allIgnored.filter((k) => tplSev[k] !== "ignore");
    expect(changed.join() === INTENTIONAL_IGNORES.join(), `non-template ignores: ${changed}`);
  });
  for (const b of boards) {
    check(`${b.name} DRC clean (--severity-all, no violation, unconnected item or parity issue)`, () => {
      const rpt = join(tmp, `${b.name}-drc.json`);
      const r = kicad(["pcb", "drc", "--severity-all", "--exit-code-violations", "--format", "json", "-o", rpt, b.pcbPath]);
      const json = JSON.parse(readFileSync(rpt, "utf8"));
      const found = [...json.violations, ...json.unconnected_items, ...(json.schematic_parity ?? [])];
      expect(r.status === 0 && found.length === 0, `exit ${r.status}: ${found.map((v) => `${v.severity} ${v.type}`).join("; ")}`);
      return "0 violations";
    });
  }

  // --- 2. Gerbers + drills ----------------------------------------------------------------------
  console.log("\n## 2. Gerbers + Excellon drills");
  for (const [i, b] of boards.entries()) {
    const out = join(PANEL_DIR, b.dir, "gerber");
    rmSync(out, { recursive: true, force: true });
    mkdirSync(out);
    const g = kicad(["pcb", "export", "gerbers", "--layers", GERBER_LAYERS, "-o", `${out}/`, b.pcbPath]);
    const d = kicad(["pcb", "export", "drill", "--format", "excellon", "-o", `${out}/`, b.pcbPath]);
    const files = readdirSync(out);
    const file = (suffix) => files.find((f) => f.endsWith(suffix));
    const text = (suffix) => readFileSync(join(out, file(suffix)), "utf8");

    check(`${b.name} export: 7 Protel-named gerbers + .drl`, () => {
      expect(g.status === 0 && d.status === 0, `kicad-cli exit ${g.status}/${d.status}: ${g.stderr}${d.stderr}`);
      const want = ["-F_Cu.gtl", "-B_Cu.gbl", "-F_Mask.gts", "-B_Mask.gbs", "-F_Silkscreen.gto", "-B_Silkscreen.gbo", "-Edge_Cuts.gm1", ".drl"];
      const missing = want.filter((s) => !file(s));
      expect(missing.length === 0, `missing ${missing}`);
      return files.length + " files";
    });
    check(`${b.name} silkscreens carry no drawing commands`, () => {
      for (const s of ["-F_Silkscreen.gto", "-B_Silkscreen.gbo"]) {
        const t = text(s);
        const p = parseGerber(t);
        expect(p.draws.length + p.flashes.length + p.regions.length === 0 && !/D0[123]\*/.test(t), `${s} draws`);
      }
    });
    check(`${b.name} drills: 4 x round Ø${HOLE} at the screw positions${i === 0 ? `, 4 slots ${SLOT_WIDTH} x ${SLOT_LEN}` : ", no slots"}`, () => {
      const drl = parseDrill(text(".drl"));
      expect(drl.holes.length === 4 && drl.holes.every((h) => h.dia === HOLE), `holes ${drl.holes.map((h) => h.dia)}`);
      for (const s of G.SCREWS) expect(drl.holes.some((h) => samePt(gerberPt(h.at), s.map((v) => +v.toFixed(4)))), `no hole at ${s}`);
      const slots = drl.slots.map((s) => ({ dia: s.dia, len: Math.hypot(s.to[0] - s.from[0], s.to[1] - s.from[1]) + s.dia }));
      if (i === 0) expect(slots.length === 4 && slots.every((s) => s.dia === SLOT_WIDTH && near(s.len, SLOT_LEN)), `slots ${JSON.stringify(slots)}`);
      else expect(slots.length === 0, `${slots.length} slots`);
      return `${drl.holes.length} holes, ${slots.length} slots`;
    });
    check(`${b.name} Edge_Cuts: ${i < G.OPENINGS ? 2 : 1} closed contour(s)`, () => {
      const cs = contours(parseGerber(text("-Edge_Cuts.gm1")));
      expect(cs.length === (i < G.OPENINGS ? 2 : 1), `${cs.length} contours`);
      expect(cs.every((c) => samePt(c[0], c.at(-1))), "open contour");
      return `${cs.length} closed`;
    });
  }

  // --- 3. Output-level copper gap and width -----------------------------------------------------
  console.log(`\n## 3. F.Cu copper gap/width (kicad-cli SVG rasterised by ${PYTHON})`);
  const svgs = boards.map((b) => {
    const svg = join(tmp, `${b.name}-F_Cu.svg`);
    const r = kicad(["pcb", "export", "svg", "--layers", "F.Cu", "--exclude-drawing-sheet", "--black-and-white", "--mode-single", "-o", svg, b.pcbPath]);
    if (r.status !== 0) throw new Error(`svg export ${b.name}: ${r.stderr}`);
    return svg;
  });
  const py = run(PYTHON, [COPPER_CHECK, ...svgs]);
  const measured = py.status === 0 ? py.stdout.trim().split("\n").map((l) => JSON.parse(l)) : [];
  check("copper-check.py ran", () => expect(py.status === 0, py.stderr.trim().split("\n").at(-1)));
  measured.forEach((m, i) => {
    const b = boards[i];
    check(`${b.name} F.Cu min gap between copper islands >= ${MIN_GAP} mm`, () => {
      expect(m.islands === m.rasterIslands, `${m.islands} islands from the primitives but ${m.rasterIslands} in the raster`);
      const detail = `${m.minGap === null ? "none within 1 mm" : `${m.minGap.toFixed(3)} mm`}, ${m.islands} islands`;
      expect(m.minGap === null || m.minGap >= MIN_GAP, `${detail} at ${JSON.stringify(m.gapAt)}`);
      return detail;
    });
    check(`${b.name} F.Cu min feature width >= ${MIN_WIDTH} mm`, () => {
      expect(m.minWidth >= MIN_WIDTH, `${m.minWidth} mm, limited at ${JSON.stringify(m.widthLimitedBy)}`);
      return `${m.widthLimitedBy ? "" : ">= "}${m.minWidth.toFixed(2)} mm, ${1 / m.pxPerMm} mm probe step`;
    });
  });

  // --- 4. Nesting of the pit cutouts ------------------------------------------------------------
  console.log("\n## 4. Pit cutout nesting (Edge.Cuts polygons read from the .kicad_pcb files)");
  const polys = boards.map((b) => edgePolys(b.pcb).sort((p, q) => area(q) - area(p)));
  boards.forEach((b, i) => {
    const [outer, cutout] = polys[i];
    check(`${b.name} Edge.Cuts: ${i < G.OPENINGS ? "outline + cutout inside it" : "outline only"}`, () => {
      expect(polys[i].length === (i < G.OPENINGS ? 2 : 1), `${polys[i].length} polygons`);
      if (cutout) expect(cutout.every((p) => G.pointInPoly(p, outer)) && polyDist(cutout, outer) > 0, "cutout leaves the outline");
    });
    if (i === 0 || !cutout) return;
    check(`${b.name} cutout inside ${boards[i - 1].name} cutout with >= ${MIN_NEST_STEP} mm step`, () => {
      const prev = polys[i - 1][1];
      expect(cutout.every((p) => G.pointInPoly(p, prev)), "vertex outside");
      const step = polyDist(cutout, prev);
      expect(step >= MIN_NEST_STEP, `step ${step.toFixed(3)} mm`);
      return `min step ${step.toFixed(2)} mm`;
    });
  });

  // --- 5. Rail slots vs art-ufo-v2 --------------------------------------------------------------
  console.log("\n## 5. Rail slots vs the art-ufo-v2 template");
  check(`${boards[0].name} has the four UFO slot footprints verbatim (uuids aside)`, () => {
    const slotBlocks = (pcb) => footprints(pcb).filter((f) => f.includes("(drill oval")).map(stripUuids).sort();
    const mine = slotBlocks(boards[0].pcb), ufo = slotBlocks(readFileSync(UFO_PCB, "utf8"));
    expect(ufo.length === 4 && mine.length === 4, `${mine.length} vs ${ufo.length} blocks`);
    mine.forEach((m, k) => expect(m === ufo[k], `block at ${footprintAt(m)} differs`));
    return mine.map((m) => footprintAt(m).join(",")).join("  ");
  });
  check("no other board has a slot footprint", () => {
    for (const b of boards.slice(1)) expect(!b.pcb.includes("(drill oval"), b.name);
  });

  // --- 6. Stack ---------------------------------------------------------------------------------
  console.log("\n## 6. Stack");
  check("every board is 1.6 mm thick", () => {
    for (const b of boards) expect(/\(general\s*\(thickness 1\.6\)/.test(b.pcb), b.name);
  });
  check("directory colour order equals geometry.js LAYERS", () => {
    const dirs = boards.map((b) => b.dir.slice(7));
    const want = G.LAYERS.map((l) => l.name.split(" ")[0].toLowerCase());
    expect(dirs.join() === want.join(), `${dirs} vs ${want}`);
    return dirs.join(" > ");
  });
  check("4 screw pads at identical coordinates on every board (= geometry.js SCREWS)", () => {
    const screwsOf = (b) => footprints(b.pcb).filter((f) => f.includes('"Takazudo:stack-M3-screw-hole-pad6"')).map(footprintAt);
    const want = G.SCREWS;
    for (const b of boards) {
      const got = screwsOf(b);
      expect(got.length === 4 && got.every((p, k) => samePt(p, want[k].map((v) => +v.toFixed(6)))), `${b.name}: ${JSON.stringify(got)}`);
    }
    return want.map((p) => p.map((v) => +v.toFixed(3)).join(",")).join("  ");
  });
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

console.log(`\n${failures ? `${failures} FAIL` : "all checks PASS"}`);
process.exit(failures ? 1 : 0);
