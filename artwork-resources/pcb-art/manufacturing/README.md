# Fabrication decision — 2026-09-25

Decision for [issue 14](https://github.com/Takazudo/zudo-blanks/issues/14), frozen for issues 15–17. `policy.json` is the machine-readable contract. This record chooses the local adaptation and packaging process; production geometry, native validation and CAM follow in those issues. The approved artwork is still Revision 5 with **Kumiko wide**. No board has factory acceptance.

## Evidence and current capability check

Checked **2026-09-25** against the live official pages below. These published capabilities are distinct from this project's stricter choices. Source geometry SHA256 is `00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e`. `policy.json` freezes the other input hashes, including both manufacturing reviews and the native manifest. The incoming review figures and CSVs remain original evidence, including their limitations.

[JLCPCB rigid capabilities](https://jlcpcb.com/capabilities/Capab), sections Drilling, Traces, Soldermask and Outline: FR-4; 1.6 mm thickness ±10%; 1 oz copper; NPTH minimum 0.50 mm; nonplated slot minimum 1.0 mm; sharp rectangular internal corners unsupported; NPTH/route copper clearance 0.2 mm. General copper width/space is 0.10/0.10 mm, while exposed coils, grids and same-net spacing specify 0.25 mm. Black/white mask bridges require 0.13 mm; other listed colors 0.10 mm. Mask opening to neighboring traces is 0.09 mm. V-score copper clearance is 0.4 mm, size tolerance ±0.4 mm, panel range 70–475 mm, groove angle 25°. Routed dimensional tolerance is ±0.2 mm regular / ±0.1 mm precision; precision has extra tooling conditions. Spaced panel routing requires 2 mm; tabs leave serrations. These are catalog limits, not approval of artwork or strength.

[JLCPCB PCB Panelization](https://jlcpcb.com/help/article/pcb-panelization), **last updated September 9, 2026**, V-cut/V-Groove items 1–6 and 10: zero separation at scores; straight horizontal/vertical lines across the whole sheet; 70 × 70 mm minimum; 475 × 475 mm maximum with both score directions; parallel scores at least 2 mm apart; at most 25 score lines per axis. The article also limits different designs to ten. We declare actual distinct board IDs and use a conservative ten-member cap in every package. A multi-design fee or lower cost is not inferred.

[KiCad 10 PCB Editor manual](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html), sections **Board outlines (Edge Cuts)**, **Solder mask/paste**, **Graphical shapes**, **Pad properties**, **Drill files**, and **Board finish**: closed nonintersecting Edge.Cuts contours define material and internal voids. NPTH mechanical pads represent unplated circular/oval drills. Mask graphics denote openings. Global mask minimum-web settings can merge plotted openings; board finish metadata only affects Gerber job attributes. Therefore do not use automatic mask-web merging to fix black facets. Set mask expansion and automatic web merging to zero for explicit artwork geometry; enforce spacing independently. Export NPTH separately from PTH and do not duplicate drill contours on Edge.Cuts. KiCad DRC does not replace a geometric check of the union of graphic polygons.

The source exporter already interprets F.Mask as openings, preserves painter order, subtracts black facets and represents NPTH independently. Strip Mine `scripts/build-panels.mjs`, `export-panels.py` and `panels.test.mjs` were read for translation, score drawings and packaging structure only. Its plated-pad, edge-copper and DRC choices are not inherited.

## Frozen rules

All distances below are nominal millimetres. Numeric comparison tolerances are **0.001 mm distance** and **0.00001 mm² area**; tolerances cover serialization, never an unlisted design exception. Use 1 nm native coordinates and retain analytic arcs or sufficiently fine curves (at least 64 segments per circle quadrant in geometric proofs).

| Requirement | Project choice | Purpose |
| --- | ---: | --- |
| Process | 2 copper layers, FR-4, 1.6 mm, 1 oz | Same construction for every package; no electronic components |
| Decorative routing | 1.0 mm cutter, 0.5 mm internal corner radius | Explicit tool-center regions and swept cut envelopes |
| Material ligament / structural bridge | ≥1.0 mm | Separate minimum-width and connectivity checks |
| Stack support before drilling | full disk radius 3.05 mm | Preserve all four spacer seats, not only the hole's annulus |
| Top copper / visible-gold clearance to any route or true drill | ≥0.30 / ≥0.35 mm | Includes inner apertures, outer perimeter and oval slots |
| Lower copper / visible-gold clearance to outer rectangle | ≥0.50 / ≥0.55 mm | Scoring allowance encoded in individual boards before panelization |
| Lower copper / visible gold to internal route or drill | ≥0.30 / ≥0.35 mm | Decorative edges stay routed |
| Copper beneath an opening | ≥0.05 mm margin | Mask opening contained in copper |
| Finished graphic copper width / separate copper gap | ≥0.25 / ≥0.25 mm | Use the more restrictive published coil/grid class for all art |
| Visible gold width / mask web | ≥0.25 / ≥0.25 mm | One consistent art rule; exceeds 0.13 mm black-mask floor |
| Hidden copper join | width ≥0.25 mm, length ≤0.60 mm per indexed gap | Join nearby decorative islands beneath retained mask |
| Mask to unrelated copper | ≥0.09 mm | Do not confuse own underlying copper with a neighboring island |
| Local mask repair reach | ≤0.50 mm from the indexed offending feature | Prevent broad edits to the approved motif |
| Scored seam to decorative aperture or support disk | ≥1.0 mm | Entire score corridor must remain solid and clear |

Width means the width of the finished union, including narrow necks, branches and standalone fragments, not nominal input stroke width. At a finite end, cap a gold or material branch where its 0.25 mm or 1.0 mm full width ends; an arbitrarily acute surviving needle is not an exception. Connected erosion can miss a disappearing branch, so inspect erosion/reconstruction residue and opposing nonadjacent boundary segments as well. Mark candidates by board, coordinate and original feature; repair locally by adding substrate (shrinking the adjacent cutout), then recheck tool access. Do not silently discard width candidates as numerical dust. Distinguish a rounded terminal cap from a narrow branch of positive length.

**Geometry and appearance invariants:** top rectangle `[0,0,101.3,128.5]`; lower rectangle `[0,17.1,101.3,111.4]`; thickness 1.6 and spacer gap 3.0. Stack centers are `(6.5,23.6)`, `(94.8,23.6)`, `(6.5,104.9)`, `(94.8,104.9)` with Ø3.2 NPTH on every board. Only tops have four 10.28 × 3.2 mm NPTH slots, at the original slightly asymmetric centers in `policy.json`. No global alignment or symmetry cleanup. Require one connected board after drilling, continuous full-width upper/lower strips at least 1.0 mm deep, a solid final floor except the four drills, and every decorative top opening backed by the lower rectangle.

Keep Spider's radial irregular web; Coral/Fault's descending nested irregular aperture unions; Fault's angular black and rounded red cliffs; Kumiko's angular planar gold/black illusion; all seven different Woven lower maze paths. Round only inaccessible route corners, preserving straight angular segments. All five tops retain the outer gold frame, four stack rims and four slot rims (nine paths per top). Rail rims initially have 0.30 mm inner clearance: retreat their inner edge by 0.05 mm to meet 0.35 mm clearance, leaving nominal 0.35 mm visible width. Index this operation by each original `rail-slot` featureIndex 0–3 on every top. Coral L01 stack rims at original featureIndex **1, 2 and 3** also approach the decorative contour to 0.248274 mm in the approved input. Move only these three circular centerlines inward from radius **2.70 to 2.55 mm**, retaining 0.40 mm width and exact drill centers; repaint them last. All other border centerlines remain unchanged. Prove each of the nine closed paths retains a continuous 0.25 mm gold core. The outer frame needs no retreat. Full-gold lower layers remain ENIG fill with necessary safe setbacks. Lower mask-only layers retain no decorative copper/openings and never acquire exposed gold. B.Cu artwork, B.Mask artwork, paste, silk, PTH and edge plating remain empty/disabled. The nominal two-layer construction does not authorize adding rear copper art.

## Indexed local adaptation

1. **Close the 56 selected small apertures** listed with original `issueId`, `geometryHoleIndex0`, area and coordinates in `policy.json`. Add substrate only in each original hole; retain that board's mask. The sum is **139.19764395 mm² across eight wide layers**. Do not replace them with round holes, enlarge them through support, or switch to standard Kumiko. Closing **wide L01-H11**, original hole index **101**, also removes `kumiko-void-wide-L01-THIN-68-101` (0.116618566 mm at the recorded closest points). Retain original hole 68 except its individually indexed inaccessible corner treatment. The eight standard findings and all nine standard boards remain unchanged and **non-orderable alternatives**.
2. For each remaining decorative aperture `A`, compute its admissible 0.5 mm cutter-center region. Inaccessible tips become substrate; the candidate finished aperture is the union of 0.5 mm swept disks over **all** admissible center components. This is a tool-envelope definition, not whole-board smoothing. Do not discard a smaller center component. Each disconnected center region needs a recorded accessible plunge and path, or an indexed local closure/shrink. Known split center regions: wide Kumiko L05 original hole 14; Woven L04 original hole 0. Neither fact is resolved merely because a tool fits elsewhere in the hole. No change to functional drills.
3. Preserve unchanged contours exactly outside each recorded delta. On each changed original aperture, write its source hash, original index, changed-coordinate bounding boxes, operation, before/after area, contour hashes and measured tests. The probe's per-hole changes are a seed list, not permission to change unrelated areas. For nonempty holes, local corner displacement is bounded by **0.75 mm**; larger corner displacement or split-center closure must get a separate indexed record with measured area and a targeted comparison under the same local policy. Known complete closures are explicitly exempt from that displacement bound. Any extra complete aperture closure, topological motif replacement or failed invariant is a blocker requiring evidence, not an automatic fallback.
4. Enforce minimum material width locally. Prefer substrate additions at an indexed thin neck over aperture enlargement or opening merger. No global buffer/simplify pass over board art or physical geometry. Recompute tool sweeps after each repair. Nesting is tested on corrected aperture unions, not assumed from the originals.
5. Reconstruct gold using original fills/strokes and paint order, including Kumiko black facets and last-painted rims. Apply the numeric safe-edge masks to corrected geometry. Preserve original gold on original surviving substrate; newly filled tiny holes stay mask-colored. Full-gold lower material may follow the complete safe substrate, with every added exposed patch indexed. Record edge clipping by board and nearest original art feature, not merely a single global percentage.
6. Resolve copper gaps by **hidden joins first**: add a ≥0.25 mm wide local bridge beneath intact mask, staying inside the copper safe region. Do not open mask over it. Resolve mask-web gaps by retreating the adjacent gold locally until the **0.25 mm** web exists. Kumiko black facet points stay black. An incidental unpainted mask sliver at the intersection of top rims/motif may be merged into gold only if it contains no original black-facet paint and the operation is separately indexed. The nine rim paths take priority over nearby motif tips; trim/retreat the motif first. The only additional gold-merge permission is the explicitly bounded Spider L01 channel erratum below.
7. Cap sub-width gold tips, or remove an isolated sub-width gold fragment only after an indexed local widening is impossible without invading a black facet or protected border. Bounds, original feature IDs, area and reason are mandatory. Copper can remain hidden beneath a removed mask sliver. Do not present a minimum inscribed-circle test as proof of every feature's printable width.

Existing art gap entries have no issueId; use the stable key `art:<sourceExportSha256>:<boardId>:<feature>:<polygonA0>:<polygonB0>` and retain their original closest-point coordinates from `validation/export-art-review.json` / `resources/manufacturing-review/artwork-gap-review.csv`. Link all selected input findings, even if they disappear as a consequence of a prior correction. New findings under 0.25 mm receive equivalent keys tied to the measured input hash. The nine standard boards' findings remain separate. A production ledger must account for every output delta and every known selected finding; no blanket DRC exclusions.

Appearance budgets are **≤2% aperture area loss per board**, except **wide L01 ≤3.5%** because its measured 1.0 mm tool-envelope loss is 3.05419%. Existing approved source corners cannot be routed exactly. Combined edge/width/mask adjustments may remove **≤30% gold area per ENIG board**, but this budget never permits deleting a motif, shadow facet or border. Every changed design needs a full-board and targeted comparison, and every ENIG board needs numeric before/after gold metrics. Exceeding a budget requires an explicit evidence-based decision amendment; do not quietly relax tests. These are project review gates, not manufacturer limits.

## Spider L01 channel erratum — 2026-09-25

Issue 15's relocated guides expose three narrow unpainted channels between the main Spider radial network and source guide strokes 111, 97 and 112. The source has no explicit black fills or strokes; its radial paths and aperture-following guides belong to the same web motif. The specific source stroke pairs nevertheless had nonzero gaps (approximately 0.155110, 0.164872 and 0.123074 mm). This is a permitted local change to their connection, not a claim that the approved artwork already joined them.

The reviewed manufacturing candidate is SHA256 `ceda4de34fb2ca999e263bfaba0233730f7a60551049807c319721239855d0a1`. The captured evidence candidate is `f40a5bd4f0abb63d9f20f81a6f53eb397ac9c92e4c0c1c9d88152cb97927d068`; the three gaps and closest points remained identical on read-back. `spider-channel-erratum.json` binds the approved input, the six original stroke hashes, the exact pre-merge Spider mask and four patch geometries. This evidence is a permission envelope; it does not approve completed manufacturing artwork.

| Channel / original stroke indices (zero-based) | Closest-point midpoint mm | Measured gap mm | Patches | Added gold mm² |
| --- | --- | ---: | ---: | ---: |
| SP-L01-CHANNEL-01 / 41–111 | (33.715887, 56.778474) | 0.034614 | 2 | 9.739923 |
| SP-L01-CHANNEL-02 / 33–97 | (64.357504, 73.903113) | 0.044372 | 1 | 12.352887 |
| SP-L01-CHANNEL-03 / 38–112 | (30.178096, 78.087342) | 0.002574 | 1 | 7.779394 |

Permit **only four patches in these recorded channels**, with a hard combined cap of **30.0 mm²**. The 32-segment reference measures 29.872204 mm²; the captured 64-segment implementation example measures 29.892211 mm². These measurements are evidence, not equality requirements. Add them to the pre-merge gold union; remove no existing gold. Preserve all nine top rim cores, the radial paths, their guide strands, and all physical contours/drills. Every added point must stay in the **0.35 mm mask-safe region** and within the existing 0.50 mm local-art correction reach. No explicit black paint may be covered. All other copper, mask, geometry, clearance, finish and appearance rules remain in force. This permission does not apply to other boards, other Spider channels or Kumiko facets.

The 32-segment reference patch calculation is pair-specific: let `C(X)` be `X.buffer(0.1255, quad_segs=32).buffer(-0.1255, quad_segs=32)`. For the recorded components A/B, extract `(C(A union B) minus (C(A) union C(B))) minus (A union B)`. A 64-segment implementation may extract the connected added polygons from `C(M) minus M` for the full pre-merge mask M, but select only polygons touching both members of the recorded pairs. Apply exactly four selected channel patches; discard every unrelated candidate polygon. The proposed patch for each recorded ID must lie inside the union of its captured 32-segment reference and 64-segment implementation polygons, allowing only the existing 0.001 mm coordinate tolerance, remain within 0.1255 mm of the pre-merge gold (plus the existing 0.001 mm distance tolerance), touch both named components, and satisfy the total-area/clearance/paint gates. This bounds the measured discretization and extraction differences without permitting arbitrary additions up to the area cap. Do not apply closing to the entire mask. Their long coordinate bounds represent narrow channels; record the entire patch geometry, not merely the nearest-point marker. A tiny connector that only makes a distinct-component warning disappear is insufficient.

Before applying the exception, verify the approved source and stroke hashes and compare the candidate's pre-merge Spider mask to the captured mask. A changed overall candidate hash is acceptable only for separately ledgered unrelated-board or provenance changes **while the Spider mask is identical** (normalized WKB hash, or explicit geometry equivalence within the existing numerical tolerances). Different Spider geometry or a patch outside its recorded channel envelope requires a new indexed review; the area cap alone grants no broader permission. The two captured patch realizations define the narrow permission envelope; their areas are not fixed equality targets. This envelope does not authorize moving the pre-merge artwork. Pre-merge mask distance may differ only within 0.001 mm; compare area at fixed 1 nm precision or reproduce the captured quantized-mask hash. Account for every resulting coordinate delta explicitly. Recompute copper from the final accepted mask and rerun its independent rules.

Issue 15 must prove **positive gold widths and negative mask widths**, including branches/channels inside a single connected component; preserve the source strands and rim cores; and reject new trapped mask pockets or sub-width channel ends. Require full-board and enlarged before/after comparisons showing the actual four additions and source/candidate hashes. Convex-corner reconstruction residue must be distinguished from a positive-length thin branch; neither eroded-core connectivity nor a vanished component-gap warning is sufficient. The captured full-board and enlarged comparison is `spider-channel-erratum.png`; it shows preserved strands and the bounded additions. Regenerate it from repository root with `uv run --python 3.13 --with shapely==2.1.2 --with pillow python artwork-resources/pcb-art/manufacturing/render_spider_erratum.py`. Final production width tests and output-level visual acceptance remain pending. The earlier decision probe and approved Rev5 history remain immutable; the policy test reconstructs the exact pre-erratum policy for the old probe hash and verifies this additive exception separately.

## Spider L01 rib-width erratum — 2026-09-25

The width conflict beside central source strokes **7/8** cannot be repaired by moving three gold strands inside the existing material. At their midpoints `(69.8334,46.2349)` and `(61.1195,51.5244)`, the rib measures **1.661166 / 1.661193 mm**. After two 0.35 mm mask setbacks, only **0.961166 / 0.961193 mm** remains. Two 0.251 mm guides, a 0.280 mm central stroke and two 0.250 mm black channels require **1.282 mm**. The current internal black channels are approximately 0.080 mm wide. Even substituting the published 0.13 mm black-mask floor would require **1.042 mm**, still more than the available space; that comparison does not authorize reducing the frozen 0.25 mm rule. The two long enclosed ink islands are not exempt because they admit a larger circle somewhere else.

Permit a **2.0 mm material ribbon with flat caps and miter joins**, along exactly:

```text
(73.5804,43.9604) -> (66.0864,48.5094) -> (56.1526,54.5394)
```

The initial operation is `new_body = captured_body union ribbon`. It removes no material and changes no outside dimensions or functional drills. `spider-rib-decision.json` binds the approved source hash `00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e`, the captured body from `spider-channel-erratum.json`, the exact ribbon/addition hashes, and the affected original hole-contour hashes. The initial addition measures **6.074302 mm²**; require the exact ribbon operation within existing numerical tolerances, with an upper area bound of **6.10 mm²**. The cap alone grants no authority to add material elsewhere.

Only original decorative hole indices **1, 6 and 16** are affected. The initial probe retains the board's connected piece and hole count, full radius-3.05 mm support disks before drilling, continuous upper/lower strips, backed top apertures and all functional drills. Its cumulative aperture loss versus approved Rev5 is **0.180907%**, below the unchanged **2%** Spider per-board budget. These are checks of the initial material proposal, not the completed routing/artwork pipeline.

Re-run the existing **1.0 mm cutter sweep over every center component** of the three affected remaining apertures. The bounded probe finds **0.215386 mm²** of additional unreached area on those apertures; it does not leave that area as an accepted machining discrepancy. Permit at most **0.25 mm²** additional material from this specific cutter-envelope correction, with each original hole/coordinate delta indexed, and at most **6.35 mm²** combined material addition. No arbitrary extra fill or edits to other apertures are authorized by this erratum. The 2% cumulative aperture-loss budget and all mechanical invariants still apply after this correction. The operator supplies a candidate contour, not a plunge/toolpath or strength proof; recheck actual access, internal corners, minimum material widths and native/CAM contours.

Keep the central paths of strokes **7/8** and their **0.280 mm** width. Move only the adjacent portions of guide strokes **98/101/103** to the following nominal offsets, retaining **0.251 mm** guide widths. For a directed central segment `(dx,dy)`, define the positive unit normal as `(-dy,dx)/length`.

| Central segment | Guide | Signed center offset mm |
| --- | --- | ---: |
| stroke 7 | 98 | +0.5165 |
| stroke 7 | 101 | -0.5165 |
| stroke 8 | 101 | -0.5165 |
| stroke 8 | 103 | +0.5165 |

In a straight 2.0 mm section, these positions provide **0.251 mm black channels** and **0.358 mm outer mask clearance**: `0.358 + 0.251 + 0.251 + 0.280 + 0.251 + 0.251 + 0.358 = 2.000`. These are nominal targets; all guide ends and transitions must independently meet the existing 0.25 mm positive-gold/negative-mask widths and 0.35 mm mask clearance. Limit transition displacement to **0.50 mm** from the indexed original guide portions, inside the ribbon buffered by 0.50 mm; retain every other portion of these closed guide paths. Preserve the radial motif, all nine rim cores, flat gold appearance, and mask/finish/layer order. Rebuild copper only after validating the final mask.

Compose this operation with the prior channel erratum explicitly. Its four authorized gold patches and <=30.0 mm² gold-addition cap remain unchanged. The rib/guide change envelope is disjoint from those patches. Evaluate source/hash bindings at the relevant intermediate pipeline stage; only the newly authorized rib-local body and guide deltas may differ when comparing to that prior captured Spider state. Account for the differences in a separate ledger. This is not permission to broaden either erratum or to treat every later Spider shape as equivalent.

Issue 15 must provide complete indexed deltas, cumulative aperture metrics, updated support/bridge/backing/one-piece checks, cutter-center/plunge/toolpath evidence, positive-gold and negative-mask width proofs including transitions, and full-board/enlarged comparisons of the corrected geometry and finished appearance. Issue 16 must independently verify regenerated native PCB and CAM output. `spider-rib-comparison.png` shows only the initial material addition; planned artwork locations are a cross-section budget, not accepted final artwork. Regenerate the bounded evidence and figure with:

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow python artwork-resources/pcb-art/manufacturing/probe_spider_rib.py
```

No production or factory acceptance is granted. Do not silently accept excess area, a new aperture closure, a support regression, a failed transition, or a failed cutter-access check; record the exact evidence for a further bounded decision if required.

## Spider L01 complete-network amendment — 2026-09-25

Historical scope: superseded by the unfiltered-network correction below. Its survey excluded wide central gold intervals and missed remaining channels.

This amendment **supersedes the material, affected-aperture and guide-portion scope of the earlier 7/8 rib erratum**. Retain its evidence as history. Apply the complete network once from the captured pre-rib body in `spider-channel-erratum.json`; do not add the old 6.35 mm² allowance to the new allowance. The four channel-merge patches, their exact envelopes and their <=30.0 mm² gold cap remain unchanged. No other board or process rule changes.

The reproducible survey in `spider-network-decision.json` binds the immutable approved source and `spider-network-input.json`, a captured diagnostic candidate, not approved output. Normal sections at <=0.20 mm intervals locate **38 sustained runs below 0.13 mm** (369.509 channel-mm) and **46 interior runs below 0.25 mm** (483.324 channel-mm), across 12 and 14 connected black regions respectively. Each run records the source segment, adjacent guide, position, width range and connected-region hash. These are genuine long channels, not an inference from erosion component counts. Five outer-rim taper flags on 74/75/80/88/91 remain separate indexed terminal checks under the existing rim policy; this amendment permits no extra material there. The survey is not an exhaustive final-width certificate.

### Exact material operation

Add 2.0 mm ribbons, **flat caps and miter joins**, along all points of approved source paths **2, 3, 4, 5, 6, 9, 10, 15, 16, 17, 18, 25, 27, 31, 34, 36 and 39**. Include the earlier **7/8** path as one continuous mitered ribbon, once. Use the exact coordinates and hashes in the decision evidence; no extensions, freehand patches or width changes. Union this network with the hash-bound pre-rib body without material removal. Initial addition is **73.921152 mm²**, including the earlier **6.074302 mm²**. The additional ribbon area relative to the captured survey body is **67.846462 mm²**; that is an explanatory comparison, not the operation's baseline or a second budget.

Only original decorative apertures **0, 1, 2, 3, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17 and 18** change. Preserve apertures 4/8/9/10 exactly. On each affected post-union aperture `A`, compute every component of `C = A.buffer(-0.5, quad_segs=64)` and retain the aperture `C.buffer(0.5, quad_segs=64).intersection(A)`. This exact cutter-envelope cleanup adds **2.208271 mm²**, for **76.129423 mm² combined addition** relative to the pre-rib body. The evidence binds each aperture, cleanup delta and final shape by normalized WKB hash; the numeric maxima in policy allow only the existing 0.00001 mm² arithmetic tolerance. An area cap alone never authorizes another shape. Do not repeat cleanup until an arbitrary result converges, transfer budget between apertures or change an unaffected aperture.

After the measured cleanup, cumulative aperture loss versus approved Rev5 is **1.215701%**, within the unchanged **2%** cap. The probe preserves 19 decorative apertures, all eight functional holes/slots, one material component, exact outer dimensions, full pre-drill radius-3.05 mm support disks, upper/lower bridges and backing. Material is only added, so existing material ligaments and the unchanged lower floor cannot shrink. All 19 apertures retain one nonempty connected 1.0 mm cutter-center region and a contained plunge disk. This establishes geometric access feasibility; final serialized contours, finite cutter paths, native/CAM output and actual manufacturing remain separate gates.

### Indexed guide relocation and transitions

Keep all central radial paths and their 0.280 mm width. The following table lists adjacent guide indices on the negative/positive normal sides of each directed approved path; normal is `(-dy,dx)/length`:

| Central path | Negative guide | Positive guide |
| --- | ---: | ---: |
| 2 | 104 | 109 |
| 3 | 105 | 106 |
| 4 | 98 | 104 |
| 5 | 103 | 105 |
| 6 | 95 | 98 |
| 7 | 101 | 98 |
| 8 | 101 | 103 |
| 9 | 96 | 95 |
| 10 | 100 | 101 |
| 15 | 103 | 99 |
| 16 | 103 | 102 |
| 17 | 108 | 103 |
| 18 | 107 | 103 |
| 25 | 106 | 103 |
| 27 | 105 | 103 |
| 31 | 100 | 103 |
| 34 | 102 | 103 |
| 36 | 107 | 103 |
| 39 | 110 | 103 |

The evidence freezes **50 guide portions** by original contour hash, edge index, clipped original endpoints and corresponding central-segment interval. Place their straight centerlines at **±0.5165 mm**, retaining **0.251 mm** guide gold. The greatest nominal move from the approved guide is **0.140923 mm**; all nominal portion strokes fit the measured 0.35 mm mask-safe region. The evidence also provides **125 per-segment cross sections**. The straight-section budget is unchanged: `.358 clearance + .251 gold + .251 ink + .280 gold + .251 ink + .251 gold + .358 clearance = 2.000 mm`.

Only these portions and their endpoint transitions may change. A transition must lie in both the network ribbon buffered by **0.50 mm** and the **0.50 mm neighborhood of that indexed original portion's endpoint**. Its centerline remains within **0.50 mm** of the indexed original guide; preserve every other portion of the manufacturing guide paths. Split shared edge 101:1 at the 7/8 junction and use the corresponding miter intersection, rather than moving the whole edge twice. At other consecutive portions, use bounded miter/rounded joins with independently compliant gold and ink widths; nominal straight sections do not certify joins.

Rounded ink terminals are permitted only as an indexed cap of the **same existing channel**, with a full >=0.25 mm disk at the terminal and no positive-length sub-width approach. They must retain protected radial gold, guide strands, all nine rim cores and the channel's existing connectivity; do not create a new enclosed ink pocket, erase a channel or extend any of the four older gold-merge patches. A short cross-sectional chord through the end of a valid round cap is not itself a thin branch. Prove the complete terminal/approach boundary; do not exempt a channel because a larger disk fits elsewhere. Reject any transition that needs a larger envelope, loss of a strand, alteration of an unrelated guide or a new connection. Record that blocker for a decision, not an automatic repair.

The new network envelope can overlap the older patch neighborhoods at junctions; the old claim of disjointness applied only to the 7/8 ribbon. **The four actual gold patch geometries still remain unchanged.** Reconcile intermediate-stage hashes and separately ledger all new material, guide and terminal changes. Preserve the approved radial motif and flat gold appearance. Rebuild hidden copper only after final mask validation; all 0.25 mm copper/gold/ink rules and 0.35 mm mask setbacks remain in force.

Require full-board and enlarged **actual finished-art** comparisons, both-phase within-component width proofs, exact indexed geometry checks, support/bridge/backing/registration invariants, cutter-center/plunge/finite-path evidence and independent native/CAM checks. `spider-network-comparison.png` compares material only and does not approve the finished artwork. Reproduce the decision and its tests with:

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow python artwork-resources/pcb-art/manufacturing/probe_spider_network.py
uv run --python 3.13 --with shapely==2.1.2 --with pillow python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -p 'test_spider_network.py'
```

No production or factory acceptance is granted. This amendment retains the conservative process targets; it is not a process-class relaxation and cannot pass any measured 0.08 mm channel.

## Spider L01 unfiltered-network correction — 2026-09-25

**This is the current material and guide scope.** Erratum `spider-l01-unfiltered-network-2026-09-25` supersedes the preceding complete-network amendment's incomplete 17-path addition, its affected-aperture list, 50-portion list and material totals. The earlier 7/8 ribbon remains included exactly once. Preserve all earlier evidence as history and all four original gold-merge patch geometries unchanged. Their <=30.0 mm² budget does not fund terminal changes. No other board or process rule changes.

The preceding survey wrongly skipped a channel whenever its central gold interval exceeded 0.31 mm; an opposite-side gold merge can widen that interval without repairing the remaining black channel. The corrected survey checks **every approved source stroke 0–94 and both adjacent sides**, using the captured post-patch mask topology with no central-width exclusion. It records **64 sustained interior runs below 0.25 mm, including 48 below 0.13 mm**. This adds 18 / 10 runs respectively to the historical totals. Sections are at most 0.20 mm apart and a sustained run is at least 1 mm. The five rim flags on 74/75/80/88/91 remain mandatory separate terminal checks. This survey locates sustained defects; it does not certify unsampled boundaries, endpoints or final artwork.

`spider-complete-decision.json` binds approved source SHA256 `00835f3a5db6cec4806d0747d274c7c65dff0e1f0f0a8c79316b488f6e5c870e`, the original pre-rib body, historical survey input, original path coordinates/contour hashes, every material delta, and the local terminal input `spider-complete-input.json`. The last capture derives from mask candidate SHA256 `a27ad404f0e12b5291b0a31d9c7b02681fa5401e3fd20e7716d0bd910ac27225`; it is a diagnostic checkpoint, not an approved manufacturing file. The probe and exporter hashes are also frozen.

### Corrected exact material and guide set

Union **2.0 mm flat-cap/miter ribbons** along complete approved paths **0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 27, 31, 33, 34, 36, 38, 39, 41**, plus the continuous **7/8** ribbon once: **34 source paths total**. Use exactly the evidence coordinates, without path extensions or material removal, from the pre-rib captured body. Initial material addition is **112.960935002 mm²**. All original decorative apertures **0–18** now change; the previous preservation requirement for apertures 4/8/9/10 is superseded by these exact changes.

For each of those 19 post-ribbon apertures `A`, perform the existing one-pass, all-center-component cleanup: retain `A.intersection(A.buffer(-0.5, quad_segs=64).buffer(0.5, quad_segs=64))`. Its exact measured material addition is **3.429195687 mm²**, combined **116.390130688 mm²** versus the pre-rib body. Policy maxima allow only 0.00001 mm² arithmetic tolerance. Enforce the per-aperture cleanup/final hashes and the final body hash; neither an equal area nor repeated cleanup authorizes another shape. Cumulative aperture loss is **1.810398%** versus approved Rev5, below the unchanged **2%** limit.

Keep the preceding table's guide sides and add only these missed sides (normal `(-dy,dx)/length`):

| Source path | Side | Adjacent guide |
| --- | ---: | ---: |
| 0 | − | 109 |
| 1 | − | 106 |
| 11 | + | 96 |
| 12 | + | 100 |
| 13 | − | 99 |
| 14 | − | 102 |
| 19 | + | 108 |
| 20 | + | 107 |
| 21 | − | 113 |
| 22 | − | 110 |
| 23 | + | 113 |
| 24 | + | 110 |
| 33 | + | 103 |
| 38 | + | 103 |
| 41 | + | 103 |

The resulting **68 original edge-indexed guide portions** and **215 material cross sections** are enumerated in the evidence. Preserve central radial artwork at 0.280 mm, use 0.251 mm guide gold at signed 0.5165 mm offsets, and retain nominal 0.251 mm ink and 0.358 mm outer clearance. These nominal budgets and all portions fitting the 0.35 mm safe region establish proposal feasibility, not final union-width proof.

Map each portion using its **original edge index, local clipped interval and corresponding endpoints**. Join consecutive relocated edges at their actual line intersection. Never remap the whole closed guide by normalized contour arclength: changed lengths can connect a portion to the wrong source corner. The evidence lists **19 bounded miter joins**, including the 13 previously measured joins; maximum displacement is **0.183809 mm**. Guide100's source31/10 join is explicitly `(63.223765345,62.581985559)` mm, **0.136550 mm** from original vertex `(63.0875,62.5908)`. Shared guide101 edge1 must still be split at the 7/8 correspondence. Retain all unrelated guide portions.

### Exact guide103/source31 rounded transition

At original guide103 edge27 endpoint `(62.3351,62.7319)`, the straight extrapolated miter would move 0.874289 mm and is forbidden. Replace only the captured local reverse jog with this cubic, sampled into **64 segments**:

| Point | x mm | y mm |
| --- | ---: | ---: |
| P0 | 62.181101247 | 62.580686103 |
| C1 | 62.173142711 | 62.609611208 |
| C2 | 62.197407281 | 62.735236294 |
| P3 | 62.204648978 | 62.764349140 |

Use full precision from the evidence. Maximum measured source-guide displacement is **0.148507 mm**, within 0.50 mm. The curved paint change is inside the old 0.50 mm endpoint neighborhood. It reconnects the captured candidate-created ink pocket to its existing channel (82→81 ink components in this local experiment), with no gold connection or strand deletion. This permits only that indexed connectivity correction, never deletion of an approved black facet or arbitrary trapped pocket.

The curve alone leaves a pointed ink terminal that extends beyond the 0.50 mm endpoint neighborhood. Permit **only the three geometry-bound paint-cap polygons** in `terminal.caps` of the evidence, with their exact normalized WKB hashes and coordinates. Their combined area is **0.047654677 mm²**, including **0.000584674 mm²** outside the old 0.50 mm neighborhood; maximum endpoint distance is **0.542619 mm**. These polygons alone may occupy the **0.55 mm** endpoint neighborhood. This is not an interchangeable area budget or permission to enlarge other transitions. Guide displacement and every other transition envelope remain <=0.50 mm; the network ribbon-plus-0.50 mm bound and 0.35 mm mask-safe setback remain mandatory.

The caps are derived once from the captured curved ink minus its union of radius-0.125 mm disks (64 segments per quadrant). Do not apply this opening globally or repeatedly. After 0.000001 mm-grid serialization, the local ink differs from that full-width disk-union reference by **0.000000346 mm²** and **0.000018096 mm** Hausdorff distance. The additional complete-terminal check extends that proof region over all three caps plus a 0.001 mm boundary neighborhood, covering their tails outside 0.50 mm as well as the full local approach. Check both the complete approach and terminal boundary; unrelated corners inside the 0.55 mm viewing circle are not additional authorized caps. A polygonal round cap can produce small re-opening residue, so use the explicit disk-union boundary comparison as well as both-phase connected-core and miter-residue screens. The local gold/ink screens measure **0.000000935 / 0.000000073 mm²**; gold remains five components with five eroded cores, and cap application retains all 81 curved-ink components. The probe preserves radial gold, nine rim cores, prior four patches and the safe region. These measurements prove this bounded terminal on the captured diagnostic artwork; they do not prove the complete final 68-portion mask or copper.

### Retained implementation gates

The full material probe retains all **19 decorative apertures**, eight functional holes/slots, exact dimensions, one component, full pre-drill radius-3.05 mm support disks, bridges, lower floor and backing. Every aperture retains a connected 1.0 mm cutter-center region and contained plunge disk. Recheck these invariants, finite cutter paths and swept coverage on actual serialized output. Keep source/history immutable, the approved radial motif, all nine rims, all four earlier patch geometries, 0.25 mm positive-gold/negative-mask/copper widths and 0.35 mm mask clearance. No generalized width or process-class relaxation is authorized.

Issue 15 must account for all 68 relocated portions and every transition, verify complete final gold/ink/copper widths and topology, and supply full-board/enlarged material and actual finished-art comparisons. Regenerate native output and require issue 16's independent CAM checks. `spider-complete-comparison.png` compares the complete material proposal and this one local terminal; final-art and factory acceptance remain pending. A failed invariant or excessive transition remains a blocker. Reproduce this bounded evidence and its light tests with:

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow python artwork-resources/pcb-art/manufacturing/probe_spider_complete.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -p 'test_spider_complete.py' -v
```

## Process-class amendment — 2026-09-25

Owner-approved correction to the universal 0.25 mm art target, recorded as policy erratum `process-classes-2026-09-25`. The published sources and the limits of each claim are in `process-class-sources.json`: JLCPCB general 1 oz copper is 0.10/0.10 mm. Uncovered coils, hatched grids and same-net spacing are 0.25 mm. The black/white mask bridge is 0.13 mm. `rulesMm` is unchanged and remains the default for every feature this amendment does not match.

| Feature | Minimum |
| --- | ---: |
| Copper of the four full-gold lower pours (Spider L03/L05/L07, Coral L04) | 0.10 width / 0.10 gap |
| Isolated convex copper island (no interior ring, convex-hull deficit ≤ area tolerance, re-evaluated on final copper) | 0.10 width / 0.10 gap |
| Gap between components of different classes | larger of the two class widths |
| All other copper, including unnetted decorative networks and channels inside one connected component | 0.25 |
| Black mask web, Coral/Fault/Kumiko/Woven | 0.13 |
| Black mask web, Spider (all layers) | 0.25 |
| Visible gold window | 0.25 |

The 0.13 mm black web holds only if the mask is ordered unchanged, with no automatic expansion, gang-opening conversion, dam removal or facet deletion. Final CAM/process confirmation remains external and pending. Spider's stronger repairs stay in force.

`probe_process_classes.py` classifies a native candidate read-only and writes `process-class-decision.json` plus `process-class-comparison.png`. The measured candidate's file hashes are bound in the erratum. The snapshot classifies 44 general copper features and records six fixed cross-section witnesses that still fail their applicable class, including Kumiko L01 ink at 0.021 mm, Coral L01 visible gold at 0.087 mm and three copper-free gaps near 0.1 mm between retained-special components that need 0.25 mm. Both a 0.10 and a 0.25 mm negative-copper core screen are recorded; the witnesses are examples, not a complete failure list. Reclassification waives none of them; issue 15 must repair each one locally or prove it within the 0.001 mm tolerance. Re-measure from repository root with `PROCESS_CLASS_NATIVE_DIR=<native manufacturing dir> uv run --python 3.13 --with shapely==2.1.2 --with pillow python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests`. This amendment is not a production approval.

## Separate manufacturing artifacts and tests

Never modify `preview-source/assets/geometry.json`, `reference-revision4.json`, `reference-revision3.json`, the historic tests, or imported evidence to make corrections pass. In particular, `preview-source/tests/rev5_gold.py` continues to compare the approved Rev5 and immutable Rev4 inputs, retaining exact physical/lower-art assertions. New manufacturing code must load the frozen input, apply explicit indexed deltas, and emit **a separately named manufacturing geometry artifact** with provenance. Do not repoint the reference test, preview, manifest or screenshots to corrected shapes without labeling the artifact's role. The production exporter must read that new artifact explicitly.

Named downstream gates (equivalent test-file naming is acceptable; the assertions are mandatory):

| Gate | Owner and required assertions |
| --- | --- |
| `reference-history` | #15: run unchanged `preview-source/tests/rev5_gold.py` and existing revision geometry tests on approved inputs; all frozen input hashes match |
| `manufacturing-inventory-and-registration` | #15: selected 43 / alternative 9; exact palette/finish/layer order, dimensions, NPTH centers and top-only slots |
| `manufacturing-indexed-deltas` | #15: bijective ledger ↔ actual geometry/art differences, original index/hash/coordinates, all 56 closures and ligament resolution, all selected art findings dispositioned; alternatives unchanged |
| `manufacturing-material-and-tool-access` | #15: support disks before drills; after-drill connectivity, full bridges, floor, backing, opposed-boundary width and residue checks; center-region access, plunge/path and swept-envelope coverage for every aperture; contour/radius/width checks on emitted geometry |
| `manufacturing-art-and-appearance` | #15: union-level copper widths/gaps, black web and visible gold widths, containment/setbacks, preserved facet paint and nine top rims, budgets, nesting and Woven path distinctness; compare every changed design |
| `native-and-cam` | #16: actual native load/DRC of 52 boards with alternatives segregated; all 43 selected Gerber/Excellon outputs independently parsed/rendered; output hashes tied to all geometry/art/NPTH rules; proper layer polarity and no drill-outline duplication |
| `panel-membership-yield-and-scores` | #17: exact groups, finish identity, rail/score corridors, translations only, all board output contours/art/drills preserved after depanelization, quantities and waste; native and actual panel CAM verification |

`probe_decision.py` is reproducible **decision evidence**, not the production implementation of those gates. It evaluates local cutter-envelope candidates for 43 boards and verifies support disks, bridges, floor, top backing, nesting, connectivity and distances between distinct boundaries. It deliberately makes **no full local-width, final-art or real toolpath claim**. `decision-probe.json` records the result and original hole indices. `decision-comparisons.png` shows every selected top, H11 and the ligament, plus an indexed Kumiko mask-retreat example. `top-border-comparisons.png` enlarges the upper rims of all five designs; the probe checks the 0.25 mm core and closed annulus for all 45 top borders. The selected Coral collar correction is included in the before/after views. The mask-web example demonstrates the local operation, not a fully corrected mask. The all-board final comparison and union-level printability checks remain mandatory in #15/#16.

Reproduce this issue's light checks from repository root:

```sh
uv run --python 3.13 --with shapely==2.1.2 --with pillow --with numpy python artwork-resources/pcb-art/manufacturing/probe_decision.py
uv run --python 3.13 --with shapely==2.1.2 python -m unittest discover -s artwork-resources/pcb-art/manufacturing/tests -v
uv run --python 3.13 --with shapely==2.1.2 python artwork-resources/pcb-art/preview-source/tests/rev5_gold.py
```

## Lower packaging and permitted splits

Select **lead-free HASL** for every non-ENIG mask-only board. No exposed conductive art is added to make that finish visible. Separate masks and finishes even when both masks are black. Each unique board ID occurs once across its assigned layout, sorted lexicographically and placed row-major. Use only translation `(column × 101.3 + rail, row × 94.3 + rail − 17.1)`. All boards keep their original orientation and scale.

| Lower package | IDs per set | Grid | Sheet mm including rails | Unused cells | Sheets |
| --- | ---: | --- | --- | ---: | ---: |
| white / lead-free HASL | 7 | 2 × 4 | 212.6 × 387.2 | 1 | 25 |
| black / ENIG | 6 | 3 × 2 | 313.9 × 198.6 | 0 | 25 |
| red / lead-free HASL | 10 | 3 × 4 | 313.9 × 387.2 | 2 | 25 |
| green / lead-free HASL | 4 | 2 × 2 | 212.6 × 198.6 | 0 | 25 |
| purple / lead-free HASL | 1 | standalone | 101.3 × 94.3 | 0 | 25 |
| yellow / lead-free HASL | 1 | standalone | 101.3 × 94.3 | 0 | 25 |
| blue / lead-free HASL | 1 | standalone | 101.3 × 94.3 | 0 | 25 |
| black / lead-free HASL | 8 | 2 × 4 | 212.6 × 387.2 | 0 | 25 |

`policy.json` lists exact member IDs. Five **black ENIG tops stay individual routed boards** (25 each), with no tabs or scores on their outside edges. Singleton lower packages are individual lower packages; do not also order the individual reference exports of boards belonging to combined sheets. Base plan: **13 packages**, 325 ordered sheets/standalone units, **1,075 useful PCBs**: 125 tops + 950 lowers = 25 complete stacks of each design. The three unused grid cells per five-design set are explicitly blank substrate waste (75 cells across the order), never substitute boards, extra designs or useful yield.

For a multi-board sheet add **5 mm sacrificial rails on all four sides**; score along every internal row/column boundary and every rail/board boundary. Scores traverse the entire sheet, including waste cells and rails, with no stopped scores, steps or kerf spacing. Minimum parallel score spacing is **3 mm**, at most **25 per axis**, and sheets stay within **70–475 mm in both axes**. Rail width 5 mm makes the nearest parallel lines compliant. Draw scores on `Dwgs.User` and export a separate fabrication drawing; they are neither Edge.Cuts nor silkscreen. Route only the panel outside and decorative voids; retain one connected sheet before scoring. No PTH tooling holes or fiducials are introduced. No automatic plated pads or rule exemptions from Strip Mine.

Check a ±1.0 mm score corridor against every decorative aperture and full support disk, plus ≥0.50 mm copper and ≥0.55 mm visible-gold clearance to each seam. The outer lower rectangle is scored only; all decorative cutout edges stay cleanly routed. Final score residual-web depth, bending loads, handling of the large perforated sheets and ±0.4 mm scored outline tolerance are **pending CAM / physical-fit confirmation**. Scores are not evidence of precision routed outer edges. Assembly critical features are the separately drilled common centers. Do not claim the routing-size tolerance for scored boundaries.

The above grids are the default minimum package count by compatibility. **Permitted splits only:** if a panel fails an exact dimension, whole-line score corridor, handling/support or depanelization test, split that same color+finish group into smaller full rectangular grids along complete rows/columns; use 5 mm rails again, preserve each ID exactly once, and order 25 of each result. A one-board remainder becomes a routed singleton. Record failed measurement and resulting membership. Keep the ten-member cap, 475 mm limit and same board orientation. Do not create more panels merely to avoid declared multi-design fees. Do not mix finish/color, duplicate IDs to fill blanks, change board dimensions, score through apertures, use mouse bites on decorative edges, or introduce hand cutting as the default. A factory-specific refusal is pending external evidence, not a reason to silently replace this plan.

## Readiness and remaining confirmation

This issue completes a local design decision and scoped comparisons. #15 implements and proves corrected geometry; #16 independently verifies native/output geometry; #17 verifies actual combined sheets and the order manifest. Buying, payment, vendor contact and manufacturing approval are outside this workflow.

Keep separate pending items for: actual tool availability and plunge/CAM strategy; mask registration and untouched black facets; finish/color availability in the quote (including lead-free HASL with no exposed art); ENIG area/routing/multi-design charges; scored-web handling and edge tolerance; thickness/spacer/screw/washer/nut tolerances and physical fit. Nominal stack depths are 33.8 mm for Spider/Coral (8 boards) and 38.4 mm for Fault/Kumiko/Woven (9). For 125 stacks the nominal hardware inventory is **500 screws, 3,800 spacers, 500 nuts**; washer type/count and screw usable length require hardware confirmation. Do not describe any of those external checks as passed.
