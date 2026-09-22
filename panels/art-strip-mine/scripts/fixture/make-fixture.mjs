// Writes fixture.kicad_pcb / fixture.kicad_pro: a 30x30 board exercising every kicad-emit builder.
// Usage: node make-fixture.mjs [outDir]   (defaults to this directory)

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { assertUniqueUuids, board, circle, line, outline, project, rect, screwFootprint, slotFootprint } from "../kicad-emit.mjs";

const K = "fixture";

export function fixtureBoard() {
  const items = [
    outline([[30, 30], [0, 30], [0, 0], [30, 0]], `${K}:Edge.Cuts:outline:0`),
    outline([[11, 11], [19, 11], [19, 19], [11, 19]], `${K}:Edge.Cuts:outline:1`),
    ...["F.Cu", "F.Mask"].flatMap((layer) => [
      line([22, 22], [27, 27], 0.3, layer, `${K}:${layer}:line:0`),
      circle([5, 15], 1.5, layer, `${K}:${layer}:circle:0`),
      rect(23, 9, 4, 4, layer, `${K}:${layer}:rect:0`),
    ]),
    slotFootprint(15, 4, `${K}:slot:0`),
    screwFootprint(5, 25, `${K}:screw:0`),
  ];
  const pcb = board({ items });
  assertUniqueUuids(pcb, "fixture.kicad_pcb");
  return pcb;
}

export function writeFixture(outDir) {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, "fixture.kicad_pcb"), fixtureBoard());
  writeFileSync(join(outDir, "fixture.kicad_pro"), project("fixture"));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFixture(process.argv[2] ?? fileURLToPath(new URL(".", import.meta.url)));
}
