# Native Board Handoff

The board files are in panels/art-spider-nest, panels/art-coral-vault, panels/art-fault-line, panels/art-kumiko-void, and panels/art-woven-maze. The selected set contains 43 boards using wide Kumiko. Nine standard Kumiko boards are in panels/art-kumiko-void/alternatives/standard and form a complete alternative.

pcb/manifest.json and pcb/manifest.csv preserve the source board IDs and provide the layer, color, finish, board path, export metadata, and original handoff path. The board paths point into repository panel homes. The default local export writes generated vectors under artwork-resources/pcb-art/generated/rev5-export/resources/vector; that generated tree is ignored.

Each file is a standalone KiCad 8+ board with embedded mechanical NPTH footprints. The files are an editable handoff, not a manufacturing release. The source reports geometry and S-expression checks, but native KiCad parsing, DRC, CAM, quote, physical fit, and factory acceptance have not been established here.

The native layers describe routed outlines and apertures on Edge.Cuts, functional holes as NPTH pads, front exposed art on F.Cu/F.Mask, and no back-side art. F.Mask is positive opening geometry. The exact export clearance choice is recorded in the manifest and generator; recheck it against the chosen supplier.

From the repository root, generate a separate review export with:

    python3 artwork-resources/pcb-art/tools/export_kicad.py --input artwork-resources/pcb-art/preview-source/assets/geometry.json --output artwork-resources/pcb-art/generated/rev5-export

The exporter protects existing outputs and accepts an explicit new output directory. It does not update the panel-home boards.
