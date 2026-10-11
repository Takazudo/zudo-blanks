---
name: panel-preview
description: Maintain source-derived previews and family documentation when a KiCad panel project is added, changed, or removed.
---

# Panel previews and families

The site lives in `doc/`, native boards in `panels/`, and frozen visual geometry in
`artwork-resources/pcb-art/preview-source/`. The completed order archive is
`order-packages/four-art-series/ordered/`; its setup entry point remains
`scripts/art-order/README.md`.

## Source and representation

- Derive inventory from every top-level panel directory and every native board;
  classify primary, alternative, fabrication and test inputs. Archived copies are
  evidence, not additional designs. Keep a small curated mapping to the 19 family
  pages and preserve widths/revisions as table rows with stable anchors.
- Cards lead to internal documentation. Link exact repository sources secondarily.
  Use README/native facts for labels and status; nominal HP names are not measured
  dimensions or a finish guarantee. Do not invent manufacturing readiness.
- For multi-board stacks show selected layers and their order. Grouped lower sheets
  belong under Manufacturing; they are not a separate family. Inspection PNG/SVG
  previews never substitute for native boards, Gerbers or drill files.
- Frozen Revision 5 visual geometry differs from locally adapted native/CAM
  geometry. Kumiko wide is the selected nine-board set; standard remains a separate
  reference alternative. Keep both viewer selections intact.
- The owner reported the four-series order completed on 2026-10-10 JST. Preserve
  its exact 13 adopted ZIPs, provenance, 34 source boards, evidence and checksums.
  Completed-order status does not prove physical assembly or fit. Carry forward
  the newer assembly prose and distinguish it from historical alternatives.

## Update and verify

1. Read affected panel READMEs, native boards and manifests. Update the curated
   family mapping and authored prose only where facts change. Use the content
   generator for inventory/tables; preserve prose outside generated regions.
2. Run `cd doc && pnpm check:content` to check dynamic inventory and output drift.
   Fast metadata/content work must not require KiCad or macOS `sips`. Regenerate
   committed native preview images separately only when affected board sources
   actually change, with the renderer's documented dependencies.
3. Keep frozen viewer geometry unchanged unless separately authorized. Bundle the
   existing pinned dependencies locally (`npm ci --prefix
   artwork-resources/pcb-art/preview-source` from repository root). The canonical
   five-design bundle is `/viewers/pcb-art/`; Strip Mine is
   `/viewers/strip-mine/`. Preserve scene controls, Kumiko wide/standard and Strip
   Mine pattern 5, Strata/blobs. Use query-bearing full-size links and titled lazy
   iframes, with posters instead of loading every viewer in galleries.
4. Keep adapter STEP and plain 3U 8HP STL/FreeCAD files available. Index selected
   local files only. Viewer HTML stays outside `/assets/` rewriting. Do not copy
   the archive, abandoned individual/red10 trees, or bulk CAM/vector output into
   public assets. Repository archive downloads belong on ordinary docs pages.
5. Run the full verification sequence in `doc/OPERATIONS.md`, including strict
   source/built links and anchors, content, images, viewers, redirects, wind audit,
   and the local built Worker. Verify the archive read-only with the unchanged
   `verify_ordered.py`. Review representative plain, Saucer and layered families
   at desktop/mobile sizes, light/dark, and inspect viewer controls and downloads.

Keep prose, comments and commits English. Preserve attribution, image proportions
and root-hosted asset paths. Follow the configured heavy guard for local production
builds/browser suites; never regenerate native fabrication as part of docs checks.
