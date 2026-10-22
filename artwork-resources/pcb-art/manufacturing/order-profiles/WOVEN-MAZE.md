# Woven Maze: 25 complete stacks

Use the `woven-maze` profile and `individual` variant in the Art order packages
workflow, with `upload_bundle` enabled to retrieve its verified output. The
workflow rejects other pairings for this profile. The four-series profile,
completed order archive, tool image, permissions and source artwork are unchanged.

This profile purchases nine distinct standalone boards, 25 of each (225 pieces).
It does not combine lower boards into scored sheets. L01 is black ENIG artwork,
101.3 x 128.5 mm. L02-L09 are 101.3 x 94.3 mm mask-only lower boards,
alternating white and black, with lead-free HASL selected. All are FR-4,
1.6 mm, two copper layers, 1 oz, with no silkscreen, paste or plated holes.
Each source ID is fixed in physical stack order.

The existing export pipeline copies committed native boards and projects,
checks their generation hashes, runs pinned KiCad DRC, checks CAM geometry,
drills, copper and mask, and produces previews and per-package hashes.
No CAD regeneration is introduced. Pinned Linux KiCad reports a false
Edge.Cuts self-intersection on L01 only, so its DRC copy alone joins the
existing contour-seam rotation; coordinates, UUIDs and segments are unchanged,
and CAM consumes the committed source.
A failure blocks the successful bundle upload; investigate it without
changing source art or relaxing verification.

After download, verify the complete bundle using `--verify-bundle` with the
exact workflow source SHA and run ID. Review the nine CAM previews and
`variants/individual/ORDER.md` before cart upload. The top needs ENIG;
white/black lowers retain their mask-only intent. Supplier CAM acceptance and
physical fit remain external review gates. This workflow never submits an order.
