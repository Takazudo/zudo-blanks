// Minimal Gerber (RS-274X) and Excellon readers for KiCad's metric output, shared by
// emit.test.mjs and check-pcbs.mjs.

const EPS = 1e-6;
export const near = (a, b) => Math.abs(a - b) < EPS;
export const samePt = (p, q) => near(p[0], q[0]) && near(p[1], q[1]);

// --- Gerber (RS-274X) parsing: just enough for KiCad's FSLAX46Y46 metric output -------------
export function parseGerber(text) {
  const draws = [];
  const flashes = [];
  const regions = [];
  const apertures = {};
  let ap = null;
  let pos = [0, 0];
  let arc = false;
  let region = null;
  for (const raw of text.split("\n")) {
    const l = raw.trim();
    if (!l || l.startsWith("G04") || l.startsWith("%TF") || l.startsWith("%TA") || l.startsWith("%TO") || l.startsWith("%TD")) continue;
    const ad = l.match(/^%ADD(\d+)([A-Za-z]+),([^*]*)\*%$/);
    if (ad) {
      apertures[ad[1]] = { shape: ad[2], params: ad[3].split("X").map(Number) };
      continue;
    }
    if (l.startsWith("%") || /^[0-9]/.test(l)) continue; // other extended commands / macro bodies
    if (l === "G36*") region = [];
    else if (l === "G37*") (regions.push(region), (region = null));
    const d = l.match(/^D(\d+)\*$/);
    if (d && Number(d[1]) >= 10) ap = d[1];
    if (/G0?1\*?/.test(l) && !/G0?[23]/.test(l)) arc = false;
    if (/G0?[23]\*/.test(l)) arc = true;
    const op = l.match(/^(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0([123])\*$/);
    if (!op) continue;
    const to = [op[1] !== undefined ? op[1] / 1e6 : pos[0], op[2] !== undefined ? op[2] / 1e6 : pos[1]];
    if (op[5] === "1") {
      const draw = { ap, from: pos, to, arc };
      if (arc) draw.center = [pos[0] + (op[3] ?? 0) / 1e6, pos[1] + (op[4] ?? 0) / 1e6];
      if (region) region.push(to);
      else draws.push(draw);
    } else if (op[5] === "2") {
      if (region) region.push(to);
    } else flashes.push({ ap, at: to });
    pos = to;
  }
  return { apertures, draws, flashes, regions };
}

// KiCad gerbers put +y up, so board y is negated.
export const gerberPt = (p) => [p[0], -p[1]];

export function contours(g) {
  const out = [];
  let cur = null;
  for (const d of g.draws) {
    if (!cur || !samePt(cur.at(-1), d.from)) out.push((cur = [d.from]));
    cur.push(d.to);
  }
  return out;
}

// --- Excellon parsing ---------------------------------------------------------------------------
export function parseDrill(text) {
  const tools = {};
  const holes = [];
  const slots = [];
  let tool = null;
  for (const l of text.split("\n").map((s) => s.trim())) {
    const def = l.match(/^T(\d+)C([\d.]+)$/);
    if (def) {
      tools[def[1]] = Number(def[2]);
      continue;
    }
    const sel = l.match(/^T(\d+)$/);
    if (sel) {
      tool = sel[1];
      continue;
    }
    const slot = l.match(/^X(-?[\d.]+)Y(-?[\d.]+)G85X(-?[\d.]+)Y(-?[\d.]+)$/);
    if (slot) {
      slots.push({ dia: tools[tool], from: [+slot[1], +slot[2]], to: [+slot[3], +slot[4]] });
      continue;
    }
    const hole = l.match(/^X(-?[\d.]+)Y(-?[\d.]+)$/);
    if (hole) holes.push({ dia: tools[tool], at: [+hole[1], +hole[2]] });
  }
  return { tools, holes, slots };
}
