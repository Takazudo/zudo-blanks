// Same-colour lower boards, translated without scaling; V-score seams on Dwgs.User.
import { mkdirSync, writeFileSync } from "node:fs";
import "../preview/geometry.js";
import { board, outline, line, screwFootprint, project, assertUniqueUuids } from "./kicad-emit.mjs";
const G = globalThis.StripMineGeometry;
const h = G.H - 2 * G.KEEP_OUT;
export const layouts = [
  { name: "strip-mine-black-panel", colour: "black", cols: 3, rows: 1, boards: [2, 4, 6] },
  { name: "strip-mine-red-panel", colour: "red", cols: 2, rows: 2, boards: [1, 3, 5, 7] },
];
for (const p of layouts) {
  const w = p.cols * G.W, height = p.rows * h;
  const items = [outline([[0, 0], [w, 0], [w, height], [0, height]], p.name + ":outer")];
  const placements = [];
  p.boards.forEach((i, n) => {
    const dx = (n % p.cols) * G.W, dy = Math.floor(n / p.cols) * h - G.KEEP_OUT;
    const move = ([x, y]) => [x + dx, y + dy];
    placements.push({ board: i + 1, dx, dy });
    items.push(outline(G.openings[i].map(move), p.name + ":pit:" + i));
    for (const layer of ["F.Cu", "F.Mask"]) {
      G.composeBoard(i).rims.forEach(({ pts, w }, r) => pts.forEach((a, k) =>
        items.push(line(move(a), move(pts[(k + 1) % pts.length]), w, layer, `${p.name}:${i}:${layer}:${r}:${k}`))));
    }
    G.SCREWS.forEach((pt, s) => items.push(screwFootprint(...move(pt), `${p.name}:${i}:screw:${s}`)));
  });
  const scores = [];
  for (let x = 1; x < p.cols; x++) scores.push([[x * G.W, 0], [x * G.W, height]]);
  for (let y = 1; y < p.rows; y++) scores.push([[0, y * h], [w, y * h]]);
  scores.forEach(([a, b], k) => items.push(line(a, b, 0.1, "Dwgs.User", p.name + ":vscore:" + k)));
  const pcb = board({ items });
  assertUniqueUuids(pcb);
  const dir = new URL("../panel-" + p.colour + "/", import.meta.url);
  mkdirSync(dir, { recursive: true });
  writeFileSync(new URL(p.name + ".kicad_pcb", dir), pcb);
  writeFileSync(new URL(p.name + ".kicad_pro", dir), project(p.name));
  writeFileSync(new URL("layout.json", dir), JSON.stringify({ ...p, width: w, height, placements, scores }, null, 2) + "\n");
  writeFileSync(new URL("FABRICATION.txt", dir),
    `${p.name}: ${w.toFixed(1)} x ${height.toFixed(1)} mm, 1.6 mm FR-4, 2 layers, 1 oz, ${p.colour} mask, ENIG.\n` +
    `Panel by customer; ${p.boards.length} DIFFERENT designs. One panel makes one stack's ${p.colour} lower boards.\n` +
    "V-SCORE ALL lines in the separate User_Drawings Gerber (KiCad Dwgs.User layer). These are NOT routed slots or silkscreen.\n" +
    "Route the outside perimeter and all inner pit contours from Edge_Cuts. No silkscreen.\n" +
    "Copper intentionally reaches the routed pit edges. Confirm this and V-score acceptance with CAM before manufacture.\n" +
    "Preserve finished sub-board dimensions 101.3 x 94.3 mm and all hole positions.\n" +
    "Panel contains no top board and no blue bottom board.\n");
  console.log(p.name, w.toFixed(1), "x", height.toFixed(1), "mm");
}
