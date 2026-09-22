// KiCad 8 board/project emitter for the Strip Mine panels. Dependency-free (Node >= 20).
// Output is deterministic: every uuid is a v5 uuid derived from a caller-supplied key.

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const UFO_PROJECT = new URL("../../art-ufo-v2/ufo-panel.kicad_pro", import.meta.url);

// Fixed v5 namespace for this project (= uuid5(URL ns, "https://github.com/Takazudo/zudo-blanks/panels/art-strip-mine")).
const NAMESPACE = "30ee8466-c11b-5f43-9d04-77adc0f215e6";
const NAMESPACE_BYTES = Buffer.from(NAMESPACE.replace(/-/g, ""), "hex");

export function uuid5(key) {
  const h = createHash("sha1").update(NAMESPACE_BYTES).update(String(key)).digest();
  h[6] = (h[6] & 0x0f) | 0x50;
  h[8] = (h[8] & 0x3f) | 0x80;
  const x = h.subarray(0, 16).toString("hex");
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20)}`;
}

// KiCad writes up to 6 decimals with trailing zeros stripped and never uses exponent notation.
export function num(n) {
  if (!Number.isFinite(n)) throw new Error(`kicad-emit: non-finite number ${n}`);
  let s = n.toFixed(6);
  if (s.includes(".")) s = s.replace(/0+$/, "").replace(/\.$/, "");
  return s === "-0" ? "0" : s;
}

const xy = (p) => `${num(p[0])} ${num(p[1])}`;

// Re-indent a tab-indented block so it sits `depth` tabs deep inside the board.
const indent = (text, depth = 1) =>
  text
    .split("\n")
    .map((l) => "\t".repeat(depth) + l)
    .join("\n");

const FILLED_STROKE = ["(stroke", "\t(width 0)", "\t(type default)", ")", "(fill solid)"];

function graphic(kind, geometry, strokeFill, layer, key) {
  return [`(${kind}`, ...geometry.map((g) => `\t${g}`), ...strokeFill.map((s) => `\t${s}`), `\t(layer "${layer}")`, `\t(uuid "${uuid5(key)}")`, ")"].join("\n");
}

export function line(a, b, w, layer, key) {
  return graphic("gr_line", [`(start ${xy(a)})`, `(end ${xy(b)})`], ["(stroke", `\t(width ${num(w)})`, "\t(type default)", ")"], layer, key);
}

export function circle(c, r, layer, key) {
  return graphic("gr_circle", [`(center ${xy(c)})`, `(end ${num(c[0] + r)} ${num(c[1])})`], FILLED_STROKE, layer, key);
}

export function rect(x, y, w, h, layer, key) {
  return graphic("gr_rect", [`(start ${num(x)} ${num(y)})`, `(end ${num(x + w)} ${num(y + h)})`], FILLED_STROKE, layer, key);
}

// Closed Edge.Cuts polygon, same form as the UFO outline. Used for outer outlines and inner cutouts.
export function outline(pts, key) {
  return graphic(
    "gr_poly",
    ["(pts", `\t${pts.map((p) => `(xy ${xy(p)})`).join(" ")}`, ")"],
    ["(stroke", "\t(width 0.1)", "\t(type solid)", ")", "(fill none)"],
    "Edge.Cuts",
    key,
  );
}

function property(name, value, { at = "0 0 0", unlocked, layer, hide, size, thickness }, key) {
  return [
    `(property "${name}" "${value}"`,
    `\t(at ${at})`,
    ...(unlocked ? ["\t(unlocked yes)"] : []),
    `\t(layer "${layer}")`,
    ...(hide ? ["\t(hide yes)"] : []),
    `\t(uuid "${uuid5(`${key}:prop:${name}`)}")`,
    "\t(effects",
    "\t\t(font",
    `\t\t\t(size ${size} ${size})`,
    `\t\t\t(thickness ${thickness})`,
    "\t\t)",
    "\t)",
    ")",
  ];
}

function footprint(libName, x, y, key, properties, attr, pad) {
  return [
    `(footprint "${libName}"`,
    '\t(layer "F.Cu")',
    `\t(uuid "${uuid5(`${key}:fp`)}")`,
    `\t(at ${num(x)} ${num(y)})`,
    ...properties.flatMap(([name, value, opts]) => property(name, value, opts, key).map((l) => `\t${l}`)),
    ...(attr ? [`\t(attr ${attr})`] : []),
    ...pad.map((l) => `\t${l}`),
    `\t\t(uuid "${uuid5(`${key}:pad`)}")`,
    "\t)",
    ")",
  ].join("\n");
}

// Oval-slot mounting hole, reproducing the four blocks in panels/art-ufo-v2/ufo-panel.kicad_pcb.
// The UFO file carries two forms of the same pad: the library footprint (top slots) and an
// anonymous "" footprint (bottom slots, one of which has a pad offset). `anonymous` selects the latter.
export function slotFootprint(x, y, key, { padOffset = [0, 0], anonymous = false } = {}) {
  const pad = [
    '(pad "" thru_hole roundrect',
    `\t(at ${xy(padOffset)} 90)`,
    "\t(size 4 11.08)",
    "\t(drill oval 3.2 10.28)",
    '\t(layers "*.Cu" "*.Mask")',
    "\t(remove_unused_layers no)",
    "\t(roundrect_rratio 0.5)",
  ];
  if (anonymous) {
    const t = { size: 1.27, thickness: 0.15 };
    return footprint(
      "",
      x,
      y,
      key,
      [
        ["Reference", "", { ...t, layer: "F.SilkS" }],
        ["Value", "", { ...t, layer: "F.Fab" }],
        ["Footprint", "", { ...t, layer: "F.Fab", hide: true }],
        ["Datasheet", "", { ...t, layer: "F.Fab", hide: true }],
        ["Description", "", { ...t, layer: "F.Fab", hide: true }],
      ],
      null,
      pad,
    );
  }
  const t = { unlocked: true, layer: "F.Fab", hide: true, size: 1, thickness: 0.15 };
  return footprint(
    "Takazudo:BlankPanelHole-M3-size2",
    x,
    y,
    key,
    [
      ["Reference", "REF**", { ...t, at: "4.37 -3.56 0", layer: "F.SilkS", thickness: 0.1 }],
      ["Value", "BlankPanelHole-M3-size2", { ...t, at: "0.15 3.71 0" }],
      ["Footprint", "Takazudo:BlankPanelHole-M3-size2", t],
      ["Datasheet", "", t],
      ["Description", "", t],
    ],
    "through_hole",
    pad,
  );
}

// M3 stack screw hole: plated 3.2 mm drill in a 6 mm round pad (footprint Takazudo:stack-M3-screw-hole-pad6).
export function screwFootprint(x, y, key) {
  const t = { unlocked: true, layer: "F.Fab", hide: true, size: 1, thickness: 0.15 };
  return footprint(
    "Takazudo:stack-M3-screw-hole-pad6",
    x,
    y,
    key,
    [
      ["Reference", "REF**", { ...t, layer: "F.SilkS", thickness: 0.1 }],
      ["Value", "stack-M3-screw-hole-pad6", t],
      ["Footprint", "Takazudo:stack-M3-screw-hole-pad6", t],
      ["Datasheet", "", t],
      ["Description", "", t],
    ],
    "through_hole",
    ['(pad "1" thru_hole circle', "\t(at 0 0)", "\t(size 6 6)", "\t(drill 3.2)", '\t(layers "*.Cu" "*.Mask")', "\t(remove_unused_layers no)"],
  );
}

// Header blocks copied verbatim from panels/art-ufo-v2/ufo-panel.kicad_pcb.
const HEADER = `(kicad_pcb
	(version 20240108)
	(generator "pcbnew")
	(generator_version "8.0")
	(general
		(thickness 1.6)
		(legacy_teardrops no)
	)
	(paper "A4")
	(layers
		(0 "F.Cu" signal)
		(31 "B.Cu" signal)
		(32 "B.Adhes" user "B.Adhesive")
		(33 "F.Adhes" user "F.Adhesive")
		(34 "B.Paste" user)
		(35 "F.Paste" user)
		(36 "B.SilkS" user "B.Silkscreen")
		(37 "F.SilkS" user "F.Silkscreen")
		(38 "B.Mask" user)
		(39 "F.Mask" user)
		(40 "Dwgs.User" user "User.Drawings")
		(41 "Cmts.User" user "User.Comments")
		(42 "Eco1.User" user "User.Eco1")
		(43 "Eco2.User" user "User.Eco2")
		(44 "Edge.Cuts" user)
		(45 "Margin" user)
		(46 "B.CrtYd" user "B.Courtyard")
		(47 "F.CrtYd" user "F.Courtyard")
		(48 "B.Fab" user)
		(49 "F.Fab" user)
		(50 "User.1" user)
		(51 "User.2" user)
		(52 "User.3" user)
		(53 "User.4" user)
		(54 "User.5" user)
		(55 "User.6" user)
		(56 "User.7" user)
		(57 "User.8" user)
		(58 "User.9" user)
	)
	(setup
		(pad_to_mask_clearance 0)
		(allow_soldermask_bridges_in_footprints no)
		(pcbplotparams
			(layerselection 0x00010f0_ffffffff)
			(plot_on_all_layers_selection 0x0000000_00000000)
			(disableapertmacros no)
			(usegerberextensions no)
			(usegerberattributes yes)
			(usegerberadvancedattributes yes)
			(creategerberjobfile yes)
			(dashed_line_dash_ratio 12.000000)
			(dashed_line_gap_ratio 3.000000)
			(svgprecision 4)
			(plotframeref no)
			(viasonmask no)
			(mode 1)
			(useauxorigin no)
			(hpglpennumber 1)
			(hpglpenspeed 20)
			(hpglpendiameter 15.000000)
			(pdf_front_fp_property_popups yes)
			(pdf_back_fp_property_popups yes)
			(dxfpolygonmode yes)
			(dxfimperialunits yes)
			(dxfusepcbnewfont yes)
			(psnegative no)
			(psa4output no)
			(plotreference yes)
			(plotvalue yes)
			(plotfptext yes)
			(plotinvisibletext no)
			(sketchpadsonfab no)
			(subtractmaskfromsilk no)
			(outputformat 1)
			(mirror no)
			(drillshape 0)
			(scaleselection 1)
			(outputdirectory "gerber/")
		)
	)
	(net 0 "")`;

// items: s-expression strings from the builders above, in output order.
export function board({ items }) {
  return `${HEADER}\n${items.map((i) => indent(i)).join("\n")}\n)\n`;
}

// Severities relaxed for net-less, edge-touching artwork; all other rules keep the UFO template's severity.
// The lib_* checks are ignored too: footprints are emitted inline and the "Takazudo" library is a
// per-machine KiCad setting (no fp-lib-table in this repo), so those checks only report the environment.
const IGNORED_RULES = ["copper_edge_clearance", "shorting_items", "solder_mask_bridge", "lib_footprint_issues", "lib_footprint_mismatch"];

export function project(name) {
  const pro = JSON.parse(readFileSync(UFO_PROJECT, "utf8"));
  pro.meta.filename = `${name}.kicad_pro`;
  for (const rule of IGNORED_RULES) pro.board.design_settings.rule_severities[rule] = "ignore";
  return `${JSON.stringify(pro, null, 2)}\n`;
}

export function assertUniqueUuids(text, label = "board") {
  const seen = new Set();
  for (const [, id] of text.matchAll(/\(uuid "([^"]+)"\)/g)) {
    if (seen.has(id)) throw new Error(`kicad-emit: duplicate uuid ${id} in ${label}`);
    seen.add(id);
  }
  return seen.size;
}
