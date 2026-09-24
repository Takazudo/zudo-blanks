# Continuation Notes

The Revision 5 handoff contains five layered blank panels. Its selected set is 43 boards with wide Kumiko; the nine standard Kumiko boards form a complete alternative. Keep the original IDs and layer numbers in any new manifest.

## Design source

The editable geometry is in preview-source/src and its canonical serialization is preview-source/assets/geometry.json. Revision 3 and Revision 4 snapshots are immutable comparison inputs. Update the generator and regenerate outputs for intentional design changes. Keep KiCad-only edits in a separately tracked production working copy.

## Native board review

The boards are standalone KiCad PCB files in panels/art-*. Check their dimensions and holes, copper and mask alignment, single-board connectivity, and finish metadata in the KiCad version used for the work. Record each DRC result. Do not suppress a violation without a board-specific explanation.

The imported source notes flag small Kumiko apertures, narrow material, and narrow copper or mask gaps. Resolve those against the chosen process and record the exact board, layer, coordinates, change, and reason. Preserve the angular Spider and Kumiko designs except for local tool-radius adaptations that have been reviewed.

## Output and evidence

Generate Gerber and drill outputs into a new, dated local review directory. Open them in an independent CAM viewer and compare outline, holes, layers, color, and finish with the manifest. Record the output hashes and the actual result. Keep those review files local unless a later task explicitly adds a compact, reviewed record.

No factory review, production quote, order, or physical fit is included in this source import. Do not infer those outcomes from geometric or S-expression checks.
