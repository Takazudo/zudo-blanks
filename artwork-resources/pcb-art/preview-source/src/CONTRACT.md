# Geometry and viewer contract — Revision 5

All units are millimetres. The origin is the top-left of the front PCB, x right and y down. Each Python design module exports `build()` and uses Shapely `body` geometry before mounting drills. `kumiko_void.py` also exports `build_wide()`; its standard `build()` preserves Revision 3 geometry and artwork.

## Physical envelope

- Front PCB: 101.3 × 128.5 mm.
- Lower PCBs: 101.3 × 94.3 mm, y=17.1…111.4 mm.
- PCB thickness: 1.6 mm; physical spacer gap: 3.0 mm.
- Four common Ø3.2 mm stack drills at (6.5,23.6), (94.8,23.6), (6.5,104.9), (94.8,104.9).
- Preserve the full radius-3.05 mm material support region around every stack drill before drilling.
- The front additionally has four rail slots with 10.28 × 3.2 mm drill dimensions; locations are defined in `build_common.py`.

Every layer must be one connected Polygon after its own drills are subtracted. Screws and neighboring layers never count as material connections. Each layer must retain continuous upper and lower bridges. A 0.5 mm inward offset must retain one significant connected component; this is a neck check, not fabrication DRC. Every design ends with a solid floor. Decorative top apertures stay within the lower-board rectangle so their depth is backed by the stack.

Artwork is flat. The viewer extrudes each actual board by 1.6 mm without inventing raised copper or bevel geometry. Kumiko's apparent bevels come from gold and black graphic facets. Spider and Kumiko use angular decorative shapes; functional drills are still round or slotted.

## Source and finish policy

The five design modules use `make_layer()` and `plate(index)` from `build_common.py`. Do not add mounting holes in a design module: `scripts/build_geometry.py` applies the common drills, serializes geometry, applies finish policy and validates each board.

`src/finish_policy.py` is authoritative. One-based ENIG layers are Spider 1/3/5/7, Coral 1/4, Fault 1, Kumiko 1/4/7, Woven 1. All other layers have `surface:'mask'`, empty artwork arrays and `finish:'mask-only'`; the renderer allocates no decorative artwork mesh or texture for those layers. Full-gold layers use `surface:'gold'` and `finish:'enig-fill'`.

The five-family configuration contains 43 PCBs: 11 ENIG and 32 mask-only. Standard and wide Kumiko are alternatives with the same nine-layer color and finish sequence. The serialized data validates both alternatives, totaling 52 board records; they are not an instruction to manufacture an extra stack.

Revision 5 adds shared cosmetic rims to EVERY top PCB, including both Kumiko variants. There is one outside frame, four stack-hole rims and four rail-slot rims per top. Spider and Kumiko use angular decorative outlines. Functional holes remain round or slotted. These are flat exposed-copper graphics, not a requirement to plate the hole walls. All lower-layer artwork and all physical outer/hole coordinates are preserved from Revision 4. The immutable comparison snapshot is `assets/reference-revision4.json`.

Palette sequences:

- Spider: black/white/gold/white/gold/white/gold/red.
- Coral: black/green/purple/gold/red/yellow/red/blue.
- Fault: black/red alternating, ending in black (9).
- Kumiko: black/red/green repeated three times.
- Woven: black/white alternating, ending in black (9).

## Serialized data

`globalThis.PCB_ART_DATA` contains `{schemaVersion:4, revision:5, spec, designs:[...]}`. `spec` includes common dimensions, screws, rail slots, spacer and rail geometry. The canonical design IDs remain `spider-nest`, `coral-vault`, `fault-line`, `kumiko-void`, `woven-maze`.

`topGoldBorders` on each design and `goldBorders` on its top layer record the flat border widths, offsets and containment checks. Tagged strokes are appended last so the borders remain visible over the motif. The outside frame has a 0.55 mm centerline inset and 0.32 mm width. Stack-hole rings have a 2.70 mm centerline radius and 0.40 mm width; rail-slot rims have a 2.10 mm offset from the slot axis and 0.40 mm width. Spider/Kumiko use octagonal stack rims and rectangular slot rims.

