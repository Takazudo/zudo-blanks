---
name: panel-preview
description: Maintain source-derived previews and the repository catalog when a KiCad panel project is added, changed, or removed.
---

# Panel previews

Use this skill for future panel catalog and preview updates. The site lives in `doc/`, native board sources in `panels/`, visual art source in `artwork-resources/pcb-art/preview-source`, and fabrication records in `artwork-resources/pcb-art/manufacturing`.

## Source and representation

- Derive the inventory from every top-level `panels/` directory. Link each entry to its real `main` GitHub directory. Use the native board and project README for labels, dimensions, colors and status; directory HP names are nominal labels, not a measured width or finish guarantee.
- For a single-board project, render that board. For a multi-board stack, show all selected layers with their order and link each board. For grouped sheets, show each native sheet. Do not depict an entire stack as one fabricated PCB.
- Distinguish Revision 5 **visual design** geometry from locally adapted **native/CAM** geometry. The 3D viewer uses frozen `preview-source/assets/geometry.json`; the catalog PNGs and five top Edge.Cuts inspection vectors use current native `.kicad_pcb` files. A vector or PNG is an inspection resource, never a substitute for native PCB, Gerbers, drill files or factory review.
- Kumiko **wide** is the selected nine-board set. Standard is an unchanged reference-only alternative. Keep the complete sets separate. Local DRC/CAM checks are recorded; factory CAM, quote, finish availability and physical fit are still pending. The optional exhaustive width certificate has not passed.

## Update and verify

1. Read the new panel's README, native boards and relevant manufacturing manifest. Extend `doc/scripts/generate_panel_catalog.py` only if the new project needs different source selection or status rules.
2. Run `python3 doc/scripts/generate_panel_catalog.py`. It regenerates `doc/data/panel-inventory.json`, the catalog MDX and compact KiCad-derived PNGs. Use `--only <directory>` while iterating; run the full inventory before committing. KiCad CLI, Pillow and macOS `sips` are required.
3. If the visual design model changed intentionally, review the approved geometry hash and manufacturing effects first. `preview-source/scripts/build_geometry.py` regenerates geometry separately; `npm run build` reads and verifies the **frozen** geometry and builds ignored offline HTML. Never accept an accidental geometry hash change from preview work.
4. Run `python3 doc/scripts/stage_pcb_art_assets.py` to stage the single offline 3D viewer, curated images, review comparisons and top Edge.Cuts vectors. Published page links use `previews/index.html?design=<id>` or `?design=kumiko-void&variant=wide`; `variant=standard` is reference-only. Use a literal HTML `<a>` in MDX so the asset viewer does not turn the viewer URL into a file-details page. The extra self-contained per-design HTML files under `preview-source/dist/` stay local/ignored.
5. Run `python3 doc/scripts/check_panel_catalog.py`, `cd doc && pnpm check && pnpm check:links -- --strict-broken --strict-absolute --strict-anchors`. Review representative plain, Saucer, existing art and all five layered pages at desktop/mobile sizes. For heavy production builds and browser suites, use the repository heavy guard.

Keep published prose, comments and commits in English. Preserve original art attribution, image proportions and `/pj/zblanks/` asset paths. Keep bulk CAM ZIPs and generated vector trees local and ignored; link canonical sources and regeneration instructions from the site.
