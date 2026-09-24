# Finish Plan

This file records the Revision 5 finish policy used by the geometry generator. It describes design intent and serialized artwork; it does not establish a fabricator's available finishes, price, or acceptance rules.

## Selected 43-board set

| Design | Front-to-back mask sequence | ENIG layers |
| --- | --- | --- |
| Spider Nest | black, white, black/gold, white, black/gold, white, black/gold, red | 1, 3, 5, 7 |
| Coral Vault | black, green, purple, black/gold, red, yellow, red, blue | 1, 4 |
| Fault Line | black, red, black, red, black, red, black, red, black | 1 |
| Kumiko Void, wide | black, red, green, black, red, green, black, red, green | 1, 4, 7 |
| Woven Maze | black, white, black, white, black, white, black, white, black | 1 |

The selected set has 11 ENIG boards and 32 mask-only boards. Standard Kumiko has the same nine-layer color and finish sequence as wide Kumiko and is stored as a complete alternative.

## Finish semantics

- ENIG artwork is exposed front copper under openings in F.Mask. A gold color in the preview describes the visible finish, not yellow solder mask.
- The top board of each design carries ENIG decorative artwork. Revision 5 adds an outer frame and rims around four stack holes and four rail slots to each of the six top variants.
- Full-gold ENIG layers are Spider Nest 3/5/7 and Coral Vault 4.
- A mask-only layer contains no decorative front copper, no decorative mask openings, and no back artwork. This means no exposed decorative copper; it does not specify copper-free FR-4 laminate.
- Gold around a hole is flat surface artwork. It does not require plated hole walls or plated board edges.
- The black Kumiko facets are represented by flat copper and solder-mask regions. The viewer does not imply raised metal bars or bevelled parts.

## Preserve the distinction between art and export rules

The Revision 5 viewer records approved visible artwork. The delivered native PCB draft applies a separate edge-clearance adaptation: exported mask openings are at least 0.35 mm from routed or drilled boundaries, copper is at least 0.30 mm away, and copper may extend 0.05 mm under the mask. Those are generator choices recorded with the export data, not factory-approved requirements. Review the original design against the exported result before accepting any manufacturing change.

## Source of the policy

src/finish_policy.py is authoritative for generated finish metadata. The design modules provide the shape and art definitions. assets/geometry.json is the serialized Revision 5 geometry input; the Rev3 and Rev4 reference snapshots are preserved for comparison.
