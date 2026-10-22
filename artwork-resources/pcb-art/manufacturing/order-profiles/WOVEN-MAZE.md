# Woven Maze: 25 complete stacks

Use the `woven-maze` profile in the Art order packages workflow with
`upload_bundle` enabled. The workflow accepts `individual` (standalone boards
only) or `all` (all three alternatives below in one bundle, sharing the same
individual DRC/CAM evidence) and rejects other pairings. The four-series profile,
completed order archive, tool image, permissions and source artwork are unchanged.

Choose ONE alternative; never combine them. Physical stack order is L01-L09.
All boards are FR-4, 1.6 mm, two copper layers, 1 oz, with no silkscreen, paste
or plated holes. L01 is black ENIG artwork, 101.3 x 128.5 mm, and is always a
standalone routed board; it is never scored. L02-L09 are 101.3 x 94.3 mm
mask-only lower boards, alternating white and black, with lead-free HASL.

| Alternative | Lines | Purchase quantity | Pieces |
| --- | ---: | --- | ---: |
| `individual` | 9 | 25 of each standalone board | 225 |
| `grouped` | 3 | L01 x25; white sheet x25; black sheet x25 | 225 |
| `split-pairs` | 5 | L01 x25; four 2x1 sheets x25 each | 225 |

`grouped` sheets are 212.6 x 198.6 mm 2x2 customer panels with 5 mm rails,
one copy of each member per sheet, no blank cells and no surplus:
white HASL L02/L04 (top row), L06/L08; black HASL L03/L05, L07/L09.
`split-pairs` sheets are 212.6 x 104.3 mm 2x1 panels with the same rails,
scores and finish, two members each: white L02/L04 and L06/L08; black L03/L05
and L07/L09. Placement is translation-only in sorted row-major order. Member outer
rectangles become full-span V-scores on a separate Dwgs.User drawing; the
maze apertures and outer sheet edge stay routed on Edge.Cuts, and NPTH mounts
come from Excellon. Score clearance follows `policy.json` (1.0 mm to
apertures/support disks). Sheet quantities are sheets: four pieces per 2x2 sheet, two per 2x1 sheet.

The export pipeline copies committed native boards and projects, checks their
generation hashes, runs pinned KiCad DRC, checks CAM geometry, drills, copper
and mask, and produces previews and per-package hashes. Each grouped sheet is
built fresh, checked against inverse-translated member geometry, and gets its
own native DRC, Gerber/Excellon and score-drawing verification. No CAD
regeneration is introduced. Pinned Linux KiCad reports a false Edge.Cuts
self-intersection on individual L01 only, so its DRC copy alone joins the
existing contour-seam rotation; coordinates, UUIDs and segments are unchanged,
and CAM consumes the committed source. No lower board or sheet uses a seam
rotation. A failure blocks the successful bundle upload; investigate it without
changing source art or relaxing verification.

After download, verify the complete bundle using `--verify-bundle` with the
exact workflow source SHA and run ID, then review the CAM previews and the chosen
`variants/*/ORDER.md`. Prices, factory CAM/scoring acceptance, residual web,
scored-edge appearance, depanelization/handling and physical fit remain external
review gates. This workflow never submits an order.
