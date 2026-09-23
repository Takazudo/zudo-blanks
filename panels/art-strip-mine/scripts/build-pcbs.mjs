// Writes the nine Strip Mine KiCad projects (pcb-NN-<colour>/strip-mine-NN.kicad_{pcb,pro}) from
// the shared preview geometry. Usage: node panels/art-strip-mine/scripts/build-pcbs.mjs
// All boards share the top board's frame: KiCad origin top-left, +y down, same as the preview.

import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import "../preview/geometry.js";
import { assertUniqueUuids, bareHoleFootprint, board, circle, line, num, outline, project, rect, screwFootprint, slotFootprint } from "./kicad-emit.mjs";

const G = globalThis.StripMineGeometry;

// Preview pattern 5 ("Strata, blobs") is TOP_VARIANTS index 4.
const PATTERN = 4;
const ART_LAYERS = ["F.Cu", "F.Mask"];
const PANEL_DIR = new URL("../", import.meta.url);

// Slot blocks at the UFO positions; the bottom two are the UFO file's anonymous footprints.
const UFO_SLOTS = [
  { at: [10.17, 2.87] },
  { at: [91.13, 2.86] },
  { at: [10.19, 125.66], anonymous: true, padOffset: [-0.03, -0.02] },
  { at: [91.14, 125.65], anonymous: true },
];

const colourOf = (i) => G.LAYERS[i].name.split(" ")[0].toLowerCase();

function lowerOutline() {
  const [x0, y0, x1, y1] = [0, G.KEEP_OUT, G.W, G.H - G.KEEP_OUT];
  return [[x1, y1], [x0, y1], [x0, y0], [x1, y0]];
}

const polyArea = (pts) => Math.abs(pts.reduce((s, [x, y], k) => { const [nx, ny] = pts[(k + 1) % pts.length]; return s + x * ny - nx * y; }, 0)) / 2;

// Consecutive segments of a polyline, dropping any that collapse to a point at KiCad's 6-decimal precision.
function segments(pts, closed) {
  const out = [];
  const n = closed ? pts.length : pts.length - 1;
  for (let k = 0; k < n; k++) {
    const a = pts[k], b = pts[(k + 1) % pts.length];
    if (num(a[0]) === num(b[0]) && num(a[1]) === num(b[1])) continue;
    out.push([a, b]);
  }
  return out;
}

function buildBoard(i) {
  const name = `strip-mine-${String(i + 1).padStart(2, "0")}`;
  const art = G.composeBoard(i, { pattern: PATTERN });
  const outer = i === 0 ? G.TOP_OUTLINE : lowerOutline();
  const cutout = i < G.OPENINGS ? G.openings[i] : null;
  const count = { line: 0, circle: 0, rect: 0, footprint: 0 };
  const items = [outline(outer, `${name}:Edge.Cuts:outline:0`)];
  if (cutout) items.push(outline(cutout, `${name}:Edge.Cuts:cutout:0`));

  for (const layer of ART_LAYERS) {
    art.strokes.forEach(({ pts, w }, s) => segments(pts, false).forEach(([a, b], k) => { items.push(line(a, b, w, layer, `${name}:${layer}:stroke:${s}:${k}`)); count.line++; }));
    art.rims.forEach(({ pts, w, closed }, s) => segments(pts, closed).forEach(([a, b], k) => { items.push(line(a, b, w, layer, `${name}:${layer}:rim:${s}:${k}`)); count.line++; }));
    art.dots.forEach(({ x, y, r }, s) => { items.push(circle([x, y], r, layer, `${name}:${layer}:dot:${s}`)); count.circle++; });
    art.rects.forEach(({ x, y, w, h }, s) => { items.push(rect(x, y, w, h, layer, `${name}:${layer}:rect:${s}`)); count.rect++; });
  }

  if (i === 0) {
    UFO_SLOTS.forEach(({ at, ...opts }, s) => { items.push(slotFootprint(at[0], at[1], `${name}:F.Cu:slot:${s}`, opts)); count.footprint++; });
  }
  G.SCREWS.forEach(([x, y], s) => { items.push((i === 8 ? bareHoleFootprint : screwFootprint)(x, y, `${name}:F.Cu:screw:${s}`)); count.footprint++; });

  const pcb = board({ items });
  assertUniqueUuids(pcb, `${name}.kicad_pcb`);
  const [bx0, by0, bx1, by1] = G.bbox(outer);
  const summary = `${name} ${colourOf(i).padEnd(5)} outer ${num(bx0)}..${num(bx1)} x ${num(by0)}..${num(by1)}  cutout ${cutout ? polyArea(cutout).toFixed(1) : "-"} mm2  lines ${count.line}  circles ${count.circle}  rects ${count.rect}  footprints ${count.footprint}`;
  return { name, dir: `pcb-${name.slice(-2)}-${colourOf(i)}`, pcb, summary };
}

for (let i = 0; i < G.LAYERS.length; i++) {
  const { name, dir, pcb, summary } = buildBoard(i);
  const out = fileURLToPath(new URL(`${dir}/`, PANEL_DIR));
  mkdirSync(out, { recursive: true });
  writeFileSync(`${out}${name}.kicad_pcb`, pcb);
  if (!existsSync(`${out}${name}.kicad_pro`)) writeFileSync(`${out}${name}.kicad_pro`, project(name));
  console.log(summary);
}