A design contains `{id, number, name, subtitle, description, notes, sources, layers, checks, stackDepth, totalAreaMm2, finishSummary, comparisonToRevision3}`. The comparison records `previousAreaMm2`, `currentAreaMm2`, `areaScale`, `previousBoundsMm` and `currentBoundsMm` for actual decorative top apertures, excluding mounting drills.

Each layer contains `{index,colorKey,name,nameJa,mask,surface,solid,note,outer,holes,art,finish,finishLabel,stats}`. `outer` and each item of `holes` are arrays of `[x,y]` coordinates, without repeating the first point. Coordinates are serialized to 0.0001 mm. Holes include decorative cutouts and mounting drills. Stats include aperture area and bounds, one-component connectivity, support and bridge checks, and inward-offset connectivity.

Hole rings that collapse to zero area when rounded are omitted before triangulation. This changes no positive-area geometry. Baseline comparisons ignore only those same zero-area rings in the older serialized data. Standard Kumiko geometry and its original motif are retained; Revision 5 adds the common top gold borders after the motif.

`art.strokes` entries use `{pts,w,color?,closed?}`. `art.fills` entries use `{pts,color?}`. Omitted color means gold; explicit black fill gives the Kumiko optical shadow. A full-gold surface does not require a polygon covering its entire remaining area in `art.fills`. `artStyle:'angular'` requests butt line caps and miter joins.

## Kumiko alternatives

The canonical Kumiko design is the preserved standard model with `variantId:'standard'`, `variantLabel:'標準'`, `defaultVariant:'wide'`. Its `variants` array contains one fully serialized wide model with the same family `id`, `variantId:'wide'` and `variantLabel:'開口拡大'`. Alternative records do not contain another `variants` array.

The viewer selects by family ID plus variant ID. The main family navigation defaults to wide; the standard standalone HTML sets `PCB_INITIAL_VARIANT='standard'`, and the wide standalone sets it to `'wide'`. Switching alternatives preserves camera pose, isolated layer, spacing and display switches. PNG names identify the selected variant. Automation uses `__PCB_PREVIEW__.setVariant()` and the reported `variantId` state.

## Revision 4 design behavior

Spider uses large irregular structural webs near the supported perimeter. The top graphic continues the same web's lines outward across the remaining margins rather than applying a separate tiled field. Coral uses expanded flowing chambers that change irregularly and narrow at depth. Fault uses a tall asymmetric canyon with alternating angular and rounded cliffs and locally varying retreat. Woven retains seven distinct lower maze route families while spreading their coordinates into the expanded opening. Kumiko wide expands the structural cut domain while retaining its asanoha geometry and flat gold/black treatment.

For Coral and Fault, validate the union of all decorative apertures on each layer: area must decrease and every deeper union must lie within the preceding union, allowing only serialization tolerance. Hole count may change; material must stay connected. Nesting does not imply a uniform offset or a repeated contour.

`patternCoverage` checks that top artwork reaches the remaining upper, lower, left, right and central face regions on Spider, Coral and Kumiko. It does not prescribe a fixed tile, density or manufacturing gold-area estimate.

## Build and verification

`scripts/build.mjs` bundles three.js, geometry, CSS and viewer code into seven fully offline HTML files: one index, five family entries and one additional Kumiko-wide entry. The shell markers are `<!--STYLE-->`, `<!--DATA-->` and `<!--APP-->`; replacements preserve literal JavaScript replacement-string characters. No CDN, external fonts, CSS or scripts are required at runtime.

`assets/reference-revision3.json` is the immutable comparison baseline, included in the source bundle but not loaded by the HTML. `npm run build` writes `assets/geometry.json`, `assets/validation.json` and `dist/`.

`node tests/browser.mjs --revision` runs the focused Revision 5 browser and independent polygon checks. `tests/rev5_gold.py` separately verifies exact physical geometry preservation, unchanged lower art and all 54 closed top border strokes. The reports and comparison images use actual serialized board geometry and actual WebGL captures. Previous Revision 3 and Revision 4 reports are retained separately.
