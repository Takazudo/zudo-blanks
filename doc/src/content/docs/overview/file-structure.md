---
title: Repository Structure
sidebar_position: 3
---

- [`panels/`](https://github.com/Takazudo/zudo-blanks/tree/main/panels) contains the top-level project directories indexed by the [catalog](/docs/panels/). Simple projects hold one KiCad board; layered art and grouped lower sheets contain multiple boards and may have nested project directories.
- [`artwork-resources/pcb-art/preview-source`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/preview-source) holds the frozen Revision 5 visual geometry and interactive viewer sources.
- [`artwork-resources/pcb-art/manufacturing`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/manufacturing) holds the fabrication policy, indexed corrections, local validation, native/CAM and package records.
- [`artwork-resources/pcb-art/resources`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/resources) holds comparison images, review inputs and order planning sources.
- [`footprints/`](https://github.com/Takazudo/zudo-blanks/tree/main/footprints) and [`symbols/`](https://github.com/Takazudo/zudo-blanks/tree/main/symbols) hold shared KiCad libraries.
- [`order-packages/four-art-series/ordered/`](https://github.com/Takazudo/zudo-blanks/tree/main/order-packages/four-art-series/ordered) holds the frozen completed order, original fabrication bytes, completion report and provenance. Generators and original native designs remain in the source directories above.
- `doc/` is the zudo-doc site. Its `public/assets` tree stages web copies from the canonical source data.
- [`.claude/skills/panel-preview`](https://github.com/Takazudo/zudo-blanks/tree/main/.claude/skills/panel-preview) documents preview maintenance for future panels.

[Panel inventory](/docs/panels/) · [Source of truth](/docs/guides/engineering/source-of-truth/)

## Original art import and file roles

The original PCB art manifest has 52 board IDs: the historical 43-board five-design selection plus nine standard Kumiko alternatives. These counts describe that import, not the whole current panel inventory. [IMPORT_MANIFEST.json](https://github.com/Takazudo/zudo-blanks/blob/main/artwork-resources/pcb-art/IMPORT_MANIFEST.json) preserves imported, transformed, deduplicated and omitted source paths.

`preview-source/src/designs`, `build_common.py` and `finish_policy.py` hold editable design inputs. `pcb/manifest.json` and `manifest.csv` preserve IDs, layers and finishes. `resources/reference` holds original references; `validation` and `reports` hold compact geometry/export evidence; `tools` contains local review helpers. Historical `resources/order` inputs are distinct from the completed archive.

The current site stages a deliberate selection of images, inspection vectors and mechanical models. Other files are external repository downloads; it does not copy or index the entire order archive. Generated vector outputs and local review exports stay ignored.
